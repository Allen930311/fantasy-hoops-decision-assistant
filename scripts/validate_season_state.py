#!/usr/bin/env python3
"""Validate season-scoped Fantasy Hoops league and roster state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("season_dir", nargs="?", default="seasons/2026-27")
    args = parser.parse_args()

    season_dir = Path(args.season_dir)
    league = json.loads((season_dir / "league.json").read_text(encoding="utf-8"))
    rosters = json.loads((season_dir / "rosters.json").read_text(encoding="utf-8"))

    errors: list[str] = []

    if league.get("season") != rosters.get("season"):
        errors.append("league.json and rosters.json season values differ")

    teams = rosters.get("teams")
    if not isinstance(teams, list):
        errors.append("rosters.teams must be a list")
        teams = []

    expected_teams = league.get("league_size")
    expected_roster = league.get("roster_size")

    if len(teams) != expected_teams:
        errors.append(f"expected {expected_teams} teams, found {len(teams)}")

    team_ids: list[str] = []
    players: list[str] = []
    owner_teams: list[str] = []

    for team in teams:
        team_id = team.get("team_id")
        team_players = team.get("players")
        if not isinstance(team_id, str) or not team_id:
            errors.append("every team requires a non-empty team_id")
            continue
        team_ids.append(team_id)

        if team.get("is_owner") is True:
            owner_teams.append(team_id)

        if not isinstance(team_players, list):
            errors.append(f"{team_id}: players must be a list")
            continue
        if len(team_players) != expected_roster:
            errors.append(
                f"{team_id}: expected {expected_roster} players, found {len(team_players)}"
            )
        players.extend(team_players)

    duplicate_team_ids = sorted({x for x in team_ids if team_ids.count(x) > 1})
    if duplicate_team_ids:
        errors.append(f"duplicate team_ids: {duplicate_team_ids}")

    duplicate_players = sorted({x for x in players if players.count(x) > 1})
    if duplicate_players:
        errors.append(f"duplicate rostered players: {duplicate_players}")

    owner_team_id = league.get("owner_team_id")
    if owner_teams != [owner_team_id]:
        errors.append(
            f"expected exactly owner team {owner_team_id!r}, found {owner_teams!r}"
        )
    if rosters.get("owner_team_id") != owner_team_id:
        errors.append("league.json and rosters.json owner_team_id differ")

    scoring = league.get("scoring")
    if not isinstance(scoring, dict) or not scoring:
        errors.append("league scoring must be a non-empty object")

    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"OK season={league['season']} teams={len(teams)} "
        f"players={len(players)} unique_players={len(set(players))} "
        f"owner_team={owner_team_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
