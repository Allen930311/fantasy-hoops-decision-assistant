#!/usr/bin/env python3
"""Independent, offline daily-report validator and immutable local writer.

Input JSON schema: league (league.json object), rosters (rosters.json object),
ownership (current-state.json object),
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
import re
import unicodedata
from pathlib import Path
from datetime import date as Date
from urllib.parse import urlparse
from nba_data_adapter import calculate_custom_fp
from report_archive_naming import next_archive_path

STATS = ("PTS","3PTM","OREB","DREB","AST","STL","BLK","TO","FTA","PF","TECH","EJCT","FF")
BONUSES = ("DD","TD")
QUALITY_STATES = {"VERIFIED_VALUE","VERIFIED_ZERO","THIRD_PARTY_RECONSTRUCTED","CONFLICTING","UNKNOWN"}

def player_name_key(value):
    """Normalize harmless display differences while leaving identity explicit.

    Accents, case, whitespace, and periods (notably the ``Jr.`` suffix) do not
    distinguish NBA player identities. Other punctuation is preserved. Every
    roster/overlay collision is checked before this key is used for ownership.
    """
    if not isinstance(value,str):
        raise ValueError("player identity must be a string")
    folded=unicodedata.normalize("NFKD",value).casefold()
    unmarked="".join(char for char in folded if unicodedata.category(char)!="Mn")
    return " ".join(unmarked.replace(".","").split())

def score(stats, scoring):
    result=calculate_custom_fp(stats,scoring)
    if result["missing"]:
        if "CONFLICTING_REB" in result["missing"]:
            raise ValueError("conflicting REB total: OREB + DREB does not reconcile")
        if "DD_TD_INCONSISTENT" in result["missing"]:
            raise ValueError("DD/TD bonus disagrees with official stat-derived eligibility")
        raise ValueError("missing or invalid scoring fields: " + ",".join(result["missing"]))
    return result["value"]

def _transactions_and_ownership(rosters, report, overlay):
    """Apply only fully evidenced, explicitly completed unsynced adds/drops."""
    teams = rosters["teams"]
    if len({t["team_id"] for t in teams}) != len(teams):
        raise ValueError("duplicate fantasy team ids")
    ownership = {}
    ownership_by_key = {}
    for t in teams:
        for name in list(t.get("players", [])) + list(t.get("additional_owned_players", [])):
            if name in ownership:
                raise ValueError(f"duplicate roster ownership: {name}")
            key=player_name_key(name)
            if key in ownership_by_key:
                raise ValueError(f"ambiguous normalized roster identity: {ownership_by_key[key]} / {name}")
            ownership[name] = t["team_id"]
            ownership_by_key[key] = name
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
            drop_key=player_name_key(drop)
            actual_drop=ownership_by_key.get(drop_key)
            if actual_drop is None or ownership.get(actual_drop) != team_id:
                raise ValueError(f"transaction drop not owned by team: {drop}")
            del ownership[actual_drop]
            del ownership_by_key[drop_key]
        added = tx["add"]
        added_key=player_name_key(added)
        if added_key in ownership_by_key:
            raise ValueError(f"transaction add already owned: {added}")
        ownership[added] = team_id
        ownership_by_key[added_key] = added
    # Current effective ADD overlay is authoritative; do not union dated files.
    unassigned=[]
    for player in overlay.get("unassigned_confirmed_owned_players", []):
        name = player if isinstance(player, str) else player.get("name")
        if not name: raise ValueError("invalid unassigned ownership entry")
        unassigned.append(player_name_key(name))
    if len(unassigned) != len(set(unassigned)):
        raise ValueError("duplicate unassigned confirmed ownership")
    if set(unassigned) & set(ownership_by_key):
        raise ValueError("unassigned ownership conflicts with roster ownership")
    # Legacy exclusions are only valid for FA filtering, not owner coverage.
    exclusions = report.get("confirmed_unsynced_adds", [])
    exclusion_keys=[player_name_key(name) for name in exclusions]
    if len(exclusion_keys) != len(set(exclusion_keys)):
        raise ValueError("duplicate unsynced ADD exclusions")
    return ownership, set(exclusion_keys) | set(unassigned)


def _player_rows(games, report_date):
    rows = {}
    finals = 0
    for game in games:
        if str(game.get("status","")).casefold() != "final":
            continue
        if game.get("date_taipei") != report_date:
            raise ValueError("completed game's Taipei date does not match report date")
        if not game.get("source_url") or not game.get("id"):
            raise ValueError("completed game missing source provenance")
        if not game.get("players") and not game.get("fetch_error"):
            raise ValueError("completed game without player box-score rows")
        finals += 1
        if not game.get("players"):
            continue
        for p in game.get("players", []):
            status=str(p.get("status", "")).casefold().strip().replace("_"," ")
            if status in ("dnp", "inactive", "did not play") or status.startswith("dnp-") or status.startswith("dnp "):
                continue
            name = p.get("name")
            if status!="played":
                raise ValueError(f"{name or 'player'}: unknown game participation status {p.get('status')!r}")
            if not name or not isinstance(p.get("stats"), dict):
                raise ValueError("player row without name or stats")
            if (p.get("game_id") != game.get("id") or not p.get("player_id") or
                    not str(game.get("id", "")).isdigit() or len(str(game.get("id"))) != 10):
                raise ValueError(f"{name}: missing or mismatched GAME_ID/PLAYER_ID")
            if name in rows:
                raise ValueError(f"duplicate same-day player row: {name}")
            stats=dict(p["stats"])
            stats["__quality__"]=p.get("quality", {})
            stats["__official_player_id__"]=p.get("official_player_id")
            stats["__identity_status__"]=p.get("identity_status")
            stats["__identity_source__"]=p.get("identity_source_url")
            stats["__identity_source_sha256__"]=p.get("identity_source_sha256")
            stats["__provider_player_id__"]=p.get("provider_player_id", p.get("player_id"))
            stats["__player_id__"]=p.get("player_id")
            stats["__game_source_url__"]=game.get("source_url")
            stats["__game_source_sha256__"]=game.get("raw_source_sha256")
            rows[name] = stats
    return rows


def _check_schedule(payload):
    """Fail closed if a completed NBA game is omitted from the box-score input."""
    schedule = payload.get("schedule_games")
    source = payload.get("schedule_source_url")
    if not isinstance(schedule, list) or not source:
        raise ValueError("missing independent NBA schedule/game-status evidence")
    for x in schedule:
        gid=str(x.get("id", ""))
        if not gid.isdigit() or len(gid) != 10:
            raise ValueError("schedule row lacks official NBA GAME_ID")
        if x.get("status") not in ("final","live","scheduled","Final","Live","Scheduled"):
            raise ValueError(f"unknown schedule game status: {x.get('status')}")
    expected = [x["id"] for x in schedule if str(x.get("status","")).casefold() == "final"]
    if len(expected) != len(set(expected)):
        raise ValueError("duplicate games in schedule")
    supplied = [x["id"] for x in payload["games"] if str(x.get("status","")).casefold() == "final"]
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
    league, rosters, games, report, overlay = (payload[k] for k in ("league", "rosters", "games", "report", "ownership"))
    scoring = league["scoring"]
    if league["season"] != rosters.get("season"):
        raise ValueError("league/rosters season mismatch")
    unknown = set(scoring) - set(STATS) - set(BONUSES)
    if unknown:
        raise ValueError(f"unsupported scoring categories: {sorted(unknown)}")
    ownership, exclusions = _transactions_and_ownership(rosters, report, overlay)
    ownership_by_key={player_name_key(name):team for name,team in ownership.items()}
    _check_schedule(payload)
    source_failures=report.get("source_failures", [])
    if not isinstance(source_failures,list):
        raise ValueError("report source_failures must be a list")
    final_ids={x["id"] for x in payload["schedule_games"] if str(x.get("status","")).casefold()=="final"}
    for failure in source_failures:
        if not isinstance(failure,dict) or not all(failure.get(k) for k in ("provider","url","kind","message","impact")):
            raise ValueError("source failure must include provider, URL, kind, message and impact")
        if failure["impact"] not in ("OWNER_COVERAGE_UNKNOWN","FIELD_QUALITY_REVIEW"):
            raise ValueError(f"unknown source failure impact: {failure['impact']}")
        if failure.get("game_id") is not None and failure["game_id"] not in final_ids:
            raise ValueError("source failure references a game that is not Final in the schedule")
    quality_gaps=report.get("quality_gaps", [])
    if not isinstance(quality_gaps,list):
        raise ValueError("report quality_gaps must be a list")
    rows = _apply_identity_aliases(_player_rows(games, report["date"]), report, ownership)
    owner = league["owner_team_id"]
    expected = {p for p in rows if ownership_by_key.get(player_name_key(p)) == owner}
    observed = report["owner_players"]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError(f"owner coverage mismatch missing={sorted(expected-set(observed))} extra={sorted(set(observed)-expected)}")
    others = report.get("other_players", [])
    free = report.get("free_agents", [])
    if len(others) != len(set(others)) or len(free) != len(set(free)):
        raise ValueError("duplicate featured players")
    if set(observed) & set(others + free) or set(others) & set(free):
        raise ValueError("player duplicated across report sections")
    if any(ownership_by_key.get(player_name_key(p)) in (None, owner) for p in others):
        raise ValueError("other-team pick not owned by another fantasy team")
    if any(player_name_key(p) in ownership_by_key or player_name_key(p) in exclusions for p in free):
        raise ValueError("rostered or confirmed unsynced ADD misclassified as free agent")
    claimability=report.get("free_agent_claimability", {})
    for name in free:
        evidence=claimability.get(name)
        if not isinstance(evidence,dict) or evidence.get("confidence") not in ("CONFIRMED_CLAIMABLE","WAIVER_UNVERIFIED","INFERRED_UNROSTERED","UNKNOWN"):
            raise ValueError(f"free-agent recommendation missing Claimability Confidence: {name}")
        if evidence["confidence"] == "CONFIRMED_CLAIMABLE" and not all(evidence.get(k) for k in ("source_url","checked_at")):
            raise ValueError(f"confirmed claimability lacks current evidence: {name}")
        released={x.get("name") for x in overlay.get("released_availability_unverified", []) if isinstance(x,dict)}
        if name in released and evidence["confidence"] == "CONFIRMED_CLAIMABLE":
            raise ValueError(f"released player needs newer Yahoo availability evidence: {name}")
    if any(p not in rows for p in observed + others + free):
        raise ValueError("featured player without completed-game box score")
    if not report.get("source_urls") or not report.get("body"):
        raise ValueError("missing report text or sources")
    if any(not report["provenance"].get(k) for k in ("roster_commit_sha", "rosters_blob_sha",
          "league_blob_sha", "ownership_blob_sha", "data_cutoff_taipei", "generated_at_taipei", "data_rights_status")):
        raise ValueError("missing provenance")
    if report["provenance"]["data_rights_status"] not in ("AUTHORIZED_FOR_GITHUB","PRIVATE_RESEARCH_ONLY"):
        raise ValueError("unknown source data publication-rights status")
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
            continue
        quality=stats.get("__quality__") or {}
        if stats.get("REB") is not None and stats.get("OREB") is not None and stats.get("DREB") is not None and stats["REB"]!=stats["OREB"]+stats["DREB"]:
            quality={**quality,"OREB":"CONFLICTING","DREB":"CONFLICTING"}
        invalid={k:quality.get(k,"UNKNOWN") for k in scoring if k not in BONUSES
                 and quality.get(k,"UNKNOWN") not in ("VERIFIED_VALUE","VERIFIED_ZERO")}
        official_id=stats.get("__official_player_id__")
        source=stats.get("__identity_source__")
        parsed=urlparse(source or "")
        source_hash=stats.get("__identity_source_sha256__")
        allowed_hosts={"nba.com","www.nba.com","cdn.nba.com","stats.nba.com"}
        same_game_source=(source==stats.get("__game_source_url__") and source_hash==stats.get("__game_source_sha256__"))
        same_provider_id=(str(stats.get("__provider_player_id__"))==str(official_id)==str(stats.get("__player_id__")))
        identity_evidence=(parsed.scheme=="https" and parsed.hostname in allowed_hosts and same_game_source and
                           bool(re.fullmatch(r"[0-9a-f]{64}",str(source_hash or ""))))
        if not (official_id and str(official_id).isdigit() and stats.get("__identity_status__")=="VERIFIED" and same_provider_id and identity_evidence):
            invalid["NBA_PLAYER_ID"]="UNKNOWN"
        bad_states={k:v for k,v in invalid.items() if v not in QUALITY_STATES and k != "NBA_PLAYER_ID"}
        if bad_states:
            raise ValueError(f"invalid field quality for {name}: {bad_states}")
        if invalid:
            missing[name]="PARTIAL_FP: unverified fields " + ",".join(sorted(invalid))
    return scores, missing


def render(payload, scores, missing):
    r=payload["report"]
    has_pending_games=any(str(g.get("status","")).casefold() in ("live","scheduled") for g in payload.get("schedule_games",[]))
    status="PROVISIONAL" if missing or has_pending_games or r.get("source_failures") or r.get("quality_gaps") else "VALIDATED"
    ownership,_=_transactions_and_ownership(payload["rosters"],r,payload["ownership"])
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
        "ownership_blob_sha": provenance["ownership_blob_sha"],
        "data_rights_status": provenance["data_rights_status"],
        "roster_as_of": payload["rosters"].get("as_of", "UNKNOWN"),
        "schedule_source_url": payload["schedule_source_url"],
        "source_urls": r["source_urls"],
        "validation_summary": {
            "completed_games":sum(str(g["status"]).casefold()=="final" for g in payload["games"]),
            "owner_players":len(r["owner_players"]),
            "other_players":len(r.get("other_players", [])),
            "free_agents":len(r.get("free_agents", [])),
            "source_failures":len(r.get("source_failures", [])),
            "quality_gaps":len(r.get("quality_gaps", [])),
            "owner_coverage_status":"UNKNOWN_DUE_TO_SOURCE_GAP" if any(x.get("impact")=="OWNER_COVERAGE_UNKNOWN" for x in r.get("source_failures",[])) else "MATCHED_TO_AVAILABLE_FINAL_ROWS",
            "fp_verified_players":sum(1 for n in scores if n not in missing),
            "fp_partial_players":sum(1 for n in scores if n in missing),
            "fp_missing":missing
        },
        "narrative_sha256": hashlib.sha256(r["body"].encode("utf-8")).hexdigest()
    }
    # JSON strings/lists/maps are valid YAML scalars and flow collections.
    out=["---"]+[f"{k}: "+json.dumps(v,ensure_ascii=False,sort_keys=True)
                  for k,v in metadata.items()]+["---","",
         "# 每日 Fantasy 戰報資料驗證","",
         f"**狀態：{status}**。球員 FP 由 league.json 逐項計算；未核實欄位不補零。",""]
    headers=["球員","MIN","PTS","OREB","DREB","AST","STL","BLK","3PTM","TO","FTA","PF","TECH","EJCT","FF","FP","Claimability Confidence"]
    for title,key in [("我的球隊（全出賽覆蓋）","owner_players"),
                      ("其他 15 隊精選","other_players"),("自由市場精選","free_agents")]:
        out.extend(["## "+title,"","| "+" | ".join(headers)+" |",
                    "| "+" | ".join(["---"]*len(headers))+" |"])
        for name in r.get(key,[]):
            s=rows[name]
            vals=[name,str(s.get("MIN","?"))]+[str(s[k]) if s.get(k) is not None else "缺" for k in headers[2:15]]
            vals.append((f"{scores[name]:.2f}" if name not in missing else f"PARTIAL_FP {scores[name]:.2f}") if name in scores else "BLOCKED")
            vals.append(r.get("free_agent_claimability", {}).get(name,{}).get("confidence","—"))
            out.append("| "+" | ".join(vals)+" |")
        out.append("")
    if r.get("source_failures"):
        out.extend(["## 資料來源失敗 / 尚待覆核","", "下列來源請求失敗或未完成；依 impact 欄位確認其影響。缺少 box score 時，不可解讀為 DNP、缺席或零 FP。"]+
                   [f"- {x.get('game_id','schedule')}: {x['provider']} {x['kind']} — {x['message']} ({x['url']})" for x in r["source_failures"]]+[""])
    if r.get("quality_gaps"):
        out.extend(["## 全場欄位品質缺口","", "以下出賽列未達 VERIFIED_FP；衝突或未知欄位未補零。"]+
                   [f"- {x.get('game_id','?')} / {x.get('player_id','?')} / {x.get('name','?')}: {', '.join(x.get('missing',[]))}" for x in r["quality_gaps"]]+[""])
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
    digest=hashlib.sha256(text.encode("utf-8")).hexdigest()
    for p in folder.glob(date+"*.md"):
        if p.read_bytes()==text.encode("utf-8"):
            return p,digest,False
    while True:
        path=next_archive_path(folder,date,status)
        try:
            with path.open("x",encoding="utf-8") as stream:
                stream.write(text)
            return path,digest,True
        except FileExistsError:
            continue

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
