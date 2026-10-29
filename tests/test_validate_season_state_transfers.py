"""Regression checks for team-local pending departure evidence."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


VALIDATOR = Path(__file__).resolve().parents[1] / "scripts" / "validate_season_state.py"


def _run_validator(tmp_path: Path, same_team_extra: bool):
    season = tmp_path / "2026-27"
    (season / "ownership").mkdir(parents=True)
    league = {
        "season": "2026-27",
        "league_size": 2,
        "roster_size": 1,
        "owner_team_id": "team_02",
        "scoring": {"PTS": 1},
    }
    rosters = {
        "season": "2026-27",
        "owner_team_id": "team_02",
        "teams": [
            {
                "team_id": "team_01",
                "is_owner": False,
                "players": [],
                "pending_baseline_departures": [
                    {"player": "Example Player", "date": "2026-10-29", "source": "confirmed_transfer"}
                ],
                **({"additional_owned_players": ["Example Player"]} if same_team_extra else {}),
            },
            {
                "team_id": "team_02",
                "is_owner": True,
                "players": ["Unrelated Player" if same_team_extra else "Example Player"],
            },
        ],
    }
    for file_name, data in [("league.json", league), ("rosters.json", rosters)]:
        (season / file_name).write_text(json.dumps(data), encoding="utf-8")
    (season / "ownership" / "current-state.json").write_text(
        json.dumps({
            "season": "2026-27",
            "unassigned_confirmed_owned_players": [],
            "released_availability_unverified": [],
        }),
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(season)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_departed_player_can_be_confirmed_on_another_team(tmp_path):
    result = _run_validator(tmp_path, same_team_extra=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_departed_player_cannot_still_be_owned_by_same_team(tmp_path):
    result = _run_validator(tmp_path, same_team_extra=True)
    assert result.returncode != 0
    assert "pending departure still owned by same team" in result.stdout
