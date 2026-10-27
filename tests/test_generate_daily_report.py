"""Integration contract for the real-data daily report orchestrator."""
import json
import sys
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
        self.assertEqual(payload["report"]["short_appearance_alerts"][0]["status"],
                         "SHORT_APPEARANCE_WATCH_INJURY_UNVERIFIED")
        scores,missing=validate(payload)
        text,status=render(payload,scores,missing)
        self.assertEqual(status,"VALIDATED")
        self.assertEqual(str(scores["Justin Champagnie"]),"5.00")
        self.assertIn("Justin Champagnie",text)
        self.assertIn("短時間出賽，傷因未核實",text)


if __name__=="__main__":
    unittest.main()
