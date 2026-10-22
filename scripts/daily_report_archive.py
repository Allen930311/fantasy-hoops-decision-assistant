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
from datetime import date as Date

STATS = ("PTS","3PTM","OREB","DREB","AST","STL","BLK","TO","FTA","PF","TECH","EJCT","FF")
BONUSES = ("DD","TD")

def score(stats, scoring):
    missing = [key for key in STATS if key in scoring and (key not in stats or stats[key] is None)]
    if missing:
        raise ValueError("missing scoring fields: " + ",".join(missing))
    values = [stats.get("PTS", 0), stats.get("OREB", 0) + stats.get("DREB", 0),
              stats.get("AST", 0), stats.get("STL", 0), stats.get("BLK", 0)]
    double = sum(v >= 10 for v in values)
    # DD and TD are cumulative under the current league.json notes.
    flags = {"DD": int(double >= 2), "TD": int(double >= 3)}
    for k in BONUSES:
        if k in scoring and k in stats and stats[k] is not None and stats[k] != flags[k]:
            raise ValueError(f"{k} bonus disagrees with official stat-derived eligibility")
    return sum(stats.get(k, 0) * weight for k,weight in scoring.items() if k not in BONUSES) + sum(flags[k]*scoring.get(k,0) for k in BONUSES)

def _transactions_and_ownership(rosters, report):
    """Apply only fully evidenced, explicitly completed unsynced adds/drops."""
    teams = rosters["teams"]
    if len({t["team_id"] for t in teams}) != len(teams):
        raise ValueError("duplicate fantasy team ids")
    ownership = {}
    for t in teams:
        for name in t["players"]:
            if name in ownership:
                raise ValueError(f"duplicate roster ownership: {name}")
            ownership[name] = t["team_id"]
    for tx in report.get("confirmed_transactions", []):
        if tx.get("status") != "completed" or not all(
            tx.get(k) for k in ("team_id", "add", "confirmed_at", "source")
        ):
            raise ValueError("unsynced transaction lacks completed evidence")
        team_id = tx["team_id"]
        if team_id not in {t["team_id"] for t in teams}:
            raise ValueError(f"unknown transaction team: {team_id}")
        drop = tx.get("drop")
        if drop:
            if ownership.get(drop) != team_id:
                raise ValueError(f"transaction drop not owned by team: {drop}")
            del ownership[drop]
        added = tx["add"]
        if added in ownership:
            raise ValueError(f"transaction add already owned: {added}")
        ownership[added] = team_id
    # Legacy extra exclusions are only valid for FA filtering, not owner coverage.
    exclusions = report.get("confirmed_unsynced_adds", [])
    if len(exclusions) != len(set(exclusions)):
        raise ValueError("duplicate unsynced ADD exclusions")
    return ownership, set(exclusions)


def _player_rows(games, report_date):
    rows = {}
    finals = 0
    for game in games:
        if game.get("status") != "final":
            continue
        if game.get("date_taipei") != report_date:
            raise ValueError("completed game's Taipei date does not match report date")
        if not game.get("source_url") or not game.get("id"):
            raise ValueError("completed game missing source provenance")
        if not game.get("players"):
            raise ValueError("completed game without player box-score rows")
        finals += 1
        for p in game.get("players", []):
            if p.get("status") in ("DNP", "inactive", "did_not_play"):
                continue
            name = p.get("name")
            if not name or not isinstance(p.get("stats"), dict):
                raise ValueError("player row without name or stats")
            if name in rows:
                raise ValueError(f"duplicate same-day player row: {name}")
            rows[name] = p["stats"]
    if finals == 0:
        raise ValueError("no completed games")
    return rows


def _check_schedule(payload):
    """Fail closed if a completed NBA game is omitted from the box-score input."""
    schedule = payload.get("schedule_games")
    source = payload.get("schedule_source_url")
    if not isinstance(schedule, list) or not schedule or not source:
        raise ValueError("missing independent NBA schedule/game-status evidence")
    expected = [x["id"] for x in schedule if x.get("status") == "final"]
    if len(expected) != len(set(expected)):
        raise ValueError("duplicate games in schedule")
    supplied = [x["id"] for x in payload["games"] if x.get("status") == "final"]
    if len(supplied) != len(set(supplied)):
        raise ValueError("duplicate completed game ids")
    if set(supplied) != set(expected):
        raise ValueError(f"schedule coverage mismatch missing={sorted(set(expected)-set(supplied))} unexpected={sorted(set(supplied)-set(expected))}")


def _apply_identity_aliases(rows, report, ownership):
    """Identity mapping is explicit and sourced, never fuzzy or guessed."""
    for alias in report.get("identity_aliases", []):
        actual, canonical = alias.get("box_name"), alias.get("roster_name")
        if not actual or not canonical or not alias.get("source"):
            raise ValueError("identity alias must be explicit and sourced")
        if canonical not in ownership or actual not in rows:
            raise ValueError("identity alias cannot be resolved")
        if canonical in rows and actual != canonical:
            raise ValueError("identity alias collisions")
        if canonical != actual:
            rows[canonical] = rows.pop(actual)
    return rows


def validate(payload):
    league, rosters, games, report = (payload[k] for k in ("league", "rosters", "games", "report"))
    scoring = league["scoring"]
    if league["season"] != rosters.get("season"):
        raise ValueError("league/rosters season mismatch")
    unknown = set(scoring) - set(STATS) - set(BONUSES)
    if unknown:
        raise ValueError(f"unsupported scoring categories: {sorted(unknown)}")
    ownership, exclusions = _transactions_and_ownership(rosters, report)
    _check_schedule(payload)
    rows = _apply_identity_aliases(_player_rows(games, report["date"]), report, ownership)
    owner = league["owner_team_id"]
    expected = {p for p in rows if ownership.get(p) == owner}
    observed = report["owner_players"]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError(f"owner coverage mismatch missing={sorted(expected-set(observed))} extra={sorted(set(observed)-expected)}")
    others = report.get("other_players", [])
    free = report.get("free_agents", [])
    if len(others) != len(set(others)) or len(free) != len(set(free)):
        raise ValueError("duplicate featured players")
    if set(observed) & set(others + free) or set(others) & set(free):
        raise ValueError("player duplicated across report sections")
    if any(ownership.get(p) in (None, owner) for p in others):
        raise ValueError("other-team pick not owned by another fantasy team")
    if any(p in ownership or p in exclusions for p in free):
        raise ValueError("rostered or confirmed unsynced ADD misclassified as free agent")
    if any(p not in rows for p in observed + others + free):
        raise ValueError("featured player without completed-game box score")
    if not report.get("source_urls") or not report.get("body"):
        raise ValueError("missing report text or sources")
    if any(not report["provenance"].get(k) for k in ("roster_commit_sha", "rosters_blob_sha",
          "league_blob_sha", "data_cutoff_taipei", "generated_at_taipei")):
        raise ValueError("missing provenance")
    scores, missing = {}, {}
    for name in observed + others + free:
        stats = rows[name]
        if not stats.get("MIN"):
            missing[name] = "missing MIN"
            continue
        try:
            scores[name] = score(stats, scoring)
        except (TypeError, ValueError) as exc:
            missing[name] = str(exc)
    return scores, missing


def render(payload, scores, missing):
    r=payload["report"]
    status="PROVISIONAL" if missing else "VALIDATED"
    ownership,_=_transactions_and_ownership(payload["rosters"],r)
    rows=_apply_identity_aliases(_player_rows(payload["games"],r["date"]),r,ownership)
    provenance = r["provenance"]
    metadata={
        "season": payload["league"]["season"],
        "report_date_taipei": r["date"],
        "generated_at_taipei": provenance["generated_at_taipei"],
        "data_cutoff_taipei": provenance["data_cutoff_taipei"],
        "status": status,
        "roster_commit_sha": provenance["roster_commit_sha"],
        "rosters_blob_sha": provenance["rosters_blob_sha"],
        "league_blob_sha": provenance["league_blob_sha"],
        "roster_as_of": payload["rosters"].get("as_of", "UNKNOWN"),
        "schedule_source_url": payload["schedule_source_url"],
        "source_urls": r["source_urls"],
        "validation_summary": {
            "completed_games":sum(g["status"]=="final" for g in payload["games"]),
            "owner_players":len(r["owner_players"]),
            "other_players":len(r.get("other_players", [])),
            "free_agents":len(r.get("free_agents", [])),
            "fp_verified_players":len(scores),
            "fp_missing":missing
        },
        "narrative_sha256": hashlib.sha256(r["body"].encode("utf-8")).hexdigest()
    }
    # JSON strings/lists/maps are valid YAML scalars and flow collections.
    out=["---"]+[f"{k}: "+json.dumps(v,ensure_ascii=False,sort_keys=True)
                  for k,v in metadata.items()]+["---","",
         "# 每日 Fantasy 戰報資料驗證","",
         f"**狀態：{status}**。球員 FP 由 league.json 逐項計算；未核實欄位不補零。",""]
    headers=["球員","MIN","PTS","OREB","DREB","AST","STL","BLK","3PTM","TO","FTA","PF","TECH","EJCT","FF","FP"]
    for title,key in [("我的球隊（全出賽覆蓋）","owner_players"),
                      ("其他 15 隊精選","other_players"),("自由市場精選","free_agents")]:
        out.extend(["## "+title,"","| "+" | ".join(headers)+" |",
                    "| "+" | ".join(["---"]*len(headers))+" |"])
        for name in r.get(key,[]):
            s=rows[name]
            vals=[name,str(s.get("MIN","?"))]+[str(s[k]) if s.get(k) is not None else "缺" for k in headers[2:-1]]
            vals.append(f"{scores[name]:.2f}" if name in scores else "PROVISIONAL")
            out.append("| "+" | ".join(vals)+" |")
        out.append("")
    if missing:
        out.extend(["## 待補數據",""]+
                   [f"- {name}: {reason}" for name,reason in missing.items()]+[""])
    out.extend(["## 戰報正文","",r["body"].rstrip(),""])
    return "\n".join(out),status


def write_immutable(folder, date, text, status):
    if status not in ("VALIDATED", "PROVISIONAL"):
        raise ValueError("invalid archive status")
    try:
        valid_date = Date.fromisoformat(date)
        if valid_date.isoformat() != date:
            raise ValueError("noncanonical date")
    except (TypeError, ValueError) as exc:
        raise ValueError("report date must be canonical YYYY-MM-DD") from exc
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
        try:
            with path.open("x",encoding="utf-8") as stream:
                stream.write(text)
            return path,digest,True
        except FileExistsError:
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
