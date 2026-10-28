#!/usr/bin/env python3
"""Assemble a run receipt from caller-supplied execution evidence.

This module does not fetch NBA data, run a schedule, publish to GitHub, or
write to Drive. A caller may mark a report STORED only after providing the
complete text read back from an Owner-accessible persistent destination and
explicitly attesting the target properties. Receipt fields are not a platform
signature: scheduled-task history and connector receipts must be independently
checked before treating them as production proof.
"""
from __future__ import annotations

import hashlib
import errno
import json
import os
import re
import stat
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

CONTENT = {"VALIDATED", "PROVISIONAL"}
RUNTIME = {"EXECUTED_CANONICAL", "RUNTIME_INTEGRATION_BLOCKED", "NOT_EXECUTED"}
DELIVERY = {"DELIVERED", "FAILED"}
PUBLICATION = {"PUBLISHED", "PR_PENDING", "PUBLICATION_BLOCKED", "NOT_REQUESTED"}
SOURCE_USE = {"AUTHORIZED", "UNVERIFIED", "BLOCKED"}
PUBLICATION_RIGHTS = {"AUTHORIZED", "UNVERIFIED", "BLOCKED"}
EXECUTION_MODE = {"SCHEDULED_PRODUCTION", "MANUAL_REPLAY", "CI", "SYNTHETIC", "UNKNOWN"}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SECRET_QUERY_KEY = re.compile(
    r"(^|[_-])(access[_-]?token|api[_-]?key|client[_-]?secret|consumer[_-]?secret|"
    r"subscription[_-]?key|auth|authorization|bearer|token|secret|password|passwd|"
    r"credential|signature|sig|key|private[_-]?key|session)([_-]|$)|^k$",
    re.IGNORECASE,
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_json_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def versioned_report_key(report_date: str, report_sha256: str) -> str:
    """Content-addressed private key: identical reruns are idempotent."""
    datetime.strptime(report_date, "%Y-%m-%d")
    if not re.fullmatch(r"[0-9a-f]{64}", report_sha256):
        raise ValueError("report SHA-256 must be 64 lowercase hex characters")
    return f"{report_date}/{report_sha256}.md"


def save_private_report(report_text: str, *, report_date: str,
                        storage_root: str | Path | None,
                        repo_root: str | Path,
                        owner_accessible: bool,
                        durable: bool,
                        source_use_authorized: bool,
                        storage_backend: str,
                        storage_target_id: str) -> dict[str, Any]:
    """Write one immutable report only to a configured durable private target.

    The caller must establish that the destination and the report's source use
    are authorized, Owner-accessible, and durable. This function checks path
    separation, no-overwrite behavior, and exact readback. It does not grant
    source-use rights or create a remote store. Those caller assertions are
    recorded so tests and production receipts cannot be confused.
    """
    digest = sha256_text(report_text)
    if (not storage_root or not owner_accessible or not durable
            or not source_use_authorized or not storage_backend or not storage_target_id):
        return {"storage_status": "STORAGE_BLOCKED", "location": None,
                "report_sha256": digest, "readback_sha256": None,
                "exact_readback": False, "created": False,
                "storage_backend": storage_backend or None,
                "storage_target_id": storage_target_id or None,
                "owner_accessible": bool(owner_accessible), "durable": bool(durable),
                "source_use_authorized": bool(source_use_authorized),
                "error_code": "STORAGE_OR_SOURCE_AUTHORIZATION_UNVERIFIED"}
    root = Path(storage_root).expanduser().resolve()
    repository = Path(repo_root).expanduser().resolve()
    if root == repository or repository in root.parents:
        return {"storage_status": "STORAGE_BLOCKED", "location": None,
                "report_sha256": digest, "readback_sha256": None,
                "exact_readback": False, "created": False,
                "error_code": "TARGET_INSIDE_REPOSITORY"}
    key = versioned_report_key(report_date, digest)
    path = root / key
    raw = report_text.encode("utf-8")
    created = False
    root_fd = date_fd = None
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Use directory-relative, no-follow opens for the version directory and
        # file. A pre-existing symlink must never redirect a write elsewhere.
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        root_stat = os.fstat(root_fd)
        if (not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != os.geteuid()
                or root_stat.st_mode & 0o077):
            raise PermissionError(errno.EPERM, "storage root is not private and owner-controlled")
        date_created = False
        try:
            os.mkdir(report_date, mode=0o700, dir_fd=root_fd)
            date_created = True
        except FileExistsError:
            pass
        if date_created:
            os.fsync(root_fd)
        date_fd = os.open(report_date, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=root_fd)
        date_stat = os.fstat(date_fd)
        if (not stat.S_ISDIR(date_stat.st_mode) or date_stat.st_uid != os.geteuid()
                or date_stat.st_mode & 0o077):
            raise PermissionError(errno.EPERM, "report date directory is not private and owner-controlled")
        try:
            fd = os.open(f"{digest}.md", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=date_fd)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            created = True
            os.fsync(date_fd)
        try:
            read_fd = os.open(f"{digest}.md", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=date_fd)
            with os.fdopen(read_fd, "rb") as stream:
                readback = stream.read()
        except OSError:
            raise
    except OSError as exc:
        return {"storage_status": "STORAGE_BLOCKED", "location": str(path),
                "report_sha256": digest, "readback_sha256": None,
                "exact_readback": False, "created": created,
                "storage_backend": storage_backend, "storage_target_id": storage_target_id,
                "owner_accessible": bool(owner_accessible), "durable": bool(durable),
                "source_use_authorized": bool(source_use_authorized),
                "error_code": f"{type(exc).__name__}:{exc.errno}"}
    finally:
        if date_fd is not None:
            os.close(date_fd)
        if root_fd is not None:
            os.close(root_fd)
    readback_sha = hashlib.sha256(readback).hexdigest()
    exact = readback == raw and readback_sha == digest
    return {"storage_status": "STORED" if exact else "STORAGE_BLOCKED",
            "location": str(path), "report_sha256": digest,
            "readback_sha256": readback_sha, "exact_readback": exact,
            "created": created, "storage_backend": storage_backend,
            "storage_target_id": storage_target_id,
            "owner_accessible": bool(owner_accessible), "durable": bool(durable),
            "source_use_authorized": bool(source_use_authorized),
            "error_code": None if exact else "READBACK_CONTENT_MISMATCH"}


def _timestamp(value: str, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone offset")


def report_metadata(report_text: str) -> dict[str, Any]:
    lines = report_text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("report must start with YAML front matter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("report front matter is not closed") from exc
    metadata: dict[str, Any] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(": ")
        if not sep:
            raise ValueError("report front matter must use JSON-compatible values")
        metadata[key] = json.loads(value)
    for key in ("season", "report_date_taipei", "status", "roster_commit_sha",
                "rosters_blob_sha", "league_blob_sha", "ownership_blob_sha"):
        if not metadata.get(key):
            raise ValueError(f"report front matter missing {key}")
    for key in ("roster_commit_sha", "rosters_blob_sha", "league_blob_sha", "ownership_blob_sha"):
        if not SHA40.fullmatch(str(metadata[key])):
            raise ValueError(f"{key} must be a 40-character Git object SHA")
    if metadata["status"] not in CONTENT:
        raise ValueError("report status must be VALIDATED or PROVISIONAL")
    return metadata


def _safe_url(value: Any) -> str | None:
    if value is None:
        return None
    try:
        parts = urlsplit(str(value))
    except ValueError:
        return "INVALID_URL_REDACTED"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not SECRET_QUERY_KEY.search(k)]
    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        if parts.port is not None:
            host = f"{host}:{parts.port}"
    except ValueError:
        host = "[invalid-host]"
    return urlunsplit((parts.scheme, host, parts.path, urlencode(query), ""))


def _safe_source_record(row: dict[str, Any]) -> dict[str, Any]:
    safe = {key: row[key] for key in (
        "provider", "url", "fetched_at", "http_status", "schema_version",
        "raw_sha256", "normalized_sha256", "kind", "game_id", "player_id",
    ) if row.get(key) is not None}
    if "url" in safe:
        safe["url"] = _safe_url(safe["url"])
    return safe


def _storage_evidence(expected_text: str, *, location: str | None,
                      readback_text: str | None, readback_truncated: bool,
                      error_code: str | None, storage_backend: str | None,
                      storage_target_id: str | None, storage_readback_source: str | None,
                      owner_accessible: bool, durable: bool, immutable: bool,
                      source_use_status: str) -> dict[str, Any]:
    expected_sha = sha256_text(expected_text)
    safe_location = (_safe_url(location) if location and "://" in location else location)
    authorized = source_use_status == "AUTHORIZED"
    assurance = bool(storage_backend and storage_target_id and storage_readback_source
                     and owner_accessible and durable and immutable and authorized)
    if error_code:
        return {"storage_status": "STORAGE_BLOCKED", "location": safe_location,
                "report_sha256": expected_sha, "readback_sha256": None,
                "exact_readback": False, "error_code": error_code,
                "storage_backend": storage_backend, "storage_target_id": storage_target_id,
                "storage_readback_source": storage_readback_source,
                "owner_accessible": owner_accessible, "durable": durable,
                "immutable": immutable, "source_use_authorized": authorized}
    if not assurance or not location or readback_text is None or readback_truncated:
        reason = "READBACK_UNAVAILABLE" if location else "NO_AUTHORIZED_STORAGE_TARGET"
        return {"storage_status": "STORAGE_BLOCKED", "location": safe_location,
                "report_sha256": expected_sha, "readback_sha256": None,
                "exact_readback": False,
                "error_code": reason if assurance else "STORAGE_OR_SOURCE_AUTHORIZATION_UNVERIFIED",
                "storage_backend": storage_backend, "storage_target_id": storage_target_id,
                "storage_readback_source": storage_readback_source,
                "owner_accessible": owner_accessible, "durable": durable,
                "immutable": immutable, "source_use_authorized": authorized}
    readback_sha = sha256_text(readback_text)
    exact = readback_text == expected_text and readback_sha == expected_sha
    return {"storage_status": "STORED" if exact else "STORAGE_BLOCKED",
            "location": safe_location, "report_sha256": expected_sha,
            "readback_sha256": readback_sha, "exact_readback": exact,
            "error_code": None if exact else "READBACK_CONTENT_MISMATCH",
            "storage_backend": storage_backend, "storage_target_id": storage_target_id,
            "storage_readback_source": storage_readback_source,
            "owner_accessible": owner_accessible, "durable": durable,
            "immutable": immutable, "source_use_authorized": authorized}


def build_receipt(*, report_text: str, input_payload: dict[str, Any],
                  acquisition: dict[str, Any], scheduled_for: str,
                  executed_at: str, runtime_status: str,
                  delivery_status: str, execution_mode: str,
                  source_use_status: str = "UNVERIFIED",
                  source_use_basis: str | None = None, execution_id: str | None = None,
                  runtime_error_code: str | None = None,
                  runtime_commit_sha: str | None = None,
                  latest_main_commit_sha: str | None = None,
                  runtime_evidence_source: str | None = None,
                  scheduled_task_id: str | None = None,
                  schedule_timezone: str | None = None,
                  execution_evidence_source: str | None = None,
                  delivery_report_sha256: str | None = None,
                  delivery_result_id: str | None = None,
                  delivery_evidence_source: str | None = None,
                  storage_location: str | None = None,
                  storage_backend: str | None = None,
                  storage_target_id: str | None = None,
                  storage_readback_source: str | None = None,
                  storage_owner_accessible: bool = False,
                  storage_durable: bool = False,
                  storage_immutable: bool = False,
                  storage_readback_text: str | None = None,
                  storage_readback_truncated: bool = False,
                  storage_error_code: str | None = None,
                  publication_status: str = "PUBLICATION_BLOCKED",
                  publication_reason: str | None = "SOURCE_USE_OR_PUBLICATION_RIGHTS_UNVERIFIED",
                  publication_rights_status: str = "UNVERIFIED",
                  publication_rights_basis_ref: str | None = None,
                  publication_remote_location: str | None = None,
                  publication_remote_ref: str | None = None,
                  publication_remote_commit_sha: str | None = None,
                  publication_readback_text: str | None = None,
                  validator_invoked: bool = False,
                  validator_exit_code: int | None = None) -> dict[str, Any]:
    """Assemble a receipt whose axes cannot be inferred from one another.

    ``storage_readback_text`` must come from the actual destination readback;
    ``delivery_status`` must be set by the caller only after user-facing delivery.
    This helper never performs delivery, validates external attestations, or
    treats a private copy as source-use/publication authorization. A generated
    receipt is a structured record, not proof that its caller's evidence is true.
    """
    for value, allowed, name in ((runtime_status, RUNTIME, "runtime_status"),
                                 (delivery_status, DELIVERY, "delivery_status"),
                                 (publication_status, PUBLICATION, "publication_status"),
                                 (source_use_status, SOURCE_USE, "source_use_status"),
                                 (publication_rights_status, PUBLICATION_RIGHTS, "publication_rights_status"),
                                 (execution_mode, EXECUTION_MODE, "execution_mode")):
        if value not in allowed:
            raise ValueError(f"invalid {name}: {value}")
    _timestamp(scheduled_for, "scheduled_for")
    _timestamp(executed_at, "executed_at")
    metadata = report_metadata(report_text)
    if validator_invoked and validator_exit_code is None:
        raise ValueError("validator evidence requires its exit code")
    if metadata["status"] == "VALIDATED" and not (validator_invoked and validator_exit_code == 0):
        raise ValueError("VALIDATED content requires a successful canonical validator result")
    scheduled_timing = "NOT_APPLICABLE"
    if execution_mode == "SCHEDULED_PRODUCTION" and not all(
            (execution_id, scheduled_task_id, schedule_timezone == "Asia/Taipei",
             execution_evidence_source == "automation_history")):
        raise ValueError("scheduled production receipt requires task/run IDs, Asia/Taipei timezone, and automation-history evidence")
    scheduled_dt = datetime.fromisoformat(scheduled_for.replace("Z", "+00:00"))
    executed_dt = datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
    if execution_mode == "SCHEDULED_PRODUCTION":
        scheduled_local = scheduled_dt.astimezone(ZoneInfo("Asia/Taipei"))
        if (scheduled_local.hour, scheduled_local.minute) != (15, 0):
            raise ValueError("scheduled production receipt must target 15:00 Asia/Taipei")
        if date.fromisoformat(metadata["report_date_taipei"]) != scheduled_local.date():
            raise ValueError("scheduled production report date must match scheduled Taipei date")
        scheduled_timing = ("EARLY" if executed_dt < scheduled_dt else
                            "LATE" if executed_dt > scheduled_dt else "ON_TIME")
    if source_use_status == "AUTHORIZED" and not source_use_basis:
        raise ValueError("AUTHORIZED source use requires a traceable permission basis")
    if runtime_status == "EXECUTED_CANONICAL":
        if (not runtime_commit_sha or not SHA40.fullmatch(runtime_commit_sha)
                or not latest_main_commit_sha or not SHA40.fullmatch(latest_main_commit_sha)
                or runtime_evidence_source != "canonical_runner"):
            raise ValueError("EXECUTED_CANONICAL requires exact runtime/latest-main SHAs and canonical-runner evidence")
        if runtime_commit_sha != latest_main_commit_sha or runtime_commit_sha != metadata["roster_commit_sha"]:
            raise ValueError("runtime and report source commit must match the fetched latest main SHA")
    report_sha = sha256_text(report_text)
    if delivery_status == "DELIVERED" and not all((
            delivery_report_sha256 == report_sha, delivery_result_id,
            delivery_evidence_source == "owner_facing_result")):
        raise ValueError("DELIVERED requires the exact report SHA and Owner-facing result ID evidence")
    if publication_status in {"PUBLISHED", "PR_PENDING"}:
        if (source_use_status != "AUTHORIZED" or publication_rights_status != "AUTHORIZED"
                or not publication_rights_basis_ref):
            raise ValueError("public GitHub state requires separate authorized source-use and publication-rights bases")
        valid_ref = (publication_remote_ref == "main" if publication_status == "PUBLISHED"
                     else bool(publication_remote_ref and publication_remote_ref != "main"))
        if (not valid_ref or not publication_remote_location
                or not publication_remote_commit_sha
                or not SHA40.fullmatch(publication_remote_commit_sha)):
            raise ValueError(f"{publication_status} requires exact remote location, actual ref, and commit SHA")
        if publication_readback_text != report_text:
            raise ValueError("public GitHub state requires exact remote content readback")
    report = input_payload.get("report") or {}
    schedule = input_payload.get("schedule_games") or []
    games = input_payload.get("games") or []
    final_schedule_ids = sorted(str(g["id"]) for g in schedule
                                if str(g.get("status", "")).casefold() == "final" and g.get("id"))
    final_box_ids = sorted(str(g["id"]) for g in games
                           if str(g.get("status", "")).casefold() == "final" and g.get("id"))
    missing_final = sorted(set(final_schedule_ids) - set(final_box_ids))
    summary = metadata.get("validation_summary") or {}
    records = acquisition.get("source_records") or []
    failures = acquisition.get("source_failures") or []
    storage = _storage_evidence(report_text, location=storage_location,
        readback_text=storage_readback_text,
        readback_truncated=storage_readback_truncated,
        error_code=storage_error_code, storage_backend=storage_backend,
        storage_target_id=storage_target_id, storage_readback_source=storage_readback_source,
        owner_accessible=storage_owner_accessible, durable=storage_durable,
        immutable=storage_immutable, source_use_status=source_use_status)
    receipt = {
        "schema_version": 1,
        "scheduled_for": scheduled_for,
        "executed_at": executed_at,
        "execution_mode": execution_mode,
        "execution_id": execution_id,
        "execution_evidence_source": execution_evidence_source,
        "scheduled_timing": scheduled_timing,
        "scheduled_task_id": scheduled_task_id if execution_mode == "SCHEDULED_PRODUCTION" else None,
        "schedule_timezone": schedule_timezone if execution_mode == "SCHEDULED_PRODUCTION" else None,
        "source_main_commit_sha": metadata["roster_commit_sha"],
        "runtime_status": runtime_status,
        "runtime_commit_sha": runtime_commit_sha if runtime_status == "EXECUTED_CANONICAL" else None,
        "runtime_evidence_source": runtime_evidence_source if runtime_status == "EXECUTED_CANONICAL" else None,
        "runtime_error_code": runtime_error_code if runtime_status == "RUNTIME_INTEGRATION_BLOCKED" else None,
        "source_use_status": source_use_status,
        "source_use_basis": source_use_basis if source_use_status == "AUTHORIZED" else None,
        "publication_rights_status": publication_rights_status,
        "publication_rights_basis_ref": (publication_rights_basis_ref
                                          if publication_rights_status == "AUTHORIZED" else None),
        "configuration_sha": {
            "league": metadata["league_blob_sha"],
            "rosters": metadata["rosters_blob_sha"],
            "ownership": metadata["ownership_blob_sha"],
        },
        "content_status": metadata["status"],
        "validator": {"invoked": bool(validator_invoked),
                      "exit_code": validator_exit_code,
                      "name": "daily_report_archive.validate/render" if validator_invoked else None},
        "data": {
            "data_cutoff_taipei": metadata.get("data_cutoff_taipei"),
            "schedule_provider": acquisition.get("schedule_provider"),
            "schedule_source_url": _safe_url(metadata.get("schedule_source_url")),
            "schedule_status": acquisition.get("schedule_status", "UNKNOWN"),
            "scheduled_game_count": len(schedule),
            "expected_final_game_count": len(final_schedule_ids),
            "scheduled_final_game_ids": final_schedule_ids,
            "boxscore_final_game_ids": final_box_ids,
            "missing_final_game_ids": missing_final,
            "unexpected_final_box_game_ids": sorted(set(final_box_ids) - set(final_schedule_ids)),
            "final_game_coverage": (
                len(set(final_box_ids) & set(final_schedule_ids)) / len(final_schedule_ids)
                if (acquisition.get("schedule_status") == "COMPLETE"
                    and acquisition.get("schedule_provider")
                    and acquisition.get("schedule_source_url"))
                else None) if final_schedule_ids else (
                    1.0 if acquisition.get("schedule_status") == "COMPLETE"
                    and acquisition.get("schedule_provider") and acquisition.get("schedule_source_url")
                    else None),
            "owner_players_named": len(report.get("owner_players") or []),
            "owner_coverage_status": summary.get("owner_coverage_status", "UNKNOWN"),
            "verified_fp": summary.get("fp_verified_players", 0),
            "partial_fp": summary.get("fp_partial_players", 0),
            "fp_missing": summary.get("fp_missing", {}),
            "source_record_count": len(records),
            "source_records": [_safe_source_record(row) for row in records],
            "source_failures": [_safe_source_record(row) for row in failures],
            "quality_gaps": report.get("quality_gaps", []),
        },
        "report": {"sha256": report_sha,
                   "delivery_report_sha256": delivery_report_sha256,
                   "delivery_result_id": delivery_result_id,
                   "delivery_evidence_source": delivery_evidence_source,
                   "input_sha256": deterministic_json_sha256(input_payload)},
        "delivery_status": delivery_status,
        **storage,
        "publication_status": publication_status,
        "publication_reason": publication_reason if publication_status == "PUBLICATION_BLOCKED" else None,
        "publication_remote_location": _safe_url(publication_remote_location),
        "publication_remote_ref": publication_remote_ref,
        "publication_remote_commit_sha": publication_remote_commit_sha,
        "publication_readback_sha256": (sha256_text(publication_readback_text)
                                         if publication_status in {"PUBLISHED", "PR_PENDING"} else None),
    }
    return receipt
