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
    extra_owned: list[str] = []
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
        # A screenshot can prove DROP without identifying the next ADD. Record the
        # missing baseline entries explicitly rather than pretending the dropped
        # player is still owned or inventing a replacement.
        pending = team.get("pending_baseline_departures", [])
        if not isinstance(pending, list):
            errors.append(f"{team_id}: pending_baseline_departures must be a list")
            pending = []
        deficit = expected_roster - len(team_players)
        if deficit < 0 or len(pending) != max(deficit, 0):
            errors.append(
                f"{team_id}: {len(team_players)} baseline players vs expected {expected_roster}; "
                f"pending departures {len(pending)} must equal documented deficit"
            )
        for item in pending:
            if not isinstance(item, dict) or any(
                not isinstance(item.get(key), str) or not item[key].strip()
                for key in ("player", "date", "source")
            ):
                errors.append(f"{team_id}: invalid pending baseline departure evidence")
            elif item["player"] in team_players:
                errors.append(f"{team_id}: pending departure still in roster: {item['player']}")
        players.extend(team_players)
        additional = team.get("additional_owned_players", [])
        if not isinstance(additional, list) or any(
            not isinstance(name, str) or not name.strip() for name in additional
        ):
            errors.append(f"{team_id}: additional_owned_players must be non-empty name strings")
        else:
            extra_owned.extend(additional)

    duplicate_team_ids = sorted({x for x in team_ids if team_ids.count(x) > 1})
    if duplicate_team_ids:
        errors.append(f"duplicate team_ids: {duplicate_team_ids}")

    all_known_owned = players + extra_owned
    pending_departures = [
        item.get("player")
        for team in teams
        for item in (team.get("pending_baseline_departures") or [])
        if isinstance(item, dict)
    ]
    if len(pending_departures) != len(set(pending_departures)):
        errors.append("duplicate pending departure records across teams")
    # A departure is team-local history. The departed player may already have
    # been added to a different team (or be held with team_id unknown). Reject
    # only when the same team still owns its purportedly departed player.
    for team in teams:
        current_owned = set(team.get("players") or []) | set(
            team.get("additional_owned_players") or []
        )
        pending_on_team = {
            item.get("player")
            for item in (team.get("pending_baseline_departures") or [])
            if isinstance(item, dict)
        }
        same_team_overlap = sorted(pending_on_team.intersection(current_owned))
        if same_team_overlap:
            errors.append(
                f"{team.get('team_id')}: pending departure still owned by same team: "
                f"{same_team_overlap}"
            )
    duplicate_players = sorted({x for x in set(all_known_owned) if all_known_owned.count(x) > 1})
    if duplicate_players:
        errors.append(f"duplicate team-attributed owned players: {duplicate_players}")

    current_overlay = season_dir / "ownership" / "current-state.json"
    unassigned: list[str] = []
    released: list[str] = []
    if current_overlay.exists():
        overlay = json.loads(current_overlay.read_text(encoding="utf-8"))
        if overlay.get("season") != league.get("season"):
            errors.append("ownership/current-state.json season mismatch")
        for key, target in (
            ("unassigned_confirmed_owned_players", unassigned),
            ("released_availability_unverified", released),
        ):
            entries = overlay.get(key)
            if not isinstance(entries, list):
                errors.append(f"ownership/current-state.json: {key} must be a list")
                continue
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"].strip():
                    errors.append(f"ownership/current-state.json: invalid entry in {key}")
                    continue
                if key == "unassigned_confirmed_owned_players" and entry.get("team_id") is not None:
                    errors.append(f"ownership/current-state.json: {entry['name']} is not unassigned")
                target.append(entry["name"])

        for key, names in (("unassigned", unassigned), ("released", released)):
            duplicates = sorted({name for name in set(names) if names.count(name) > 1})
            if duplicates:
                errors.append(f"duplicate {key} entries: {duplicates}")
        known_set = set(all_known_owned)
        if known_set.intersection(unassigned):
            errors.append(f"unassigned overlay overlaps known team ownership: {sorted(known_set.intersection(unassigned))}")
        if known_set.intersection(released) or set(unassigned).intersection(released):
            errors.append(f"released players still marked owned: {sorted((known_set | set(unassigned)).intersection(released))}")

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
        f"additional_owned={len(extra_owned)} total_team_owned={len(all_known_owned)} "
        f"unassigned_confirmed_owned={len(unassigned)} released_unverified={len(released)} "
        f"owner_team={owner_team_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
