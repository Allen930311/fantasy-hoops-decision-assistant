"""Regression checks for team-attributed extra owned players and current overlay."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "seasons" / "2026-27"
VALIDATOR = ROOT / "scripts" / "validate_season_state.py"


class OwnershipStateTests(unittest.TestCase):
    def _fixture(self, changes=None):
        temp = tempfile.TemporaryDirectory()
        target = Path(temp.name)
        (target / "ownership").mkdir()
        for relative in ("league.json", "rosters.json", "ownership/current-state.json"):
            source = SOURCE / relative
            obj = json.loads(source.read_text(encoding="utf-8"))
            if changes and relative in changes:
                changes[relative](obj)
            (target / relative).write_text(
                json.dumps(obj, ensure_ascii=False), encoding="utf-8"
            )
        return temp, target

    def _run(self, directory):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(directory)],
            text=True, capture_output=True, check=False,
        )

    def test_effective_state_passes(self):
        temp, root = self._fixture()
        try:
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("total_team_owned=", result.stdout)
        finally:
            temp.cleanup()

    def test_duplicate_extra_owned_fails(self):
        def corrupt(roster):
            roster["teams"][0]["additional_owned_players"] = [
                roster["teams"][0]["players"][0]
            ]
        temp, root = self._fixture({"rosters.json": corrupt})
        try:
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate team-attributed", result.stdout)
        finally:
            temp.cleanup()

    def test_unassigned_overlay_cannot_also_be_rostered(self):
        def corrupt(overlay):
            roster = json.loads((SOURCE / "rosters.json").read_text(encoding="utf-8"))
            overlay["unassigned_confirmed_owned_players"][0]["name"] = roster["teams"][0]["players"][0]
        temp, root = self._fixture({"ownership/current-state.json": corrupt})
        try:
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("overlaps known team ownership", result.stdout)
        finally:
            temp.cleanup()

    def test_dropped_player_cannot_still_be_rostered(self):
        def corrupt(overlay):
            roster = json.loads((SOURCE / "rosters.json").read_text(encoding="utf-8"))
            overlay["released_availability_unverified"][0]["name"] = roster["teams"][0]["players"][0]
        temp, root = self._fixture({"ownership/current-state.json": corrupt})
        try:
            result = self._run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("released players still marked owned", result.stdout)
        finally:
            temp.cleanup()

    def test_il_add_only_does_not_require_fictitious_drop(self):
        def plus(roster):
            roster["teams"][0]["additional_owned_players"] = ["Synthetic Test Only Player"]
        temp, root = self._fixture({"rosters.json": plus})
        try:
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
