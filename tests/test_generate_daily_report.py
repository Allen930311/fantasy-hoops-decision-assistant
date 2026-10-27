"""Integration contract for the real-data daily report orchestrator."""
import json
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


if __name__=="__main__":
    unittest.main()
