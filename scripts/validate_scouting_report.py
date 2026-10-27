#!/usr/bin/env python3
"""Fail-closed checks for season-scoped scouting dossiers; no Yahoo mutations.

Usage: python scripts/validate_scouting_report.py <dossier.json> <season-dir>
Run in a checkout of the pinned roster/scoring snapshot; this script does not
claim to verify GitHub PR merge or perform a live Yahoo availability lookup.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse
from nba_data_adapter import calculate_custom_fp

CONTENT = {"BLOCKED", "PROVISIONAL", "VALIDATED"}
REVIEW = {"NOT_RUN", "PASS", "FAIL"}
ARCHIVE = {"NOT_WRITTEN", "PR_PENDING", "ARCHIVE_BLOCKED", "ARCHIVED"}
OWNERSHIP = {
    "OWNER_ROSTER", "OTHER_TEAM_ROSTER", "OWNED_TEAM_UNKNOWN",
    "RELEASED_AVAILABILITY_UNVERIFIED", "CONFIRMED_FA",
    "CONFIRMED_WAIVER", "UNKNOWN",
}
REQUIRED_SECTIONS = ("## 0.", "## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7.")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def stats_sha256(stats: dict) -> str:
    """SHA-256 of the deterministic normalized stat payload (not external raw HTML)."""
    raw = json.dumps(stats, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + bytes([0]) + data).hexdigest()


def _read(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def _url(s: object) -> bool:
    if not isinstance(s, str) or not s:
        return False
    p = urlparse(s)
    return p.scheme == "https" and bool(p.netloc)


def _time(s: object) -> bool:
    try:
        return bool(dt.datetime.fromisoformat(s).utcoffset() is not None)
    except (TypeError, ValueError, AttributeError):
        return False


def _at_or_before(timestamp: str, cutoff: str) -> bool:
    try:
        return dt.datetime.fromisoformat(timestamp) <= dt.datetime.fromisoformat(cutoff)
    except (TypeError, ValueError, AttributeError):
        return False


def _number(n: object) -> bool:
    return isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) and n >= 0


def _text(s: object) -> bool:
    return isinstance(s, str) and bool(s.strip()) and "[待填]" not in s and s.strip() not in {"UNKNOWN", "N/A"}


def _key(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip().casefold()


def compute_game_fp(stats: dict, scoring: dict) -> tuple[float | None, list[str]]:
    """Shared adapter arithmetic; absence != 0 and DD/TD remain cumulative."""
    result=calculate_custom_fp(stats,scoring)
    if result["missing"]:
        return None,result["missing"]
    return float(result["value"]),[]


def infer_ownership(name: str, aliases: list[str], rosters: dict, overlay: dict) -> tuple[str, str | None]:
    names = {_key(x) for x in [name, *aliases]}
    found = []
    for team in rosters.get("teams", []):
        for person in [*team.get("players", []), *team.get("additional_owned_players", [])]:
            if _key(person) in names:
                found.append(team["team_id"])
    pending = overlay.get("unassigned_confirmed_owned_players", [])
    released = overlay.get("released_availability_unverified", [])
    if any(_key(p["name"]) in names for p in pending):
        found.append("UNASSIGNED")
    if len(set(found)) > 1:
        raise ValueError("ambiguous identity / contradictory ownership")
    if found:
        team = found[0]
        if team == "UNASSIGNED":
            return "OWNED_TEAM_UNKNOWN", None
        return ("OWNER_ROSTER" if team == rosters.get("owner_team_id") else "OTHER_TEAM_ROSTER"), team
    if any(_key(p["name"]) in names for p in released):
        return "RELEASED_AVAILABILITY_UNVERIFIED", None
    return "UNKNOWN", None


def validate_report(path: Path, season_dir: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = _read(path)
        league_path, rosters_path = season_dir / "league.json", season_dir / "rosters.json"
        ownership_path = season_dir / "ownership" / "current-state.json"
        league, roster, overlay = map(_read, (league_path, rosters_path, ownership_path))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as e:
        return [f"missing/invalid source: {e}"]
    if data.get("schema_version") != 1 or data.get("season") != season_dir.name:
        errors.append("report schema_version/season mismatch")
    status = data.get("content_status")
    review = data.get("review_status")
    archive = data.get("archive_status")
    if status not in CONTENT or review not in REVIEW or archive not in ARCHIVE:
        errors.append("invalid independent status fields")
    if archive == "ARCHIVED":
        errors.append("ARCHIVED cannot be self-declared in immutable dossier; requires separate GitHub main readback receipt")
    if status != "VALIDATED" and review == "PASS":
        errors.append("review PASS requires VALIDATED content")
    if status == "VALIDATED" and review == "FAIL":
        errors.append("VALIDATED content cannot have failed review")
    player = data.get("player", {})
    if not isinstance(player, dict):
        return errors + ["player must be an object"]
    name, aliases = player.get("name"), player.get("aliases", [])
    if not _text(name) or not isinstance(aliases, list) or not all(_text(x) for x in aliases):
        return errors + ["invalid player name/aliases"]
    nba_id, yahoo_id = player.get("nba_id"), player.get("yahoo_id")
    if status == "VALIDATED" and not (
        (isinstance(nba_id, str) and nba_id.isascii() and nba_id.isdecimal())
        or (isinstance(yahoo_id, str) and bool(re.fullmatch(r"[A-Za-z0-9._-]+", yahoo_id)))
    ):
        errors.append("VALIDATED requires syntactically valid stable NBA or Yahoo player ID")
    if status == "VALIDATED" and not _url(player.get("identity_source")):
        errors.append("VALIDATED requires independently sourced player identity")
    prov = data.get("provenance", {})
    if not isinstance(prov, dict):
        return errors + ["provenance must be object"]
    if not HEX40.fullmatch(str(prov.get("roster_commit_sha", ""))):
        errors.append("missing pinned roster commit SHA")
    for label, source in (("league_blob_sha", league_path), ("rosters_blob_sha", rosters_path),
                          ("ownership_blob_sha", ownership_path)):
        v = prov.get(label)
        if not isinstance(v, str) or v != blob_sha(source.read_bytes()):
            errors.append(f"{label}: does not match the checked-out pinned source")
    cutoff = prov.get("data_cutoff_taipei")
    if not _time(cutoff):
        errors.append("missing offset-aware data cutoff")
    nba_sources = prov.get("nba_sources", [])
    film = prov.get("film", [])
    if not isinstance(nba_sources, list) or not isinstance(film, list):
        return errors + ["sources/film must be arrays"]
    for s in nba_sources:
        if status == "VALIDATED" and (not isinstance(s, dict) or not HEX64.fullmatch(str(s.get("raw_source_sha256", "")))):
            errors.append("VALIDATED NBA source requires captured raw source SHA-256")
        if not isinstance(s, dict) or not _url(s.get("url")) or not _time(s.get("accessed_at")):
            errors.append("unverifiable NBA source URL/accessed_at")
        elif _time(cutoff) and not _at_or_before(s["accessed_at"], cutoff):
            errors.append("NBA source fetched after the pinned cutoff")
    for f in film:
        if (not isinstance(f, dict) or not _url(f.get("url"))
                or not _text(f.get("game_id")) or not _text(f.get("game_date"))
                or not _text(f.get("timestamp")) or not _text(f.get("observation"))
                or not _text(f.get("counterexample"))):
            errors.append("film evidence requires game/date/timestamp/observation/counterexample")
    if status == "VALIDATED" and (not nba_sources or not film):
        errors.append("VALIDATED requires NBA original evidence and film observations")
    owned = data.get("ownership", {})
    if not isinstance(owned, dict):
        return errors + ["ownership must be object"]
    actual = owned.get("status")
    if actual not in OWNERSHIP:
        errors.append("invalid ownership status")
    try:
        inferred, team = infer_ownership(name, aliases, roster, overlay)
    except (KeyError, TypeError, ValueError) as e:
        return errors + [f"ownership conflict: {e}"]
    if inferred != "UNKNOWN":
        if actual != inferred or owned.get("team_id") != team:
            errors.append(f"ownership mismatch: expected {inferred} / {team}")
    elif actual in ("OWNER_ROSTER", "OTHER_TEAM_ROSTER", "OWNED_TEAM_UNKNOWN", "RELEASED_AVAILABILITY_UNVERIFIED"):
        errors.append("cannot invent owned/released state")
    if actual in ("CONFIRMED_FA", "CONFIRMED_WAIVER"):
        proof = owned.get("yahoo_verification", {})
        if inferred != "UNKNOWN" or not isinstance(proof, dict) or not _url(proof.get("url")) or not _time(proof.get("checked_at")) or proof.get("status") != actual:
            errors.append("FA/waiver requires current independently verified Yahoo evidence and no conflicting owned state")
    if status == "VALIDATED" and actual == "UNKNOWN":
        errors.append("VALIDATED requires confirmed ownership/availability or explicit watch-only status")
    games = data.get("games", [])
    if not isinstance(games, list):
        return errors + ["games must be list"]
    complete = []
    for i, game in enumerate(games):
        if not isinstance(game, dict) or not _text(game.get("game_id")) or not _url(game.get("source_url")) or not _time(game.get("accessed_at")):
            errors.append(f"games[{i}]: missing original source provenance")
            continue
        if _time(cutoff) and not _at_or_before(game["accessed_at"], cutoff):
            errors.append(f"games[{i}]: original data fetched after cutoff")
        if status == "VALIDATED" and not HEX64.fullmatch(str(game.get("raw_source_sha256", ""))):
            errors.append(f"games[{i}]: captured original source SHA-256 required")
        if not isinstance(game.get("stats"), dict) or game.get("stats_sha256") != stats_sha256(game["stats"]):
            errors.append(f"games[{i}]: normalized stat payload SHA-256 mismatch")
        pts, missing = compute_game_fp(game.get("stats"), league["scoring"])
        if missing:
            if status == "VALIDATED":
                errors.append(f"games[{i}]: missing/invalid score fields {missing}")
        else:
            complete.append(pts)
        claimed = game.get("claimed_fp")
        if claimed is not None and (pts is None or not _number(claimed) or not math.isclose(pts, claimed, abs_tol=0.00001)):
            errors.append(f"games[{i}]: claimed FP differs from computed fantasy score")
    if status == "VALIDATED" and (not games or len(complete) != len(games)):
        errors.append("VALIDATED requires complete real game FP samples; missing != 0")
    claimed_avg = data.get("claimed_fp_per_game")
    if claimed_avg is not None and (not complete or len(complete) != len(games) or
          not _number(claimed_avg) or not math.isclose(sum(complete) / len(complete), claimed_avg, abs_tol=0.00001)):
        errors.append("claimed FP/G not reproducible from original game fields")
    narrative = data.get("narrative", {})
    if not isinstance(narrative, dict):
        return errors + ["narrative must be object"]
    if status == "VALIDATED" and any(not _text(narrative.get(k)) for k in
          ("offense", "defense", "role", "risk", "counterargument", "recommendation", "trigger")):
        errors.append("VALIDATED missing professional basketball, risk or decision narrative")
    scenarios = data.get("scenarios", {})
    if status == "VALIDATED":
        if not isinstance(scenarios, dict) or set(scenarios) != {"bear", "base", "bull"}:
            errors.append("VALIDATED requires bear/base/bull forecast scenarios")
        else:
            for key, case in scenarios.items():
                if not isinstance(case, dict) or not all(_number(case.get(k)) for k in
                    ("minutes", "fp_per_game", "games_per_week", "fp_per_week")) or not _text(case.get("rationale")):
                    errors.append(f"{key}: incomplete projection assumptions")
                elif not math.isclose(case["fp_per_game"] * case["games_per_week"], case["fp_per_week"], abs_tol=.0001):
                    errors.append(f"{key}: FP per week arithmetic mismatch")
        compare = data.get("comparison", {})
        if not isinstance(compare, dict) or not all(_text(compare.get(k)) for k in ("baseline_player", "rationale")):
            errors.append("VALIDATED requires real baseline comparison")
        elif not all(_number(compare.get(k)) for k in ("baseline_fp_per_game", "candidate_fp_per_game")) or not isinstance(compare.get("delta_fp_per_game"), (int, float)):
            errors.append("VALIDATED comparison lacks numeric basis")
        elif not math.isclose(compare["candidate_fp_per_game"] - compare["baseline_fp_per_game"], compare["delta_fp_per_game"], abs_tol=.0001):
            errors.append("replacement delta calculation mismatch")
    reviewer = data.get("review", {})
    if review == "PASS":
        if (not isinstance(reviewer, dict) or not _text(reviewer.get("reviewer"))
            or reviewer["reviewer"] == data.get("researcher")
            or not _time(reviewer.get("reviewed_at")) or not _url(reviewer.get("evidence_url"))):
            errors.append("review PASS requires independently attributable reviewer, time and evidence")
    # Report body is not satisfied merely by creating an empty markdown file.
    markdown = path.with_suffix(".md")
    try:
        body = markdown.read_text(encoding="utf-8")
        if len(body.strip()) < 250 or any(section not in body for section in REQUIRED_SECTIONS):
            errors.append("markdown body must contain 8 substantive report sections")
        if status == "VALIDATED" and ("[待填]" in body or "TODO" in body):
            errors.append("VALIDATED markdown still has placeholders")
    except OSError:
        errors.append("paired Markdown report missing")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path)
    p.add_argument("season_dir", type=Path)
    args = p.parse_args()
    errors = validate_report(args.report, args.season_dir)
    for e in errors:
        print("FAIL:", e)
    if errors:
        return 1
    print("PASS: scouting dossier structural, data and provenance gates (not live Yahoo/E2E verification)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
