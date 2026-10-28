#!/usr/bin/env python3
"""NBA schedule/box-score acquisition, provenance snapshots, and league FP math.

The NBA CDN is attempted first. ESPN's public scoreboard/summary endpoint is a
fallback adapter only; its identifiers and fields remain provider identifiers
and third-party data until an explicit NBA identity crosswalk and source review
are available. This module never guesses an NBA game/player ID from a name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

NBA_BOXSCORE = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
NBA_PLAYBYPLAY = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
NBA_DATED_SCOREBOARD = "https://stats.nba.com/stats/scoreboardv3?GameDate={game_date}&LeagueID=00"
NBA_STATIC_SCHEDULE = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
FIELDS = ("PTS", "3PTM", "OREB", "DREB", "AST", "STL", "BLK", "TO", "FTA", "PF", "TECH", "EJCT", "FF")
BONUSES = ("DD", "TD")
QUALITY = {"VERIFIED_VALUE", "VERIFIED_ZERO", "THIRD_PARTY_RECONSTRUCTED", "CONFLICTING", "UNKNOWN"}
NBA_TRADITIONAL_FIELDS={"minutes","points","threePointersMade","reboundsOffensive","reboundsDefensive","reboundsTotal",
    "assists","steals","blocks","turnovers","freeThrowsAttempted","freeThrowsMade","foulsPersonal","foulsTechnical"}
NORMALIZER_VERSION="2.2.0"
MAX_RETRY_AFTER_SECONDS=30

def normalizer_code_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class SourceError(RuntimeError):
    def __init__(self, provider: str, url: str, kind: str, detail: str, status: int | None = None):
        super().__init__(detail)
        self.provider, self.url, self.kind, self.status = provider, url, kind, status

    def as_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "url": self.url, "kind": self.kind,
                "http_status": self.status, "message": str(self)}


def parse_nba_played(value: Any) -> bool | None:
    """Parse NBA's boolean or 0/1 string field without treating '0' as truthy."""
    if isinstance(value,bool): return value
    if isinstance(value,int) and value in (0,1): return value == 1
    if isinstance(value,str):
        normalized=value.strip().casefold()
        if normalized in ("1","true","yes"): return True
        if normalized in ("0","false","no"): return False
    return None


def _retry_after_seconds(value: str | None, now: datetime | None = None) -> float | None:
    """Parse RFC Retry-After delta seconds or HTTP date; None means absent/invalid."""
    if value is None: return None
    value=value.strip()
    if not value: return None
    if value.isdigit(): return float(value)
    try:
        target=parsedate_to_datetime(value)
    except (TypeError,ValueError,OverflowError):
        return None
    if target.tzinfo is None: target=target.replace(tzinfo=timezone.utc)
    now=now or datetime.now(timezone.utc)
    return max(0.0,(target.astimezone(timezone.utc)-now.astimezone(timezone.utc)).total_seconds())


class JsonClient:
    """Small bounded HTTP client that records raw and normalized hashes."""
    def __init__(self, snapshot_dir: Path | None = None, timeout: float = 12, retries: int = 2,
                 sleep=time.sleep, opener=urllib.request.urlopen, replay: bool = False):
        self.snapshot_dir, self.timeout, self.retries = snapshot_dir, timeout, retries
        self.sleep, self.opener = sleep, opener
        self.replay=replay
        self.history: list[dict[str, Any]] = []
        self._last_request = 0.0

    def get_json(self, provider: str, url: str, schema_version: str,
                 validator=None) -> tuple[Any, dict[str, Any]]:
        if self.replay:
            return self._replay(provider,url,schema_version,validator)
        attempt = 0
        while True:
            fetched_at = datetime.now(timezone.utc).isoformat()
            try:
                wait=max(0.0,0.5-(time.monotonic()-self._last_request))
                if wait: self.sleep(wait)
                req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "fantasy-hoops-research/1.0",
                                                            "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com"})
                with self.opener(req, timeout=self.timeout) as response:
                    self._last_request=time.monotonic()
                    status = response.status
                    raw = response.read()
                    headers = response.headers
                if status == 429:
                    raise urllib.error.HTTPError(url,429,"Rate limit",headers,None)
                if status >= 400:
                    raise SourceError(provider, url, "HTTP_ERROR", f"HTTP {status}", status)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise SourceError(provider, url, "INVALID_JSON", str(exc)) from exc
                if validator and not validator(payload):
                    raise SourceError(provider, url, "SCHEMA_DRIFT", "response failed schema validation")
                normalized_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
                raw_hash = hashlib.sha256(raw).hexdigest()
                rec = {"provider": provider, "url": url, "fetched_at": fetched_at,
                       "http_status": status, "schema_version": schema_version,
                       "raw_sha256": raw_hash, "normalized_sha256": normalized_hash,
                       "fetched_with_normalizer_version": NORMALIZER_VERSION,
                       "fetched_with_normalizer_code_sha256": normalizer_code_sha256(),
                       "source_quality": "NBA_OFFICIAL_ENDPOINT" if provider in ("nba_cdn","nba_stats","nba_static_schedule") else "THIRD_PARTY_UNVERIFIED_TERMS",
                       "publication_rights": "UNVERIFIED",
                       "response_bytes": len(raw), "error_history": []}
                self.history.append(rec)
                if self.snapshot_dir:
                    self._snapshot(provider, raw_hash, raw, rec)
                return payload, rec
            except urllib.error.HTTPError as exc:
                status = exc.code
                kind = "RATE_LIMIT" if status == 429 else "FORBIDDEN" if status == 403 else "HTTP_ERROR"
                err = SourceError(provider, url, kind, f"HTTP {status}", status)
                if status == 429:
                    header=exc.headers.get("Retry-After") if exc.headers else None
                    requested=_retry_after_seconds(header)
                    row={**err.as_dict(),"fetched_at":fetched_at,"attempt":attempt+1,
                         "retry_after_header":header,"retry_after_seconds":requested}
                    if attempt >= self.retries:
                        row["retry_action"]="STOP_RETRIES_EXHAUSTED"
                        self.history.append(row)
                        raise err from exc
                    if requested is not None and requested > MAX_RETRY_AFTER_SECONDS:
                        row["retry_action"]="STOP_PROVIDER_AND_FALL_BACK"
                        row["message"]=(f"HTTP 429 Retry-After {requested:.0f}s exceeds "
                                        f"{MAX_RETRY_AFTER_SECONDS}s bound; stop provider and fall back")
                        self.history.append(row)
                        raise SourceError(provider,url,"RATE_LIMIT",row["message"],429) from exc
                    delay=requested if requested is not None else min(8,2**attempt)
                    row["retry_action"]="RETRY"
                    self.history.append(row)
                    self.sleep(delay)
                    attempt += 1
                    continue
                self.history.append({**err.as_dict(), "fetched_at": fetched_at, "attempt": attempt + 1})
                if status >= 500 and attempt < self.retries:
                    self.sleep(min(8, 2 ** attempt + random.random()))
                    attempt += 1
                    continue
                raise err from exc
            except SourceError as exc:
                self.history.append({**exc.as_dict(), "fetched_at": fetched_at, "attempt": attempt + 1})
                raise
            except (TimeoutError, OSError, urllib.error.URLError) as exc:
                err = SourceError(provider, url, "TIMEOUT" if isinstance(exc, TimeoutError) else "NETWORK_ERROR", str(exc))
                self.history.append({**err.as_dict(), "fetched_at": fetched_at, "attempt": attempt + 1})
                if attempt < self.retries:
                    self.sleep(min(8, 2 ** attempt + random.random()))
                    attempt += 1
                    continue
                raise err from exc

    def _snapshot(self, provider: str, digest: str, raw: bytes, record: dict[str, Any]) -> None:
        folder = self.snapshot_dir / provider
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{digest}.json"
        record["raw_snapshot_path"] = str(path)
        if not path.exists():
            path.write_bytes(raw)
        meta_path = folder / f"{digest}.manifest.json"
        if not meta_path.exists():
            meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _replay(self,provider: str,url: str,schema_version: str,validator=None):
        if not self.snapshot_dir: raise SourceError(provider,url,"CACHE_MISS","snapshot directory is not configured")
        matches=[]
        for manifest in (self.snapshot_dir/provider).glob("*.manifest.json"):
            try: row=json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError,json.JSONDecodeError): continue
            if row.get("url")==url and row.get("provider")==provider: matches.append((row,manifest))
        if not matches: raise SourceError(provider,url,"CACHE_MISS","no raw snapshot for URL")
        record,manifest=max(matches,key=lambda x:x[0].get("fetched_at",""))
        raw_path=manifest.with_name(manifest.name.removesuffix(".manifest.json")+".json")
        try: raw=raw_path.read_bytes()
        except OSError as exc: raise SourceError(provider,url,"CACHE_CORRUPT","raw snapshot file is missing") from exc
        if hashlib.sha256(raw).hexdigest()!=record.get("raw_sha256"):
            raise SourceError(provider,url,"CACHE_CORRUPT","raw snapshot SHA-256 mismatch")
        try: payload=json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise SourceError(provider,url,"CACHE_CORRUPT","raw snapshot is invalid JSON") from exc
        if validator and not validator(payload): raise SourceError(provider,url,"SCHEMA_DRIFT","cached response failed schema validation")
        if record.get("schema_version")!=schema_version: raise SourceError(provider,url,"SCHEMA_DRIFT","cached response schema version differs")
        record={**record,"cache_replay":True,"raw_snapshot_path":str(raw_path),
                "replayed_with_normalizer_version":NORMALIZER_VERSION,
                "replayed_with_normalizer_code_sha256":normalizer_code_sha256()}
        self.history.append(record)
        return payload,record


def _valid_nba_boxscore(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get("game"),dict): return False
    game=payload["game"]
    if not isinstance(game.get("gameId"),str) or not game["gameId"].isdigit(): return False
    for side in ("homeTeam","awayTeam"):
        team=game.get(side)
        if not isinstance(team,dict) or not isinstance(team.get("players"),list): return False
        for player in team["players"]:
            played=parse_nba_played(player.get("played"))
            if played is None: return False
            if played and not NBA_TRADITIONAL_FIELDS.issubset(player.get("statistics",{})): return False
    return True


def _valid_nba_static_schedule(payload):
    league=(payload.get("leagueSchedule") if isinstance(payload,dict) else None)
    return (isinstance(league,dict) and isinstance(league.get("seasonYear"),str) and
            isinstance(league.get("gameDates"),list) and all(
                isinstance(day,dict) and isinstance(day.get("games"),list)
                for day in league["gameDates"]))


def _static_schedule_events(payload, date_yyyymmdd):
    league=payload["leagueSchedule"]
    expected=f"{date_yyyymmdd[4:6]}/{date_yyyymmdd[6:8]}/{date_yyyymmdd[:4]}"
    days=[]
    for day in league["gameDates"]:
        raw_date=str(day.get("gameDate", ""))
        try: parsed=datetime.strptime(raw_date[:10],"%m/%d/%Y").strftime("%m/%d/%Y")
        except ValueError: continue
        if parsed==expected: days.append(day)
    if len(days)>1: raise ValueError("NBA static schedule contains duplicate date buckets")
    events=[]
    for day in days:
        for game in day["games"]:
            gid=str(game.get("gameId", ""))
            home=game.get("homeTeam") or {}; away=game.get("awayTeam") or {}
            start=game.get("gameDateTimeUTC")
            status=game.get("gameStatus")
            if not (gid.isdigit() and len(gid)==10 and status in (1,2,3) and start and
                    str(home.get("teamTricode", "")) and str(away.get("teamTricode", ""))):
                raise ValueError("NBA static schedule row is missing official identity/status fields")
            events.append({"gameId":gid,"gameStatus":status,"gameTimeUTC":start,
                "gameDateEst":date_yyyymmdd[:4]+"-"+date_yyyymmdd[4:6]+"-"+date_yyyymmdd[6:],
                "gameStatusText":game.get("gameStatusText", ""),
                "homeTeam":{"teamId":home.get("teamId"),"teamTricode":home["teamTricode"]},
                "awayTeam":{"teamId":away.get("teamId"),"teamTricode":away["teamTricode"]},
                "period":game.get("period"),"source_game_code":game.get("gameCode")})
    ids=[x["gameId"] for x in events]
    if len(ids)!=len(set(ids)): raise ValueError("NBA static schedule contains duplicate GAME_ID")
    return events


def acquire_schedule(date_yyyymmdd: str, client: JsonClient) -> dict[str, Any]:
    """Try NBA Stats, NBA's public CDN schedule, then ESPN without inventing NBA IDs."""
    errors = []
    try:
        yyyy,mm,dd=date_yyyymmdd[:4],date_yyyymmdd[4:6],date_yyyymmdd[6:]
        game_date=urllib.parse.quote(f"{mm}/{dd}/{yyyy}",safe="")
        url=NBA_DATED_SCOREBOARD.format(game_date=game_date)
        payload, record = client.get_json("nba_stats", url, "nba-scoreboardv3-v1",
            lambda x: isinstance(x, dict) and isinstance(x.get("scoreboard"), dict) and isinstance(x["scoreboard"].get("games"), list))
        events = payload["scoreboard"]["games"]
        return {"provider": "nba_stats", "record": record, "events": events, "errors": errors}
    except SourceError as exc:
        errors.append(exc.as_dict())
    try:
        payload,record=client.get_json("nba_static_schedule",NBA_STATIC_SCHEDULE,
            "nba-static-schedule-league-v2_1",_valid_nba_static_schedule)
        requested_year=int(date_yyyymmdd[:4]); requested_month=int(date_yyyymmdd[4:6])
        season_start=requested_year if requested_month>=7 else requested_year-1
        expected_season=f"{season_start}-{str(season_start+1)[-2:]}"
        if payload["leagueSchedule"].get("seasonYear") != expected_season:
            raise SourceError("nba_static_schedule",NBA_STATIC_SCHEDULE,"WRONG_SEASON",
                f"schedule season {payload['leagueSchedule'].get('seasonYear')} does not cover requested NBA date {date_yyyymmdd}")
        events=_static_schedule_events(payload,date_yyyymmdd)
        record["source_quality"]="NBA_OFFICIAL_ENDPOINT"
        record["schedule_date_normalized_sha256"]=hashlib.sha256(json.dumps(events,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        return {"provider":"nba_static_schedule","record":record,"events":events,"errors":errors}
    except SourceError as exc:
        errors.append(exc.as_dict())
    except (KeyError,TypeError,ValueError) as exc:
        errors.append(SourceError("nba_static_schedule",NBA_STATIC_SCHEDULE,"SCHEMA_DRIFT",str(exc)).as_dict())
    url = ESPN_SCOREBOARD.format(date=date_yyyymmdd)
    payload, record = client.get_json("espn", url, "espn-scoreboard-v2",
                                     lambda x: isinstance(x, dict) and isinstance(x.get("events"), list))
    record["source_quality"] = "THIRD_PARTY_UNVERIFIED_TERMS"
    return {"provider": "espn", "record": record, "events": payload["events"], "errors": errors}


def acquire_boxscore(*, nba_game_id: str | None, provider_event_id: str | None,
                     client: JsonClient) -> dict[str, Any]:
    """Fetch a box score by explicit source ID; never infer IDs from team/date."""
    errors = []
    if nba_game_id:
        if not (nba_game_id.isdigit() and len(nba_game_id) == 10):
            raise ValueError("NBA GAME_ID must be an explicit 10-digit ID")
        url = NBA_BOXSCORE.format(game_id=urllib.parse.quote(nba_game_id, safe=""))
        try:
            payload, record = client.get_json("nba_cdn", url, "nba-boxscore-live-v1",_valid_nba_boxscore)
            if payload["game"].get("gameId") != nba_game_id:
                raise SourceError("nba_cdn", url, "WRONG_GAME_ID", "response gameId differs from requested ID")
            return {"payload": payload, "record": record, "errors": errors,"provider":"nba_cdn","provider_event_id":None}
        except SourceError as exc:
            errors.append(exc.as_dict())
            if exc.kind == "WRONG_GAME_ID": raise
    if not provider_event_id:
        if errors:
            first=errors[0]
            raise SourceError(first["provider"],first["url"],first["kind"],first["message"],first.get("http_status"))
        raise SourceError("nba_cdn", "", "IDENTITY_UNRESOLVED", "no verified NBA boxscore and no provider event ID")
    url = ESPN_SUMMARY.format(event_id=urllib.parse.quote(provider_event_id, safe=""))
    payload, record = client.get_json("espn", url, "espn-summary-v2",
        lambda x: isinstance(x, dict) and isinstance(x.get("boxscore", {}).get("players"), list))
    if str(payload.get("header", {}).get("id", "")) != provider_event_id:
        raise SourceError("espn", url, "WRONG_GAME_ID", "summary event ID differs from requested event ID")
    return {"payload": payload, "record": record, "errors": errors,"provider":"espn","provider_event_id":provider_event_id}


def acquire_playbyplay(nba_game_id: str, client: JsonClient) -> dict[str, Any]:
    if not (nba_game_id.isdigit() and len(nba_game_id) == 10):
        raise ValueError("NBA GAME_ID must be an explicit 10-digit ID")
    url=NBA_PLAYBYPLAY.format(game_id=urllib.parse.quote(nba_game_id,safe=""))
    payload,record=client.get_json("nba_cdn",url,"nba-live-pbp-v1",
        lambda x:isinstance(x,dict) and isinstance(x.get("game"),dict) and isinstance(x["game"].get("actions"),list))
    if str(payload["game"].get("gameId")) != nba_game_id:
        raise SourceError("nba_cdn",url,"WRONG_GAME_ID","PBP gameId differs from requested NBA GAME_ID")
    return {"payload":payload,"record":record}


def normalize_schedule(events: list[dict[str, Any]], provider: str) -> list[dict[str, Any]]:
    """Normalize status and dates while keeping provider and NBA IDs separate."""
    out = []
    for event in events:
        if provider in ("nba_cdn", "nba_stats", "nba_static_schedule"):
            gid = str(event.get("gameId", ""))
            status_code = event.get("gameStatus")
            status = {1: "Scheduled", 2: "Live", 3: "Final"}.get(status_code, "Unknown")
            raw_start = event.get("gameTimeUTC") or event.get("gameEt")
            game_date = event.get("gameDateEst") or event.get("gameDate")
            game_dt = datetime.fromisoformat(raw_start.replace("Z", "+00:00")) if raw_start else None
            taipei = game_dt.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat() if game_dt else None
            if not (gid.isdigit() and len(gid) == 10):
                raise ValueError("NBA schedule row has invalid GAME_ID")
            out.append({"id":gid,"provider": provider, "provider_game_id": gid, "official_game_id": gid,
                        "game_date_et": game_date, "game_date_taipei": taipei, "status": status,
                        "home_team_id": str(event.get("homeTeam", {}).get("teamId", "")),
                        "away_team_id": str(event.get("awayTeam", {}).get("teamId", "")),
                        "home_team_tricode":str(event.get("homeTeam",{}).get("teamTricode","")),
                        "away_team_tricode":str(event.get("awayTeam",{}).get("teamTricode","")),
                        "game_time_utc":raw_start,
                        "period": event.get("period"), "source_quality": "NBA_OFFICIAL_ENDPOINT"})
        elif provider == "espn":
            eid = str(event.get("id", ""))
            competition = (event.get("competitions") or [{}])[0]
            raw_start = event.get("date")
            game_dt = datetime.fromisoformat(raw_start.replace("Z", "+00:00")) if raw_start else None
            et = game_dt.astimezone(ZoneInfo("America/New_York")).date().isoformat() if game_dt else None
            taipei = game_dt.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat() if game_dt else None
            state = competition.get("status", {}).get("type", {}).get("state")
            status = {"pre": "Scheduled", "in": "Live", "post": "Final"}.get(state, "Unknown")
            if not eid.isdigit(): raise ValueError("ESPN schedule row has invalid provider event ID")
            out.append({"id":None,"provider": provider, "provider_game_id": eid, "official_game_id": None,
                        "game_date_et": et, "game_date_taipei": taipei, "status": status,
                        "home_team_name": next((c.get("team", {}).get("displayName") for c in competition.get("competitors", []) if c.get("homeAway") == "home"), None),
                        "away_team_name": next((c.get("team", {}).get("displayName") for c in competition.get("competitors", []) if c.get("homeAway") == "away"), None),
                        "home_team_tricode":next((str(c.get("team",{}).get("abbreviation","")) for c in competition.get("competitors",[]) if c.get("homeAway")=="home"),""),
                        "away_team_tricode":next((str(c.get("team",{}).get("abbreviation","")) for c in competition.get("competitors",[]) if c.get("homeAway")=="away"),""),
                        "game_time_utc":raw_start,
                        "source_quality": "THIRD_PARTY_UNVERIFIED_TERMS"})
        else:
            raise ValueError(f"unsupported schedule provider {provider}")
    ids = [(row["provider"], row["provider_game_id"]) for row in out]
    if len(ids) != len(set(ids)): raise ValueError("duplicate schedule game IDs")
    return out


def resolve_official_player_id(provider: str, provider_player_id: str,
                               crosswalk: dict[str, Any]) -> str | None:
    """Require exact sourced crosswalk rows; never infer by player display name."""
    row = crosswalk.get(f"{provider}:{provider_player_id}")
    if not isinstance(row, dict) or row.get("identity_status") != "VERIFIED" or not row.get("source_url"):
        return None
    nba_id = str(row.get("nba_player_id", ""))
    return nba_id if nba_id.isdigit() else None


def resolve_provider_event_id(official_game: dict[str,Any],provider_events: list[dict[str,Any]]) -> dict[str,str]:
    """Join provider event only by exact home/away tricode and near-exact UTC tipoff.

    The returned ESPN ID remains a provider ID; the official NBA GAME_ID remains
    the canonical game identity. No player-name/date-only game inference occurs.
    """
    gid=str(official_game.get("official_game_id") or official_game.get("id") or "")
    if not gid.isdigit() or len(gid)!=10: raise ValueError("official schedule row lacks NBA GAME_ID")
    start=official_game.get("game_time_utc")
    if not start: raise ValueError("official schedule row lacks start timestamp")
    target=datetime.fromisoformat(str(start).replace("Z","+00:00")).timestamp()
    home=str(official_game.get("home_team_tricode","")).upper()
    away=str(official_game.get("away_team_tricode","")).upper()
    matches=[]
    for event in provider_events:
        event_id=str(event.get("id", "")); comps=(event.get("competitions") or [{}])[0]
        pairs={str(c.get("homeAway")):str(c.get("team",{}).get("abbreviation","")).upper() for c in comps.get("competitors",[])}
        stamp=event.get("date")
        try: delta=abs(datetime.fromisoformat(str(stamp).replace("Z","+00:00")).timestamp()-target)
        except (TypeError,ValueError): continue
        if pairs.get("home")==home and pairs.get("away")==away and delta<=120 and event_id.isdigit():
            matches.append((event_id,stamp))
    if len(matches)!=1:
        raise SourceError("espn","","IDENTITY_UNRESOLVED",f"expected one tricode/time match for NBA GAME_ID {gid}, found {len(matches)}")
    event_id,stamp=matches[0]
    return {"nba_game_id":gid,"provider":"espn","provider_event_id":event_id,
            "home_team_tricode":home,"away_team_tricode":away,
            "official_tipoff_utc":str(start),"provider_tipoff_utc":str(stamp),
            "join_rule":"exact_home_away_tricode_plus_utc_start_within_120s"}


def normalize_espn_summary(payload: dict[str, Any], *, nba_game_id: str | None = None,
                           taipei_date: str | None = None) -> list[dict[str, Any]]:
    """Normalize ESPN traditional stats; TECH/EJCT/FF stay UNKNOWN until PBP validated."""
    normalized = []
    for team in payload["boxscore"]["players"]:
        for group in team.get("statistics", []):
            keys = group.get("keys", [])
            for row in group.get("athletes", []):
                vals = row.get("stats", [])
                if len(vals) != len(keys):
                    raise ValueError("ESPN player stat schema length mismatch")
                raw = dict(zip(keys, vals))
                if raw.get("minutes") == "--" or row.get("didNotPlay"):
                    continue
                try:
                    fg3 = int(raw["threePointFieldGoalsMade-threePointFieldGoalsAttempted"].split("-")[0])
                    ft_pair = raw["freeThrowsMade-freeThrowsAttempted"].split("-")
                    stats = {"MIN": raw["minutes"], "PTS": int(raw["points"]), "3PTM": fg3,
                             "OREB": int(raw["offensiveRebounds"]), "DREB": int(raw["defensiveRebounds"]),
                             "REB": int(raw["rebounds"]),
                             "AST": int(raw["assists"]), "STL": int(raw["steals"]), "BLK": int(raw["blocks"]),
                             "TO": int(raw["turnovers"]), "FTA": int(ft_pair[1]), "PF": int(raw["fouls"]),
                             "TECH": None, "EJCT": None, "FF": None}
                except (KeyError, ValueError, IndexError) as exc:
                    raise ValueError(f"invalid ESPN boxscore fields: {exc}") from exc
                player = row["athlete"]
                normalized.append({"game_id":nba_game_id,"official_game_id": nba_game_id,"provider_game_id": str(payload.get("header", {}).get("id", "")),
                    "player_id":str(player["id"]),"official_player_id": None, "provider_player_id": str(player["id"]),
                    "name": player["displayName"], "team_name": team["team"].get("displayName"),"status":"PLAYED",
                    "date_taipei": taipei_date, "stats": stats,
                    "quality": {k: ("THIRD_PARTY_RECONSTRUCTED" if v is not None else "UNKNOWN") for k, v in stats.items() if k != "MIN"},
                    "identity_status": "UNRESOLVED_OFFICIAL_PLAYER_ID", "source_quality": "THIRD_PARTY_UNVERIFIED_TERMS"})
    return normalized


def _minutes(value: str) -> str:
    if value in (None,"", "PT0M0.00S", "PT0M00.00S"): return "0:00"
    import re
    m=re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?",str(value))
    if not m: raise ValueError(f"unsupported NBA minutes value {value!r}")
    seconds=Decimal(m.group(2) or "0")
    mins=int(m.group(1) or 0)+int(seconds//60)
    secs=int(seconds%60)
    return f"{mins}:{secs:02d}"


def incident_events(pbp_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return deduplicated official TECH/EJCT/FF incidents keyed by NBA person ID."""
    game=pbp_payload.get("game",{})
    actions=game.get("actions")
    if not isinstance(actions,list): raise ValueError("PBP is incomplete: missing game.actions")
    action_ids=[str(a.get("actionNumber", "")) for a in actions]
    if any(not x for x in action_ids) or len(action_ids)!=len(set(action_ids)):
        raise ValueError("PBP has missing or duplicated actionNumber; refusing duplicate incident scoring")
    by_player: dict[str,list[dict[str,Any]]]={}
    for action in actions:
        person=action.get("personId")
        if person is None: continue
        kind=None
        action_type=str(action.get("actionType","")).casefold()
        subtype=str(action.get("subType","")).casefold()
        descriptor=str(action.get("descriptor","")).casefold()
        if action_type=="ejection" or subtype=="ejection": kind="EJCT"
        elif action_type=="foul" and (subtype=="technical" or descriptor=="technical" or
                ("technical" in str(action.get("description","")).casefold() and "foul" in str(action.get("description","")).casefold())): kind="TECH"
        elif action_type=="foul" and ("flagrant" in subtype or "flagrant" in descriptor): kind="FF"
        if kind:
            by_player.setdefault(str(person),[]).append({"event_id":str(action["actionNumber"]),"kind":kind,
                "period":action.get("period"),"clock":action.get("clock"),"description":action.get("description","")})
    return by_player


def normalize_nba_boxscore(boxscore_payload: dict[str, Any], pbp_payload: dict[str, Any] | None,
                           *, taipei_date: str | None = None, source_url: str | None = None,
                           source_sha256: str | None = None) -> list[dict[str, Any]]:
    """Normalize NBA official box score + PBP for one verified Game ID."""
    game=boxscore_payload.get("game",{})
    gid=str(game.get("gameId", ""))
    if not gid.isdigit() or len(gid)!=10 or (pbp_payload is not None and str(pbp_payload.get("game",{}).get("gameId"))!=gid):
        raise ValueError("boxscore/PBP official GAME_ID mismatch")
    if game.get("gameStatus")!=3:
        raise ValueError("only Final official box scores can be normalized as played stats")
    incidents=incident_events(pbp_payload) if pbp_payload is not None else {}
    out=[]
    for team_key in ("homeTeam","awayTeam"):
        team=game.get(team_key,{})
        for player in team.get("players",[]):
            person_id=str(player.get("personId", ""))
            if not person_id.isdigit(): raise ValueError("NBA player row lacks official personId")
            played=parse_nba_played(player.get("played"))
            if played is None:
                raise ValueError(f"NBA player row has unknown played status for {person_id}")
            if played is False:
                raw_status=player.get("status")
                player_status=str(raw_status) if raw_status is not None else None
                is_inactive="inactive" in (player_status or "").casefold()
                out.append({"game_id":gid,"official_game_id":gid,"provider_game_id":gid,
                    "player_id":person_id,"official_player_id":person_id,"provider_player_id":person_id,
                    "identity_status":"VERIFIED","identity_source_url":source_url,
                    "identity_source_sha256":source_sha256,
                    "name":player.get("name"),"team_id":str(team.get("teamId")),"team_name":team.get("teamName"),
                    "date_taipei":taipei_date,"status":"INACTIVE" if is_inactive else "DNP",
                    "player_status":player_status,"dnp_reason":None,
                    "stats":{},"quality":{},"incidents":[],
                    "source_quality":"NBA_OFFICIAL_ENDPOINT"})
                continue
            raw=player.get("statistics",{})
            try:
                stats={"MIN":_minutes(raw["minutes"]),"PTS":int(raw["points"]),
                    "3PTM":int(raw["threePointersMade"]),"OREB":int(raw["reboundsOffensive"]),
                    "DREB":int(raw["reboundsDefensive"]),"REB":int(raw["reboundsTotal"]),
                    "AST":int(raw["assists"]),"STL":int(raw["steals"]),"BLK":int(raw["blocks"]),
                    "TO":int(raw["turnovers"]),"FTA":int(raw["freeThrowsAttempted"]),
                    "FTM":int(raw["freeThrowsMade"]),"PF":int(raw["foulsPersonal"]),
                    "TECH":int(raw["foulsTechnical"])}
            except (KeyError,TypeError,ValueError) as exc:
                raise ValueError(f"incomplete official traditional boxscore for {person_id}: {exc}") from exc
            q={k:("VERIFIED_VALUE" if v else "VERIFIED_ZERO") for k,v in stats.items() if k not in ("MIN","FTM","REB")}
            player_events=incidents.get(person_id,[]) if pbp_payload is not None else None
            for kind in ("TECH","EJCT","FF"):
                observed=sum(e["kind"]==kind for e in player_events) if player_events is not None else None
                if kind=="TECH" and observed is not None and stats["TECH"]!=observed:
                    q["TECH"]="CONFLICTING"
                elif kind!="TECH":
                    stats[kind]=observed
                    q[kind]=("VERIFIED_VALUE" if observed else "VERIFIED_ZERO") if observed is not None else "UNKNOWN"
            if stats["OREB"]+stats["DREB"]!=stats["REB"]:
                q["OREB"]=q["DREB"]="CONFLICTING"
            out.append({"game_id":gid,"official_game_id":gid,"provider_game_id":gid,
                "player_id":person_id,"official_player_id":person_id,"provider_player_id":person_id,
                "identity_status":"VERIFIED","identity_source_url":source_url,
                "identity_source_sha256":source_sha256,
                "name":player.get("name"),"team_id":str(team.get("teamId")),"team_name":team.get("teamName"),
                "date_taipei":taipei_date,"status":"PLAYED","stats":stats,"quality":q,
                "incidents":player_events,"source_quality":"NBA_OFFICIAL_ENDPOINT"})
    return out


def acquire_game_bundle(nba_game_id: str, client: JsonClient,
                        event_crosswalk: dict[str,str] | None = None) -> dict[str, Any]:
    """Fetch and normalize one exact official game, preserving both raw manifests."""
    provider_event_id=None
    if event_crosswalk:
        if event_crosswalk.get("nba_game_id")!=nba_game_id or event_crosswalk.get("provider")!="espn" or not event_crosswalk.get("provider_event_id"):
            raise ValueError("provider event crosswalk does not bind the requested NBA GAME_ID")
        provider_event_id=event_crosswalk["provider_event_id"]
    box=acquire_boxscore(nba_game_id=nba_game_id,provider_event_id=provider_event_id,client=client)
    if box["provider"]=="espn":
        comp=(box["payload"].get("header",{}).get("competitions") or [{}])[0]
        raw_date=comp.get("date")
        played=datetime.fromisoformat(str(raw_date).replace("Z","+00:00"))
        taipei=played.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()
        players=normalize_espn_summary(box["payload"],nba_game_id=nba_game_id,taipei_date=taipei)
        if event_crosswalk and str(box["payload"].get("header",{}).get("id"))!=provider_event_id:
            raise SourceError("espn",box["record"]["url"],"WRONG_GAME_ID","fallback event ID crosswalk mismatch")
        digest=hashlib.sha256(json.dumps(players,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        status_type=comp.get("status",{}).get("type",{}).get("state")
        return {"game_id":nba_game_id,"game_date_et":played.astimezone(ZoneInfo("America/New_York")).date().isoformat(),
                "game_date_taipei":taipei,"status":"Final" if status_type=="post" else "Unknown",
                "periods":None,"overtime":None,
                "source_records":[box["record"]],"source_errors":box["errors"],
                "game_id_crosswalk":event_crosswalk,
                "boxscore_source_url":box["record"]["url"],"boxscore_raw_sha256":box["record"]["raw_sha256"],
                "normalized_sha256":digest,"players":players,"source_quality":"THIRD_PARTY_UNVERIFIED_TERMS",
                "fp_quality_note":"Provider player IDs have no official NBA crosswalk; all rows remain partial/blocked"}
    game=box["payload"]["game"]
    pbp_error=None
    try: pbp=acquire_playbyplay(nba_game_id,client)
    except SourceError as exc:
        pbp_error=exc.as_dict();pbp=None
    played=datetime.fromisoformat(game["gameTimeUTC"].replace("Z","+00:00"))
    taipei=played.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()
    periods=int(game.get("period") or 0)
    players=normalize_nba_boxscore(box["payload"],pbp["payload"] if pbp else None,taipei_date=taipei,
        source_url=box["record"]["url"],source_sha256=box["record"]["raw_sha256"])
    digest=hashlib.sha256(json.dumps(players,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return {"game_id":nba_game_id,"game_date_et":game.get("gameEt"),"game_date_taipei":taipei,
            "status":"Final" if game.get("gameStatus")==3 else game.get("gameStatusText","Unknown"),
            "periods":periods,"overtime":periods>4,
            "source_records":[box["record"]]+([pbp["record"]] if pbp else []),
            "source_errors":box["errors"]+([pbp_error] if pbp_error else []),
            "playbyplay_status":"AVAILABLE" if pbp else "UNKNOWN",
            "boxscore_source_url":box["record"]["url"],"boxscore_raw_sha256":box["record"]["raw_sha256"],
            "normalized_sha256":digest,"players":players}


def acquire_game_bundle_with_fallback(official_game:dict[str,Any],client:JsonClient)->dict[str,Any]:
    """Try NBA first, then a strict tricode/tipoff ESPN crosswalk on source failure."""
    gid=str(official_game.get("official_game_id") or official_game.get("id") or "")
    try:
        return acquire_game_bundle(gid,client)
    except SourceError as primary:
        timestamp=official_game.get("game_time_utc")
        if not timestamp: raise
        dt=datetime.fromisoformat(str(timestamp).replace("Z","+00:00"))
        day=dt.astimezone(ZoneInfo("America/New_York")).strftime("%Y%m%d")
        url=ESPN_SCOREBOARD.format(date=day)
        payload,record=client.get_json("espn",url,"espn-scoreboard-v2",
            lambda x:isinstance(x,dict) and isinstance(x.get("events"),list))
        crosswalk=resolve_provider_event_id(official_game,payload["events"])
        bundle=acquire_game_bundle(gid,client,crosswalk)
        bundle["source_errors"]=[primary.as_dict()]+bundle.get("source_errors",[])
        bundle["source_records"].append(record)
        bundle["game_id_crosswalk"]=crosswalk
        return bundle


def calculate_custom_fp(stats: dict[str, Any], scoring: dict[str, Any]) -> dict[str, Any]:
    """Single exact-arithmetic FP calculator shared by scouting and daily reports."""
    unknown_categories=set(scoring)-set(FIELDS)-set(BONUSES)
    if unknown_categories: raise ValueError(f"unsupported league scoring keys: {sorted(unknown_categories)}")
    if not isinstance(stats,dict): return {"value":None,"components":{},"missing":list(scoring)}
    required=[key for key in scoring if key not in BONUSES]
    values={};missing=[]
    for key in required:
        raw=stats.get(key)
        if isinstance(raw,bool) or raw is None:
            missing.append(key);continue
        try: value=Decimal(str(raw))
        except Exception:
            missing.append(key);continue
        if not value.is_finite() or value<0:
            missing.append(key);continue
        values[key]=value
    if missing: return {"value":None,"components":{},"missing":missing}
    if "REB" in stats and stats["REB"] is not None:
        try: total_rebounds=Decimal(str(stats["REB"]))
        except Exception: return {"value":None,"components":{},"missing":["CONFLICTING_REB"]}
        if total_rebounds != values.get("OREB",Decimal(0))+values.get("DREB",Decimal(0)):
            return {"value":None,"components":{},"missing":["CONFLICTING_REB"]}
    categories=[values.get(key,Decimal(0)) for key in ("PTS","OREB","DREB","AST","STL","BLK")]
    qualifying=sum(int(value>=10) for value in (categories[0],categories[1]+categories[2],*categories[3:]))
    derived={"DD":int(qualifying>=2),"TD":int(qualifying>=3)}
    for key in BONUSES:
        if key in stats and stats[key] is not None:
            try: supplied=Decimal(str(stats[key]))
            except Exception: return {"value":None,"components":{},"missing":["DD_TD_INCONSISTENT"]}
            if supplied != Decimal(derived[key]):
                return {"value":None,"components":{},"missing":["DD_TD_INCONSISTENT"]}
    components={}
    for key,weight in scoring.items():
        try: multiplier=Decimal(str(weight))
        except Exception: return {"value":None,"components":{},"missing":[f"INVALID_SCORING_WEIGHT:{key}"]}
        value=Decimal(derived[key]) if key in BONUSES else values[key]
        components[key]=value*multiplier
    total=sum(components.values(),Decimal("0")).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    return {"value":total,"components":{k:str(v) for k,v in components.items()},"derived_bonuses":derived,"missing":[]}


def scoring_trace(stats: dict[str, Any], quality: dict[str, str], scoring: dict[str, Any],
                  *, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Quality-gated custom score using exact decimals and ROUND_HALF_UP to 0.01."""
    unknown_categories = set(scoring) - set(FIELDS) - set(BONUSES)
    if unknown_categories: raise ValueError(f"unsupported league scoring keys: {sorted(unknown_categories)}")
    for key in FIELDS:
        state = quality.get(key, "UNKNOWN")
        if state not in QUALITY: raise ValueError(f"invalid quality for {key}: {state}")
    if "OREB" in stats and "DREB" in stats and stats["OREB"] is not None and stats["DREB"] is not None:
        rebounds = stats.get("REB")
        if rebounds is not None and stats["OREB"] + stats["DREB"] != rebounds:
            quality = {**quality, "OREB": "CONFLICTING", "DREB": "CONFLICTING"}
    if events is not None:
        ids = [e.get("event_id") for e in events]
        if any(not x for x in ids) or len(ids) != len(set(ids)):
            raise ValueError("incident events need unique stable event_id values")
        event_stats = {k: 0 for k in ("TECH", "EJCT", "FF")}
        for e in events:
            kind = e.get("kind")
            if kind not in event_stats: continue
            event_stats[kind] += 1
        for key, value in event_stats.items():
            if quality.get(key) == "UNKNOWN":
                stats[key], quality[key] = value, "THIRD_PARTY_RECONSTRUCTED"
            elif stats.get(key) != value:
                quality[key] = "CONFLICTING"
    required = [k for k in scoring if k not in BONUSES]
    bad = [k for k in required if quality.get(k, "UNKNOWN") in ("UNKNOWN", "CONFLICTING") or stats.get(k) is None]
    if bad:
        # Still return a computable known subtotal; never call it a complete FP.
        components = {k: str(Decimal(str(stats[k])) * Decimal(str(w))) for k, w in scoring.items()
                      if k not in BONUSES and quality.get(k) in ("VERIFIED_VALUE", "VERIFIED_ZERO", "THIRD_PARTY_RECONSTRUCTED") and stats.get(k) is not None}
        subtotal = sum((Decimal(v) for v in components.values()), Decimal("0"))
        state = "BLOCKED" if len(components) == 0 else "PARTIAL_FP"
        return {"status": state, "value": str(subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "components": components, "missing": bad, "quality": quality, "rounding": "ROUND_HALF_UP_0.01"}
    calculation=calculate_custom_fp(stats,scoring)
    if calculation["missing"]:
        components={}
        for key,weight in scoring.items():
            if key in BONUSES or quality.get(key) not in ("VERIFIED_VALUE","VERIFIED_ZERO","THIRD_PARTY_RECONSTRUCTED"):
                continue
            try: components[key]=str(Decimal(str(stats[key]))*Decimal(str(weight)))
            except (KeyError,TypeError,ValueError): continue
        subtotal=sum((Decimal(v) for v in components.values()),Decimal("0")).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        return {"status":"PARTIAL_FP" if components else "BLOCKED","value":str(subtotal),
                "components":components,"missing":calculation["missing"],"quality":quality,"rounding":"ROUND_HALF_UP_0.01"}
    trusted = all(quality.get(k) in ("VERIFIED_VALUE", "VERIFIED_ZERO") for k in required)
    return {"status": "VERIFIED_FP" if trusted else "PARTIAL_FP",
            "value": str(calculation["value"]),
            "components": calculation["components"], "derived_bonuses": calculation["derived_bonuses"], "missing": [],
            "quality": quality, "rounding": "ROUND_HALF_UP_0.01"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="Schedule date YYYYMMDD")
    ap.add_argument("--game-id", help="Explicit 10-digit NBA Game ID")
    ap.add_argument("--provider-event-id", help="Explicit ESPN event ID fallback")
    ap.add_argument("--snapshot-dir", type=Path, default=Path(".cache/nba"))
    ap.add_argument("--replay-cache",action="store_true",help="Use exact saved raw responses without network access")
    args = ap.parse_args()
    client = JsonClient(args.snapshot_dir,replay=args.replay_cache)
    output: dict[str, Any] = {"fetch_history": client.history}
    try:
        if args.date:
            output["schedule"] = acquire_schedule(args.date, client)
        if args.game_id or args.provider_event_id:
            if args.game_id:
                output["game"] = acquire_game_bundle(args.game_id,client)
            else:
                output["boxscore"] = acquire_boxscore(nba_game_id=None, provider_event_id=args.provider_event_id, client=client)
    except SourceError as exc:
        output["error"] = exc.as_dict()
        output["fetch_history"] = client.history
        print(json.dumps(output, ensure_ascii=False, indent=2))
        raise SystemExit(2)
    output["fetch_history"] = client.history
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
