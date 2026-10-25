#!/usr/bin/env python3
"""Structural contract checks for the season-scoped scouting watchlist.

Not a live Yahoo availability verifier or a completed-report factual validator.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

STATUSES = {"QUEUED", "RESEARCHING", "REVIEW_PENDING", "SCOUTED", "BLOCKED"}
PRIORITIES = {"P0", "P1", "P2", "P3"}


def _date(value, field, errors):
    try:
        dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{field}: expected ISO YYYY-MM-DD")
        return None
    return value


def validate_watchlist(season_dir: Path) -> list[str]:
    """Validate shape and safe report references, never infer live FA status."""
    errors: list[str] = []
    path = season_dir / "scouting" / "watchlist.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"watchlist unreadable: {exc}"]
    if not isinstance(data, dict):
        return ["watchlist must be an object"]
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("season") != season_dir.name:
        errors.append("season does not match directory")
    as_of = _date(data.get("as_of"), "as_of", errors)
    targets = data.get("targets")
    if not isinstance(targets, list):
        return errors + ["targets must be a list"]

    seen = set()
    reports_root = (season_dir / "scouting" / "reports").resolve()
    for idx, t in enumerate(targets):
        prefix = f"targets[{idx}]"
        if not isinstance(t, dict):
            errors.append(f"{prefix}: must be object")
            continue
        name = t.get("player_name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix}: player_name missing")
        elif name.casefold().strip() in seen:
            errors.append(f"{prefix}: duplicate player_name")
        else:
            seen.add(name.casefold().strip())
        if t.get("priority") not in PRIORITIES:
            errors.append(f"{prefix}: unknown priority")
        if t.get("status") not in STATUSES:
            errors.append(f"{prefix}: unknown status")
        if not isinstance(t.get("research_question"), str) or not t["research_question"].strip():
            errors.append(f"{prefix}: research_question missing")
        date = _date(t.get("requested_on"), f"{prefix}.requested_on", errors)
        if date and as_of and date > as_of:
            errors.append(f"{prefix}: requested_on is later than as_of")
        aliases = t.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(x, str) or not x.strip() for x in aliases):
            errors.append(f"{prefix}: aliases must be non-empty strings")
        if "availability" in t or "team_id" in t or "fantasy_points" in t:
            errors.append(f"{prefix}: research queue must not assert FA/ownership/FP facts")
        report = t.get("report_path")
        if report is None:
            if t.get("status") in {"REVIEW_PENDING", "SCOUTED"}:
                errors.append(f"{prefix}: reviewed/scouted case requires report_path")
        elif not isinstance(report, str):
            errors.append(f"{prefix}: report_path must be string or null")
        else:
            candidate = (season_dir / "scouting" / report).resolve()
            if candidate.suffix != ".md" or not candidate.is_relative_to(reports_root):
                errors.append(f"{prefix}: unsafe report_path")
            elif not candidate.is_file():
                errors.append(f"{prefix}: report_path does not exist")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("season_dir", type=Path, nargs="?", default=Path("seasons/2026-27"))
    args = parser.parse_args()
    errors = validate_watchlist(args.season_dir)
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        return 1
    print("PASS: scouting watchlist structural contract (not scouting E2E)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
