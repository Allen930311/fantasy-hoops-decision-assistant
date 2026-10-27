#!/usr/bin/env python3
"""Fetch official NBA schedules, box scores, and PBP for live regression runs.

Writes a compact local evidence receipt with selected regression-case stats.
Raw response bytes stay in the caller's local snapshot directory. The receipt is
not a daily report, archive, rights grant, or scheduled-production proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from nba_data_adapter import (JsonClient, NORMALIZER_VERSION, SourceError,
    acquire_game_bundle_with_fallback, acquire_schedule, normalize_schedule,
    normalizer_code_sha256, scoring_trace)

CASES={
    "andrew_wiggins":("0022600122","Andrew Wiggins","203952"),
    "pelle_larsson":("0022600122","Pelle Larsson","1641796"),
    "zaccharie_risacher":("0022600122","Zaccharie Risacher","1642258"),
    "aaron_gordon":("0022600127","Aaron Gordon","203932"),
    "justin_champagnie":("0022600119","Justin Champagnie","1630551"),
    "alperen_sengun":("0022600125","Alperen Sengun","1630578"),
}

def run(dates: list[str], snapshot_dir: Path, root: Path, replay: bool=False) -> dict:
    league=json.loads((root/"seasons/2026-27/league.json").read_text(encoding="utf-8"))
    rosters=json.loads((root/"seasons/2026-27/rosters.json").read_text(encoding="utf-8"))
    overlay=json.loads((root/"seasons/2026-27/ownership/current-state.json").read_text(encoding="utf-8"))
    owner=next(t for t in rosters["teams"] if t["team_id"]==league["owner_team_id"])
    owned=set(owner.get("players",[])+owner.get("additional_owned_players",[]))
    unassigned={x if isinstance(x,str) else x["name"] for x in overlay.get("unassigned_confirmed_owned_players",[])}
    client=JsonClient(snapshot_dir,replay=replay)
    date_rows=[]; all_games={}; all_players=[]
    for date in dates:
        if len(date)!=8 or not date.isdigit(): raise ValueError("dates must be YYYYMMDD")
        result=acquire_schedule(date,client)
        schedule=normalize_schedule(result["events"],result["provider"])
        final=[x for x in schedule if x["status"]=="Final"]
        fetched=[]
        for scheduled in final:
            gid=scheduled.get("official_game_id")
            if not gid: raise ValueError(f"Final game has no official GAME_ID: {scheduled}")
            bundle=acquire_game_bundle_with_fallback(scheduled,client)
            if bundle["status"]!="Final": raise ValueError(f"box score not final for {gid}")
            if bundle["game_date_taipei"]!=scheduled["game_date_taipei"]:
                raise ValueError(f"schedule/boxscore Taipei date mismatch for {gid}")
            if gid in all_games: raise ValueError(f"duplicate official GAME_ID {gid}")
            all_games[gid]=bundle
            fetched.append({"game_id":gid,"status":bundle["status"],
                "game_date_et":bundle["game_date_et"],"game_date_taipei":bundle["game_date_taipei"],
                "periods":bundle.get("periods"),"overtime":bundle.get("overtime"),
                "played_player_rows":len([p for p in bundle["players"] if p["status"]=="PLAYED"]),
                "dnp_player_rows":len([p for p in bundle["players"] if p["status"]=="DNP"]),
                "inactive_player_rows":len([p for p in bundle["players"] if p["status"]=="INACTIVE"]),
                "player_rows":len(bundle["players"]),
                "source_records":[{k:r[k] for k in ("provider","url","fetched_at","http_status","schema_version","raw_sha256","normalized_sha256","fetched_with_normalizer_version","fetched_with_normalizer_code_sha256","replayed_with_normalizer_version","replayed_with_normalizer_code_sha256","publication_rights","raw_snapshot_path") if k in r} for r in bundle["source_records"]],
                "normalized_sha256":bundle["normalized_sha256"],
                "normalized_by_version":NORMALIZER_VERSION,
                "normalized_by_code_sha256":normalizer_code_sha256()})
            all_players.extend(bundle["players"])
        date_rows.append({"nba_date_et":f"{date[:4]}-{date[4:6]}-{date[6:]}",
            "schedule_provider":result["provider"],"schedule_source_url":result["record"]["url"],
            "schedule_fetched_at":result["record"]["fetched_at"],"schedule_http_status":result["record"]["http_status"],
            "schedule_raw_sha256":result["record"]["raw_sha256"],"schedule_normalized_sha256":result["record"]["normalized_sha256"],
            "scheduled":sum(x["status"]=="Scheduled" for x in schedule),"live":sum(x["status"]=="Live" for x in schedule),
            "final_expected":len(final),"final_fetched":len(fetched),"games":fetched,
            "fallback_errors":result["errors"]})
    traces=[]
    for p in all_players:
        if p["status"]!="PLAYED": continue
        traces.append((p,scoring_trace(p["stats"],p["quality"],league["scoring"],events=p["incidents"])))
    by_id={p["official_player_id"]:p for p in all_players if p["status"]=="PLAYED"}
    cases={}
    for key,(gid,name,pid) in CASES.items():
        p=next((x for x in all_players if x["game_id"]==gid and x["name"]==name),None)
        if not p: raise ValueError(f"real source did not return {key} in {gid}")
        if p["official_player_id"]!=pid: raise ValueError(f"official Player ID mismatch for {key}")
        score=next(v for row,v in traces if row is p)
        cases[key]={"game_id":gid,"player_id":pid,"player_name":name,"status":score["status"],
            "fp":score["value"],"fp_trace":score["components"],"quality":score["quality"],
            "missing":score["missing"],"stats":p["stats"],"incidents":p["incidents"]}
    gordon=cases["aaron_gordon"]
    if sum(x["kind"]=="TECH" for x in gordon["incidents"])!=2 or sum(x["kind"]=="EJCT" for x in gordon["incidents"])!=1 or gordon["fp"]!="3.25":
        raise ValueError("Aaron Gordon official TECH/EJCT/FP regression mismatch")
    sengun=cases["alperen_sengun"]
    if (sengun["stats"].get("PTS"),sengun["stats"].get("REB"),sengun["stats"].get("AST"))!=(29,9,9):
        raise ValueError("Alperen Sengun 29/9/9 regression mismatch")
    champ=cases["justin_champagnie"]
    if champ["stats"].get("MIN")!="3:55":
        raise ValueError("Justin Champagnie short-appearance regression mismatch")
    # The official stats verify the short appearance, but not its injury cause.
    champ["injury_alert_status"]="SHORT_APPEARANCE_WATCH_INJURY_UNVERIFIED"
    verified=sum(t["status"]=="VERIFIED_FP" for _,t in traces)
    partial=sum(t["status"]=="PARTIAL_FP" for _,t in traces)
    blocked=sum(t["status"]=="BLOCKED" for _,t in traces)
    return {"generated_at_utc":datetime.now(timezone.utc).isoformat(),"season":league["season"],
        "normalizer_version":NORMALIZER_VERSION,"normalizer_code_sha256":normalizer_code_sha256(),
        "e2e_runner_code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "league_blob_sha256":hashlib.sha256((root/"seasons/2026-27/league.json").read_bytes()).hexdigest(),
        "rosters_blob_sha256":hashlib.sha256((root/"seasons/2026-27/rosters.json").read_bytes()).hexdigest(),
        "ownership_blob_sha256":hashlib.sha256((root/"seasons/2026-27/ownership/current-state.json").read_bytes()).hexdigest(),
        "dates":date_rows,"player_rows":len(all_players),"played_rows":len(traces),
        "dnp_rows":len([p for p in all_players if p["status"]=="DNP"]),
        "inactive_rows":len([p for p in all_players if p["status"]=="INACTIVE"]),
        "verified_fp":verified,"partial_fp":partial,"blocked_fp":blocked,
        "fp_conflicts":[{"game_id":p["game_id"],"player_id":p["official_player_id"],"name":p["name"],"missing":t["missing"],"quality":t["quality"]}
                         for p,t in traces if t["status"]!="VERIFIED_FP"],
        "owner_played_players":[{"game_id":p["game_id"],"player_id":p["official_player_id"],"name":p["name"],"fp":t["value"],"fp_status":t["status"]}
                                for p,t in traces if p["name"] in owned],
        "unassigned_overlay_excluded_from_fa":sorted(unassigned),"cases":cases,
        "fetch_errors":[x for x in client.history if "kind" in x],
        "classification":"REAL_DATA_ACQUISITION_AND_SCORING_ONLY; not report archive, not rights authorization, not production schedule evidence"}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dates",nargs="+",required=True,help="NBA ET dates YYYYMMDD; e.g. 20261024 20261025 20261026")
    p.add_argument("--snapshot-dir",type=Path,required=True,help="Local-only raw cache; do not upload without rights")
    p.add_argument("--output",type=Path,required=True,help="Local evidence receipt path")
    p.add_argument("--replay-cache",action="store_true",help="Re-run against exact raw response snapshots without network access")
    p.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args()
    evidence=run(args.dates,args.snapshot_dir,args.repo_root,args.replay_cache)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(args.output),"dates":len(evidence["dates"]),
        "final_games":sum(x["final_expected"] for x in evidence["dates"]),
        "fetched_games":sum(x["final_fetched"] for x in evidence["dates"]),
        "player_rows":evidence["player_rows"],"played_rows":evidence["played_rows"],
        "dnp_rows":evidence["dnp_rows"],"inactive_rows":evidence["inactive_rows"],
        "verified_fp":evidence["verified_fp"],
        "partial_fp":evidence["partial_fp"],"blocked_fp":evidence["blocked_fp"],
        "fetch_errors":len(evidence["fetch_errors"]),"cases":{k:{"game_id":v["game_id"],"player_id":v["player_id"],"fp":v["fp"],"status":v["status"]} for k,v in evidence["cases"].items()}},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
