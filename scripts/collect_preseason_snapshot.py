#!/usr/bin/env python3
"""Collect a frozen, traceable NBA preseason snapshot for the 2026-27 model.

The NBA Stats API supplies the schedule, game box scores, play-by-play,
player game logs, historical baselines, and current roster mapping. ESPN's
public stats endpoint is used only for historical TECH/FLAG/EJECT totals,
which the NBA base player log does not expose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


NBA_BASE = "https://stats.nba.com/stats/"
ESPN_BASE = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/"
NBA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
ESPN_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_cutoff(value: str | None) -> datetime:
    if not value:
        return utc_now()
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), datetime.max.time(), timezone.utc)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def response_summary(payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"top_level_keys": list(payload) if isinstance(payload, dict) else []}
    if not isinstance(payload, dict):
        return summary
    meta = payload.get("meta")
    if isinstance(meta, dict):
        summary["source_meta_time"] = meta.get("time")
    result_sets = payload.get("resultSets") or payload.get("resultSet")
    if isinstance(result_sets, dict):
        result_sets = [result_sets]
    if isinstance(result_sets, list):
        summary["result_sets"] = [
            {
                "name": item.get("name"),
                "row_count": len(item.get("rowSet", [])),
                "column_count": len(item.get("headers", [])),
            }
            for item in result_sets
            if isinstance(item, dict)
        ]
    scoreboard = payload.get("scoreboard")
    if isinstance(scoreboard, dict):
        summary["game_count"] = len(scoreboard.get("games", []))
    game = payload.get("game")
    if isinstance(game, dict) and isinstance(game.get("actions"), list):
        summary["action_count"] = len(game["actions"])
    boxscore = payload.get("boxScoreTraditional")
    if isinstance(boxscore, dict):
        summary["home_player_rows"] = len(boxscore.get("homeTeam", {}).get("players", []))
        summary["away_player_rows"] = len(boxscore.get("awayTeam", {}).get("players", []))
    return summary


class SnapshotCollector:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.sources: list[dict[str, Any]] = []

    def fetch(self, provider: str, url: str, relative_path: str, *, nba: bool = True) -> Any:
        headers = NBA_HEADERS if nba else ESPN_HEADERS
        last_error: Exception | None = None
        for attempt in range(4):
            request = Request(url, headers=headers)
            try:
                with urlopen(request, timeout=60) as response:
                    raw = response.read()
                payload = json.loads(raw)
                target = self.output_dir / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                entry = {
                    "provider": provider,
                    "request_url": url,
                    "retrieved_at_utc": utc_text(utc_now()),
                    "payload_file": relative_path,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    **response_summary(payload),
                }
                self.sources.append(entry)
                return payload
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Failed to collect {url}: {last_error}") from last_error

    def nba(self, endpoint: str, params: dict[str, Any], relative_path: str) -> Any:
        url = NBA_BASE + endpoint + "?" + urlencode(params)
        return self.fetch("NBA Stats API", url, relative_path, nba=True)

    def espn(self, endpoint: str, params: dict[str, Any], relative_path: str) -> Any:
        url = ESPN_BASE + endpoint + "?" + urlencode(params)
        return self.fetch("ESPN stats", url, relative_path, nba=False)


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cutoff-utc",
        help="Inclusive UTC cutoff, e.g. 2026-10-14T04:20:00Z. Defaults to collection start time.",
    )
    parser.add_argument("--season", default="2026-27")
    parser.add_argument(
        "--output-dir",
        default="seasons/2026-27/data/preseason-2026-10-14",
    )
    args = parser.parse_args()

    cutoff = parse_cutoff(args.cutoff_utc)
    started_at = utc_now()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    collector = SnapshotCollector(output_dir)

    # The current NBA roster is league-state context; fantasy ownership remains
    # the owner-confirmed season snapshot in rosters.json.
    current_players = collector.nba(
        "commonallplayers",
        {"LeagueID": "00", "Season": args.season, "IsOnlyCurrentSeason": "1"},
        "nba/commonallplayers_2026-27.json",
    )
    historical_rookies = collector.nba(
        "commonallplayers",
        {"LeagueID": "00", "Season": "2025-26", "IsOnlyCurrentSeason": "1"},
        "nba/commonallplayers_2025-26.json",
    )

    player_set = result_set(current_players)
    headers = player_set["headers"]
    rows = player_set["rowSet"]
    index = {header: position for position, header in enumerate(headers)}
    target_roster_path = Path("seasons/2026-27/rosters.json")
    if not target_roster_path.exists():
        raise FileNotFoundError(f"Expected season roster at {target_roster_path}")
    roster = json.loads(target_roster_path.read_text(encoding="utf-8"))
    target_names = {name for team in roster["teams"] for name in team["players"]}
    current_rows = [row for row in rows if row[index["DISPLAY_FIRST_LAST"]] in target_names]
    nba_team_ids = sorted({int(row[index["TEAM_ID"]]) for row in current_rows if row[index["TEAM_ID"]]})
    for team_id in nba_team_ids:
        collector.nba(
            "commonteamroster",
            {"LeagueID": "00", "Season": args.season, "TeamID": team_id},
            f"nba/team_rosters/{team_id}.json",
        )
        time.sleep(0.12)

    # Current preseason and two seasons of NBA game logs support the observed
    # rate, prior-year baseline, and a stale-history fallback for returners.
    collector.nba(
        "playergamelogs",
        {"LeagueID": "00", "Season": args.season, "SeasonType": "Pre Season", "PlayerID": "0"},
        "nba/playergamelogs_2026-27_preseason.json",
    )
    collector.nba(
        "playergamelogs",
        {"LeagueID": "00", "Season": "2025-26", "SeasonType": "Regular Season", "PlayerID": "0"},
        "nba/playergamelogs_2025-26_regular.json",
    )
    collector.nba(
        "playergamelogs",
        {"LeagueID": "00", "Season": "2024-25", "SeasonType": "Regular Season", "PlayerID": "0"},
        "nba/playergamelogs_2024-25_regular.json",
    )
    collector.nba(
        "leaguedashplayerstats",
        {
            "College": "",
            "Conference": "",
            "Country": "",
            "DateFrom": "",
            "DateTo": "",
            "Division": "",
            "DraftPick": "",
            "DraftYear": "",
            "GameScope": "",
            "GameSegment": "",
            "Height": "",
            "LastNGames": "0",
            "LeagueID": "00",
            "Location": "",
            "MeasureType": "Base",
            "Month": "0",
            "OpponentTeamID": "0",
            "Outcome": "",
            "PORound": "0",
            "PerMode": "PerGame",
            "Period": "0",
            "PlayerExperience": "",
            "PlayerPosition": "",
            "Season": "2025-26",
            "SeasonSegment": "",
            "SeasonType": "Regular Season",
            "ShotClockRange": "",
            "StarterBench": "",
            "TeamID": "0",
            "VsConference": "",
            "VsDivision": "",
        },
        "nba/leaguedashplayerstats_2025-26_regular.json",
    )

    for season_year, season_type, label in ((2026, 2, "2025-26"), (2025, 2, "2024-25")):
        for page in (1, 2):
            collector.espn(
                "statistics/byathlete",
                {
                    "region": "us",
                    "lang": "en",
                    "contentorigin": "espn",
                    "season": season_year,
                    "seasontype": season_type,
                    "limit": 500,
                    "page": page,
                },
                f"espn/special_stats_{label}_page{page}.json",
            )

    start = date(2026, 10, 3)
    final_cutoff_date = cutoff.date()
    games: dict[str, dict[str, Any]] = {}
    day = start
    while day <= final_cutoff_date:
        date_text = day.isoformat()
        scoreboard = collector.nba(
            "scoreboardv3",
            {"LeagueID": "00", "GameDate": day.strftime("%m/%d/%Y")},
            f"nba/scoreboards/{date_text}.json",
        )
        for game in scoreboard.get("scoreboard", {}).get("games", []):
            if game.get("gameLabel") != "Preseason":
                continue
            game_id = str(game.get("gameId", ""))
            if not game_id:
                continue
            games[game_id] = game
        day += timedelta(days=1)

    cutoff_games: dict[str, dict[str, Any]] = {}
    for game_id, game in sorted(games.items()):
        game_time = game.get("gameTimeUTC")
        if not game_time:
            continue
        parsed_game_time = datetime.fromisoformat(game_time.replace("Z", "+00:00"))
        if parsed_game_time.astimezone(timezone.utc) <= cutoff:
            cutoff_games[game_id] = game

    completed = {
        game_id: game
        for game_id, game in cutoff_games.items()
        if int(game.get("gameStatus", 0)) == 3
        and str(game.get("gameStatusText", "")).casefold().startswith("final")
    }

    for game_id in sorted(completed):
        collector.nba(
            "boxscoretraditionalv3",
            {"GameID": game_id},
            f"nba/boxscores/{game_id}.json",
        )
        collector.nba(
            "playbyplayv3",
            {"GameID": game_id, "StartPeriod": "1", "EndPeriod": "10"},
            f"nba/playbyplay/{game_id}.json",
        )
        time.sleep(0.08)

    manifest = {
        "schema_version": 1,
        "season": args.season,
        "cutoff_utc": utc_text(cutoff),
        "collection_started_at_utc": utc_text(started_at),
        "collection_finished_at_utc": utc_text(utc_now()),
        "preseason_start_date": start.isoformat(),
        "completed_game_count": len(completed),
        "scheduled_or_in_progress_game_count_by_cutoff": len(cutoff_games) - len(completed),
        "completed_game_ids": sorted(completed),
        "sources": collector.sources,
    }
    (output_dir / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"snapshot={output_dir} cutoff={manifest['cutoff_utc']} "
        f"completed_games={len(completed)} "
        f"not_final_by_cutoff={manifest['scheduled_or_in_progress_game_count_by_cutoff']} "
        f"sources={len(collector.sources)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
