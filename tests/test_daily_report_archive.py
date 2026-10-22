"""Offline deterministic tests for the independent daily report archive."""
import copy
import json
import subprocess
import sys
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"daily_report_archive.py"
spec=importlib.util.spec_from_file_location("daily_archive",SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SCORING={"PTS":1,"3PTM":2,"OREB":2.5,"DREB":1.5,"AST":2,"STL":3,"BLK":3,
         "TO":-2,"FTA":-0.25,"PF":-1,"TECH":-1,"EJCT":-10,"FF":-5,"DD":7,"TD":6}
def fixture():
    stats={k:0 for k in module.STATS}
    stats.update(MIN="30:15",PTS=12,OREB=3,DREB=6,AST=10,PF=2)
    return {"schedule_games":[{"id":"game1","status":"final"}],
            "schedule_source_url":"https://www.nba.com/schedule",
            "league":{"season":"2026-27","owner_team_id":"team_02","scoring":SCORING},
            "rosters":{"season":"2026-27","teams":[{"team_id":"team_02","players":["A","DNP"]},{"team_id":"team_01","players":["B"]}]},
            "games":[{"id":"game1","status":"final","date_taipei":"2026-10-22",
                      "source_url":"https://www.nba.com/game/example","players":[{"name":"A","stats":stats},{"name":"B","stats":stats}]}],
            "report":{"date":"2026-10-22","other_players":[],"owner_players":["A"],"free_agents":[],
                      "confirmed_unsynced_adds":["Z"],"body":"# 今日戰報",
                      "source_urls":["https://www.nba.com/game/example"],
                      "provenance":{k:"verified" for k in ("roster_commit_sha","rosters_blob_sha","league_blob_sha","data_cutoff_taipei","generated_at_taipei")}}}
class ArchiveTests(unittest.TestCase):
    def test_scoring_oreb_dreb_double_double(self):
        p=fixture()
        scores,missing=module.validate(p)
        self.assertEqual(scores["A"],12+3*2.5+6*1.5+10*2-2+7)
        self.assertFalse(missing)
    def test_triple_double_cumulative(self):
        p=fixture()
        p["games"][0]["players"][0]["stats"]["DREB"]=10
        scores,_=module.validate(p)
        self.assertEqual(scores["A"],12+3*2.5+10*1.5+10*2-2+7+6)
    def test_missing_penalty_provisional(self):
        p=fixture()
        del p["games"][0]["players"][0]["stats"]["PF"]
        scores,missing=module.validate(p)
        self.assertEqual(scores,{})
        self.assertIn("A",missing)
        self.assertEqual(module.render(p,scores,missing)[1],"PROVISIONAL")
    def test_owner_missing_fails(self):
        p=fixture()
        p["report"]["owner_players"]=[]
        with self.assertRaises(ValueError):module.validate(p)
    def test_rostered_fa_fails(self):
        p=fixture()
        p["report"]["free_agents"]=["B"]
        with self.assertRaises(ValueError):module.validate(p)
    def test_unsynced_add_fails(self):
        p=fixture()
        p["report"]["free_agents"]=["Z"]
        with self.assertRaises(ValueError):module.validate(p)
    def test_dnp_excluded(self):
        self.assertEqual(set(fixture()["report"]["owner_players"]),{"A"})
        module.validate(fixture())
    def test_idempotency_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=module.write_immutable(Path(tmp),"2026-10-22","one","VALIDATED")
            b=module.write_immutable(Path(tmp),"2026-10-22","one","VALIDATED")
            c=module.write_immutable(Path(tmp),"2026-10-22","two","VALIDATED")
            self.assertTrue(a[2]);self.assertFalse(b[2]);self.assertTrue(c[2])
            self.assertEqual(c[0].name,"2026-10-22.v2.md")
    def test_provisional_and_validated_coexist(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=module.write_immutable(Path(tmp),"2026-10-22","draft","PROVISIONAL")
            b=module.write_immutable(Path(tmp),"2026-10-22","final","VALIDATED")
            self.assertNotEqual(a[0],b[0])

    def test_owner_unsynced_completed_add_is_covered(self):
        p=fixture()
        p["report"]["confirmed_transactions"]=[{"status":"completed","team_id":"team_02","add":"C","confirmed_at":"2026-10-22","source":"owner confirmation"}]
        p["games"][0]["players"].append({"name":"C","stats":copy.deepcopy(p["games"][0]["players"][0]["stats"])})
        with self.assertRaisesRegex(ValueError,"owner coverage mismatch"):module.validate(p)
        p["report"]["owner_players"].append("C")
        scores,missing=module.validate(p)
        self.assertIn("C",scores)
        self.assertFalse(missing)
    def test_unconfirmed_transaction_is_rejected(self):
        p=fixture()
        p["report"]["confirmed_transactions"]=[{"status":"planned","team_id":"team_02","add":"C","confirmed_at":"2026-10-22","source":"intent"}]
        with self.assertRaisesRegex(ValueError,"completed evidence"):module.validate(p)
    def test_selected_other_team_is_scored(self):
        p=fixture()
        p["report"]["other_players"]=["B"]
        scores,missing=module.validate(p)
        self.assertIn("B",scores)
        self.assertFalse(missing)
    def test_false_other_or_nonexistent_fa_is_rejected(self):
        p=fixture()
        p["report"]["other_players"]=["C"]
        with self.assertRaises(ValueError):module.validate(p)
        p=fixture()
        p["report"]["free_agents"]=["NotInGame"]
        with self.assertRaises(ValueError):module.validate(p)
    def test_dnp_row_is_not_scored(self):
        p=fixture()
        p["games"][0]["players"].append({"name":"DNP","status":"DNP","stats":{}})
        module.validate(p)
    def test_missing_minutes_provisional(self):
        p=fixture()
        del p["games"][0]["players"][0]["stats"]["MIN"]
        scores,missing=module.validate(p)
        self.assertIn("A",missing)
        self.assertEqual(module.render(p,scores,missing)[1],"PROVISIONAL")
    def test_render_includes_structured_player_box(self):
        p=fixture()
        scores,missing=module.validate(p)
        text,status=module.render(p,scores,missing)
        self.assertEqual(status,"VALIDATED")
        self.assertIn("| A | 30:15 | 12 | 3 | 6 |",text)
        self.assertIn("## 戰報正文",text)
    def test_mismatched_taipei_date_rejected(self):
        p=fixture()
        p["games"][0]["date_taipei"]="2026-10-21"
        with self.assertRaises(ValueError):module.validate(p)
    def test_duplicate_game_player_rejected(self):
        p=fixture()
        p["games"].append(copy.deepcopy(p["games"][0]))
        with self.assertRaises(ValueError):module.validate(p)
    def test_unknown_scoring_category_rejected(self):
        p=fixture()
        p["league"]["scoring"]["MAGIC"]=42
        with self.assertRaises(ValueError):module.validate(p)


    def test_real_unrostered_player_can_be_scored(self):
        p=fixture()
        p["games"][0]["players"].append({"name":"C","stats":copy.deepcopy(p["games"][0]["players"][0]["stats"])})
        p["report"]["free_agents"]=["C"]
        scores,missing=module.validate(p)
        self.assertIn("C",scores)
        self.assertFalse(missing)


    def test_historical_real_game_is_provisional(self):
        path=Path(__file__).parent/"fixtures"/"historical-nba-finals-2025-06-23-partial.json"
        p=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(p["fixture_type"],"historical_real_box_partial")
        self.assertEqual(p["report"]["owner_players"],["Shai Gilgeous-Alexander"])
        scores,missing=module.validate(p)
        for name in ["Shai Gilgeous-Alexander","Jalen Williams"]:
            self.assertNotIn(name,scores)
            self.assertIn(name,missing)
            self.assertIn("TECH",missing[name])
        self.assertEqual(module.render(p,scores,missing)[1],"PROVISIONAL")

    def test_cli_full_archive_and_readback(self):
        p=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            inp=Path(tmp)/"input.json"
            out=Path(tmp)/"reports"
            inp.write_text(json.dumps(p),encoding="utf-8")
            cmd=[sys.executable,str(SCRIPT),str(inp),"--output-dir",str(out)]
            first=json.loads(subprocess.check_output(cmd,text=True))
            self.assertEqual(first["status"],"VALIDATED")
            self.assertTrue(first["created"])
            body=Path(first["path"]).read_text(encoding="utf-8")
            self.assertIn("| A | 30:15 | 12 | 3 | 6 |",body)
            again=json.loads(subprocess.check_output(cmd,text=True))
            self.assertFalse(again["created"])
            self.assertEqual(first["sha256"],again["sha256"])
            self.assertEqual(first["path"],again["path"])

    def test_cli_real_historical_case_is_provisional(self):
        path=Path(__file__).parent/"fixtures"/"historical-nba-finals-2025-06-23-partial.json"
        with tempfile.TemporaryDirectory() as tmp:
            cmd=[sys.executable,str(SCRIPT),str(path),"--output-dir",tmp]
            result=json.loads(subprocess.check_output(cmd,text=True))
            self.assertEqual(result["status"],"PROVISIONAL")
            self.assertTrue(result["path"].endswith(".provisional.md"))
            self.assertIn("TECH",result["missing"]["Shai Gilgeous-Alexander"])
            self.assertTrue(Path(result["path"]).exists())


    def test_completed_game_omitted_from_boxscore_fails(self):
        p=fixture()
        p["schedule_games"].append({"id":"game2","status":"final"})
        with self.assertRaisesRegex(ValueError,"schedule coverage mismatch"):
            module.validate(p)
    def test_in_progress_game_does_not_require_boxscore(self):
        p=fixture()
        p["schedule_games"].append({"id":"game2","status":"live"})
        module.validate(p)
    def test_missing_schedule_evidence_fails_closed(self):
        p=fixture()
        del p["schedule_source_url"]
        with self.assertRaisesRegex(ValueError,"missing independent NBA schedule"):
            module.validate(p)
    def test_explicit_sourced_name_alias(self):
        p=fixture()
        p["rosters"]["teams"][0]["players"][0]="Alperen Sengun"
        p["games"][0]["players"][0]["name"]="Alperen Şengün"
        p["report"]["owner_players"]=["Alperen Sengun"]
        with self.assertRaisesRegex(ValueError,"owner coverage mismatch"):
            module.validate(p)
        p["report"]["identity_aliases"]=[{"box_name":"Alperen Şengün",
                                         "roster_name":"Alperen Sengun",
                                         "source":"https://www.nba.com/player/example"}]
        scores,missing=module.validate(p)
        self.assertIn("Alperen Sengun",scores)
        self.assertFalse(missing)

if __name__=="__main__":unittest.main()
