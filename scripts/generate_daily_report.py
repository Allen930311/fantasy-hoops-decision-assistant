#!/usr/bin/env python3
"""Fetch a Taipei-dated NBA slate and build a private, validated daily report.

NBA source snapshots and normalized report inputs are written only to a private
directory outside this checkout. Public GitHub publication remains a separate,
rights-gated operation performed by publish_daily_report_github.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from daily_report_archive import validate, render, write_immutable, player_name_key as _name_key
from nba_data_adapter import (NBA_BOXSCORE, NORMALIZER_VERSION, JsonClient, SourceError,
    acquire_game_bundle_with_fallback, acquire_schedule, normalize_schedule,
    normalizer_code_sha256, scoring_trace)

TAIPEI=ZoneInfo("Asia/Taipei")
SHORT_APPEARANCE_WATCH_SECONDS=5*60


def _minutes_seconds(value: str | None) -> int | None:
    if not isinstance(value,str) or ":" not in value: return None
    try:
        minutes,seconds=value.split(":",1)
        return int(minutes)*60+int(seconds)
    except (TypeError,ValueError):
        return None


def _read_pinned_json(root: Path, commit_sha: str, relative: str):
    committed=subprocess.check_output(["git","show",f"{commit_sha}:{relative}"],cwd=root)
    working=(root/relative).read_bytes()
    if working!=committed:
        raise ValueError(f"working-tree decision source differs from pinned commit: {relative}")
    return json.loads(committed.decode("utf-8"))


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _git_sha(root: Path, ref: str) -> str:
    return subprocess.check_output(["git","rev-parse",ref],cwd=root,text=True).strip()


def _source_blob_sha(root: Path, relative: str, commit_sha: str) -> str:
    return _git_sha(root,f"{commit_sha}:{relative}")


def _private_path(path: Path, root: Path, label: str) -> Path:
    resolved=path.resolve()
    if resolved==root.resolve() or root.resolve() in resolved.parents:
        raise ValueError(f"{label} must be outside the repository until public data rights are documented")
    return resolved


def _load_aliases(path: Path | None) -> list[dict]:
    if path is None: return []
    aliases=_read_json(path)
    if not isinstance(aliases,list): raise ValueError("identity aliases input must be a JSON array")
    for row in aliases:
        if not isinstance(row,dict) or not all(row.get(k) for k in ("box_name","roster_name","source")):
            raise ValueError("each identity alias needs box_name, roster_name and source")
    return aliases


def _record_sources(history: list[dict]) -> list[str]:
    return list(dict.fromkeys(x["url"] for x in history if x.get("url")))


def _failure(row: dict, *, impact: str) -> dict:
    return {"game_id":row.get("game_id"),"provider":row.get("provider","unknown"),
            "url":row.get("url") or "https://www.nba.com/","kind":row.get("kind","UNKNOWN"),
            "message":row.get("message","source failed without additional detail"),"impact":impact}


def generate_payload(*, root: Path, report_date: str, nba_date_et: str,
                     snapshot_dir: Path, aliases: list[dict] | None=None,
                     replay_cache: bool=False, client: JsonClient | None=None) -> tuple[dict,dict]:
    """Acquire every Final game and build the canonical validator input."""
    report_day=date.fromisoformat(report_date)
    if report_day.isoformat()!=report_date: raise ValueError("report date must be YYYY-MM-DD")
    if len(nba_date_et)!=8 or not nba_date_et.isdigit(): raise ValueError("NBA ET date must be YYYYMMDD")
    source_commit_sha=_git_sha(root,"HEAD")
    league=_read_pinned_json(root,source_commit_sha,"seasons/2026-27/league.json")
    rosters=_read_pinned_json(root,source_commit_sha,"seasons/2026-27/rosters.json")
    ownership=_read_pinned_json(root,source_commit_sha,"seasons/2026-27/ownership/current-state.json")
    alias_rows=aliases or []
    client=client or JsonClient(snapshot_dir,replay=replay_cache)
    source_failures=[]
    schedule_source_url=None
    schedule_games=[]
    games=[]
    schedule_provider=None
    schedule_status="FAILED"
    fallback_errors=[]
    try:
        schedule_result=acquire_schedule(nba_date_et,client)
        schedule_provider=schedule_result["provider"]
        schedule_source_url=schedule_result["record"]["url"]
        fallback_errors=schedule_result.get("errors",[])
        normalized=normalize_schedule(schedule_result["events"],schedule_provider)
        if schedule_provider=="espn" and any(not row.get("official_game_id") for row in normalized):
            schedule_status="PARTIAL"
            source_failures.append(_failure({"provider":"espn","url":schedule_source_url,
                "kind":"OFFICIAL_GAME_ID_UNRESOLVED","message":"ESPN schedule has no sourced NBA GAME_ID; refusing to infer a game identity"},impact="OWNER_COVERAGE_UNKNOWN"))
            normalized=[]
        else:
            schedule_status="COMPLETE"
        schedule_games=[{"id":row["official_game_id"],"status":row["status"],
                         "date_taipei":row["game_date_taipei"],"game_time_utc":row["game_time_utc"]}
                        for row in normalized if row.get("official_game_id")]
        for scheduled in normalized:
            if scheduled["status"]!="Final": continue
            gid=scheduled["official_game_id"]
            if not gid: continue
            errors_before=len(client.history)
            try:
                bundle=acquire_game_bundle_with_fallback(scheduled,client)
                if bundle.get("status")!="Final":
                    raise SourceError("nba_cdn",bundle.get("boxscore_source_url", ""),"NOT_FINAL",
                                      f"schedule says Final but box score status is {bundle.get('status')}")
                if bundle.get("game_id")!=gid:
                    raise SourceError("nba_cdn",bundle.get("boxscore_source_url", ""),"WRONG_GAME_ID",
                                      f"box score identity does not match scheduled NBA GAME_ID {gid}")
                rows=[]
                for player in bundle["players"]:
                    rows.append({"name":player.get("name"),"status":"played" if player["status"]=="PLAYED" else player["status"].casefold(),
                        "game_id":player["game_id"],"player_id":player["player_id"],
                        "official_player_id":player.get("official_player_id"),
                        "provider_player_id":player.get("provider_player_id",player.get("player_id")),
                        "identity_status":player.get("identity_status"),
                        "identity_source_url":player.get("identity_source_url"),
                        "identity_source_sha256":player.get("identity_source_sha256"),
                        "stats":player.get("stats",{}),"quality":player.get("quality",{})})
                games.append({"id":gid,"status":"final","date_taipei":bundle["game_date_taipei"],
                    "source_url":bundle["boxscore_source_url"],"raw_source_sha256":bundle["boxscore_raw_sha256"],
                    "players":rows,"periods":bundle.get("periods"),"overtime":bundle.get("overtime",False)})
                for error in bundle.get("source_errors",[]):
                    source_failures.append(_failure({**error,"game_id":gid},impact="FIELD_QUALITY_REVIEW"))
            except (SourceError,ValueError,KeyError) as exc:
                recent=client.history[errors_before:]
                entries=[x for x in recent if x.get("kind")]
                if not entries:
                    entries=[{"game_id":gid,"provider":getattr(exc,"provider","nba_cdn"),
                        "url":getattr(exc,"url",NBA_BOXSCORE.format(game_id=gid)),
                        "kind":getattr(exc,"kind","NORMALIZATION_ERROR"),"message":str(exc)}]
                for error in entries:
                    source_failures.append(_failure({**error,"game_id":gid},impact="OWNER_COVERAGE_UNKNOWN"))
                games.append({"id":gid,"status":"final","date_taipei":scheduled["game_date_taipei"],
                    "source_url":NBA_BOXSCORE.format(game_id=gid),"fetch_error":{"kind":entries[-1].get("kind")},"players":[]})
    except (SourceError,ValueError,KeyError) as exc:
        errors=[x for x in client.history if x.get("kind")]
        if not errors:
            errors=[{"provider":getattr(exc,"provider","nba_stats"),
                     "url":getattr(exc,"url","https://stats.nba.com/stats/scoreboardv3"),
                     "kind":getattr(exc,"kind","SCHEDULE_NORMALIZATION_ERROR"),"message":str(exc)}]
        for error in errors:
            source_failures.append(_failure(error,impact="OWNER_COVERAGE_UNKNOWN"))
        schedule_source_url=getattr(exc,"url",None) or "https://stats.nba.com/stats/scoreboardv3"
        schedule_provider=getattr(exc,"provider","nba_stats")

    generated=datetime.now(TAIPEI).isoformat(timespec="seconds")
    source_urls=_record_sources(client.history)
    if schedule_source_url and schedule_source_url not in source_urls: source_urls.insert(0,schedule_source_url)
    owned_by={}
    roster_name_by_key={}
    for team in rosters["teams"]:
        for name in [*team.get("players",[]),*team.get("additional_owned_players",[])]:
            key=_name_key(name)
            if key in owned_by and owned_by[key]!=team["team_id"]: raise ValueError(f"ambiguous current roster identity: {name}")
            if key in roster_name_by_key and roster_name_by_key[key]!=name:
                raise ValueError(f"ambiguous normalized roster name: {roster_name_by_key[key]} / {name}")
            owned_by[key]=team["team_id"]
            roster_name_by_key[key]=name
    unassigned={_name_key(x if isinstance(x,str) else x["name"])
                for x in ownership.get("unassigned_confirmed_owned_players",[])}
    released={_name_key(x["name"]) for x in ownership.get("released_availability_unverified",[]) if x.get("name")}
    alias_to_roster={_name_key(x["box_name"]):x["roster_name"] for x in alias_rows}
    rows=[]
    for game in games:
        for row in game["players"]:
            key=_name_key(row["name"] or "")
            canonical=alias_to_roster.get(key) or roster_name_by_key.get(key) or row["name"]
            if canonical!=row["name"] and row["status"]=="played":
                alias_key=(row["name"],canonical)
                if not any((x["box_name"],x["roster_name"])==alias_key for x in alias_rows):
                    alias_rows.append({"box_name":row["name"],"roster_name":canonical,
                        "source":f"NBA official box-score display name; PLAYER_ID {row.get('official_player_id') or row.get('player_id')}; {game.get('source_url')}"})
                alias_to_roster[key]=canonical
            rows.append({"game":game,"row":row,"name":canonical,"source_name":row["name"],
                         "team_id":owned_by.get(_name_key(canonical)),"key":_name_key(canonical)})
    scores={};row_by_name={};quality_gaps=[]
    for entry in rows:
        row=entry["row"]
        if row["status"]!="played": continue
        if entry["name"] in row_by_name:
            raise ValueError(f"duplicate same-day normalized player identity: {entry['name']}")
        row_by_name[entry["name"]]=row
        trace=scoring_trace(row["stats"],row["quality"],league["scoring"])
        scores[entry["name"]]=trace
        if trace["status"]!="VERIFIED_FP":
            quality_gaps.append({"game_id":row["game_id"],"player_id":row.get("official_player_id") or row.get("player_id"),
                "name":entry["name"],"missing":trace["missing"],"quality":trace["quality"]})
    owner_players=sorted(name for name,trace in scores.items() if owned_by.get(_name_key(name))==league["owner_team_id"])
    other_names=[name for name,trace in scores.items() if owned_by.get(_name_key(name)) not in (None,league["owner_team_id"])
                 and trace["status"]=="VERIFIED_FP"]
    other_names=sorted(other_names,key=lambda n:Decimal(scores[n]["value"]),reverse=True)[:5]
    free_names=[name for name,trace in scores.items() if _name_key(name) not in owned_by and
                _name_key(name) not in unassigned and _name_key(name) not in released and trace["status"]=="VERIFIED_FP"]
    free_names=sorted(free_names,key=lambda n:Decimal(scores[n]["value"]),reverse=True)[:3]
    claimability={name:{"confidence":"INFERRED_UNROSTERED","source_url":schedule_source_url,
        "checked_at":generated,"reason":"Not in latest repository roster/ownership files; Yahoo live waiver/FA was not checked"}
        for name in free_names}
    dnp_names=sorted({entry["name"] for entry in rows if entry["team_id"]==league["owner_team_id"] and
                      entry["row"]["status"] in ("dnp","inactive")})
    short_appearance_alerts=[]
    for entry in rows:
        row=entry["row"]
        seconds=_minutes_seconds(row.get("stats",{}).get("MIN"))
        if entry["team_id"]==league["owner_team_id"] and row["status"]=="played" and seconds is not None and 0<seconds<SHORT_APPEARANCE_WATCH_SECONDS:
            short_appearance_alerts.append({"name":entry["name"],"game_id":row["game_id"],
                "player_id":row.get("official_player_id") or row.get("player_id"),
                "minutes":row["stats"]["MIN"],"status":"SHORT_APPEARANCE_WATCH_INJURY_UNVERIFIED",
                "source_url":entry["game"].get("source_url"),
                "note":"短時間出賽只觸發追蹤；沒有來源核實傷因，不推定受傷或 DNP。"})
    live=[x for x in schedule_games if x["status"]=="Live"]
    upcoming=[x for x in schedule_games if x["status"]=="Scheduled"]
    final_count=sum(x["status"]=="Final" for x in schedule_games)
    overtime=[g["id"] for g in games if g.get("overtime")]
    overtime_unknown=[g["id"] for g in games if g.get("overtime") is None]
    body_lines=[f"# {report_date} Fantasy 每日戰報",
        f"資料按 {nba_date_et[:4]}-{nba_date_et[4:6]}-{nba_date_et[6:]} 美東賽程核對；報告生成 {generated}。",
        f"賽程來源：{schedule_provider or 'unavailable'}；Final {final_count}、Live {len(live)}、Scheduled {len(upcoming)}。",
        f"成功切換備援前的來源錯誤數：{len(fallback_errors)}；逐筆錯誤保留在 acquisition receipt。",
        "只有 Final Box Score 進入球員計分；Live/Scheduled 不當成 DNP。",
        "",
        "## Owner 球員",
        ("本日完賽賽事中，Owner 名冊出賽球員："+(", ".join(owner_players) if owner_players else "無已核實出賽資料。")),
        ("明確列為 DNP/Inactive 的 Owner 球員："+(", ".join(dnp_names) if dnp_names else "無。")),
        "每位 Owner 出賽者的逐欄數據、FP 狀態與計算列於下方驗證表。",
        f"全場已出賽球員中有 {len(quality_gaps)} 列欄位未知或互相衝突；這些列標為 PARTIAL_FP 並在缺口節列出。",
        "",
        "## 其他球隊表現",
        ("依目前 16 隊名冊，精選最高 VERIFIED_FP："+(", ".join(f"{n} ({scores[n]['value']} FP)" for n in other_names) if other_names else "沒有可核實的候選。")),
        "僅按本場資料排序，不將單場數據外推成預測。",
        "",
        "## 未列入名冊的單場候選",
        ("以下只是未出現在目前 repo roster/overlay 的表現候選，不代表 Yahoo 可領取："+
         (", ".join(f"{n} ({scores[n]['value']} FP; Claimability Confidence=INFERRED_UNROSTERED)" for n in free_names) if free_names else "無 VERIFIED_FP 候選。")),
        "Yahoo 申請於 2026-10-19 遭拒；未取得 live waiver/FA，不提出已確認可執行的 ADD。",
        "",
        "## GM 建議",
        "預設 HOLD；WATCH 需待新角色、傷病或 Yahoo 可用性證據。沒有足夠證據時不建議 DROP 或 TRADE，不執行 Yahoo roster 操作。",
        "",
        "## 傷病與資料缺口",
        "NBA box score/PBP 不提供可靠的受傷診斷；DNP 或短時間出賽不直接推論傷因。短時間出賽依下列條件發出 WATCH，傷因仍為 UNKNOWN：",
        *([f"- WATCH：{x['name']} {x['minutes']}（GAME_ID {x['game_id']}, PLAYER_ID {x['player_id']}）；僅標記短時間出賽，傷因未核實。來源：{x['source_url']}" for x in short_appearance_alerts]
          or ["- 本日沒有 Owner 球員符合短時間出賽追蹤門檻。"]),
        ("加時賽 GAME_ID："+(", ".join(overtime) if overtime else ("未知，來源未提供節數。" if overtime_unknown else "無。"))),
        f"NBA Source Terms / GitHub 公開再發布權尚未核實；本機報告標記 PRIVATE_RESEARCH_ONLY。"]
    report={"date":report_date,"owner_players":owner_players,"other_players":other_names,
        "free_agents":free_names,"free_agent_claimability":claimability,"identity_aliases":alias_rows,
        "body":"\n".join(body_lines),"source_urls":source_urls,"source_failures":source_failures,
        "quality_gaps":quality_gaps,"short_appearance_alerts":short_appearance_alerts,
        "provenance":{"roster_commit_sha":source_commit_sha,
            "rosters_blob_sha":_source_blob_sha(root,"seasons/2026-27/rosters.json",source_commit_sha),
            "league_blob_sha":_source_blob_sha(root,"seasons/2026-27/league.json",source_commit_sha),
            "ownership_blob_sha":_source_blob_sha(root,"seasons/2026-27/ownership/current-state.json",source_commit_sha),
            "roster_as_of":rosters.get("as_of"),"ownership_as_of":ownership.get("as_of"),
            "data_cutoff_taipei":generated,"generated_at_taipei":generated,
            "data_rights_status":"PRIVATE_RESEARCH_ONLY"}}
    payload={"league":league,"rosters":rosters,"ownership":ownership,"games":games,
        "schedule_games":schedule_games,"schedule_source_url":schedule_source_url or "https://stats.nba.com/stats/scoreboardv3",
        "report":report}
    acquisition={"generated_at_taipei":generated,"report_date_taipei":report_date,
        "nba_date_et":f"{nba_date_et[:4]}-{nba_date_et[4:6]}-{nba_date_et[6:]}",
        "schedule_provider":schedule_provider,"schedule_source_url":schedule_source_url,
        "schedule_status":schedule_status,"schedule_games":schedule_games,
        "source_records":client.history,"source_failures":source_failures,"fallback_errors":fallback_errors,
        "quality_gaps":quality_gaps,
        "normalizer_version":NORMALIZER_VERSION,
        "normalizer_code_sha256":normalizer_code_sha256(),
        "classification":"PRIVATE_LOCAL_REPORT; rights and public archive not authorized"}
    return payload,acquisition


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-date-taipei",default=datetime.now(TAIPEI).date().isoformat())
    parser.add_argument("--nba-date-et",help="YYYYMMDD; default is the ET date one day before Taipei report date")
    parser.add_argument("--snapshot-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--identity-aliases",type=Path,help="Optional explicit JSON alias rows: box_name, roster_name, source")
    parser.add_argument("--replay-cache",action="store_true")
    parser.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    root=args.repo_root.resolve()
    snapshot_dir=_private_path(args.snapshot_dir,root,"snapshot directory")
    output_dir=_private_path(args.output_dir,root,"report output directory")
    report_day=date.fromisoformat(args.report_date_taipei)
    nba_date_et=args.nba_date_et or (report_day-timedelta(days=1)).strftime("%Y%m%d")
    aliases=_load_aliases(args.identity_aliases)
    payload,acquisition=generate_payload(root=root,report_date=args.report_date_taipei,
        nba_date_et=nba_date_et,snapshot_dir=snapshot_dir,aliases=aliases,replay_cache=args.replay_cache)
    scores,missing=validate(payload)
    text,status=render(payload,scores,missing)
    output_dir.mkdir(parents=True,exist_ok=True)
    report_path,digest,created=write_immutable(output_dir,args.report_date_taipei,text,status)
    input_digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    input_path=output_dir/f"{args.report_date_taipei}.{input_digest[:12]}.input.json"
    input_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    acquisition_path=output_dir/f"{args.report_date_taipei}.{input_digest[:12]}.receipt.json"
    acquisition_path.write_text(json.dumps(acquisition,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"content_status":status,"archive_state":"ARCHIVE_BLOCKED",
        "archive_reason":"PRIVATE_RESEARCH_ONLY; public GitHub rights are unverified",
        "report_path":str(report_path),"report_sha256":digest,"created":created,
        "input_path":str(input_path),"acquisition_receipt":str(acquisition_path),
        "schedule_games":len(payload["schedule_games"]),
        "final_games":sum(x["status"]=="Final" for x in payload["schedule_games"]),
        "owner_players":len(payload["report"]["owner_players"]),
        "verified_fp":sum(n not in missing for n in scores),"partial_fp":sum(n in missing for n in scores),
        "source_failures":len(payload["report"].get("source_failures",[])),
        "quality_gaps":len(payload["report"].get("quality_gaps",[])),
        "replay_cache":args.replay_cache},ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
