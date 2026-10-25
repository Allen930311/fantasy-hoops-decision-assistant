"""Adversarial structural/data checks. ALL game/video URLs are synthetic test fixtures."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_scouting_report import validate_report, compute_game_fp, blob_sha  # noqa: E402


class ScoutingReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.season = Path(self.tmp.name) / "2026-27"
        (self.season / "ownership").mkdir(parents=True)
        for name in ("league.json", "rosters.json"):
            (self.season / name).write_bytes((ROOT / "seasons/2026-27" / name).read_bytes())
        (self.season / "ownership/current-state.json").write_bytes(
            (ROOT / "seasons/2026-27/ownership/current-state.json").read_bytes())
        self.roster = json.loads((self.season / "rosters.json").read_text())
        self.score = json.loads((self.season / "league.json").read_text())["scoring"]
        self.overlay = json.loads((self.season / "ownership/current-state.json").read_text())
        self.folder = self.season / "scouting/reports/herbert-jones"
        self.folder.mkdir(parents=True)
        self.path = self.folder / "2026-10-25.v1.json"
        self.markdown = self.path.with_suffix(".md")
        self.markdown.write_text(
            "# SYNTHETIC TEST FIXTURE — NOT A REAL SCOUTING REPORT\n" +
            "\n".join(f"## {i}. Test section {i}\n" + ("Only synthetic validation text. " * 6) for i in range(8)),
            encoding="utf-8",
        )
        self.stats = {k: 0 for k in self.score}
        self.stats.update({"PTS": 15, "OREB": 2, "DREB": 8, "AST": 4, "STL": 2, "BLK": 1, "FTA": 4, "3PTM": 1, "TO": 2, "PF": 2, "DD": 1, "TD": 0})
        fp, missing = compute_game_fp(self.stats, self.score)
        self.assertEqual(missing, [])
        self.report = {
            "schema_version": 1, "season": "2026-27",
            "researcher": "synthetic-writer",
            "player": {"name": "Herbert Jones", "nba_id": "9999999", "yahoo_id": None, "identity_source": "https://example.invalid/synthetic-identity", "aliases": ["Herb Jones"]},
            "content_status": "VALIDATED", "review_status": "PASS", "archive_status": "NOT_WRITTEN",
            "provenance": {
                "roster_commit_sha": "f" * 40,
                "league_blob_sha": blob_sha((self.season / "league.json").read_bytes()),
                "rosters_blob_sha": blob_sha((self.season / "rosters.json").read_bytes()),
                "ownership_blob_sha": blob_sha((self.season / "ownership/current-state.json").read_bytes()),
                "data_cutoff_taipei": "2026-10-25T12:00:00+08:00",
                "nba_sources": [{"url": "https://example.invalid/synthetic-nba-game", "accessed_at": "2026-10-25T11:00:00+08:00"}],
                "film": [{"url": "https://example.invalid/synthetic-film", "game_id": "TEST-GAME", "game_date": "2026-10-25", "timestamp": "01:00-01:20", "observation": "Test observation", "counterexample": "Test counterexample"}],
            },
            "ownership": {"status": "OWNER_ROSTER", "team_id": "team_02"},
            "games": [{"game_id": "TEST-1", "source_url": "https://example.invalid/synthetic-game-boxscore", "accessed_at": "2026-10-25T11:00:00+08:00", "stats": self.stats, "claimed_fp": fp}],
            "claimed_fp_per_game": fp,
            "narrative": {k: "SYNTHETIC test narrative, not an actual NBA conclusion." for k in
                          ("offense", "defense", "role", "risk", "counterargument", "recommendation", "trigger")},
            "scenarios": {k: {"minutes": 30, "fp_per_game": 35, "games_per_week": 3, "fp_per_week": 105,
                "rationale": "Synthetic assumptions, not an empirical player projection"} for k in ("bear", "base", "bull")},
            "comparison": {"baseline_player": "Synthetic baseline", "baseline_fp_per_game": 30,
                "candidate_fp_per_game": 35, "delta_fp_per_game": 5, "rationale": "Synthetic delta check only"},
            "review": {"reviewer": "synthetic-independent-reviewer", "reviewed_at": "2026-10-25T12:00:00+08:00",
                       "evidence_url": "https://example.invalid/synthetic-review"}
        }

    def check(self, data=None):
        self.path.write_text(json.dumps(self.report if data is None else data, ensure_ascii=False), encoding="utf-8")
        return validate_report(self.path, self.season)

    def assert_rejects(self, token):
        self.assertIn(token, "; ".join(self.check()))

    def test_passing_synthetic_full_schema(self):
        self.assertEqual(self.check(), [])

    def test_our_roster_cannot_be_fa(self):
        self.report["ownership"] = {"status": "CONFIRMED_FA", "team_id": None,
             "yahoo_verification": {"url": "https://example.invalid/fake-yahoo", "checked_at": "2026-10-25T12:00:00+08:00", "status": "CONFIRMED_FA"}}
        self.assert_rejects("ownership mismatch")

    def test_unknown_team_add_is_owned(self):
        self.report["player"] = {"name": "Keon Ellis", "nba_id": "9999999", "identity_source": "https://example.invalid/synthetic-identity", "aliases": []}
        self.report["ownership"] = {"status": "CONFIRMED_FA", "team_id": None}
        self.assert_rejects("OWNED_TEAM_UNKNOWN")

    def test_released_is_not_free_agent(self):
        self.report["player"] = {"name": "Kentavious Caldwell-Pope", "nba_id": "synthetic-test-only", "aliases": []}
        self.report["ownership"] = {"status": "CONFIRMED_FA", "team_id": None}
        self.assert_rejects("RELEASED_AVAILABILITY_UNVERIFIED")

    def test_other_roster_attribution(self):
        self.report["player"] = {"name": "LaMelo Ball", "nba_id": "synthetic-test-only", "aliases": []}
        self.report["ownership"] = {"status": "OWNER_ROSTER", "team_id": "team_02"}
        self.assert_rejects("OTHER_TEAM_ROSTER")

    def test_additional_owned_player_is_not_free_agent(self):
        self.report["player"] = {"name": "Aaron Wiggins", "nba_id": "9999999",
          "identity_source": "https://example.invalid/synthetic-identity", "aliases": []}
        self.report["ownership"] = {"status": "CONFIRMED_FA", "team_id": None}
        self.assert_rejects("OTHER_TEAM_ROSTER")

    def test_nba_source_cannot_postdate_cutoff(self):
        self.report["provenance"]["nba_sources"][0]["accessed_at"] = "2026-10-26T00:00:00+08:00"
        self.assert_rejects("after the pinned cutoff")

    def test_invented_stable_id_rejected(self):
        self.report["player"]["nba_id"] = "not-verified"
        self.assert_rejects("syntactically valid stable NBA")

    def test_missing_identity_source_rejected(self):
        self.report["player"]["identity_source"] = None
        self.assert_rejects("independently sourced")

    def test_missing_fta_fails_validated(self):
        del self.report["games"][0]["stats"]["FTA"]
        self.report["games"][0]["claimed_fp"] = None
        self.report["claimed_fp_per_game"] = None
        self.assert_rejects("missing/invalid score fields")

    def test_missing_ftas_can_be_provisional_without_false_fp(self):
        self.report["content_status"] = "PROVISIONAL"
        self.report["review_status"] = "NOT_RUN"
        del self.report["games"][0]["stats"]["FTA"]
        self.report["games"][0]["claimed_fp"] = None
        self.report["claimed_fp_per_game"] = None
        self.assertEqual(self.check(), [])

    def test_dd_td_not_trusted(self):
        self.report["games"][0]["stats"]["DD"] = 0
        self.assert_rejects("DD_TD_INCONSISTENT")

    def test_wrong_fantasy_claim(self):
        self.report["games"][0]["claimed_fp"] += 2
        self.assert_rejects("claimed FP differs")

    def test_bad_source(self):
        self.report["provenance"]["film"][0]["url"] = "not-a-url"
        self.assert_rejects("film evidence requires")

    def test_wrong_sha(self):
        self.report["provenance"]["ownership_blob_sha"] = "0" * 40
        self.assert_rejects("ownership_blob_sha")

    def test_self_review_rejected(self):
        self.report["review"]["reviewer"] = self.report["researcher"]
        self.assert_rejects("independently attributable")

    def test_false_archive_claim_rejected(self):
        self.report["archive_status"] = "ARCHIVED"
        self.assert_rejects("ARCHIVED cannot be self-declared")

    def test_empty_markdown_rejected(self):
        self.markdown.write_text("ok", encoding="utf-8")
        self.assert_rejects("substantive report sections")

    def test_mismatched_comparison_delta(self):
        self.report["comparison"]["delta_fp_per_game"] = 33
        self.assert_rejects("delta calculation mismatch")

    def test_scenario_arithmetic(self):
        self.report["scenarios"]["bear"]["fp_per_week"] = 1
        self.assert_rejects("FP per week arithmetic mismatch")

    def test_stable_identity_for_validated(self):
        self.report["player"]["nba_id"] = None
        self.assert_rejects("requires syntactically valid stable NBA or Yahoo player ID")


if __name__ == "__main__":
    unittest.main()
