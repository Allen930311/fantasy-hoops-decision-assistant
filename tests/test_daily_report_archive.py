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
sys.path.insert(0,str(SCRIPT.parent))
spec=importlib.util.spec_from_file_location("daily_archive",SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SCORING={"PTS":1,"3PTM":2,"OREB":2.5,"DREB":1.5,"AST":2,"STL":3,"BLK":3,
         "TO":-2,"FTA":-0.25,"PF":-1,"TECH":-1,"EJCT":-10,"FF":-5,"DD":7,"TD":6}
def fixture():
    stats={k:0 for k in module.STATS}
    stats.update(MIN="30:15",PTS=12,OREB=3,DREB=6,AST=10,PF=2)
    quality={k:("VERIFIED_VALUE" if stats[k] else "VERIFIED_ZERO") for k in module.STATS}
    gid="0022601000"
    return {"schedule_games":[{"id":gid,"status":"final"}],
            "schedule_source_url":"https://www.nba.com/schedule",
            "league":{"season":"2026-27","owner_team_id":"team_02","scoring":copy.deepcopy(SCORING)},
            "rosters":{"season":"2026-27","teams":[{"team_id":"team_02","players":["A","DNP"]},{"team_id":"team_01","players":["B"]}]},
            "ownership":{"season":"2026-27","unassigned_confirmed_owned_players":[],"released_availability_unverified":[]},
            "games":[{"id":gid,"status":"final","date_taipei":"2026-10-22",
                      "source_url":"https://www.nba.com/game/example","raw_source_sha256":"a"*64,"players":[{"name":"A","status":"played","game_id":gid,"player_id":"1","provider_player_id":"1","official_player_id":"1","identity_status":"VERIFIED","identity_source_url":"https://www.nba.com/game/example","identity_source_sha256":"a"*64,"quality":quality,"stats":stats},{"name":"B","status":"played","game_id":gid,"player_id":"2","provider_player_id":"2","official_player_id":"2","identity_status":"VERIFIED","identity_source_url":"https://www.nba.com/game/example","identity_source_sha256":"a"*64,"quality":quality,"stats":stats}]}],
            "report":{"date":"2026-10-22","other_players":[],"owner_players":["A"],"free_agents":[],
                      "confirmed_unsynced_adds":["Z"],"body":"# 今日戰報",
                      "source_urls":["https://www.nba.com/game/example"],
                      "provenance":{**{k:"verified" for k in ("roster_commit_sha","rosters_blob_sha","league_blob_sha","ownership_blob_sha","data_cutoff_taipei","generated_at_taipei")},"data_rights_status":"AUTHORIZED_FOR_GITHUB"}}}
class ArchiveTests(unittest.TestCase):
    def test_off_day_still_produces_a_valid_empty_daily_report(self):
        p=fixture();p["schedule_games"]=[];p["games"]=[];p["report"]["owner_players"]=[]
        scores,missing=module.validate(p)
        text,status=module.render(p,scores,missing)
        self.assertEqual(scores,{})
        self.assertEqual(missing,{})
        self.assertEqual(status,"VALIDATED")
        self.assertIn('"completed_games": 0',text)

    def test_live_slate_is_reported_provisionally_without_dnp_rows(self):
        p=fixture();p["schedule_games"]=[{"id":"0022601000","status":"live"}]
        p["games"]=[];p["report"]["owner_players"]=[]
        scores,missing=module.validate(p)
        text,status=module.render(p,scores,missing)
        self.assertEqual(status,"PROVISIONAL")
        self.assertEqual(missing,{})
        self.assertIn('"completed_games": 0',text)
        self.assertEqual(text.count("| A |"),0)

    def test_boxscore_failure_emits_provisional_with_unknown_owner_coverage(self):
        p=fixture();missing_id="0022601001"
        p["schedule_games"].append({"id":missing_id,"status":"final"})
        p["games"].append({"id":missing_id,"status":"final","date_taipei":"2026-10-22",
            "source_url":"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022601001.json",
            "fetch_error":{"kind":"FORBIDDEN"},"players":[]})
        p["report"]["source_failures"]=[{"game_id":missing_id,"provider":"nba_cdn","url":p["games"][1]["source_url"],
            "kind":"FORBIDDEN","message":"HTTP 403; switched to fallback, no verified identity rows",
            "impact":"OWNER_COVERAGE_UNKNOWN"}]
        scores,missing=module.validate(p)
        text,status=module.render(p,scores,missing)
        self.assertEqual(status,"PROVISIONAL")
        self.assertIn('"owner_coverage_status": "UNKNOWN_DUE_TO_SOURCE_GAP"',text)
        self.assertIn("不可解讀為 DNP、缺席或零 FP",text)

    def test_unfeatured_game_player_quality_gap_keeps_report_provisional(self):
        p=fixture();p["report"]["quality_gaps"]=[{"game_id":"0022601000","player_id":"3",
            "name":"Unfeatured","missing":["TECH"]}]
        scores,missing=module.validate(p)
        text,status=module.render(p,scores,missing)
        self.assertEqual(status,"PROVISIONAL")
        self.assertIn('"quality_gaps": 1',text)
        self.assertIn("Unfeatured: TECH",text)

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
        c=copy.deepcopy(p["games"][0]["players"][0]);c["name"]="C";c["player_id"]="3";c["provider_player_id"]="3";c["official_player_id"]="3"
        p["games"][0]["players"].append(c)
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

    def test_did_not_play_spelling_is_not_scored(self):
        p=fixture()
        row=copy.deepcopy(p["games"][0]["players"][0]);row["name"]="DNP";row["status"]="Did Not Play"
        p["games"][0]["players"].append(row)
        module.validate(p)

    def test_unknown_participation_status_fails_closed(self):
        p=fixture();p["games"][0]["players"][0]["status"]="scheduled"
        with self.assertRaisesRegex(ValueError,"unknown game participation status"):
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
        c=copy.deepcopy(p["games"][0]["players"][0]);c["name"]="C";c["player_id"]="3";c["provider_player_id"]="3";c["official_player_id"]="3"
        p["games"][0]["players"].append(c)
        p["report"]["free_agents"]=["C"]
        p["report"]["free_agent_claimability"]={"C":{"confidence":"INFERRED_UNROSTERED"}}
        scores,missing=module.validate(p)
        self.assertIn("C",scores)
        self.assertFalse(missing)

    def test_unassigned_overlay_is_not_free_agent(self):
        p=fixture()
        p["ownership"]["unassigned_confirmed_owned_players"]=[{"name":"C","team_id":None}]
        c=copy.deepcopy(p["games"][0]["players"][0]);c["name"]="C";c["player_id"]="3";c["provider_player_id"]="3";c["official_player_id"]="3"
        p["games"][0]["players"].append(c)
        p["report"]["free_agents"]=["C"]
        p["report"]["free_agent_claimability"]={"C":{"confidence":"UNKNOWN"}}
        with self.assertRaisesRegex(ValueError,"rostered or confirmed unsynced ADD"):
            module.validate(p)

    def test_additional_owned_player_counts_for_coverage(self):
        p=fixture()
        p["rosters"]["teams"][0]["additional_owned_players"]=["C"]
        c=copy.deepcopy(p["games"][0]["players"][0]);c["name"]="C";c["player_id"]="3";c["provider_player_id"]="3";c["official_player_id"]="3"
        p["games"][0]["players"].append(c)
        with self.assertRaisesRegex(ValueError,"owner coverage mismatch"):
            module.validate(p)
        p["report"]["owner_players"].append("C")
        self.assertIn("C",module.validate(p)[0])

    def test_unverified_fields_never_become_verified_fp(self):
        p=fixture()
        p["games"][0]["players"][0]["quality"]["TECH"]="THIRD_PARTY_RECONSTRUCTED"
        scores,missing=module.validate(p)
        self.assertIn("A",scores)
        self.assertIn("PARTIAL_FP",missing["A"])
        self.assertEqual(module.render(p,scores,missing)[1],"PROVISIONAL")

    def test_reb_mismatch_never_becomes_verified_fp(self):
        p=fixture();p["games"][0]["players"][0]["stats"]["REB"]=1
        scores,missing=module.validate(p)
        self.assertNotIn("A",scores)
        self.assertIn("conflicting REB total",missing["A"])
        self.assertEqual(module.render(p,scores,missing)[1],"PROVISIONAL")

    def test_identity_source_and_id_must_be_bound_to_game_blob(self):
        p=fixture();row=p["games"][0]["players"][0]
        row["identity_source_url"]="https://example.invalid/player/1"
        scores,missing=module.validate(p)
        self.assertIn("A",scores);self.assertIn("NBA_PLAYER_ID",missing["A"])
        row=p["games"][0]["players"][0];row["identity_source_url"]="https://www.nba.com/game/example"
        row["identity_source_sha256"]="b"*64;row["provider_player_id"]="different"
        scores,missing=module.validate(p)
        self.assertIn("NBA_PLAYER_ID",missing["A"])

    def test_game_player_ids_required(self):
        p=fixture()
        p["games"][0]["players"][0]["game_id"]="wrong"
        with self.assertRaisesRegex(ValueError,"mismatched GAME_ID/PLAYER_ID"):
            module.validate(p)

    def test_fa_claimability_confidence_required(self):
        p=fixture();c=copy.deepcopy(p["games"][0]["players"][0]);c["name"]="C";c["player_id"]="3";c["provider_player_id"]="3";c["official_player_id"]="3"
        p["games"][0]["players"].append(c);p["report"]["free_agents"]=["C"]
        with self.assertRaisesRegex(ValueError,"Claimability Confidence"):
            module.validate(p)


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
        p["schedule_games"].append({"id":"0022601001","status":"final"})
        with self.assertRaisesRegex(ValueError,"schedule coverage mismatch"):
            module.validate(p)
    def test_in_progress_game_does_not_require_boxscore(self):
        p=fixture()
        p["schedule_games"].append({"id":"0022601001","status":"live"})
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


    def test_archive_rejects_path_traversal_and_invalid_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("../escape","2026-10-22/../../escape","2026-02-30","2026-10-2"):
                with self.subTest(bad=bad):
                    with self.assertRaises(ValueError):
                        module.write_immutable(Path(tmp),bad,"data","VALIDATED")
    def test_archive_does_not_overwrite_previous_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=module.write_immutable(Path(tmp),"2026-10-22","v1","VALIDATED")
            next_version=module.write_immutable(Path(tmp),"2026-10-22","v2","VALIDATED")
            self.assertEqual(first[0].read_text(encoding="utf-8"),"v1")
            self.assertEqual(next_version[0].read_text(encoding="utf-8"),"v2")
            self.assertNotEqual(first[0],next_version[0])

    def test_next_version_counts_legacy_provisional_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"2026-10-22.provisional.md").write_text("v1")
            (folder/"2026-10-22.v4.provisional.md").write_text("legacy v4")
            row=module.write_immutable(folder,"2026-10-22","new draft","PROVISIONAL")
            self.assertEqual(row[0].name,"2026-10-22.provisional.v5.md")


    def test_empty_completed_game_player_rows_fail_closed(self):
        p=fixture()
        p["games"][0]["players"]=[]
        p["report"]["owner_players"]=[]
        with self.assertRaisesRegex(ValueError,"without player box-score rows"):
            module.validate(p)
    def test_archive_invalid_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"invalid archive status"):
                module.write_immutable(Path(tmp),"2026-10-22","text","ARCHIVED")

if __name__=="__main__":unittest.main()
