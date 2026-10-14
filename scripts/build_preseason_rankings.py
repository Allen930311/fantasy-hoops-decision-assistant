#!/usr/bin/env python3
"""Build reproducible 2026-27 preseason actual and regular-season rankings."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCORING_TO_FIELD = {
    "PTS": "PTS",
    "3PTM": "FG3M",
    "FTA": "FTA",
    "OREB": "OREB",
    "DREB": "DREB",
    "AST": "AST",
    "STL": "STL",
    "BLK": "BLK",
    "TO": "TOV",
    "PF": "PF",
    "TECH": "TECH",
    "EJCT": "EJCT",
    "FF": "FF",
    "DD": "DD",
    "TD": "TD",
}
ACTUAL_FIELDS = tuple(SCORING_TO_FIELD)
PGL_BASE_FIELDS = ("PTS", "FG3M", "FTA", "OREB", "DREB", "AST", "STL", "BLK", "TOV", "PF")
PGL_COMPARE_FIELDS = {
    "PTS": "PTS",
    "3PTM": "FG3M",
    "FTA": "FTA",
    "OREB": "OREB",
    "DREB": "DREB",
    "AST": "AST",
    "STL": "STL",
    "BLK": "BLK",
    "TO": "TOV",
    "PF": "PF",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().replace("&", " and ").replace("'", "").replace(".", "")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def normalize_name_without_suffix(value: str) -> str:
    tokens = normalize_name(value).split()
    if tokens and tokens[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        tokens.pop()
    return " ".join(tokens)


def number(value: Any) -> float | None:
    if value is None or value == "" or value == "-":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def result_set(payload: dict[str, Any], name: str | None = None) -> dict[str, Any]:
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    for item in sets:
        if name is None or item.get("name") == name:
            return item
    if sets:
        return sets[0]
    raise ValueError(f"No result set found (requested {name!r})")


def rows_as_dicts(payload: dict[str, Any], set_name: str | None = None) -> list[dict[str, Any]]:
    data = result_set(payload, set_name)
    return [dict(zip(data["headers"], row)) for row in data["rowSet"]]


def parse_minutes(value: Any) -> float | None:
    if value is None or value == "" or value == "-":
        return None
    text = str(value)
    if ":" in text:
        minutes, seconds = text.split(":", 1)
        try:
            return int(minutes) + int(seconds) / 60.0
        except ValueError:
            return None
    parsed = number(text)
    return parsed


def custom_double_and_triple(stats: dict[str, Any]) -> tuple[int | None, int | None]:
    categories = ["PTS", "REB", "AST", "STL", "BLK"]
    if any(number(stats.get(field)) is None for field in categories):
        return None, None
    count = sum((number(stats.get(field)) or 0) >= 10 for field in categories)
    return int(count >= 2), int(count >= 3)


def weighted_fp(stats: dict[str, Any], weights: dict[str, float]) -> float | None:
    if any(number(stats.get(field)) is None for field in ACTUAL_FIELDS):
        return None
    return sum((number(stats[field]) or 0.0) * float(weights[field]) for field in ACTUAL_FIELDS)


def mean_or(values: list[float], fallback: float) -> float:
    return statistics.mean(values) if values else fallback


def median_or(values: list[float], fallback: float) -> float:
    return statistics.median(values) if values else fallback


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_espn_special_data(snapshot: Path, season_label: str) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    special: dict[str, dict[str, float]] = {}
    metadata: dict[str, Any] = {}
    for page in (1, 2):
        payload = load_json(snapshot / f"espn/special_stats_{season_label}_page{page}.json")
        category_schema = {item["name"]: item for item in payload.get("categories", [])}
        for athlete_row in payload.get("athletes", []):
            athlete = athlete_row.get("athlete", {})
            display_name = athlete.get("displayName", "")
            name_key = normalize_name(display_name)
            if not name_key:
                continue
            values: dict[str, float] = {}
            for category in athlete_row.get("categories", []):
                schema = category_schema.get(category.get("name"), {})
                names = schema.get("names", [])
                data_values = category.get("values", [])
                for stat_name, stat_value in zip(names, data_values):
                    parsed = number(stat_value)
                    if parsed is not None:
                        values[stat_name] = parsed
            if name_key in special:
                raise ValueError(f"Duplicate ESPN athlete identity: {display_name}")
            special[name_key] = values
            metadata[name_key] = {
                "display_name": display_name,
                "espn_id": athlete.get("id"),
                "games_played": values.get("gamesPlayed"),
            }
    return special, metadata


def aggregate_player_logs(payload: dict[str, Any], set_name: str = "PlayerGameLogs") -> dict[int, dict[str, Any]]:
    rows = rows_as_dicts(payload, set_name)
    players: dict[int, dict[str, Any]] = {}
    seen: set[tuple[int, str]] = set()
    for row in rows:
        player_id = int(row["PLAYER_ID"])
        game_id = str(row["GAME_ID"])
        unique_key = (player_id, game_id)
        if unique_key in seen:
            continue
        seen.add(unique_key)
        minutes = number(row.get("MIN"))
        if minutes is None:
            continue
        item = players.setdefault(
            player_id,
            {
                "player_id": player_id,
                "player_name": row.get("PLAYER_NAME", ""),
                "games": set(),
                "minutes": 0.0,
                "totals": defaultdict(float),
                "game_rows": [],
            },
        )
        item["games"].add(game_id)
        item["minutes"] += minutes
        double, triple = custom_double_and_triple(
            {
                "PTS": row.get("PTS"),
                "REB": row.get("REB"),
                "AST": row.get("AST"),
                "STL": row.get("STL"),
                "BLK": row.get("BLK"),
            }
        )
        stat_lookup = {
            "PTS": "PTS",
            "3PTM": "FG3M",
            "FTA": "FTA",
            "OREB": "OREB",
            "DREB": "DREB",
            "AST": "AST",
            "STL": "STL",
            "BLK": "BLK",
            "TO": "TOV",
            "PF": "PF",
            "DD": None,
            "TD": None,
        }
        for output_field, source_field in stat_lookup.items():
            value = double if output_field == "DD" else triple if output_field == "TD" else number(row.get(source_field))
            if value is not None:
                item["totals"][output_field] += value
        item["game_rows"].append(row)
    return players


def parse_espn_special_for_player(
    special: dict[str, dict[str, float]],
    name: str,
    games_played: int,
) -> dict[str, float] | None:
    values, _match_kind = lookup_espn_special_name(special, name)
    if not values:
        return None
    reported_gp = values.get("gamesPlayed")
    if reported_gp is not None and abs(reported_gp - games_played) > 1:
        # The ESPN and NBA feeds occasionally differ on a player's season total;
        # the exact mismatch remains visible in player provenance and validation.
        return None
    fields = {
        "TECH": values.get("technicalFouls"),
        "FF": values.get("flagrantFouls"),
        "EJCT": values.get("ejections"),
    }
    if any(value is None for value in fields.values()):
        return None
    return {key: float(value) for key, value in fields.items() if value is not None}


def lookup_espn_special_name(
    special: dict[str, dict[str, float]],
    name: str,
) -> tuple[dict[str, float] | None, str]:
    exact_key = normalize_name(name)
    if exact_key in special:
        return special[exact_key], "exact"
    suffix_key = normalize_name_without_suffix(name)
    matches = [
        values
        for candidate, values in special.items()
        if normalize_name_without_suffix(candidate) == suffix_key
    ]
    if len(matches) == 1:
        return matches[0], "unique_suffix_alias"
    return None, "ambiguous_suffix_alias" if matches else "missing"


def build_history(
    snapshot: Path,
    season_label: str,
    special: dict[str, dict[str, float]],
) -> dict[int, dict[str, Any]]:
    payload = load_json(snapshot / f"nba/playergamelogs_{season_label}_regular.json")
    raw = aggregate_player_logs(payload)
    for player_id, item in raw.items():
        gp = len(item["games"])
        special_stats = parse_espn_special_for_player(special, item["player_name"], gp)
        item["gp"] = gp
        item["special_stats"] = special_stats
        item["complete"] = special_stats is not None and gp > 0 and item["minutes"] > 0
        if special_stats is not None:
            for field, value in special_stats.items():
                item["totals"][field] = value
        for field in ACTUAL_FIELDS:
            item["totals"].setdefault(field, None)
        fp = weighted_fp(item["totals"], {field: 1.0 for field in ACTUAL_FIELDS})
        # weighted_fp above checks only presence; this temporary score is replaced
        # in build_players using the owner-defined league weights.
        item["unweighted_total"] = fp
        item["name_key"] = normalize_name(item["player_name"])
    return raw


def get_player_positions(snapshot: Path) -> dict[int, str]:
    positions: dict[int, str] = {}
    for path in sorted((snapshot / "nba/team_rosters").glob("*.json")):
        payload = load_json(path)
        result_sets = payload.get("resultSets") or payload.get("resultSet") or []
        if isinstance(result_sets, dict):
            result_sets = [result_sets]
        for data in result_sets:
            headers = data.get("headers", [])
            if "PLAYER_ID" not in headers:
                continue
            if "POSITION" not in headers:
                continue
            id_index = headers.index("PLAYER_ID")
            pos_index = headers.index("POSITION")
            for row in data.get("rowSet", []):
                positions[int(row[id_index])] = str(row[pos_index] or "")
    return positions


def simple_position(position: str) -> str:
    text = position.strip().upper()
    for code, label in (("G", "G"), ("F", "F"), ("C", "C")):
        if text.startswith(code):
            return label
    return "UNK"


def parse_special_events(play_by_play: dict[str, Any]) -> tuple[dict[int, dict[str, int]], bool]:
    game = play_by_play.get("game", {})
    actions = game.get("actions")
    if not isinstance(actions, list):
        return {}, False
    stats: dict[int, dict[str, int]] = defaultdict(lambda: {"TECH": 0, "FF": 0, "EJCT": 0})
    explicit_ejections: set[int] = set()
    technicals: dict[int, int] = defaultdict(int)
    for action in actions:
        player_id = int(action.get("personId") or 0)
        if player_id <= 0:
            continue
        action_type = str(action.get("actionType", "")).casefold()
        subtype = str(action.get("subType", "")).casefold()
        description = str(action.get("description", "")).casefold()
        if "eject" in action_type or "eject" in subtype or "eject" in description:
            explicit_ejections.add(player_id)
        if action_type != "foul":
            continue
        # NBA Stats represents these as Foul actions, including Double Technical,
        # Hanging Technical, and flopping's "Tech Foul". Do not count the
        # separate Free Throw / Free Throw Technical action as another foul.
        if (
            "technical" in subtype
            or "technical foul" in description
            or "tech foul" in description
        ):
            stats[player_id]["TECH"] += 1
            technicals[player_id] += 1
        if "flagrant" in subtype or "flagrant foul" in description:
            stats[player_id]["FF"] += 1
            if "flagrant 2" in subtype or "flagrant foul 2" in description:
                explicit_ejections.add(player_id)
    for player_id in set(stats) | explicit_ejections:
        if player_id in explicit_ejections or technicals.get(player_id, 0) >= 2:
            stats[player_id]["EJCT"] = 1
    return dict(stats), True


def load_preseason(
    snapshot: Path,
    roster_map: dict[int, dict[str, Any]],
    weights: dict[str, float],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    manifest = load_json(snapshot / "source_manifest.json")
    completed_ids = set(map(str, manifest.get("completed_game_ids", [])))
    nba_names = {
        item["payload_file"]: item.get("retrieved_at_utc")
        for item in manifest.get("sources", [])
    }
    game_counts: dict[str, int] = defaultdict(int)
    game_records: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "games": set(),
            "played_game_ids": set(),
            "minutes": 0.0,
            "totals": defaultdict(float),
            "missing_fields": set(),
            "dnp_reasons": [],
            "injury_dnp_count": 0,
            "boxscore_rows": 0,
            "source_game_ids": set(),
        }
    )
    game_box_rows: dict[tuple[str, int], dict[str, Any]] = {}
    game_detail_rows: list[dict[str, Any]] = []
    for game_id in sorted(completed_ids):
        box_path = snapshot / f"nba/boxscores/{game_id}.json"
        pbp_path = snapshot / f"nba/playbyplay/{game_id}.json"
        box_payload = load_json(box_path)
        pbp_payload = load_json(pbp_path)
        box = box_payload.get("boxScoreTraditional", {})
        special_by_player, pbp_complete = parse_special_events(pbp_payload)
        for side in ("homeTeam", "awayTeam"):
            team = box.get(side, {})
            team_code = str(team.get("teamTricode", ""))
            if team_code:
                game_counts[team_code] += 1
            for player in team.get("players", []):
                player_id = int(player.get("personId") or 0)
                if player_id not in roster_map:
                    continue
                record = game_records[player_id]
                record["games"].add(game_id)
                record["source_game_ids"].add(game_id)
                comment = str(player.get("comment", "") or "").strip()
                raw_stats = player.get("statistics") or {}
                minutes = parse_minutes(raw_stats.get("minutes"))
                if minutes is None:
                    if comment:
                        record["dnp_reasons"].append({"game_id": game_id, "reason": comment})
                        if re.search(r"injury|illness", comment, flags=re.I):
                            record["injury_dnp_count"] += 1
                    else:
                        record["missing_fields"].add(f"{game_id}:minutes")
                    game_detail_rows.append({
                        "game_id": game_id, "player_id": player_id,
                        "player_name": roster_map[player_id]["player_name"],
                        "nba_team": team_code, "status": "did_not_play" if comment else "data_missing_minutes",
                        "minutes": None, "dnp_comment": comment,
                        **{field: None for field in ACTUAL_FIELDS}, "custom_fp": None,
                    })
                    continue
                if minutes <= 0:
                    if comment:
                        record["dnp_reasons"].append({"game_id": game_id, "reason": comment})
                        if re.search(r"injury|illness", comment, flags=re.I):
                            record["injury_dnp_count"] += 1
                    game_detail_rows.append({
                        "game_id": game_id, "player_id": player_id,
                        "player_name": roster_map[player_id]["player_name"],
                        "nba_team": team_code, "status": "did_not_play",
                        "minutes": 0, "dnp_comment": comment,
                        **{field: None for field in ACTUAL_FIELDS}, "custom_fp": None,
                    })
                    continue

                mapped = {
                    "PTS": raw_stats.get("points"),
                    "3PTM": raw_stats.get("threePointersMade"),
                    "FTA": raw_stats.get("freeThrowsAttempted"),
                    "OREB": raw_stats.get("reboundsOffensive"),
                    "DREB": raw_stats.get("reboundsDefensive"),
                    "AST": raw_stats.get("assists"),
                    "STL": raw_stats.get("steals"),
                    "BLK": raw_stats.get("blocks"),
                    "TO": raw_stats.get("turnovers"),
                    "PF": raw_stats.get("foulsPersonal"),
                    "REB": raw_stats.get("reboundsTotal"),
                }
                double, triple = custom_double_and_triple(mapped)
                mapped["DD"], mapped["TD"] = double, triple
                special = special_by_player.get(player_id, {"TECH": 0, "FF": 0, "EJCT": 0})
                for field in ("TECH", "FF", "EJCT"):
                    mapped[field] = special[field] if pbp_complete else None
                record["played_game_ids"].add(game_id)
                record["minutes"] += minutes
                record["boxscore_rows"] += 1
                record["totals"]["GP"] += 1
                for field in ACTUAL_FIELDS:
                    value = number(mapped.get(field))
                    if value is None:
                        record["missing_fields"].add(f"{game_id}:{field}")
                    else:
                        record["totals"][field] += value
                mapped["MIN"] = minutes
                mapped["GAME_ID"] = game_id
                mapped["NBA_TEAM"] = team_code
                mapped["PLAYER_ID"] = player_id
                mapped["COMMENT"] = comment
                game_box_rows[(game_id, player_id)] = mapped
                custom_fp = weighted_fp(mapped, weights)
                game_detail_rows.append({
                    "game_id": game_id, "player_id": player_id,
                    "player_name": roster_map[player_id]["player_name"],
                    "nba_team": team_code, "status": "played", "minutes": round(minutes, 3),
                    "dnp_comment": comment,
                    **{field: mapped.get(field) for field in ACTUAL_FIELDS},
                    "custom_fp": round(custom_fp, 4) if custom_fp is not None else None,
                })

    # Independent official endpoint check: per-game logs must cover the same
    # completed games and agree with boxscore arithmetic for every appearance.
    pgl_payload = load_json(snapshot / "nba/playergamelogs_2026-27_preseason.json")
    pgl_rows = rows_as_dicts(pgl_payload, "PlayerGameLogs")
    pgl_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for row in pgl_rows:
        game_id = str(row.get("GAME_ID", ""))
        player_id = int(row["PLAYER_ID"])
        if game_id in completed_ids and player_id in roster_map:
            pgl_by_key[(game_id, player_id)] = row
    mismatches: list[dict[str, Any]] = []
    dd_td_differences: list[dict[str, Any]] = []
    for key, box_row in game_box_rows.items():
        pgl_row = pgl_by_key.get(key)
        if not pgl_row:
            mismatches.append({"game_id": key[0], "player_id": key[1], "field": "missing_playergamelog"})
            continue
        for box_field, pgl_field in PGL_COMPARE_FIELDS.items():
            expected = number(box_row.get(box_field))
            actual = number(pgl_row.get(pgl_field))
            if expected is None or actual is None or abs(expected - actual) > 1e-6:
                mismatches.append(
                    {
                        "game_id": key[0],
                        "player_id": key[1],
                        "field": box_field,
                        "boxscore": expected,
                        "playergamelog": actual,
                    }
                )
        expected_minutes = number(box_row.get("MIN"))
        actual_minutes = number(pgl_row.get("MIN"))
        if expected_minutes is None or actual_minutes is None or abs(expected_minutes - actual_minutes) > 0.06:
            mismatches.append(
                {
                    "game_id": key[0],
                    "player_id": key[1],
                    "field": "MIN",
                    "boxscore": expected_minutes,
                    "playergamelog": actual_minutes,
                }
            )
        for category, expected in (("DD", box_row.get("DD")), ("TD", box_row.get("TD"))):
            pgl_field = "DD2" if category == "DD" else "TD3"
            actual = number(pgl_row.get(pgl_field))
            if actual is not None and expected is not None and abs(expected - actual) > 1e-6:
                dd_td_differences.append(
                    {
                        "game_id": key[0],
                        "player_id": key[1],
                        "field": category,
                        "boxscore_derived": expected,
                        "playergamelog": actual,
                    }
                )
    for key in pgl_by_key:
        if key not in game_box_rows:
            mismatches.append({"game_id": key[0], "player_id": key[1], "field": "missing_boxscore_player"})

    return game_records, {
        "completed_game_ids": sorted(completed_ids),
        "completed_game_count": len(completed_ids),
        "nba_team_completed_game_counts": dict(sorted(game_counts.items())),
        "player_game_rows": len(game_box_rows),
        "rostered_boxscore_rows_including_dnp": len(game_detail_rows),
        "playergamelog_rows_for_completed_games": len(pgl_by_key),
        "boxscore_playergamelog_differences": mismatches,
        "boxscore_playergamelog_difference_count": len(mismatches),
        "canonical_preseason_stat_source": "NBA Stats boxscoretraditionalv3",
        "nba_dd_td_definition_differences": dd_td_differences,
    }, sorted(game_detail_rows, key=lambda row: (row["game_id"], row["player_id"]))


def add_current_rosters(snapshot: Path, fantasy_rosters: dict[str, Any]) -> list[dict[str, Any]]:
    nba_payload = load_json(snapshot / "nba/commonallplayers_2026-27.json")
    nba_rows = rows_as_dicts(nba_payload)
    by_name: dict[str, dict[str, Any]] = {}
    for row in nba_rows:
        name_key = normalize_name(str(row.get("DISPLAY_FIRST_LAST", "")))
        if name_key:
            if name_key in by_name:
                raise ValueError(f"Duplicate NBA roster identity: {row.get('DISPLAY_FIRST_LAST')}")
            by_name[name_key] = row
    positions = get_player_positions(snapshot)
    players: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for team in fantasy_rosters.get("teams", []):
        for roster_order, player_name in enumerate(team["players"], start=1):
            row = by_name.get(normalize_name(player_name))
            if not row:
                players.append(
                    {
                        "fantasy_team_id": team["team_id"],
                        "fantasy_team_label": team.get("label", team["team_id"]),
                        "is_owner": team.get("is_owner") is True,
                        "roster_order": roster_order,
                        "player_name": player_name,
                        "nba_match_status": "unmatched",
                        "player_id": None,
                        "nba_team": "",
                        "nba_position": "UNK",
                        "position_group": "UNK",
                    }
                )
                continue
            player_id = int(row["PERSON_ID"])
            if player_id in seen_ids:
                raise ValueError(f"NBA player ID appears more than once in fantasy rosters: {player_id}")
            seen_ids.add(player_id)
            position = positions.get(player_id, "")
            players.append(
                {
                    "fantasy_team_id": team["team_id"],
                    "fantasy_team_label": team.get("label", team["team_id"]),
                    "is_owner": team.get("is_owner") is True,
                    "roster_order": roster_order,
                    "player_name": player_name,
                    "nba_match_status": "matched",
                    "player_id": player_id,
                    "nba_display_name": row.get("DISPLAY_FIRST_LAST", ""),
                    "nba_team": row.get("TEAM_ABBREVIATION", ""),
                    "nba_team_id": row.get("TEAM_ID"),
                    "nba_roster_status": row.get("ROSTERSTATUS"),
                    "nba_position": position,
                    "position_group": simple_position(position),
                    "from_year": row.get("FROM_YEAR"),
                }
            )
    return players


def baseline_check(snapshot: Path, baseline: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    payload = load_json(snapshot / "nba/leaguedashplayerstats_2025-26_regular.json")
    rows = rows_as_dicts(payload, "LeagueDashPlayerStats")
    by_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_id[int(row["PLAYER_ID"])].append(row)
    mismatches: list[dict[str, Any]] = []
    for player_id, history in baseline.items():
        if player_id not in by_id:
            continue
        # NBA's league dash may contain one row for each traded team plus a
        # combined row. Use the row whose GP is the largest as a per-game check.
        dash = max(by_id[player_id], key=lambda row: number(row.get("GP")) or 0)
        gp = number(dash.get("GP")) or 0
        if gp <= 0:
            continue
        item = history
        for source_field, pgl_field in {
            "PTS": "PTS",
            "FG3M": "3PTM",
            "FTA": "FTA",
            "OREB": "OREB",
            "DREB": "DREB",
            "AST": "AST",
            "STL": "STL",
            "BLK": "BLK",
            "TOV": "TO",
            "PF": "PF",
        }.items():
            historical_total = number(item["totals"].get(SCORING_TO_FIELD.get(source_field, source_field)))
            official_rate = number(dash.get(source_field))
            if historical_total is None or official_rate is None:
                continue
            computed_rate = historical_total / item["gp"]
            if abs(computed_rate - official_rate) > 0.16:
                mismatches.append(
                    {
                        "player_id": player_id,
                        "field": source_field,
                        "computed_from_gamelog": round(computed_rate, 4),
                        "league_dash_per_game": official_rate,
                        "tolerance": 0.16,
                    }
                )
    return mismatches


def prepare_history(
    snapshot: Path,
    roster_players: list[dict[str, Any]],
    weights: dict[str, float],
) -> tuple[dict[int, dict[str, Any]], dict[str, float], dict[str, Any]]:
    current_special, current_meta = read_espn_special_data(snapshot, "2025-26")
    prior_special, prior_meta = read_espn_special_data(snapshot, "2024-25")
    histories: dict[str, dict[int, dict[str, Any]]] = {
        "2025-26": build_history(snapshot, "2025-26", current_special),
        "2024-25": build_history(snapshot, "2024-25", prior_special),
    }
    # A 2025-26 NBA roster row with FROM_YEAR=2025 identifies a rookie in the
    # prior season. Use the median rookie rate as the projection prior for the
    # 2026 draft class, rather than treating no NBA history as zero.
    rookie_roster_payload = load_json(snapshot / "nba/commonallplayers_2025-26.json")
    rookie_rows = rows_as_dicts(rookie_roster_payload)
    rookie_ids = {
        int(row["PERSON_ID"])
        for row in rookie_rows
        if str(row.get("FROM_YEAR", "")) == "2025"
    }
    rookie_histories = [
        item
        for player_id, item in histories["2025-26"].items()
        if player_id in rookie_ids and item["gp"] >= 10 and item["complete"] and item["minutes"] > 0
    ]
    league_histories = [
        item
        for item in histories["2025-26"].values()
        if item["gp"] >= 20 and item["complete"] and item["minutes"] > 0
    ]
    rookie_pool = rookie_histories if len(rookie_histories) >= 8 else league_histories
    rookie_rates = [
        (weighted_fp(item["totals"], weights) or 0.0) / item["minutes"] * 36.0
        for item in rookie_pool
    ]
    rookie_mpg = [item["minutes"] / item["gp"] for item in rookie_pool]
    rookie_availability = [min(1.0, item["gp"] / 82.0) for item in rookie_pool]
    league_availability = [min(1.0, item["gp"] / 82.0) for item in league_histories]
    priors = {
        "rookie_fp36": median_or(rookie_rates, 25.0),
        "rookie_mpg": median_or(rookie_mpg, 18.0),
        "rookie_availability": median_or(rookie_availability, 0.72),
        "league_availability": mean_or(league_availability, 0.72),
    }

    current_rows = rows_as_dicts(load_json(snapshot / "nba/commonallplayers_2026-27.json"))
    current_rookie_ids = {
        int(row["PERSON_ID"])
        for row in current_rows
        if str(row.get("FROM_YEAR", "")) == "2026"
    }
    player_history: dict[int, dict[str, Any]] = {}
    for player in roster_players:
        player_id = player.get("player_id")
        if player_id is None:
            continue
        recent = histories["2025-26"].get(player_id)
        recent_gp = int(recent["gp"]) if recent else 0
        if player_id in current_rookie_ids:
            availability = priors["rookie_availability"]
            availability_source = "2025-26 rookie cohort prior"
        else:
            availability = (recent_gp + 20.0 * priors["league_availability"]) / (82.0 + 20.0)
            availability_source = "2025-26 GP/82 shrunk toward league mean"
        selected: dict[str, Any] | None = None
        selected_season = ""
        for season in ("2025-26", "2024-25"):
            candidate = histories[season].get(player_id)
            if candidate and candidate["gp"] > 0 and candidate["complete"]:
                selected = candidate
                selected_season = season
                break
        if selected:
            totals = dict(selected["totals"])
            historical_fp_total = weighted_fp(totals, weights)
            mpg = selected["minutes"] / selected["gp"] if selected["gp"] else None
            fp36 = historical_fp_total / selected["minutes"] * 36.0 if selected["minutes"] else None
            player_history[player_id] = {
                "source_season": selected_season,
                "games": selected["gp"],
                "minutes": selected["minutes"],
                "mpg": mpg,
                "fp_total": historical_fp_total,
                "fpg": historical_fp_total / selected["gp"] if selected["gp"] else None,
                "fp36": fp36,
                "availability": max(0.0, min(1.0, availability)),
                "availability_games_2025_26": recent_gp,
                "availability_source": availability_source,
                "complete": True,
                "source_player_name": selected["player_name"],
            }
        else:
            source = "2025-26 rookie cohort prior" if player_id in current_rookie_ids else "projection_prior"
            player_history[player_id] = {
                "source_season": source,
                "games": 0,
                "minutes": 0.0,
                "mpg": priors["rookie_mpg"],
                "fp_total": None,
                "fpg": None,
                "fp36": priors["rookie_fp36"],
                "availability": max(0.0, min(1.0, availability)),
                "availability_games_2025_26": recent_gp,
                "availability_source": availability_source,
                "complete": False,
                "source_player_name": "",
            }
    dash_mismatches = baseline_check(snapshot, histories["2025-26"])
    metadata = {
        "rookie_prior_players": len(rookie_histories),
        "rookie_prior_source": "2025-26 rookie cohort median" if len(rookie_histories) >= 8 else "2025-26 league median fallback",
        "current_rookie_count_in_fantasy_rosters": sum(1 for p in roster_players if p.get("player_id") in current_rookie_ids),
        "espn_special_stat_name_matches_2025_26": sum(
            1 for player in roster_players
            if lookup_espn_special_name(current_special, player["player_name"])[0] is not None
        ),
        "espn_special_stat_name_matches_2024_25": sum(
            1 for player in roster_players
            if lookup_espn_special_name(prior_special, player["player_name"])[0] is not None
        ),
        "espn_special_stat_suffix_alias_matches_2025_26": sum(
            1 for player in roster_players
            if lookup_espn_special_name(current_special, player["player_name"])[1] == "unique_suffix_alias"
        ),
        "espn_special_stat_suffix_alias_matches_2024_25": sum(
            1 for player in roster_players
            if lookup_espn_special_name(prior_special, player["player_name"])[1] == "unique_suffix_alias"
        ),
        "espn_special_stat_ambiguous_suffix_matches_2025_26": sum(
            1 for player in roster_players
            if lookup_espn_special_name(current_special, player["player_name"])[1] == "ambiguous_suffix_alias"
        ),
        "espn_special_stat_ambiguous_suffix_matches_2024_25": sum(
            1 for player in roster_players
            if lookup_espn_special_name(prior_special, player["player_name"])[1] == "ambiguous_suffix_alias"
        ),
        "espn_special_stat_records_2025_26": len(current_meta),
        "espn_special_stat_records_2024_25": len(prior_meta),
        "dash_mismatches": dash_mismatches,
        "rookie_prior_fp36": priors["rookie_fp36"],
        "rookie_prior_mpg": priors["rookie_mpg"],
        "rookie_prior_availability": priors["rookie_availability"],
        "league_prior_availability": priors["league_availability"],
        "league_prior_players": len(league_histories),
    }
    return player_history, priors, metadata


def player_status(player: dict[str, Any], observation: dict[str, Any], team_game_count: int) -> str:
    if observation.get("played_game_ids"):
        return "played"
    if observation.get("dnp_reasons"):
        return "did_not_play"
    if player.get("nba_match_status") != "matched":
        return "data_missing_unmatched_roster_player"
    if team_game_count == 0:
        return "team_has_no_completed_game"
    return "data_missing_not_listed_in_boxscore"


def rank_teams(
    players: list[dict[str, Any]],
    observations: dict[int, dict[str, Any]],
    history: dict[int, dict[str, Any]],
    weights: dict[str, float],
    team_game_counts: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    modeled: list[dict[str, Any]] = []
    for player in players:
        player_id = player.get("player_id")
        observation = observations.get(player_id, {}) if player_id is not None else {}
        hist = history.get(player_id, {}) if player_id is not None else {}
        total = {field: observation.get("totals", {}).get(field) for field in ACTUAL_FIELDS}
        gp = len(observation.get("played_game_ids", set()))
        actual_complete = gp > 0 and not observation.get("missing_fields") and all(number(total.get(field)) is not None for field in ACTUAL_FIELDS)
        actual_fp_total = weighted_fp(total, weights) if actual_complete else None
        actual_fpg = actual_fp_total / gp if actual_fp_total is not None and gp else None
        actual_fp36 = actual_fp_total / observation["minutes"] * 36.0 if actual_fp_total is not None and observation.get("minutes", 0) > 0 else None
        hist_fp36 = hist.get("fp36")
        hist_mpg = hist.get("mpg")
        pre_minutes = float(observation.get("minutes", 0.0))
        pre_mpg = pre_minutes / gp if gp else None
        pre_fp36 = actual_fp_total / pre_minutes * 36.0 if actual_fp_total is not None and pre_minutes > 0 else None
        if hist.get("complete") and hist.get("games", 0) > 0:
            rate_weight = min(0.35, pre_minutes / (pre_minutes + 720.0)) if pre_fp36 is not None else 0.0
            role_weight = min(0.25, pre_minutes / (pre_minutes + 360.0)) if pre_mpg is not None else 0.0
        else:
            rate_weight = min(0.60, pre_minutes / (pre_minutes + 360.0)) if pre_fp36 is not None else 0.0
            role_weight = min(0.50, pre_minutes / (pre_minutes + 240.0)) if pre_mpg is not None else 0.0
        projected_fp36 = (
            hist_fp36 * (1.0 - rate_weight) + pre_fp36 * rate_weight
            if hist_fp36 is not None and pre_fp36 is not None
            else hist_fp36
        )
        projected_mpg = (
            hist_mpg * (1.0 - role_weight) + pre_mpg * role_weight
            if hist_mpg is not None and pre_mpg is not None
            else hist_mpg
        )
        projected_mpg = max(0.0, min(44.0, projected_mpg or 0.0))
        projected_active_fpg = projected_fp36 * projected_mpg / 36.0 if projected_fp36 is not None else None
        hist_availability = hist.get("availability")
        expected_availability = float(hist_availability if hist_availability is not None else 0.75)
        expected_availability = max(0.0, min(1.0, expected_availability))
        expected_games = expected_availability * 82.0
        expected_fpg = projected_active_fpg * expected_availability if projected_active_fpg is not None else None
        expected_fp82 = expected_fpg * 82.0 if expected_fpg is not None else None
        injury_dnp_count = int(observation.get("injury_dnp_count", 0))
        baseline_gp = int(hist.get("games", 0))
        uncertainty = 0.12 + 0.35 / math.sqrt(baseline_gp + 10.0) + 0.20 / math.sqrt(gp + 1.0)
        if not hist.get("complete"):
            uncertainty += 0.15
        if hist.get("source_season") == "2024-25":
            uncertainty += 0.08
        if hist.get("availability_games_2025_26", 0) == 0 and hist.get("availability_source", "").startswith("2025-26 GP"):
            uncertainty += 0.10
        if injury_dnp_count:
            uncertainty += min(0.15, 0.05 * injury_dnp_count)
        uncertainty = min(0.75, uncertainty)
        risk_flags: list[str] = []
        if not hist.get("complete"):
            risk_flags.append("projection_prior_only")
        if hist.get("source_season") == "2024-25":
            risk_flags.append("stale_2024_25_baseline")
        if hist.get("availability_games_2025_26", 0) == 0 and hist.get("availability_source", "").startswith("2025-26 GP"):
            risk_flags.append("no_2025_26_games_availability_risk")
        if gp == 0:
            risk_flags.append("no_completed_preseason_minutes")
        if injury_dnp_count:
            risk_flags.append("preseason_injury_or_illness_dnp")
        status = player_status(player, observation, team_game_counts.get(str(player.get("nba_team", "")), 0))
        modeled_player = {
            **player,
            "preseason_status": status,
            "preseason_games_played": gp,
            "preseason_minutes": round(pre_minutes, 2),
            "preseason_mp_per_game": round(pre_mpg, 3) if pre_mpg is not None else None,
            "preseason_actual_fp_total": round(actual_fp_total, 3) if actual_fp_total is not None else None,
            "preseason_actual_fpg": round(actual_fpg, 3) if actual_fpg is not None else None,
            "preseason_actual_fp36": round(actual_fp36, 3) if actual_fp36 is not None else None,
            "preseason_complete_stats": bool(actual_complete),
            "preseason_missing_fields": ";".join(sorted(observation.get("missing_fields", set()))),
            "preseason_dnp_count": len(observation.get("dnp_reasons", [])),
            "preseason_dnp_reasons": "; ".join(
                f"{item['game_id']}:{item['reason']}" for item in observation.get("dnp_reasons", [])
            ),
            "injury_dnp_count": injury_dnp_count,
            "baseline_season": hist.get("source_season", ""),
            "baseline_games": baseline_gp,
            "baseline_minutes": round(float(hist.get("minutes", 0.0)), 2),
            "baseline_mp_per_game": round(float(hist.get("mpg", 0.0)), 3) if hist.get("mpg") is not None else None,
            "baseline_custom_fpg": round(float(hist.get("fpg")), 3) if hist.get("fpg") is not None else None,
            "baseline_custom_fp36": round(float(hist.get("fp36")), 3) if hist.get("fp36") is not None else None,
            "role_preseason_shrink_weight": round(role_weight, 4),
            "rate_preseason_shrink_weight": round(rate_weight, 4),
            "projected_minutes_per_game": round(projected_mpg, 3),
            "projected_custom_fp36": round(projected_fp36, 3) if projected_fp36 is not None else None,
            "projected_active_fpg": round(projected_active_fpg, 3) if projected_active_fpg is not None else None,
            "historical_availability_rate": round(float(hist_availability), 4) if hist_availability is not None else None,
            "availability_baseline_games_2025_26": int(hist.get("availability_games_2025_26", 0)),
            "availability_source": hist.get("availability_source", ""),
            "projected_availability_rate": round(expected_availability, 4),
            "projected_games_of_82": round(expected_games, 2),
            "projected_expected_fpg_per_team_game": round(expected_fpg, 3) if expected_fpg is not None else None,
            "projected_expected_fp_per_82_team_games": round(expected_fp82, 3) if expected_fp82 is not None else None,
            "projection_low_fpg": round(expected_fpg * (1.0 - uncertainty), 3) if expected_fpg is not None else None,
            "projection_high_fpg": round(expected_fpg * (1.0 + uncertainty), 3) if expected_fpg is not None else None,
            "uncertainty_pct_scenario_band": round(uncertainty, 4),
            "confidence": "low" if uncertainty >= 0.48 else "medium" if uncertainty >= 0.32 else "high",
            "risk_flags": ";".join(risk_flags),
            "source_boxscore_game_ids": ";".join(sorted(observation.get("source_game_ids", set()))),
        }
        modeled.append(modeled_player)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in modeled:
        grouped[player["fantasy_team_id"]].append(player)
    teams: list[dict[str, Any]] = []
    for team_id, team_players in grouped.items():
        team_players.sort(key=lambda item: item["roster_order"])
        actual = sorted(
            [player for player in team_players if player.get("preseason_actual_fpg") is not None],
            key=lambda item: float(item["preseason_actual_fpg"]),
            reverse=True,
        )
        projected = sorted(
            [player for player in team_players if player.get("projected_expected_fp_per_82_team_games") is not None],
            key=lambda item: float(item["projected_expected_fpg_per_team_game"]),
            reverse=True,
        )
        actual_top10 = actual[:10]
        projected_top10 = projected[:10]
        actual_rankable = len(actual_top10) == 10
        projected_rankable = len(projected_top10) == 10 and len(team_players) == 13
        actual_score = sum(float(p["preseason_actual_fpg"]) for p in actual_top10) if actual_rankable else None
        projected_score = sum(float(p["projected_expected_fpg_per_team_game"]) for p in projected_top10) if projected_rankable else None
        active_score = sum(float(p["projected_active_fpg"]) for p in projected_top10) if projected_rankable else None
        low_score = sum(float(p["projection_low_fpg"]) for p in projected_top10) if projected_rankable else None
        high_score = sum(float(p["projection_high_fpg"]) for p in projected_top10) if projected_rankable else None
        teams.append(
            {
                "team_id": team_id,
                "team_label": team_players[0]["fantasy_team_label"],
                "is_owner": team_players[0]["is_owner"],
                "roster_count": len(team_players),
                "actual_players_with_sample": len(actual),
                "actual_players_without_sample": len(team_players) - len(actual),
                "actual_coverage_pct": round(len(actual) / len(team_players) * 100.0, 1) if team_players else 0.0,
                "actual_top10_fp_per_game": round(actual_score, 3) if actual_score is not None else None,
                "actual_top10_sample_count": len(actual_top10),
                "actual_rankable": actual_rankable,
                "projected_roster_coverage": len(projected),
                "projected_top10_expected_fp_per_team_game": round(projected_score, 3) if projected_score is not None else None,
                "projected_top10_active_fpg": round(active_score, 3) if active_score is not None else None,
                "projected_top10_scenario_low": round(low_score, 3) if low_score is not None else None,
                "projected_top10_scenario_high": round(high_score, 3) if high_score is not None else None,
                "projected_top13_expected_fp_per_team_game": round(
                    sum(float(p["projected_expected_fpg_per_team_game"]) for p in team_players if p["projected_expected_fpg_per_team_game"] is not None), 3
                ),
                "projected_top10_rankable": projected_rankable,
                "team_nba_game_exposure": sum(team_game_counts.get(str(p.get("nba_team", "")), 0) for p in team_players),
                "projection_low_confidence_players": sum(1 for p in team_players if p["confidence"] == "low"),
                "injury_dnp_players": sum(1 for p in team_players if p["injury_dnp_count"] > 0),
                "unmatched_nba_roster_players": sum(1 for p in team_players if p["nba_match_status"] != "matched"),
            }
        )
    actual_valid = all(team["actual_rankable"] for team in teams) and len(teams) == 16
    projected_valid = all(team["projected_top10_rankable"] for team in teams) and len(teams) == 16
    if actual_valid:
        for rank, team in enumerate(sorted(teams, key=lambda item: (-item["actual_top10_fp_per_game"], item["team_id"])), start=1):
            team["actual_rank"] = rank
    else:
        for team in teams:
            team["actual_rank"] = None
    if projected_valid:
        for rank, team in enumerate(
            sorted(teams, key=lambda item: (-item["projected_top10_expected_fp_per_team_game"], item["team_id"])),
            start=1,
        ):
            team["projected_rank"] = rank
    else:
        for team in teams:
            team["projected_rank"] = None
    teams.sort(key=lambda item: item["team_id"])
    return modeled, teams


def build_report(
    output_path: Path,
    league: dict[str, Any],
    roster: dict[str, Any],
    manifest: dict[str, Any],
    teams: list[dict[str, Any]],
    players: list[dict[str, Any]],
    source_qa: dict[str, Any],
    history_meta: dict[str, Any],
    official: bool,
) -> None:
    score_text = "\n".join(
        f"  {field}: {weight:+g}" for field, weight in league["scoring"].items()
    )
    actual_ranked = sorted(
        [team for team in teams if team.get("actual_rank") is not None],
        key=lambda team: team["actual_rank"],
    )
    projected_ranked = sorted(
        [team for team in teams if team.get("projected_rank") is not None],
        key=lambda team: team["projected_rank"],
    )
    status = "Official ranking — post-validation" if official else "Draft ranking — validation pending"
    lines = [
        "# 2026–27 Preseason Actual and Regular-Season Rankings",
        "",
        f"> **Status:** {status}",
        f"> **Data cutoff (UTC):** {manifest['cutoff_utc']}",
        f"> **Retrieved:** {manifest['collection_started_at_utc']} to {manifest['collection_finished_at_utc']}",
        f"> **Owner team:** `{league['owner_team_id']}` / 第2隊",
        "",
        "## Scope and authority",
        "",
        "Fantasy ownership comes from this season's owner-confirmed `rosters.json`; current NBA franchise and player identity come from NBA Stats API `CommonAllPlayers`. The report uses the custom weights in `league.json`. It does not use Yahoo or ESPN Fantasy Points.",
        "",
        f"- Roster: {len(roster['teams'])} teams × {league['roster_size']} players = {sum(len(team['players']) for team in roster['teams'])} names.",
        f"- Completed preseason games in the captured snapshot: {manifest['completed_game_count']}; scheduled or in-progress games by cutoff: {manifest['scheduled_or_in_progress_game_count_by_cutoff']}.",
        f"- Current NBA roster matches: {sum(1 for player in players if player['nba_match_status'] == 'matched')}/{len(players)}.",
        f"- Prior-season special-stat name matches (ESPN): {history_meta['espn_special_stat_name_matches_2025_26']}/{len(players)} for 2025–26 and {history_meta['espn_special_stat_name_matches_2024_25']}/{len(players)} for 2024–25; unique suffix-only aliases: {history_meta['espn_special_stat_suffix_alias_matches_2025_26']} and {history_meta['espn_special_stat_suffix_alias_matches_2024_25']} respectively. Ambiguous suffix aliases are not matched ({history_meta['espn_special_stat_ambiguous_suffix_matches_2025_26']} and {history_meta['espn_special_stat_ambiguous_suffix_matches_2024_25']} roster names).",
        "",
        "## Scoring and field definitions",
        "",
        "Every game is recomputed from the season's configured scoring fields:",
        "",
        "```text",
        "FP = " + " + ".join(f"{weight:g}×{field}" if weight >= 0 else f"({weight:g})×{field}" for field, weight in league["scoring"].items()),
        "```",
        "",
        "The game-level source fields are `PTS`, three-point makes, free-throw attempts, offensive and defensive rebounds, assists, steals, blocks, turnovers, personal fouls, technical fouls, ejections, flagrant fouls, double-doubles, and triple-doubles. `DD` means at least two of points/rebounds/assists/steals/blocks reach 10; `TD` means at least three. A triple-double also receives the configured `DD` bonus because `league.json` treats the two bonuses cumulatively. Technical/Flagrant/Ejection counts are taken from NBA Stats play-by-play for preseason and ESPN's per-athlete special-stat fields for the historical baseline; all other fields come from NBA Stats API. Preseason `TECH` counts each `Foul` action labeled technical, including double technicals, hanging technicals, and flopping technicals; the associated technical free-throw attempt is not counted as another foul.",
        "",
        "## 2026 preseason actual sample ranking",
        "",
        "This table ranks the sum of each fantasy roster's ten highest observed 2026 preseason custom FP/G values. Players with no completed appearance are excluded from this sample and are not assigned zero. Coverage and sample size appear beside each team.",
        "",
        "| Rank | Team | Top-10 actual FP/G | Players with sample | Coverage |",
        "|---:|---|---:|---:|---:|",
    ]
    if actual_ranked:
        for team in actual_ranked:
            lines.append(
                f"| {team['actual_rank']} | {team['team_label']} | {team['actual_top10_fp_per_game']:.1f} | {team['actual_players_with_sample']}/13 | {team['actual_coverage_pct']:.1f}% |"
            )
    else:
        lines.append("| — | No complete 16-team sample ranking | — | — | — |")
    lines.extend(
        [
            "",
            "## 2026–27 regular-season projection ranking",
            "",
            f"The primary projection score is the sum of the ten highest players' expected custom FP per fantasy-team game. Player expected FP/G equals the projected active-game rate multiplied by an availability rate. Availability starts from prior-season GP/82 and is shrunk toward the 2025–26 league mean ({history_meta['league_prior_availability']:.4f}, {history_meta['league_prior_players']} players with at least 20 GP and complete stats) using a 20-game prior. Preseason samples update per-36 production and role minutes with fixed shrinkage; they cannot dominate a full prior season. The scenario range is a heuristic sensitivity band, not a calibrated confidence interval.",
            "",
            "For a player with a full historical baseline, preseason production weight is `min(0.35, preseason_minutes / (preseason_minutes + 720))`; the projected FP/36 is the historical FP/36 and preseason FP/36 weighted by that share. Projected minutes use `min(0.25, preseason_minutes / (preseason_minutes + 360))` against historical minutes per game. Players who need a cohort-only rate prior use 2025–26 rookie-cohort medians, with preseason rate/minute weights capped at 0.60/0.50 and denominators 360/240 minutes; uncertainty is wider. Expected FP/team game is `(projected FP/36 × projected minutes / 36) × availability`; availability is `(2025–26 GP + 20 × league 2025–26 GP/82 mean) / 102`, except 2026 rookies use the rookie-cohort availability median. A player with zero 2025–26 games is explicitly risk-flagged even when the production baseline must fall back to 2024–25.",
            "",
            "The player scenario half-width is `min(0.75, 0.12 + 0.35/sqrt(baseline GP + 10) + 0.20/sqrt(preseason GP + 1) + applicable risk add-ons)`. Risk add-ons are +0.15 for a cohort-only production prior, +0.08 for a 2024–25 production baseline, +0.10 for zero 2025–26 GP, and +0.05 per explicit preseason injury/illness DNP up to +0.15. Team scenario bounds sum the selected ten players' corresponding low/high expected FP/G; they are sensitivity ranges, not probabilities.",
            "",
            "| Rank | Team | Top-10 expected FP/team game | Top-10 active FP/G | Scenario range | Low-confidence players |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )
    if projected_ranked:
        for team in projected_ranked:
            lines.append(
                f"| {team['projected_rank']} | {team['team_label']} | {team['projected_top10_expected_fp_per_team_game']:.1f} | {team['projected_top10_active_fpg']:.1f} | {team['projected_top10_scenario_low']:.1f}–{team['projected_top10_scenario_high']:.1f} | {team['projection_low_confidence_players']} |"
            )
    else:
        lines.append("| — | No complete 16-team projection ranking | — | — | — | — |")

    owner = next((team for team in teams if team["is_owner"]), None)
    owner_players = sorted(
        [player for player in players if player["is_owner"]],
        key=lambda player: player["roster_order"],
    )
    lines.extend(["", "## Team_02 detail and risk", ""])
    if owner:
        top_four = [team for team in projected_ranked[:4]]
        own_score = owner.get("projected_top10_expected_fp_per_team_game")
        lines.append(
            f"Team_02 projected rank: **{owner.get('projected_rank') or 'provisional'}**. It has {owner['actual_players_with_sample']}/13 players with a completed preseason sample and {owner['injury_dnp_players']} player(s) with an explicit injury/illness DNP note."
        )
        if own_score is not None and len(projected_ranked) >= 4:
            owner_score = float(own_score)
            first_score = float(projected_ranked[0]["projected_top10_expected_fp_per_team_game"])
            fourth_score = float(projected_ranked[3]["projected_top10_expected_fp_per_team_game"])
            lines.append(
                f"Team_02 projects {owner_score:.1f} expected FP/team game, {first_score - owner_score:.1f} behind the current leader and {owner_score - fourth_score:+.2f} relative to the fourth-place cutoff."
            )
        lines.extend(
            [
                "",
                "| Player | NBA team / position | Preseason status | Preseason GP | Actual FP/G | Baseline season | Projected active FP/G | Availability | Expected FP/team game | Risk |",
                "|---|---|---|---:|---:|---|---:|---:|---:|---|",
            ]
        )
        for player in owner_players:
            lines.append(
                f"| {player['player_name']} | {player.get('nba_team','')} / {player.get('nba_position','')} | {player['preseason_status']} | {player['preseason_games_played']} | {fmt(player.get('preseason_actual_fpg'))} | {player.get('baseline_season') or 'cohort prior'} | {fmt(player.get('projected_active_fpg'))} | {player['projected_availability_rate']:.0%} | {fmt(player.get('projected_expected_fpg_per_team_game'))} | {player.get('risk_flags') or '—'} |"
            )
        position_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        all_position_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        team_position_counts: dict[str, Counter[str]] = defaultdict(Counter)
        for player in players:
            group = player.get("position_group", "UNK")
            if group != "UNK":
                team_position_counts[player["fantasy_team_id"]][group] += 1
            if group != "UNK" and player.get("projected_expected_fpg_per_team_game") is not None:
                all_position_groups[group].append(player)
                if player["is_owner"]:
                    position_groups[group].append(player)
        deviations: list[tuple[str, float, float, int]] = []
        for group, group_players in position_groups.items():
            league_values = [float(p["projected_expected_fpg_per_team_game"]) for p in all_position_groups[group]]
            owner_values = [float(p["projected_expected_fpg_per_team_game"]) for p in group_players]
            league_avg = statistics.mean(league_values) if league_values else 0.0
            owner_avg = statistics.mean(owner_values) if owner_values else 0.0
            if league_avg:
                deviations.append((group, owner_avg / league_avg - 1.0, owner_avg, len(group_players)))
        if deviations:
            group, delta, owner_avg, count = min(deviations, key=lambda item: item[1])
            lines.extend(
                [
                    "",
                    f"**Lowest per-player output:** NBA primary {group} players average {owner_avg:.1f} expected FP/team game across {count} roster spots, {abs(delta):.0%} below the league average for that NBA label. This describes the roster mix, not a Yahoo position slot.",
                ]
            )
        owner_depth = team_position_counts.get(owner["team_id"], Counter())
        center_counts = [team_position_counts.get(team["team_id"], Counter()).get("C", 0) for team in teams]
        center_median = statistics.median(center_counts) if center_counts else 0
        center_values = [float(p["projected_expected_fpg_per_team_game"]) for p in position_groups.get("C", [])]
        center_average = statistics.mean(center_values) if center_values else 0.0
        lines.append(
            f"NBA-label center depth is the clearest roster-count gap: {owner_depth.get('C', 0)} center-primary players versus a league median of {center_median:g}; their average projection is {center_average:.1f} expected FP/team game, so the gap is depth rather than below-average per-player output."
        )
        extra_center_teams = {
            team_id for team_id, counts in team_position_counts.items()
            if team_id != owner["team_id"] and counts.get("C", 0) > owner_depth.get("C", 0)
        }
        offers = [
            player for player in owner_players
            if player.get("position_group") != "C" and player.get("projected_expected_fpg_per_team_game") is not None
        ]
        targets = [
            player for player in players
            if player.get("fantasy_team_id") in extra_center_teams
            and player.get("position_group") == "C"
            and player.get("projected_expected_fpg_per_team_game") is not None
            and player.get("preseason_games_played", 0) > 0
            and "preseason_injury_or_illness_dnp" not in str(player.get("risk_flags", ""))
        ]
        trade_pairs = [
            (abs(float(offer["projected_expected_fpg_per_team_game"]) - float(target["projected_expected_fpg_per_team_game"])), offer, target)
            for offer in offers for target in targets
        ]
        if trade_pairs:
            _difference, offer, target = min(trade_pairs, key=lambda item: (item[0], item[2]["player_name"]))
            value_change = float(target["projected_expected_fpg_per_team_game"]) - float(offer["projected_expected_fpg_per_team_game"])
            lines.extend(
                [
                    "",
                    f"**Ownership-legal optional 1-for-1 proposal:** offer {offer['player_name']} (team_02; {float(offer['projected_expected_fpg_per_team_game']):.1f} expected FP/team game) to {target['fantasy_team_label']} for {target['player_name']} ({float(target['projected_expected_fpg_per_team_game']):.1f}). The other roster has {team_position_counts[target['fantasy_team_id']].get('C', 0)} NBA center-primary players; team_02 would move from {owner_depth.get('C', 0)} to {owner_depth.get('C', 0) + 1}. The model's point estimate changes by {value_change:+.1f} FP/team game, so this is a depth-for-near-equal-value option, not a top-four shortcut. Confirm current Yahoo ownership and eligibility before any transaction; the analysis uses the roster snapshot only.",
                ]
            )
    else:
        lines.append("Owner-team projection unavailable because no team is marked as owner.")

    lines.extend(
        [
            "",
            "## All-roster player detail",
            "",
            "The full 208-player table, including game-level sample counts, missing fields, rate-shrink weights, availability, risk flags, and source game IDs, is in `2026-10-14-preseason-player-model.csv`. Per-game source rows for rostered players are in `2026-10-14-preseason-player-games.csv`.",
            "",
            "## Data quality, uncertainty, and limitations",
            "",
            f"- The ranking uses NBA Stats `boxscoretraditionalv3` as the canonical preseason stat source. The separate NBA `PlayerGameLogs` feed differs in {source_qa['boxscore_playergamelog_difference_count']} stat/minute cells across {source_qa['player_game_rows']} rostered player-game rows; those values were not mixed into the ranking. Sample differences: {', '.join(source_qa['boxscore_playergamelog_examples']) or 'none'}.",
            f"- Historical baseline reconciliation against NBA LeagueDashPlayerStats: {len(history_meta['dash_mismatches'])} per-game mismatch(es) outside a 0.16 stat-per-game tolerance.",
            f"- Projection-only rookie prior: {history_meta['rookie_prior_source']}; {history_meta['rookie_prior_players']} player(s) in its 2025-26 source cohort. No-history players are visibly flagged and receive wider scenario bands rather than zero.",
            "- No 2026-27 official injury report was available in the captured source set. Availability uses prior-season attendance; current preseason DNP injury/illness notes are surfaced as risks and widen the range but are not extrapolated into a season-long injury absence.",
            "- Top-10 actual preseason FP/G is a tiny-sample observation, not a regular-season forecast. Team schedules differ and preseason rotations are not representative of regular-season minutes.",
            "- Per-game projections are conditional on the owner-confirmed roster snapshot; Yahoo read-only reconciliation remains pending, so current waiver eligibility and Yahoo position eligibility are not claimed.",
            "- The projection model uses a 2025-26 baseline, per-36 rate shrinkage, role-minute shrinkage, a historical availability prior, and observed preseason participation. The published central value is a model output; low/high values are sensitivity bands, not probabilities.",
            "",
            "## Reproduction and validation",
            "",
            "```bash",
            f"python scripts/collect_preseason_snapshot.py --cutoff-utc {manifest['cutoff_utc']}",
            "python scripts/build_preseason_rankings.py --snapshot seasons/2026-27/data/preseason-2026-10-14",
            "python scripts/validate_preseason_rankings.py --snapshot seasons/2026-27/data/preseason-2026-10-14 --allow-draft",
            "# Preserve the fresh independent review in 2026-10-14-independent-validation.json",
            "python scripts/build_preseason_rankings.py --snapshot seasons/2026-27/data/preseason-2026-10-14 --official",
            "python scripts/validate_preseason_rankings.py --snapshot seasons/2026-27/data/preseason-2026-10-14",
            "```",
            "",
            "The collection command writes exact source responses and their retrieval timestamps and SHA-256 hashes to `source_manifest.json`. The frozen manifest is the reproduction source for the rankings above.",
            "",
            "## Sources and definitions",
            "",
            "- [NBA Stats API](https://stats.nba.com/stats/) — scoreboard, player game logs, traditional box scores, play-by-play, current rosters, and prior-season player statistics.",
            "- [NBA Stats glossary](https://www.nba.com/stats/help/glossary) — DD2/TD3 field definitions.",
            "- [NBA Rule No. 12: Fouls and Penalties](https://official.nba.com/rule-no-12-fouls-and-penalties/) — technical, flagrant, and ejection rules used to interpret preseason play-by-play.",
            "- [ESPN player statistics API](https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete?season=2026&seasontype=2) — historical TECH/FLAG/EJECT only; those rare stats are not in NBA base player game logs.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="seasons/2026-27/data/preseason-2026-10-14")
    parser.add_argument("--output-dir", default="seasons/2026-27/report")
    parser.add_argument("--official", action="store_true", help="Label output official after independent validation passes.")
    args = parser.parse_args()
    snapshot = Path(args.snapshot)
    output_dir = Path(args.output_dir)
    manifest = load_json(snapshot / "source_manifest.json")
    league = load_json(Path("seasons/2026-27/league.json"))
    roster = load_json(Path("seasons/2026-27/rosters.json"))
    if league["season"] != roster["season"]:
        raise ValueError("league.json and rosters.json seasons differ")
    weights = {field: float(value) for field, value in league["scoring"].items()}
    if set(weights) != set(SCORING_TO_FIELD):
        raise ValueError("league scoring fields do not match the model's required custom fields")

    players = add_current_rosters(snapshot, roster)
    history, _priors, history_meta = prepare_history(snapshot, players, weights)
    observations, source_qa, game_rows = load_preseason(
        snapshot,
        {p["player_id"]: p for p in players if p.get("player_id")},
        weights,
    )
    modeled, teams = rank_teams(
        players,
        observations,
        history,
        weights,
        source_qa["nba_team_completed_game_counts"],
    )
    source_qa["roster_player_count"] = len(players)
    source_qa["current_nba_roster_matched"] = sum(1 for p in players if p["nba_match_status"] == "matched")
    source_qa["actual_rankable_teams"] = sum(1 for team in teams if team["actual_rankable"])
    source_qa["projected_rankable_teams"] = sum(1 for team in teams if team["projected_top10_rankable"])
    source_qa["incomplete_observations"] = sum(1 for item in observations.values() if item.get("missing_fields"))
    player_names_by_id = {player.get("player_id"): player["player_name"] for player in players}
    source_qa["boxscore_playergamelog_examples"] = [
        (
            f"{player_names_by_id.get(item.get('player_id'), item.get('player_id'))} {item.get('game_id')} "
            f"{item.get('field')}: boxscore {fmt(item.get('boxscore'))}, PlayerGameLogs {fmt(item.get('playergamelog'))}"
        )
        for item in source_qa["boxscore_playergamelog_differences"][:3]
    ]
    source_qa["status"] = (
        "ready_for_independent_validation"
        if source_qa["current_nba_roster_matched"] == 208
        and source_qa["actual_rankable_teams"] == 16
        and source_qa["projected_rankable_teams"] == 16
        and source_qa["incomplete_observations"] == 0
        and not history_meta["dash_mismatches"]
        else "needs_data_review"
    )
    source_qa["official_output_requested"] = args.official

    if args.official:
        signoff_path = output_dir / "2026-10-14-independent-validation.json"
        if not signoff_path.exists():
            raise ValueError("--official requires a passing 2026-10-14-independent-validation.json")
        signoff = load_json(signoff_path)
        review_scope = signoff.get("review_scope", {})
        sample_player_games = signoff.get("sample_player_games", review_scope.get("sample_player_games", 0))
        if signoff.get("passed") is not True or int(sample_player_games) < 10:
            raise ValueError("independent review must pass and recalculate at least 10 player-game rows")
        if source_qa["status"] != "ready_for_independent_validation":
            raise ValueError("source/model QA is not ready; refusing to label rankings official")

    output_dir.mkdir(parents=True, exist_ok=True)
    player_fields = list(modeled[0].keys()) if modeled else []
    write_csv(output_dir / "2026-10-14-preseason-player-model.csv", modeled, player_fields)
    write_csv(
        output_dir / "2026-10-14-preseason-team-rankings.csv",
        teams,
        list(teams[0].keys()) if teams else [],
    )
    current_team = {
        player["player_id"]: player["fantasy_team_id"]
        for player in modeled
        if player.get("player_id") is not None
    }
    for row in game_rows:
        row["fantasy_team_id"] = current_team.get(row["player_id"], "")
    write_csv(
        output_dir / "2026-10-14-preseason-player-games.csv",
        game_rows,
        [
            "fantasy_team_id",
            "player_name",
            "player_id",
            "game_id",
            "nba_team",
            "status",
            "minutes",
            *ACTUAL_FIELDS,
            "custom_fp",
            "dnp_comment",
        ],
    )
    (output_dir / "2026-10-14-preseason-validation.json").write_text(
        json.dumps({"source_qa": source_qa, "history_qa": history_meta}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    build_report(
        output_dir / "2026-10-14-preseason-rankings.md",
        league,
        roster,
        manifest,
        teams,
        modeled,
        source_qa,
        history_meta,
        args.official,
    )
    print(
        f"players={len(modeled)} teams={len(teams)} completed_games={source_qa['completed_game_count']} "
        f"actual_rankable={source_qa['actual_rankable_teams']}/16 "
        f"projected_rankable={source_qa['projected_rankable_teams']}/16 "
        f"playergamelog_differences={source_qa['boxscore_playergamelog_difference_count']} "
        f"historical_mismatches={len(history_meta['dash_mismatches'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
