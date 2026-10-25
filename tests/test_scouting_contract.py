"""Offline tests for the research-queue structure, not factual NBA validation."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_scouting_contract import validate_watchlist  # noqa: E402


class WatchlistContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.season = Path(self.tmp.name) / "2026-27"
        (self.season / "scouting" / "reports").mkdir(parents=True)
        self.data = json.loads(
            (ROOT / "seasons" / "2026-27" / "scouting" / "watchlist.json")
            .read_text(encoding="utf-8")
        )

    def write(self, data=None):
        (self.season / "scouting" / "watchlist.json").write_text(
            json.dumps(self.data if data is None else data, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_checked_in_watchlist(self):
        self.assertEqual(
            validate_watchlist(ROOT / "seasons" / "2026-27"), []
        )

    def test_valid_snapshot(self):
        self.write()
        self.assertEqual(validate_watchlist(self.season), [])

    def test_duplicate_rejected(self):
        copy_target = copy.deepcopy(self.data["targets"][0])
        copy_target["player_name"] = "herbert jones"
        self.data["targets"].append(copy_target)
        self.write()
        self.assertIn("duplicate player_name", " ".join(validate_watchlist(self.season)))

    def test_ownership_assertion_rejected(self):
        self.data["targets"][0]["availability"] = "CONFIRMED_FA"
        self.write()
        self.assertIn("must not assert", " ".join(validate_watchlist(self.season)))

    def test_completed_without_report_rejected(self):
        self.data["targets"][0]["status"] = "SCOUTED"
        self.write()
        self.assertIn("requires report_path", " ".join(validate_watchlist(self.season)))

    def test_path_traversal_rejected(self):
        self.data["targets"][0]["report_path"] = "../../rosters.json"
        self.write()
        self.assertIn("unsafe report_path", " ".join(validate_watchlist(self.season)))

    def test_wrong_season_rejected(self):
        self.data["season"] = "2025-26"
        self.write()
        self.assertIn("season does not match directory", " ".join(validate_watchlist(self.season)))

    def test_nonexistent_report_rejected(self):
        self.data["targets"][0]["report_path"] = "reports/herbert-jones/2026-10-25.v1.md"
        self.write()
        self.assertIn("does not exist", " ".join(validate_watchlist(self.season)))


if __name__ == "__main__":
    unittest.main()
