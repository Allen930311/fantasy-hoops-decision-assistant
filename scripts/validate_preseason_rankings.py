#!/usr/bin/env python3
"""Validate frozen 2026-27 preseason rankings and every published calculation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def numeric(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def close(left: Any, right: Any, tolerance: float = 0.015) -> bool:
    a, b = numeric(left), numeric(right)
    return a is not None and b is not None and abs(a - b) <= tolerance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="seasons/2026-27/data/preseason-2026-10-14")
    parser.add_argument("--report-dir", default="seasons/2026-27/report")
    parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()

    root = Path(".")
    season = root / "seasons/2026-27"
    snapshot = Path(args.snapshot)
    report = Path(args.report_dir)
    league = read_json(season / "league.json")
    roster = read_json(season / "rosters.json")
    manifest = read_json(snapshot / "source_manifest.json")
    weights = {str(key): float(value) for key, value in league["scoring"].items()}
    fields = list(weights)

    require(len(roster["teams"]) == 16, "expected 16 fantasy teams")
    require(all(len(team["players"]) == 13 for team in roster["teams"]), "each fantasy team must have 13 players")
    roster_owner: dict[str, str] = {}
    for team in roster["teams"]:
        for name in team["players"]:
            require(name not in roster_owner, f"duplicate fantasy ownership for {name}")
            roster_owner[name] = team["team_id"]
    require(len(roster_owner) == 208, "expected 208 uniquely owned roster players")

    # Verify provenance before trusting the generated tables.
    sources = manifest.get("sources", [])
    require(bool(sources), "source manifest is empty")
    for source in sources:
        payload_path = snapshot / source["payload_file"]
        require(payload_path.is_file(), f"missing source payload: {source['payload_file']}")
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        require(digest == source.get("sha256"), f"SHA-256 mismatch: {source['payload_file']}")
        require(bool(source.get("retrieved_at_utc")), f"missing retrieval time: {source['payload_file']}")

    cutoff = datetime.fromisoformat(manifest["cutoff_utc"].replace("Z", "+00:00"))
    scoreboard_final_ids: set[str] = set()
    scoreboard_by_id: dict[str, dict[str, Any]] = {}
    for path in sorted((snapshot / "nba/scoreboards").glob("*.json")):
        payload = read_json(path)
        for game in payload.get("scoreboard", {}).get("games", []):
            if game.get("gameLabel") != "Preseason":
                continue
            game_id = str(game.get("gameId", ""))
            scoreboard_by_id[game_id] = game
            start = datetime.fromisoformat(str(game["gameTimeUTC"]).replace("Z", "+00:00"))
            if start <= cutoff and int(game.get("gameStatus", 0)) == 3 and str(game.get("gameStatusText", "")).casefold().startswith("final"):
                scoreboard_final_ids.add(game_id)
    manifest_final_ids = set(map(str, manifest.get("completed_game_ids", [])))
    require(manifest_final_ids == scoreboard_final_ids, "manifest completed-game list differs from captured final scoreboards")
    require(len(manifest_final_ids) == int(manifest["completed_game_count"]), "completed-game count is inconsistent")
    for game_id in manifest_final_ids:
        box_path = snapshot / f"nba/boxscores/{game_id}.json"
        require(box_path.is_file(), f"missing box score for {game_id}")
        require((snapshot / f"nba/playbyplay/{game_id}.json").is_file(), f"missing play-by-play for {game_id}")
        box = read_json(box_path).get("boxScoreTraditional", {})
        scoreboard = scoreboard_by_id[game_id]
        for side in ("homeTeam", "awayTeam"):
            team = box.get(side, {})
            score_side = scoreboard.get(side, {})
            require(team.get("teamTricode") == score_side.get("teamTricode"), f"team identity mismatch in game {game_id} {side}")
            box_score = numeric((team.get("statistics") or {}).get("points"))
            final_score = numeric(score_side.get("score"))
            player_points = []
            for player in team.get("players", []):
                statistics = player.get("statistics") or {}
                points = numeric(statistics.get("points"))
                minutes = str(statistics.get("minutes") or "").strip()
                if minutes not in ("", "-", "0", "0:00"):
                    require(points is not None, f"played player has no points field: {game_id} {player.get('personId')}")
                player_points.append(points)
            require(box_score is not None and final_score is not None and box_score == final_score, f"boxscore/scoreboard team score mismatch: {game_id} {side}")
            require(sum(value or 0.0 for value in player_points) == box_score, f"player points do not sum to team total: {game_id} {side}")

    player_rows = read_csv(report / "2026-10-14-preseason-player-model.csv")
    team_rows = read_csv(report / "2026-10-14-preseason-team-rankings.csv")
    game_rows = read_csv(report / "2026-10-14-preseason-player-games.csv")
    require(len(player_rows) == 208, f"player model has {len(player_rows)} rows, expected 208")
    require(len(team_rows) == 16, f"team ranking has {len(team_rows)} rows, expected 16")
    require({row["player_name"] for row in player_rows} == set(roster_owner), "player model names differ from confirmed roster")
    require(len({row["player_name"] for row in player_rows}) == 208, "player model contains duplicate names")
    for row in player_rows:
        require(row["fantasy_team_id"] == roster_owner[row["player_name"]], f"wrong owner for {row['player_name']}")
        require(row["preseason_status"] in {
            "played", "did_not_play", "team_has_no_completed_game",
            "data_missing_not_listed_in_boxscore", "data_missing_unmatched_roster_player",
        }, f"invalid preseason state for {row['player_name']}: {row['preseason_status']}")
    require({row["team_id"] for row in team_rows} == {team["team_id"] for team in roster["teams"]}, "team ranking IDs differ from roster")

    player_by_name = {row["player_name"]: row for row in player_rows}
    game_keys: set[tuple[str, str]] = set()
    played_by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    game_rows_by_key: dict[tuple[str, str], dict[str, str]] = {}
    status_counts: Counter[str] = Counter()
    for row in game_rows:
        name = row["player_name"]
        require(name in player_by_name, f"game row for non-rostered player {name}")
        key = (row["game_id"], row["player_id"])
        require(key not in game_keys, f"duplicate player-game row: {key}")
        game_keys.add(key)
        game_rows_by_key[key] = row
        require(row["game_id"] in manifest_final_ids, f"non-final/out-of-cutoff game in player table: {row['game_id']}")
        require(row["fantasy_team_id"] == player_by_name[name]["fantasy_team_id"], f"game row owner mismatch for {name}")
        status_counts[row["status"]] += 1
        if row["status"] == "played":
            require(float(row["minutes"]) > 0, f"played row has no minutes: {name} {row['game_id']}")
            require(all(numeric(row.get(field)) is not None for field in fields), f"played row has missing scored stat: {name} {row['game_id']}")
            expected = sum(float(row[field]) * weight for field, weight in weights.items())
            require(close(row["custom_fp"], expected, 0.0002), f"custom FP mismatch: {name} {row['game_id']}")
            played_by_name[name].append(row)
        else:
            require(row["custom_fp"] == "", f"unplayed/data-missing player was assigned FP: {name} {row['game_id']}")
            require(all(row.get(field, "") == "" for field in fields), f"unplayed player stats were imputed: {name} {row['game_id']}")

    # Re-derive special foul stats from raw NBA Stats actions so that a
    # calculation can pass only if every technical/flagrant/ejection is
    # represented in the published player-game rows.
    for game_id in manifest_final_ids:
        actions = read_json(snapshot / f"nba/playbyplay/{game_id}.json").get("game", {}).get("actions", [])
        require(isinstance(actions, list), f"play-by-play actions are unavailable: {game_id}")
        technicals: Counter[int] = Counter()
        flagrants: Counter[int] = Counter()
        ejections: set[int] = set()
        for action in actions:
            try:
                person_id = int(action.get("personId") or 0)
            except (TypeError, ValueError):
                continue
            if person_id <= 0:
                continue
            action_type = str(action.get("actionType", "")).casefold()
            subtype = str(action.get("subType", "")).casefold()
            description = str(action.get("description", "")).casefold()
            if "eject" in action_type or "eject" in subtype or "eject" in description:
                ejections.add(person_id)
            if action_type != "foul":
                continue
            if "technical" in subtype or "technical foul" in description or "tech foul" in description:
                technicals[person_id] += 1
            if "flagrant" in subtype or "flagrant foul" in description:
                flagrants[person_id] += 1
                if "flagrant 2" in subtype or "flagrant foul 2" in description:
                    ejections.add(person_id)
        game_player_ids = {
            int(player_id)
            for row_game_id, player_id in game_rows_by_key
            if row_game_id == game_id
        }
        for player_id in game_player_ids:
            row = game_rows_by_key[(game_id, str(player_id))]
            if row["status"] != "played":
                continue
            expected_specials = {
                "TECH": technicals[player_id],
                "FF": flagrants[player_id],
                "EJCT": int(player_id in ejections or technicals[player_id] >= 2),
            }
            for field, expected_value in expected_specials.items():
                require(
                    close(row.get(field), expected_value, 0.0001),
                    f"{field} does not reconcile to NBA Stats play-by-play: {row['player_name']} {game_id} expected {expected_value}, got {row.get(field)}",
                )

    for name, player in player_by_name.items():
        played = played_by_name.get(name, [])
        require(int(player["preseason_games_played"]) == len(played), f"GP total differs from game detail for {name}")
        if played:
            total_fp = sum(float(row["custom_fp"]) for row in played)
            total_min = sum(float(row["minutes"]) for row in played)
            require(close(player["preseason_actual_fp_total"], total_fp), f"actual FP total mismatch for {name}")
            require(close(player["preseason_minutes"], total_min, 0.02), f"minutes total mismatch for {name}")
            if player["preseason_complete_stats"].casefold() == "true":
                require(close(player["preseason_actual_fpg"], total_fp / len(played)), f"FP/G mismatch for {name}")
                require(close(player["preseason_actual_fp36"], total_fp / total_min * 36), f"FP/36 mismatch for {name}")
        else:
            require(player["preseason_actual_fpg"] == "", f"no-appearance player given actual FP/G: {name}")

    team_by_id = {row["team_id"]: row for row in team_rows}
    for team in roster["teams"]:
        entries = [player_by_name[name] for name in team["players"]]
        observed = sorted(
            [p for p in entries if numeric(p["preseason_actual_fpg"]) is not None],
            key=lambda p: float(p["preseason_actual_fpg"]), reverse=True,
        )[:10]
        projections = sorted(
            [p for p in entries if numeric(p["projected_expected_fpg_per_team_game"]) is not None],
            key=lambda p: float(p["projected_expected_fpg_per_team_game"]), reverse=True,
        )[:10]
        row = team_by_id[team["team_id"]]
        require(int(row["roster_count"]) == 13, f"team count mismatch for {team['team_id']}")
        require(int(row["actual_top10_sample_count"]) == len(observed), f"actual sample count mismatch for {team['team_id']}")
        if len(observed) == 10:
            require(close(row["actual_top10_fp_per_game"], sum(float(p["preseason_actual_fpg"]) for p in observed)), f"actual team sum mismatch for {team['team_id']}")
        else:
            require(row["actual_rank"] == "", f"team with insufficient sample received actual rank: {team['team_id']}")
        if len(projections) == 10:
            require(close(row["projected_top10_expected_fp_per_team_game"], sum(float(p["projected_expected_fpg_per_team_game"]) for p in projections)), f"projection team sum mismatch for {team['team_id']}")
        else:
            require(row["projected_rank"] == "", f"team without 10 projections received rank: {team['team_id']}")

    validations = read_json(report / "2026-10-14-preseason-validation.json")
    source_qa = validations["source_qa"]
    require(source_qa["canonical_preseason_stat_source"] == "NBA Stats boxscoretraditionalv3", "unexpected canonical preseason source")
    differences = source_qa["boxscore_playergamelog_differences"]
    require(len(differences) == source_qa["boxscore_playergamelog_difference_count"], "secondary feed difference count is inconsistent")
    require(source_qa["incomplete_observations"] == 0, "one or more played roster observations have missing scored fields")
    require(source_qa["status"] == "ready_for_independent_validation", "source/model QA is not ready")
    history_qa = validations["history_qa"]
    require(not history_qa["dash_mismatches"], f"historical baseline mismatches: {len(history_qa['dash_mismatches'])}")
    require(history_qa["espn_special_stat_suffix_alias_matches_2025_26"] == 1, "expected one unique 2025-26 ESPN suffix alias")
    require(history_qa["espn_special_stat_suffix_alias_matches_2024_25"] == 1, "expected one unique 2024-25 ESPN suffix alias")
    require(history_qa["espn_special_stat_ambiguous_suffix_matches_2025_26"] == 0, "ambiguous 2025-26 ESPN suffix alias was accepted")
    require(history_qa["espn_special_stat_ambiguous_suffix_matches_2024_25"] == 0, "ambiguous 2024-25 ESPN suffix alias was accepted")
    require(history_qa["league_prior_players"] == 452, "availability prior population does not include all 452 eligible 2025-26 histories")
    require(abs(float(history_qa["league_prior_availability"]) - 0.6888355277) < 1e-9, "availability prior mean differs from the complete eligible population")
    portis = player_by_name.get("Bobby Portis Jr.")
    if portis:
        require(portis["baseline_season"] == "2025-26", "Bobby Portis Jr. did not resolve the ESPN suffix alias to his 2025-26 baseline")
        require(int(portis["baseline_games"]) == 67, "Bobby Portis Jr. historical GP differs from the NBA 2025-26 log")
    require(source_qa["current_nba_roster_matched"] == 208, "not all 208 fantasy players matched NBA identities")
    require(source_qa["roster_player_count"] == 208, "source QA player count differs from roster")
    require(source_qa["actual_rankable_teams"] == 16, "actual rankings are not rankable for all 16 teams")
    require(source_qa["projected_rankable_teams"] == 16, "projection rankings are not rankable for all 16 teams")
    actual_ranks = sorted(int(row["actual_rank"]) for row in team_rows if row["actual_rank"])
    projected_ranks = sorted(int(row["projected_rank"]) for row in team_rows if row["projected_rank"])
    require(actual_ranks == list(range(1, 17)), "actual ranks are not a complete 1-16 ordering")
    require(projected_ranks == list(range(1, 17)), "projected ranks are not a complete 1-16 ordering")

    ranking_report = (report / "2026-10-14-preseason-rankings.md").read_text(encoding="utf-8")
    require(f"differs in {len(differences)} stat/minute cells" in ranking_report, "secondary source discrepancy is not disclosed")
    if not args.allow_draft:
        require("Official ranking — post-validation" in ranking_report, "official report label is missing")
        signoff_path = report / "2026-10-14-independent-validation.json"
        require(signoff_path.is_file(), "independent review signoff is missing")
        signoff = read_json(signoff_path)
        require(signoff.get("passed") is True, "independent review did not pass")
        sample_count = signoff.get("sample_player_games", signoff.get("review_scope", {}).get("sample_player_games", 0))
        require(int(sample_count) >= 10, "independent sample is too small")
    print(
        "PASS: 16 teams / 208 unique players; "
        f"{len(manifest_final_ids)} final games / {2 * len(manifest_final_ids)} team scores reconciled; {len(game_rows)} rostered box-score rows "
        f"({status_counts['played']} played, {status_counts['did_not_play']} DNP); "
        "all custom scores, aggregates, provenance, and complete team ranks reconcile."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
