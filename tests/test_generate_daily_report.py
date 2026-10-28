"""Integration contract for the real-data daily report orchestrator."""
import json
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import generate_daily_report as generator  # noqa: E402
from daily_report_archive import validate,render  # noqa: E402


class Client:
    history=[]


class GeneratorTests(unittest.TestCase):
    def test_dirty_decision_source_is_rejected_against_pinned_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/"seasons/2026-27/league.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"season":"2026-27"}\n',encoding="utf-8")
            subprocess.run(["git","init","-q"],cwd=root,check=True)
            subprocess.run(["git","add","."],cwd=root,check=True)
            subprocess.run(["git","-c","user.name=Test","-c","user.email=test@example.invalid",
                "commit","-q","-m","fixture"],cwd=root,check=True)
            commit=generator._git_sha(root,"HEAD")
            self.assertEqual(generator._read_pinned_json(root,commit,"seasons/2026-27/league.json"),
                             {"season":"2026-27"})
            source.write_text('{"season":"2026-27","scoring":{"PTS":0}}\n',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"differs from pinned commit"):
                generator._read_pinned_json(root,commit,"seasons/2026-27/league.json")

    def test_owner_coverage_flows_from_official_ids_into_canonical_validator(self):
        league=json.loads((ROOT/"seasons/2026-27/league.json").read_text())
        scoring=league["scoring"]
        stats={key:0 for key in scoring if key not in ("DD","TD")}
        stats.update({"MIN":"3:55","PTS":2,"OREB":1,"DREB":1,"PF":1})
        quality={key:("VERIFIED_VALUE" if value else "VERIFIED_ZERO") for key,value in stats.items() if key!="MIN"}
        game_url="https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022600119.json"
        game={"game_id":"0022600119","game_date_et":"2026-10-26","game_date_taipei":"2026-10-27",
            "status":"Final","boxscore_source_url":game_url,"boxscore_raw_sha256":"a"*64,
            "periods":4,"overtime":False,"players":[{"name":"Justin Champagnie","status":"PLAYED",
                "game_id":"0022600119","player_id":"1630551","official_player_id":"1630551",
                "provider_player_id":"1630551","identity_status":"VERIFIED","identity_source_url":game_url,
                "identity_source_sha256":"a"*64,"stats":stats,"quality":quality,"source_quality":"NBA_OFFICIAL_ENDPOINT"}],
            "source_errors":[]}
        scheduled={"id":"0022600119","official_game_id":"0022600119","game_time_utc":"2026-10-26T23:00:00Z",
            "game_date_taipei":"2026-10-27","status":"Final"}
        result={"provider":"nba_stats","record":{"url":"https://stats.nba.com/stats/scoreboardv3?GameDate=10%2F26%2F2026&LeagueID=00"},
            "events":[{"gameId":"0022600119","gameStatus":3,"gameTimeUTC":"2026-10-26T23:00:00Z",
                "gameDateEst":"2026-10-26","homeTeam":{"teamId":1610612766,"teamTricode":"CHA"},
                "awayTeam":{"teamId":1610612764,"teamTricode":"WAS"}}],"errors":[]}
        with patch.object(generator,"acquire_schedule",return_value=result), \
             patch.object(generator,"acquire_game_bundle_with_fallback",return_value=game):
            payload,_=generator.generate_payload(root=ROOT,report_date="2026-10-27",nba_date_et="20261026",
                snapshot_dir=ROOT.parent/"private-test-cache",client=Client())
        self.assertEqual(payload["report"]["owner_players"],["Justin Champagnie"])
        self.assertEqual(payload["report"]["provenance"]["roster_commit_sha"],generator._git_sha(ROOT,"HEAD"))
        self.assertEqual(payload["report"]["short_appearance_alerts"][0]["status"],
                         "SHORT_APPEARANCE_WATCH_INJURY_UNVERIFIED")
        scores,missing=validate(payload)
        text,status=render(payload,scores,missing)
        self.assertEqual(status,"VALIDATED")
        self.assertEqual(str(scores["Justin Champagnie"]),"5.00")
        self.assertIn("Justin Champagnie",text)
        self.assertIn("短時間出賽，傷因未核實",text)

    def test_accented_official_box_names_match_roster_aliases_before_fa_classification(self):
        league=json.loads((ROOT/"seasons/2026-27/league.json").read_text())
        stats={key:0 for key in league["scoring"] if key not in ("DD","TD")}
        stats["MIN"]="20:00"
        quality={key:"VERIFIED_ZERO" for key in stats if key!="MIN"}

        def player(name,gid,pid,url,digest):
            return {"name":name,"status":"PLAYED","game_id":gid,"player_id":pid,
                "official_player_id":pid,"provider_player_id":pid,"identity_status":"VERIFIED",
                "identity_source_url":url,"identity_source_sha256":digest,
                "stats":dict(stats),"quality":dict(quality),"source_quality":"NBA_OFFICIAL_ENDPOINT"}

        gid_charlotte="0022600119"
        gid_denver="0022600127"
        url_charlotte=f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gid_charlotte}.json"
        url_denver=f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gid_denver}.json"
        charlotte={"game_id":gid_charlotte,"game_date_et":"2026-10-26","game_date_taipei":"2026-10-27",
            "status":"Final","boxscore_source_url":url_charlotte,"boxscore_raw_sha256":"b"*64,
            "players":[player("Justin Champagnie",gid_charlotte,"1630551",url_charlotte,"b"*64),
                       player("Moussa Diabaté",gid_charlotte,"1631217",url_charlotte,"b"*64),
                       player("Terrence Shannon Jr",gid_charlotte,"9999999",url_charlotte,"b"*64)],"source_errors":[]}
        denver={"game_id":gid_denver,"game_date_et":"2026-10-26","game_date_taipei":"2026-10-27",
            "status":"Final","boxscore_source_url":url_denver,"boxscore_raw_sha256":"c"*64,
            "players":[player("Nikola Jokić",gid_denver,"203999",url_denver,"c"*64)],"source_errors":[]}
        events=[{"gameId":gid_charlotte,"gameStatus":3,"gameTimeUTC":"2026-10-26T23:00:00Z",
                 "gameDateEst":"2026-10-26","homeTeam":{"teamId":1610612766,"teamTricode":"CHA"},
                 "awayTeam":{"teamId":1610612764,"teamTricode":"WAS"}},
                {"gameId":gid_denver,"gameStatus":3,"gameTimeUTC":"2026-10-27T02:00:00Z",
                 "gameDateEst":"2026-10-26","homeTeam":{"teamId":1610612743,"teamTricode":"DEN"},
                 "awayTeam":{"teamId":1610612744,"teamTricode":"GSW"}}]
        result={"provider":"nba_stats","record":{"url":"https://stats.nba.com/stats/scoreboardv3?GameDate=10%2F26%2F2026&LeagueID=00"},
            "events":events,"errors":[]}
        with patch.object(generator,"acquire_schedule",return_value=result), \
             patch.object(generator,"acquire_game_bundle_with_fallback",side_effect=[charlotte,denver]):
            payload,_=generator.generate_payload(root=ROOT,report_date="2026-10-27",nba_date_et="20261026",
                snapshot_dir=ROOT.parent/"private-test-cache",client=Client())

        self.assertIn("Nikola Jokic",payload["report"]["other_players"])
        self.assertIn("Moussa Diabate",payload["report"]["other_players"])
        self.assertNotIn("Nikola Jokic",payload["report"]["free_agents"])
        self.assertNotIn("Moussa Diabate",payload["report"]["free_agents"])
        self.assertNotIn("Terrence Shannon Jr",payload["report"]["free_agents"])
        self.assertNotIn("Terrence Shannon Jr",payload["report"]["other_players"])
        aliases={x["box_name"]:x["roster_name"] for x in payload["report"]["identity_aliases"]}
        self.assertEqual(aliases["Nikola Jokić"],"Nikola Jokic")
        self.assertEqual(aliases["Moussa Diabaté"],"Moussa Diabate")
        scores,missing=validate(payload)
        self.assertEqual(missing,{})
        self.assertIn("Nikola Jokic",scores)

    def test_espn_fallback_keeps_final_provider_games_when_official_ids_are_absent(self):
        events=[]
        for n,(home,away) in enumerate((("BOS","BKN"),("NYK","DET"),("SAS","SAC"),("LAL","POR")),start=1):
            events.append({"id":f"40190987{n}","date":"2026-10-28T00:00:00Z","competitions":[{
                "status":{"type":{"state":"post"}},"competitors":[
                    {"homeAway":"home","team":{"id":str(100+n),"abbreviation":home,"displayName":home}},
                    {"homeAway":"away","team":{"id":str(200+n),"abbreviation":away,"displayName":away}}]}]})
        result={"provider":"espn","record":{"url":"https://site.api.espn.com/scoreboard?dates=20261027"},
            "events":events,"errors":[{"provider":"nba_stats","kind":"FORBIDDEN"}]}
        with patch.object(generator,"acquire_schedule",return_value=result):
            payload,receipt=generator.generate_payload(root=ROOT,report_date="2026-10-28",nba_date_et="20261027",
                snapshot_dir=ROOT.parent/"private-test-cache",client=Client())
        self.assertEqual(receipt["schedule_status"],"PARTIAL_PROVIDER_IDENTITY")
        self.assertEqual([x["id"] for x in payload["schedule_games"]],
            ["espn:401909871","espn:401909872","espn:401909873","espn:401909874"])
        self.assertEqual([x["status"] for x in payload["schedule_games"]],["Final"]*4)
        self.assertEqual([x["id"] for x in payload["games"]],[x["id"] for x in payload["schedule_games"]])
        self.assertTrue(all(x.get("fetch_error") for x in payload["games"]))
        scores,missing=validate(payload)
        text,status=render(payload,scores,missing)
        self.assertEqual(status,"PROVISIONAL")
        self.assertIn("Final 4",text)
        self.assertIn("OFFICIAL_GAME_ID_UNAVAILABLE",[x["kind"] for x in payload["report"]["source_failures"]])

    def test_official_game_to_espn_bundle_keeps_provider_and_official_ids_through_scoring(self):
        league=json.loads((ROOT/"seasons/2026-27/league.json").read_text())
        gid="0022600130"
        provider_id="401909873"
        stats={key:0 for key in league["scoring"] if key not in ("DD","TD")}
        stats.update({"MIN":"27:00","PTS":15,"3PTM":3,"DREB":5,"AST":5,"STL":1,
            "TO":3,"FTA":4,"PF":2,"TECH":None,"EJCT":None,"FF":None})
        quality={key:("UNKNOWN" if stats[key] is None else "THIRD_PARTY_RECONSTRUCTED")
            for key in stats if key!="MIN"}
        source_url="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401909873"
        digest="a"*64
        player={"name":"Stephon Castle","status":"PLAYED","game_id":gid,"player_id":"espn:1642264",
            "official_player_id":None,"provider":"espn","provider_team_id":"24",
            "provider_team_side":"home","provider_team_tricode":"SAS",
            "provider_player_id":"1642264","identity_status":"VERIFIED_PROVIDER_IDENTITY",
            "identity_source_url":source_url,"identity_source_sha256":digest,
            "stats":stats,"quality":quality,"source_quality":"THIRD_PARTY_UNVERIFIED_TERMS"}
        crosswalk={"nba_game_id":gid,"provider":"espn","provider_event_id":provider_id,
            "home_team_tricode":"SAS","away_team_tricode":"SAC",
            "home_provider_team_id":"24","away_provider_team_id":"23",
            "official_tipoff_utc":"2026-10-28T00:00:00Z","provider_tipoff_utc":"2026-10-28T00:00:00Z",
            "schedule_source_url":"https://site.api.espn.com/scoreboard?dates=20261027",
            "schedule_raw_sha256":"b"*64,
            "join_rule":"exact_home_away_tricode_plus_utc_start_within_120s"}
        bundle={"game_id":gid,"provider":"espn","provider_game_id":provider_id,"official_game_id":gid,
            "game_id_crosswalk":crosswalk,"game_date_et":"2026-10-27","game_date_taipei":"2026-10-28",
            "status":"Final","boxscore_source_url":source_url,"boxscore_raw_sha256":digest,
            "source_records":[{"provider":"espn","url":crosswalk["schedule_source_url"],"raw_sha256":"b"*64}],
            "source_errors":[],"players":[player]}
        schedule={"provider":"nba_stats","record":{"url":"https://stats.nba.com/scoreboard?GameDate=10%2F27%2F2026"},
            "events":[{"gameId":gid,"gameStatus":3,"gameTimeUTC":"2026-10-28T00:00:00Z",
                "gameDateEst":"2026-10-27","homeTeam":{"teamId":1610612759,"teamTricode":"SAS"},
                "awayTeam":{"teamId":1610612758,"teamTricode":"SAC"}}],"errors":[]}
        with patch.object(generator,"acquire_schedule",return_value=schedule), \
             patch.object(generator,"acquire_game_bundle_with_fallback",return_value=bundle):
            payload,_=generator.generate_payload(root=ROOT,report_date="2026-10-28",nba_date_et="20261027",
                snapshot_dir=ROOT.parent/"private-test-cache",client=Client())
        game=payload["games"][0]
        self.assertEqual(game["id"],gid)
        self.assertEqual(game["official_game_id"],gid)
        self.assertEqual(game["provider"],"espn")
        self.assertEqual(game["provider_game_id"],provider_id)
        self.assertEqual(game["provider_game_crosswalk"]["provider_event_id"],provider_id)
        self.assertEqual(game["players"][0]["player_id"],"espn:1642264")
        scores,missing=validate(payload)
        self.assertIn("Stephon Castle",scores)
        self.assertEqual(missing["Stephon Castle"].split(":",1)[0],"PARTIAL_FP")
        self.assertEqual(str(scores["Stephon Castle"]),"32.50")

    def test_real_adapter_fallback_bundle_flows_through_generator_without_id_conflation(self):
        from datetime import datetime, timezone
        import hashlib
        import urllib.error
        league=json.loads((ROOT/"seasons/2026-27/league.json").read_text())
        gid="0022600130"; provider_id="401909873"
        official_schedule={"provider":"nba_stats","record":{"url":"https://stats.nba.com/scoreboard"},
            "events":[{"gameId":gid,"gameStatus":3,"gameTimeUTC":"2026-10-28T00:00:00Z",
                "gameDateEst":"2026-10-27","homeTeam":{"teamId":1610612759,"teamTricode":"SAS"},
                "awayTeam":{"teamId":1610612758,"teamTricode":"SAC"}}],"errors":[]}
        espn_event={"id":provider_id,"date":"2026-10-28T00:00:00Z","competitions":[{
            "status":{"type":{"state":"post"}},"competitors":[
                {"homeAway":"home","team":{"id":"24","abbreviation":"SAS","displayName":"San Antonio Spurs"}},
                {"homeAway":"away","team":{"id":"23","abbreviation":"SAC","displayName":"Sacramento Kings"}}]}]}
        keys=["minutes","points","threePointFieldGoalsMade-threePointFieldGoalsAttempted",
            "offensiveRebounds","defensiveRebounds","rebounds","assists","steals","blocks",
            "turnovers","freeThrowsMade-freeThrowsAttempted","fouls"]
        summary={"header":{"id":provider_id,"competitions":[{"date":"2026-10-28T00:00:00Z",
            "status":{"type":{"state":"post"}},"competitors":espn_event["competitions"][0]["competitors"]}]},
            "boxscore":{"players":[
                {"team":{"id":"24","displayName":"San Antonio Spurs"},"statistics":[{"keys":keys,
                    "athletes":[{"athlete":{"id":"1642264","displayName":"Stephon Castle"},
                        "stats":["27","15","3-8","0","5","5","5","1","0","3","4-4","2"],
                        "didNotPlay":False}]}]},
                {"team":{"id":"23","displayName":"Sacramento Kings"},"statistics":[]}]}}
        class FakeClient:
            def __init__(self):
                self.history=[]
                self.espn_use_attestation="synthetic-test-attestation"
            def get_json(self,provider,url,schema_version,validator=None):
                if provider=="nba_cdn":
                    raise generator.SourceError(provider,url,"FORBIDDEN","HTTP 403",403)
                if provider=="espn" and "scoreboard" in url:
                    payload={"events":[espn_event]}
                elif provider=="espn":
                    payload=summary
                else:
                    raise AssertionError(f"unexpected provider {provider}")
                if validator and not validator(payload): raise AssertionError(f"invalid {provider} fixture")
                body=json.dumps(payload,sort_keys=True).encode()
                record={"provider":provider,"url":url,"http_status":200,"schema_version":schema_version,
                    "raw_sha256":hashlib.sha256(body).hexdigest(),"normalized_sha256":hashlib.sha256(body).hexdigest(),
                    "fetched_at":datetime.now(timezone.utc).isoformat(),"source_quality":"THIRD_PARTY_UNVERIFIED_TERMS",
                    "publication_rights":"UNVERIFIED","response_bytes":len(body),"error_history":[]}
                self.history.append(record)
                return payload,record
        client=FakeClient()
        with patch.object(generator,"acquire_schedule",return_value=official_schedule):
            payload,receipt=generator.generate_payload(root=ROOT,report_date="2026-10-28",nba_date_et="20261027",
                snapshot_dir=ROOT.parent/"private-test-cache",client=client)
        game=payload["games"][0]
        self.assertEqual(game["id"],gid)
        self.assertEqual(game["official_game_id"],gid)
        self.assertEqual(game["provider"],"espn")
        self.assertEqual(game["provider_game_id"],provider_id)
        self.assertEqual(game["provider_game_crosswalk"]["schedule_raw_sha256"],client.history[0]["raw_sha256"])
        self.assertEqual(game["players"][0]["game_id"],gid)
        self.assertEqual(game["players"][0]["player_id"],"espn:1642264")
        scores,missing=validate(payload)
        self.assertEqual(str(scores["Stephon Castle"]),"32.50")
        self.assertEqual(missing["Stephon Castle"].split(":",1)[0],"PARTIAL_FP")
        self.assertEqual(receipt["schedule_status"],"COMPLETE")
        tampered=copy.deepcopy(payload)
        tampered["games"][0]["provider_game_crosswalk"]["provider_event_id"]="401909999"
        with self.assertRaisesRegex(ValueError,"crosswalk does not bind official GAME_ID"):
            validate(tampered)
        tampered=copy.deepcopy(payload)
        tampered["games"][0]["players"][0]["provider_team_id"]="999"
        with self.assertRaisesRegex(ValueError,"crosswalk does not bind official GAME_ID"):
            validate(tampered)
        tampered=copy.deepcopy(payload)
        tampered["games"][0]["players"][0]["provider_team_id"]="23"
        with self.assertRaisesRegex(ValueError,"player team side does not match game crosswalk"):
            validate(tampered)


if __name__=="__main__":
    unittest.main()
