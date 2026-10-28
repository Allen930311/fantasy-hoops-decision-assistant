"""Contract tests for fetch provenance, source failures, identity, and league scoring."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"nba_data_adapter.py"
spec=importlib.util.spec_from_file_location("nba_adapter",SCRIPT)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)

class Response:
    status=200
    headers={}
    def __init__(self,body): self.body=body
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self,*args): return False

class StatusResponse(Response):
    def __init__(self,status,headers,body=b''):
        super().__init__(body)
        self.status=status
        self.headers=headers

class AdapterTests(unittest.TestCase):
    def test_raw_hash_and_snapshot_manifest(self):
        body=b'{"events":[]}'
        with tempfile.TemporaryDirectory() as tmp:
            attestations={"espn":"terms-review-accepted-for-test"}
            c=adapter.JsonClient(Path(tmp),sleep=lambda _:None,opener=lambda *a,**k:Response(body),source_use_attestations=attestations)
            payload,record=c.get_json("espn","https://example.test/data","test-v1",lambda x:"events" in x)
            self.assertEqual(payload,{"events":[]})
            self.assertEqual(record["raw_sha256"],hashlib.sha256(body).hexdigest())
            self.assertEqual(record["source_use_status"],"ATTESTED_UNVERIFIED")
            self.assertEqual(record["source_use_attestation_reference"],"terms-review-accepted-for-test")
            self.assertNotIn("source_use_authorization_reference",record)
            raw=Path(tmp)/"espn"/(record["raw_sha256"]+".json")
            manifest=raw.with_name(raw.stem+".manifest.json")
            self.assertEqual(raw.read_bytes(),body)
            self.assertTrue(manifest.exists())
            self.assertEqual(json.loads(manifest.read_text())["schema_version"],"test-v1")
            self.assertEqual(json.loads(manifest.read_text())["fetched_with_normalizer_version"],adapter.NORMALIZER_VERSION)
            self.assertRegex(json.loads(manifest.read_text())["fetched_with_normalizer_code_sha256"],r"^[0-9a-f]{64}$")
            replay=adapter.JsonClient(Path(tmp),replay=True,source_use_attestations=attestations)
            cached,meta=replay.get_json("espn","https://example.test/data","test-v1",lambda x:"events" in x)
            self.assertEqual(cached,payload);self.assertTrue(meta["cache_replay"])
            self.assertEqual(meta["raw_sha256"],record["raw_sha256"])
            self.assertEqual(meta["replayed_with_normalizer_version"],adapter.NORMALIZER_VERSION)
            self.assertRegex(meta["replayed_with_normalizer_code_sha256"],r"^[0-9a-f]{64}$")

    def test_official_static_schedule_fallback_preserves_game_identity_and_status(self):
        payload={"leagueSchedule":{"seasonYear":"2026-27","gameDates":[{"gameDate":"10/26/2026 00:00:00","games":[
            {"gameId":"0022600122","gameStatus":3,"gameStatusText":"Final","gameDateTimeUTC":"2026-10-26T23:30:00Z",
             "homeTeam":{"teamId":1610612748,"teamTricode":"MIA"},"awayTeam":{"teamId":1610612742,"teamTricode":"DAL"}},
            {"gameId":"0022600120","gameStatus":2,"gameStatusText":"In Progress","gameDateTimeUTC":"2026-10-27T00:00:00Z",
             "homeTeam":{"teamId":1610612739,"teamTricode":"CLE"},"awayTeam":{"teamId":1610612750,"teamTricode":"MIN"}}
        ]}]}}
        class FallbackClient:
            def get_json(self,provider,url,schema_version,validator=None):
                if provider=="nba_stats":raise adapter.SourceError(provider,url,"FORBIDDEN","HTTP 403",403)
                self.asserted=(provider,url,schema_version)
                if not validator(payload):raise AssertionError("static schedule fixture failed its schema")
                return payload,{"provider":provider,"url":url,"http_status":200,"raw_sha256":"a"*64,"normalized_sha256":"b"*64}
        client=FallbackClient()
        result=adapter.acquire_schedule("20261026",client)
        rows=adapter.normalize_schedule(result["events"],result["provider"])
        self.assertEqual(result["provider"],"nba_static_schedule")
        self.assertEqual(result["errors"][0]["kind"],"FORBIDDEN")
        self.assertEqual([(x["official_game_id"],x["status"]) for x in rows],[("0022600122","Final"),("0022600120","Live")])
        self.assertEqual(rows[0]["game_date_taipei"],"2026-10-27")
        self.assertEqual(result["record"]["schedule_date_normalized_sha256"],hashlib.sha256(
            json.dumps(result["events"],sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest())

    def test_403_fails_without_retry(self):
        import urllib.error
        calls=[]
        def opener(*a,**k):
            calls.append(1);raise urllib.error.HTTPError("https://x",403,"Forbidden",{},None)
        c=adapter.JsonClient(sleep=lambda _:None,opener=opener,source_use_attestations={"nba_cdn":"contract-test-ref"})
        with self.assertRaises(adapter.SourceError) as ctx:c.get_json("nba_cdn","https://x","v1")
        self.assertEqual(ctx.exception.kind,"FORBIDDEN");self.assertEqual(len(calls),1)

    def test_timeout_uses_bounded_retry_and_records_error(self):
        calls=[]
        def opener(*a,**k):
            calls.append(1)
            if len(calls)<3: raise TimeoutError("simulated timeout")
            return Response(b'{"ok":true}')
        c=adapter.JsonClient(retries=2,sleep=lambda _:None,opener=opener,source_use_attestations={"nba_cdn":"contract-test-ref"})
        _,record=c.get_json("nba_cdn","https://example.test/timeout","test-v1")
        self.assertEqual(record["http_status"],200)
        self.assertEqual(len(calls),3)
        self.assertEqual([x["kind"] for x in c.history if "kind" in x],["TIMEOUT","TIMEOUT"])

    def test_429_honors_retry_after_and_is_bounded(self):
        import urllib.error
        calls=[]; waits=[]
        def opener(*a,**k):
            calls.append(1)
            if len(calls)==1:
                raise urllib.error.HTTPError("https://x",429,"Rate limit",{"Retry-After":"2"},None)
            return Response(b'{"ok":true}')
        c=adapter.JsonClient(retries=1,sleep=waits.append,opener=opener)
        _,r=c.get_json("x","https://x","v1")
        self.assertEqual(r["http_status"],200);self.assertEqual(waits,[2])

    def test_429_http_date_retry_after_is_parsed(self):
        import urllib.error
        from datetime import datetime,timedelta,timezone
        from email.utils import format_datetime
        calls=[]; waits=[]
        retry_at=format_datetime(datetime.now(timezone.utc)+timedelta(seconds=5),usegmt=True)
        def opener(*a,**k):
            calls.append(1)
            if len(calls)==1:
                raise urllib.error.HTTPError("https://x",429,"Rate limit",{"Retry-After":retry_at},None)
            return Response(b'{"ok":true}')
        c=adapter.JsonClient(retries=1,sleep=waits.append,opener=opener)
        _,r=c.get_json("x","https://x","v1")
        self.assertEqual(r["http_status"],200)
        self.assertEqual(len(calls),2)
        self.assertEqual(len(waits),1)
        self.assertGreaterEqual(waits[0],3)
        self.assertEqual(c.history[0]["retry_action"],"RETRY")

    def test_429_response_object_uses_same_retry_after_handler(self):
        calls=[]; waits=[]
        def opener(*a,**k):
            calls.append(1)
            if len(calls)==1:return StatusResponse(429,{"Retry-After":"2"})
            return Response(b'{"ok":true}')
        c=adapter.JsonClient(retries=1,sleep=waits.append,opener=opener)
        _,result=c.get_json("x","https://x","v1")
        self.assertEqual(result["http_status"],200)
        self.assertEqual(len(calls),2)
        self.assertEqual(waits[0],2)
        self.assertGreaterEqual(sum(waits),2)
        self.assertEqual(c.history[0]["retry_action"],"RETRY")

    def test_429_response_object_with_long_retry_after_stops_source(self):
        calls=[]; waits=[]
        def opener(*a,**k):
            calls.append(1)
            return StatusResponse(429,{"Retry-After":"45"})
        c=adapter.JsonClient(retries=2,sleep=waits.append,opener=opener)
        with self.assertRaisesRegex(adapter.SourceError,"stop provider and fall back"):
            c.get_json("x","https://x","v1")
        self.assertEqual(len(calls),1)
        self.assertEqual(waits,[])
        self.assertEqual(c.history[0]["retry_action"],"STOP_PROVIDER_AND_FALL_BACK")

    def test_429_long_retry_after_stops_provider_instead_of_retrying_early(self):
        import urllib.error
        calls=[]; waits=[]
        def opener(*a,**k):
            calls.append(1)
            raise urllib.error.HTTPError("https://x",429,"Rate limit",{"Retry-After":"45"},None)
        c=adapter.JsonClient(retries=2,sleep=waits.append,opener=opener)
        with self.assertRaisesRegex(adapter.SourceError,"stop provider and fall back"):
            c.get_json("x","https://x","v1")
        self.assertEqual(len(calls),1)
        self.assertEqual(waits,[])
        self.assertEqual(c.history[0]["retry_action"],"STOP_PROVIDER_AND_FALL_BACK")

    def test_real_nba_played_string_zero_is_dnp_and_unknown_fails_closed(self):
        stats={"minutes":"PT00M00.00S","points":0,"threePointersMade":0,"reboundsOffensive":0,
            "reboundsDefensive":0,"reboundsTotal":0,"assists":0,"steals":0,"blocks":0,
            "turnovers":0,"freeThrowsAttempted":0,"freeThrowsMade":0,"foulsPersonal":0,"foulsTechnical":0}
        def payload(played,with_stats):
            player={"personId":1641707,"name":"Taylor Hendricks","played":played,"status":"ACTIVE"}
            if with_stats: player["statistics"]=stats
            return {"game":{"gameId":"0022600126","gameStatus":3,
                "homeTeam":{"teamId":1610612762,"teamName":"Utah Jazz","players":[player]},
                "awayTeam":{"teamId":1610612750,"teamName":"Minnesota Timberwolves","players":[]}}}
        dnp=payload("0",True)
        self.assertTrue(adapter._valid_nba_boxscore(dnp))
        normalized=adapter.normalize_nba_boxscore(dnp,None)
        self.assertEqual(normalized[0]["status"],"DNP")
        self.assertEqual(normalized[0]["player_status"],"ACTIVE")
        self.assertIsNone(normalized[0]["dnp_reason"])
        self.assertEqual(normalized[0]["stats"],{})
        self.assertEqual(normalized[0]["quality"],{})
        self.assertTrue(adapter._valid_nba_boxscore(payload("0",False)))
        for value in (0,False,"false"):
            self.assertIs(adapter.parse_nba_played(value),False)
        for value in (1,True,"1","true"):
            self.assertIs(adapter.parse_nba_played(value),True)
        played=payload("1",True)
        self.assertTrue(adapter._valid_nba_boxscore(played))
        self.assertEqual(adapter.normalize_nba_boxscore(played,None)[0]["status"],"PLAYED")
        unknown=payload("unknown",False)
        self.assertFalse(adapter._valid_nba_boxscore(unknown))
        with self.assertRaisesRegex(ValueError,"unknown played status"):
            adapter.normalize_nba_boxscore(unknown,None)

    def test_schema_and_invalid_json_errors_are_classified(self):
        c=adapter.JsonClient(sleep=lambda _:None,opener=lambda *a,**k:Response(b"not-json"))
        with self.assertRaises(adapter.SourceError) as ctx:c.get_json("x","https://x","v1")
        self.assertEqual(ctx.exception.kind,"INVALID_JSON")
        c=adapter.JsonClient(sleep=lambda _:None,opener=lambda *a,**k:Response(b'{"x":1}'))
        with self.assertRaises(adapter.SourceError) as ctx:c.get_json("x","https://x","v1",lambda x:"events" in x)
        self.assertEqual(ctx.exception.kind,"SCHEMA_DRIFT")

    def test_official_boxscore_and_pbp_id_must_match(self):
        box={"game":{"gameId":"0022600001","gameStatus":3}}
        pbp={"game":{"gameId":"0022600002","actions":[]}}
        with self.assertRaisesRegex(ValueError,"GAME_ID mismatch"):
            adapter.normalize_nba_boxscore(box,pbp)

    def test_explicit_crosswalk_only_and_no_name_guess(self):
        x={"espn:3059319":{"nba_player_id":"203952","identity_status":"VERIFIED","source_url":"https://nba.example/id"}}
        self.assertEqual(adapter.resolve_official_player_id("espn","3059319",x),"203952")
        self.assertIsNone(adapter.resolve_official_player_id("espn","unknown",x))
        self.assertIsNone(adapter.resolve_official_player_id("espn","3059319",{}))

    def test_provider_game_crosswalk_needs_exact_teams_and_tipoff(self):
        official={"id":"0022600122","home_team_tricode":"MIA","away_team_tricode":"DAL",
                  "game_time_utc":"2026-10-26T23:30:00Z"}
        events=[{"id":"401909871","date":"2026-10-26T23:30:00Z","competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"14","abbreviation":"MIA"}},
            {"homeAway":"away","team":{"id":"6","abbreviation":"DAL"}}]}]}]
        cross=adapter.resolve_provider_event_id(official,events)
        self.assertEqual(cross["provider_event_id"],"401909871")
        self.assertEqual(cross["nba_game_id"],"0022600122")
        self.assertEqual(cross["home_provider_team_id"],"14")
        self.assertEqual(cross["away_provider_team_id"],"6")
        events.append(dict(events[0],id="401999999"))
        with self.assertRaises(adapter.SourceError):adapter.resolve_provider_event_id(official,events)

    def test_official_to_espn_fallback_revalidates_summary_teams_and_tipoff(self):
        official={"id":"0022600122","home_team_tricode":"MIA","away_team_tricode":"DAL",
            "game_time_utc":"2026-10-26T23:30:00Z"}
        event={"id":"401909871","date":"2026-10-26T23:30:00Z","competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"14","abbreviation":"MIA"}},
            {"homeAway":"away","team":{"id":"6","abbreviation":"DAL"}}]}]}
        crosswalk=adapter.resolve_provider_event_id(official,[event])
        summary={"header":{"id":"401909871","competitions":[{"date":"2026-10-26T23:30:00Z",
            "status":{"type":{"state":"post"}},"competitors":[
                {"homeAway":"home","team":{"id":"14","abbreviation":"MIA"}},
                {"homeAway":"away","team":{"id":"6","abbreviation":"DAL"}}]}]},
            "boxscore":{"players":[{"team":{"id":"14"},"statistics":[{"keys":["minutes","points",
                "threePointFieldGoalsMade-threePointFieldGoalsAttempted","offensiveRebounds","defensiveRebounds",
                "rebounds","assists","steals","blocks","turnovers","freeThrowsMade-freeThrowsAttempted","fouls"],
                "athletes":[{"athlete":{"id":"1642264","displayName":"Stephon Castle"},
                    "stats":["27","15","3-8","0","5","5","5","1","0","3","4-4","2"],
                    "didNotPlay":False}]}]},
                {"team":{"id":"6"},"statistics":[]}]}}
        box={"provider":"espn","payload":summary,"record":{"url":"https://site.api.espn.com/summary?event=401909871",
            "raw_sha256":"a"*64},"errors":[]}
        with patch.object(adapter,"acquire_boxscore",return_value=box):
            result=adapter.acquire_game_bundle("0022600122",object(),crosswalk)
        self.assertEqual(result["game_id"],"0022600122")
        self.assertEqual(result["provider"],"espn")
        self.assertEqual(result["provider_game_id"],"401909871")
        self.assertEqual(result["official_game_id"],"0022600122")
        self.assertEqual(result["players"][0]["game_id"],"0022600122")
        self.assertEqual(result["players"][0]["player_id"],"espn:1642264")
        self.assertIsNone(result["players"][0]["official_player_id"])
        summary["header"]["competitions"][0]["competitors"][1]["team"]["id"]="999"
        with patch.object(adapter,"acquire_boxscore",return_value=box):
            with self.assertRaisesRegex(ValueError,"does not match scheduled provider event"):
                adapter.acquire_game_bundle("0022600122",object(),crosswalk)

    def test_espn_schedule_preserves_namespaced_provider_event_id(self):
        event={"id":"401909879","date":"2026-10-28T00:00:00Z","competitions":[{
            "status":{"type":{"state":"post"}},"competitors":[
                {"homeAway":"home","team":{"id":"24","abbreviation":"SAS","displayName":"San Antonio Spurs"}},
                {"homeAway":"away","team":{"id":"23","abbreviation":"SAC","displayName":"Sacramento Kings"}}]}]}
        row=adapter.normalize_schedule([event],"espn")[0]
        self.assertEqual(row["id"],"espn:401909879")
        self.assertEqual(row["provider_game_id"],"401909879")
        self.assertIsNone(row["official_game_id"])
        self.assertEqual(row["status"],"Final")
        self.assertEqual(row["game_date_taipei"],"2026-10-28")
        self.assertEqual(row["home_provider_team_id"],"24")

    def test_espn_schedule_rejects_missing_team_or_timezone_identity(self):
        base={"id":"401909879","date":"2026-10-28T00:00:00Z","competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"24","abbreviation":"SAS"}},
            {"homeAway":"away","team":{"id":"23","abbreviation":"SAC"}}]}]}
        bad_team={**base,"competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"24","abbreviation":"SAS"}},
            {"homeAway":"away","team":{"id":"","abbreviation":"SAC"}}]}]}
        with self.assertRaisesRegex(ValueError,"team IDs or tricodes"):
            adapter.normalize_schedule([bad_team],"espn")
        with self.assertRaisesRegex(ValueError,"timezone-aware tipoff"):
            adapter.normalize_schedule([{**base,"date":"2026-10-28T00:00:00"}],"espn")

    def test_espn_summary_is_bound_to_event_teams_time_and_provider_player_id(self):
        scheduled={"id":"espn:401909879","provider":"espn","provider_game_id":"401909879",
            "provider_event_id":"401909879","official_game_id":None,
            "home_provider_team_id":"24","away_provider_team_id":"23",
            "home_team_tricode":"SAS","away_team_tricode":"SAC",
            "game_time_utc":"2026-10-28T00:00:00Z"}
        header={"id":"401909879","competitions":[{"date":"2026-10-28T00:01:00Z","competitors":[
            {"homeAway":"home","team":{"id":"24","abbreviation":"SAS"}},
            {"homeAway":"away","team":{"id":"23","abbreviation":"SAC"}}]}]}
        keys=["minutes","points","threePointFieldGoalsMade-threePointFieldGoalsAttempted",
            "offensiveRebounds","defensiveRebounds","rebounds","assists","steals","blocks",
            "turnovers","freeThrowsMade-freeThrowsAttempted","fouls"]
        vals=["27","15","3-8","0","5","5","5","1","0","3","4-4","2"]
        payload={"header":header,"boxscore":{"players":[{"team":{"id":"24","displayName":"San Antonio Spurs"},
            "statistics":[{"keys":keys,"athletes":[{"athlete":{"id":"1642264","displayName":"Stephon Castle"},
                "stats":vals,"didNotPlay":False}]}]},
            {"team":{"id":"23","displayName":"Sacramento Kings"},"statistics":[]}]}}
        rows=adapter.normalize_espn_summary(payload,scheduled=scheduled,taipei_date="2026-10-28",
            source_url="https://site.api.espn.com/summary?event=401909879",source_sha256="a"*64)
        self.assertEqual(rows[0]["game_id"],"espn:401909879")
        self.assertEqual(rows[0]["player_id"],"espn:1642264")
        self.assertEqual(rows[0]["official_player_id"],None)
        self.assertEqual(rows[0]["stats"]["FTA"],4)
        self.assertEqual(rows[0]["stats"]["TECH"],None)
        self.assertEqual(rows[0]["identity_status"],"VERIFIED_PROVIDER_IDENTITY")
        bad={**header,"competitions":[{**header["competitions"][0],"date":"2026-10-28T00:05:00Z"}]}
        with self.assertRaisesRegex(ValueError,"does not match scheduled provider event"):
            adapter.normalize_espn_summary({**payload,"header":bad},scheduled=scheduled)

    def test_espn_automated_schedule_fallback_requires_explicit_source_use_attestation(self):
        calls=[]
        class Client:
            espn_use_attestation=None
            def get_json(self,provider,url,schema_version,validator=None):
                calls.append(provider)
                raise adapter.SourceError(provider,url,"FORBIDDEN","HTTP 403",403)
        with self.assertRaises(adapter.SourceError) as ctx:adapter.acquire_schedule("20261027",Client())
        self.assertEqual(ctx.exception.kind,"SOURCE_USE_UNVERIFIED")
        self.assertNotIn("espn",calls)

    def test_protected_data_requests_stop_before_network_without_source_use_attestation(self):
        calls=[]
        c=adapter.JsonClient(opener=lambda *a,**k:calls.append(1))
        for provider in ("nba_stats","nba_cdn","espn"):
            with self.subTest(provider=provider):
                with self.assertRaises(adapter.SourceError) as ctx:
                    c.get_json(provider,"https://example.test/data","v1")
                self.assertEqual(ctx.exception.kind,"SOURCE_USE_UNVERIFIED")
        self.assertEqual(calls,[])

    def test_provider_summary_rejects_extra_competitor_even_if_home_away_keys_repeat(self):
        scheduled={"id":"espn:401909879","provider":"espn","provider_game_id":"401909879",
            "provider_event_id":"401909879","home_provider_team_id":"24","away_provider_team_id":"23",
            "home_team_tricode":"SAS","away_team_tricode":"SAC","game_time_utc":"2026-10-28T00:00:00Z"}
        competitors=[{"homeAway":"home","team":{"id":"24","abbreviation":"SAS"}},
            {"homeAway":"away","team":{"id":"23","abbreviation":"SAC"}},
            {"homeAway":"away","team":{"id":"23","abbreviation":"SAC"}}]
        header={"id":"401909879","competitions":[{"date":"2026-10-28T00:00:00Z","competitors":competitors}]}
        self.assertFalse(adapter._provider_event_matches_schedule(scheduled,header))

    def test_official_boxscore_schema_requires_all_scoring_inputs(self):
        data={"game":{"gameId":"0022600001","homeTeam":{"players":[{"played":True,"statistics":{
            "points":1}}]},"awayTeam":{"players":[]}}}
        self.assertFalse(adapter._valid_nba_boxscore(data))

    def test_missing_official_pf_oreb_or_technical_foul_fails_schema(self):
        fields={"minutes":"PT1M0S","points":1,"threePointersMade":0,"reboundsOffensive":0,
            "reboundsDefensive":0,"reboundsTotal":0,"assists":0,"steals":0,"blocks":0,"turnovers":0,
            "freeThrowsAttempted":0,"freeThrowsMade":0,"foulsPersonal":0,"foulsTechnical":0}
        for field in ("foulsPersonal","reboundsOffensive","foulsTechnical"):
            with self.subTest(field=field):
                stats={k:v for k,v in fields.items() if k!=field}
                payload={"game":{"gameId":"0022600001","homeTeam":{"players":[{"played":True,"statistics":stats}]},
                    "awayTeam":{"players":[]}}}
                self.assertFalse(adapter._valid_nba_boxscore(payload))

    def test_null_official_scoring_field_uses_espn_fallback_and_stays_partial(self):
        game_id="0022600122"; event_id="401909871"
        stats={"minutes":"PT27M0.00S","points":15,"threePointersMade":3,
            "reboundsOffensive":0,"reboundsDefensive":5,"reboundsTotal":5,"assists":5,
            "steals":1,"blocks":0,"turnovers":3,"freeThrowsAttempted":4,"freeThrowsMade":4,
            "foulsPersonal":2,"foulsTechnical":None}
        official_box={"game":{"gameId":game_id,"gameStatus":3,"gameTimeUTC":"2026-10-26T23:30:00Z",
            "homeTeam":{"teamId":1610612748,"teamName":"Miami Heat","players":[
                {"personId":1642264,"name":"Stephon Castle","played":True,"statistics":stats}]},
            "awayTeam":{"teamId":1610612742,"teamName":"Dallas Mavericks","players":[]}}}
        event={"id":event_id,"date":"2026-10-26T23:30:00Z","competitions":[{"status":{"type":{"state":"post"}},
            "competitors":[{"homeAway":"home","team":{"id":"14","abbreviation":"MIA","displayName":"Miami Heat"}},
                {"homeAway":"away","team":{"id":"6","abbreviation":"DAL","displayName":"Dallas Mavericks"}}]}]}
        keys=["minutes","points","threePointFieldGoalsMade-threePointFieldGoalsAttempted",
            "offensiveRebounds","defensiveRebounds","rebounds","assists","steals","blocks",
            "turnovers","freeThrowsMade-freeThrowsAttempted","fouls"]
        summary={"header":{"id":event_id,"competitions":[{"date":"2026-10-26T23:30:00Z",
            "status":{"type":{"state":"post"}},"competitors":event["competitions"][0]["competitors"]}]},
            "boxscore":{"players":[
                {"team":{"id":"14","displayName":"Miami Heat"},"statistics":[{"keys":keys,
                    "athletes":[{"athlete":{"id":"1642264","displayName":"Stephon Castle"},
                        "stats":["27","15","3-8","0","5","5","5","1","0","3","4-4","2"],
                        "didNotPlay":False}]}]},
                {"team":{"id":"6","displayName":"Dallas Mavericks"},"statistics":[]}]}}
        bodies={"nba_box":json.dumps(official_box).encode(),"espn_schedule":json.dumps({"events":[event]}).encode(),
            "espn_summary":json.dumps(summary).encode()}
        requested=[]
        def opener(request,timeout):
            url=request.full_url
            requested.append(url)
            if "/boxscore/boxscore_" in url: body=bodies["nba_box"]
            elif "scoreboard?dates=" in url: body=bodies["espn_schedule"]
            elif "summary?event=" in url: body=bodies["espn_summary"]
            else: raise AssertionError(f"unexpected request {url}")
            return Response(body)
        official={"id":game_id,"official_game_id":game_id,"home_team_tricode":"MIA",
            "away_team_tricode":"DAL","game_time_utc":"2026-10-26T23:30:00Z"}
        with tempfile.TemporaryDirectory() as tmp:
            client=adapter.JsonClient(Path(tmp),sleep=lambda _:None,opener=opener,
                source_use_attestations={"nba_cdn":"fixture-only","espn":"fixture-only"})
            bundle=adapter.acquire_game_bundle_with_fallback(official,client)
        self.assertEqual(sum("/boxscore/boxscore_" in url for url in requested),1)
        self.assertEqual(bundle["provider"],"espn")
        self.assertEqual(bundle["official_game_id"],game_id)
        self.assertEqual(bundle["provider_game_id"],event_id)
        self.assertEqual(bundle["source_errors"][0]["kind"],"SCHEMA_DRIFT")
        player=bundle["players"][0]
        self.assertEqual(player["player_id"],"espn:1642264")
        league=json.loads((Path(__file__).parents[1]/"seasons/2026-27/league.json").read_text())
        trace=adapter.scoring_trace(player["stats"],player["quality"],league["scoring"])
        self.assertEqual(trace["status"],"PARTIAL_FP")
        self.assertEqual(trace["missing"],["TECH","EJCT","FF"])
        self.assertEqual(trace["value"],"32.50")

    def test_requested_game_id_mismatch_is_rejected(self):
        payload={"game":{"gameId":"0022600002","gameStatus":3}}
        class FakeClient:
            def get_json(self,*args,**kwargs):
                return payload,{"provider":"nba_cdn","url":"https://cdn.nba.com/wrong","raw_sha256":"a"*64}
        with self.assertRaisesRegex(adapter.SourceError,"gameId differs"):
            adapter.acquire_boxscore(nba_game_id="0022600001",provider_event_id=None,client=FakeClient())

    def test_duplicate_incident_ids_rejected(self):
        p={"game":{"actions":[{"actionNumber":1},{"actionNumber":1}]}}
        with self.assertRaisesRegex(ValueError,"duplicated actionNumber"):
            adapter.incident_events(p)

    def test_quality_gate_zero_vs_unknown_and_conflicts(self):
        league=json.loads((Path(__file__).parents[1]/"seasons/2026-27/league.json").read_text())
        stats={k:0 for k in adapter.FIELDS};stats.update(PTS=7,OREB=1,DREB=3,AST=2,STL=1,TO=1,FTA=3,PF=3,TECH=2,EJCT=1)
        q={k:("VERIFIED_VALUE" if stats[k] else "VERIFIED_ZERO") for k in adapter.FIELDS}
        result=adapter.scoring_trace(stats,q,league["scoring"])
        self.assertEqual(result["status"],"VERIFIED_FP");self.assertEqual(result["value"],"3.25")
        q={**q,"TECH":"UNKNOWN"}
        result=adapter.scoring_trace(stats,q,league["scoring"])
        self.assertEqual(result["status"],"PARTIAL_FP");self.assertIn("TECH",result["missing"])
        q={**q,"TECH":"CONFLICTING"}
        self.assertEqual(adapter.scoring_trace(stats,q,league["scoring"])["status"],"PARTIAL_FP")

    def test_fta_is_attempted_not_made_and_rebounds_reconcile(self):
        league=json.loads((Path(__file__).parents[1]/"seasons/2026-27/league.json").read_text())
        stats={k:0 for k in adapter.FIELDS};stats.update(PTS=0,FTA=6,FTM=5,OREB=1,DREB=2,REB=3)
        q={k:"VERIFIED_ZERO" for k in adapter.FIELDS};q.update(FTA="VERIFIED_VALUE",OREB="VERIFIED_VALUE",DREB="VERIFIED_VALUE")
        result=adapter.scoring_trace(stats,q,league["scoring"])
        self.assertEqual(result["components"]["FTA"],"-1.50")
        stats["REB"]=4
        result=adapter.scoring_trace(stats,q,league["scoring"])
        self.assertEqual(result["status"],"PARTIAL_FP");self.assertEqual(result["quality"]["OREB"],"CONFLICTING")

    def test_technical_and_ejection_are_distinct_events(self):
        pbp={"game":{"actions":[
            {"actionNumber":11,"personId":203932,"actionType":"foul","subType":"technical","description":"A Gordon Tech 1"},
            {"actionNumber":12,"personId":203932,"actionType":"foul","subType":"technical","description":"A Gordon Tech 2"},
            {"actionNumber":13,"personId":203932,"actionType":"ejection","subType":"secondtechnical","description":"Ejection A Gordon"}]}}
        events=adapter.incident_events(pbp)["203932"]
        self.assertEqual([x["kind"] for x in events],["TECH","TECH","EJCT"])

if __name__=="__main__":unittest.main()
