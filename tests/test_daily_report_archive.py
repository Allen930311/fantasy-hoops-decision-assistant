"""Offline deterministic tests for the independent daily report archive."""
import copy
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
    stats.update(PTS=12,OREB=3,DREB=6,AST=10,PF=2)
    return {"league":{"season":"2026-27","owner_team_id":"team_02","scoring":SCORING},
            "rosters":{"teams":[{"team_id":"team_02","players":["A","DNP"]},{"team_id":"team_01","players":["B"]}]},
            "games":[{"id":"game1","status":"final","players":[{"name":"A","stats":stats},{"name":"B","stats":stats}]}],
            "report":{"date":"2026-10-22","owner_players":["A"],"free_agents":["C"],
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
if __name__=="__main__":unittest.main()
