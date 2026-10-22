#!/usr/bin/env python3
"""Independent, offline daily-report validator and immutable local writer.

Input JSON schema: league (league.json object), rosters (rosters.json object),
games (list of {id,status,players:[{name,stats:{...}}]}),
report ({date,owner_players:[names],free_agents:[names],body,source_urls:[urls],
         provenance:{roster_commit_sha,rosters_blob_sha,league_blob_sha,
                     data_cutoff_taipei,generated_at_taipei}}).
No network, GitHub mutation, Yahoo or roster edits.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

STATS = ("PTS","3PTM","OREB","DREB","AST","STL","BLK","TO","FTA","PF","TECH","EJCT","FF")
BONUSES = ("DD","TD")

def score(stats, scoring):
    missing = [key for key in STATS if key in scoring and (key not in stats or stats[key] is None)]
    if missing:
        raise ValueError("missing scoring fields: " + ",".join(missing))
    values = [stats.get(k, 0) for k in ("PTS","OREB","DREB","AST","STL","BLK")]
    double = sum(v >= 10 for v in values)
    # DD and TD are cumulative under the current league.json notes.
    flags = {"DD": int(double >= 2), "TD": int(double >= 3)}
    for k in BONUSES:
        if k in scoring and k in stats and stats[k] is not None and stats[k] != flags[k]:
            raise ValueError(f"{k} bonus disagrees with official stat-derived eligibility")
    return sum(stats.get(k, 0) * weight for k,weight in scoring.items() if k not in BONUSES) + sum(flags[k]*scoring.get(k,0) for k in BONUSES)

def validate(payload):
    league, rosters, games, report = (payload[k] for k in ("league","rosters","games","report"))
    scoring = league["scoring"]
    owner = league["owner_team_id"]
    teams = rosters["teams"]
    owned = {p for t in teams for p in t["players"]}
    mine = next(t for t in teams if t["team_id"] == owner)["players"]
    completed = [g for g in games if g["status"] == "final"]
    players = {p["name"]: p["stats"] for g in completed for p in g["players"]}
    expected = set(mine) & set(players)
    observed = report["owner_players"]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError(f"owner coverage mismatch missing={sorted(expected-set(observed))} extra={sorted(set(observed)-expected)}")
    if not completed:
        raise ValueError("no completed games")
    if any(p in owned for p in report["free_agents"]):
        raise ValueError("rostered player misclassified as free agent")
    unsynced = set(report.get("confirmed_unsynced_adds", []))
    if unsynced & set(report["free_agents"]):
        raise ValueError("confirmed unsynced ADD misclassified as free agent")
    if not report.get("source_urls") or not report.get("body"):
        raise ValueError("missing report text or sources")
    if any(not report["provenance"].get(k) for k in ("roster_commit_sha","rosters_blob_sha","league_blob_sha","data_cutoff_taipei","generated_at_taipei")):
        raise ValueError("missing provenance")
    result = {}
    missing = {}
    for name in observed:
        try:
            result[name] = score(players[name], scoring)
        except ValueError as exc:
            missing[name] = str(exc)
    return result, missing

def render(payload, scores, missing):
    r=payload["report"]
    status="PROVISIONAL" if missing else "VALIDATED"
    metadata={"season":payload["league"]["season"],"report_date_taipei":r["date"],"status":status,
              "provenance":r["provenance"],"source_urls":r["source_urls"],"fp":scores,
              "missing":missing}
    return "<!-- daily-fantasy-report metadata: "+json.dumps(metadata,ensure_ascii=False,sort_keys=True)+" -->\n"+r["body"].rstrip()+"\n",status

def write_immutable(folder, date, text, status):
    folder.mkdir(parents=True,exist_ok=True)
    suffix=".provisional" if status=="PROVISIONAL" else ""
    digest=hashlib.sha256(text.encode("utf-8")).hexdigest()
    for p in folder.glob(date+"*.md"):
        if p.read_bytes()==text.encode("utf-8"):
            return p,digest,False
    index=1
    while True:
        label="" if index==1 else f".v{index}"
        path=folder/f"{date}{suffix}{label}.md"
        if not path.exists():
            path.write_text(text,encoding="utf-8")
            return path,digest,True
        index+=1

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input_json",type=Path)
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args()
    payload=json.loads(args.input_json.read_text(encoding="utf-8"))
    scores,missing=validate(payload)
    text,status=render(payload,scores,missing)
    path,digest,created=write_immutable(args.output_dir,payload["report"]["date"],text,status)
    print(json.dumps({"path":str(path),"sha256":digest,"created":created,"status":status,"missing":missing},ensure_ascii=False))
if __name__=="__main__":
    main()
