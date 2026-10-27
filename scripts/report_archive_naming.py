"""Canonical immutable daily archive filenames and safe legacy parsing."""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path

def parse_archive_filename(filename: str) -> tuple[str,str,int]:
    """Return (YYYY-MM-DD, VALIDATED|PROVISIONAL, version).

    New names put status before the optional version (date.provisional.v2.md).
    Historical date.v2.provisional.md names remain readable.
    """
    forms=(
        r"(?P<date>\d{4}-\d{2}-\d{2})(?P<status>\.provisional)?(?P<version>\.v[1-9]\d*)?\.md",
        r"(?P<date>\d{4}-\d{2}-\d{2})(?P<version>\.v[1-9]\d*)(?P<status>\.provisional)\.md",
    )
    match=next((m for p in forms if (m:=re.fullmatch(p,filename))),None)
    if not match: raise ValueError("invalid daily report filename")
    report_date=match.group("date")
    if date.fromisoformat(report_date).isoformat()!=report_date: raise ValueError("invalid daily report date")
    version=int(match.group("version")[2:]) if match.group("version") else 1
    return report_date,"PROVISIONAL" if match.group("status") else "VALIDATED",version

def filename_for(report_date: str,status: str,version: int) -> str:
    if status not in ("VALIDATED","PROVISIONAL") or version<1: raise ValueError("invalid archive status/version")
    suffix=".provisional" if status=="PROVISIONAL" else ""
    label="" if version==1 else f".v{version}"
    return f"{report_date}{suffix}{label}.md"

def next_archive_path(folder: Path,report_date: str,status: str) -> Path:
    versions=[]
    for path in folder.glob(report_date+"*.md"):
        try: parsed_date,parsed_status,version=parse_archive_filename(path.name)
        except ValueError: continue
        if parsed_date==report_date and parsed_status==status: versions.append(version)
    return folder/filename_for(report_date,status,max(versions,default=0)+1)
