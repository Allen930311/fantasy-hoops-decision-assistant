#!/usr/bin/env python3
"""Stage one validated/provisional Fantasy report in an immutable GitHub draft PR.

This adapter does not merge PRs, change rosters, or change the scheduled task.
Requires a scoped GITHUB_TOKEN (contents:write + pull-requests:write).
No production token is stored in the repository.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from report_archive_naming import parse_archive_filename

REPO = "Allen930311/fantasy-hoops-decision-assistant"
REQUIRED = ("season","report_date_taipei","status","roster_commit_sha","rosters_blob_sha","league_blob_sha","ownership_blob_sha","data_rights_status")

class GithubError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)

def read_artifact(path):
    content = path.read_bytes()
    text = content.decode("utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing YAML front matter")
    try:
        stop = lines.index("---",1)
    except ValueError as exc:
        raise ValueError("unterminated YAML front matter") from exc
    meta = {}
    for line in lines[1:stop]:
        key, separator, value = line.partition(": ")
        if not separator:
            raise ValueError("invalid front matter line")
        meta[key] = json.loads(value)
    if any(not meta.get(k) for k in REQUIRED):
        raise ValueError("missing required report metadata")
    for key in ("roster_commit_sha", "rosters_blob_sha", "league_blob_sha", "ownership_blob_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", str(meta[key])):
            raise ValueError(f"{key} must be an immutable 40-character Git SHA-1")
    if meta["status"] not in ("VALIDATED","PROVISIONAL"):
        raise ValueError("report is not validated/provisional")
    if meta["data_rights_status"] != "AUTHORIZED_FOR_GITHUB":
        raise ValueError("source data is not authorized for public GitHub archival")
    filename = path.name
    filename_date, filename_status, _ = parse_archive_filename(filename)
    if filename_date != meta["report_date_taipei"]:
        raise ValueError("archive filename must match Taipei report date")
    if filename_status != meta["status"]:
        raise ValueError("filename status mismatch")
    if not re.fullmatch(r"20\d\d-\d\d",meta["season"]):
        raise ValueError("invalid season")
    relative_path = f"seasons/{meta['season']}/report/daily/{filename}"
    return relative_path,content,meta

class Github:
    def __init__(self, token, repo=REPO):
        if not token:
            raise ValueError("GITHUB_TOKEN missing")
        self.token, self.repo = token,repo
    def request(self, method, path, payload=None):
        url=f"https://api.github.com/repos/{self.repo}/{path}"
        body=None if payload is None else json.dumps(payload).encode("utf-8")
        request=urllib.request.Request(url,data=body,method=method,
            headers={"Authorization":"Bearer "+self.token,
                     "Accept":"application/vnd.github+json",
                     "X-GitHub-Api-Version":"2022-11-28",
                     "User-Agent":"fantasy-report-archive",
                     "Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(request,timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise GithubError(exc.code,f"GitHub {method} {path}: HTTP {exc.code}") from exc
    def file(self, path, ref):
        escaped=urllib.parse.quote(path,safe="/")
        return self.request("GET",f"contents/{escaped}?ref={urllib.parse.quote(ref,safe='')}")

def _sha(content):
    return hashlib.sha256(content).hexdigest()

def _source_paths(meta):
    season=meta["season"]
    return ((f"seasons/{season}/rosters.json","rosters_blob_sha"),
            (f"seasons/{season}/league.json","league_blob_sha"),
            (f"seasons/{season}/ownership/current-state.json","ownership_blob_sha"))

def verify_snapshot_sources(gh,meta):
    """Prove the recorded source SHAs existed at the exact captured commit."""
    ref=meta["roster_commit_sha"]
    for path,key in _source_paths(meta):
        if gh.file(path,ref)["sha"]!=meta[key]:
            raise ValueError(f"source SHA does not match snapshot commit for {path}")

def verify_current_sources(gh,meta):
    head=gh.request("GET","git/ref/heads/main")["object"]["sha"]
    # Allow unrelated main commits but require the snapshot to be an ancestor of
    # current main, and require all decision-source blobs to match current main.
    if head != meta["roster_commit_sha"]:
        comparison=gh.request("GET",f"compare/{meta['roster_commit_sha']}...{head}")
        if comparison.get("status") not in ("ahead","identical"):
            raise ValueError("roster snapshot commit is not an ancestor of current main")
    verify_snapshot_sources(gh,meta)
    for path,key in _source_paths(meta):
        if gh.file(path,"main")["sha"] != meta[key]:
            raise ValueError(f"stale source SHA for {path}")
    return head

def _readback(gh,path,branch,expected):
    response=gh.file(path,branch)
    raw=base64.b64decode(response["content"])
    if raw!=expected:
        raise ValueError("GitHub branch readback content mismatch")
    return _sha(raw)

def stage_draft_pr(gh, artifact):
    path,content,meta=read_artifact(artifact)
    head=verify_current_sources(gh,meta)
    digest=_sha(content)
    branch="fantasy-report/"+meta["report_date_taipei"]+"-"+digest[:12]
    try:
        gh.request("POST","git/refs",{"ref":"refs/heads/"+branch,"sha":head})
    except GithubError as exc:
        if exc.status != 422:
            raise
        # Branch may exist for a same-content rerun; content is verified below.
    try:
        gh.request("PUT","contents/"+urllib.parse.quote(path,safe="/"),
            {"message":"report: stage "+meta["report_date_taipei"]+" daily Fantasy archive",
             "content":base64.b64encode(content).decode("ascii"),"branch":branch})
    except GithubError as exc:
        if exc.status != 422:
            raise
        # Accept only an exact already-existing identical blob.
    _readback(gh,path,branch,content)
    owner=gh.repo.split("/")[0]
    query=urllib.parse.urlencode({"state":"open","head":owner+":"+branch,"base":"main"})
    existing=gh.request("GET","pulls?"+query)
    if existing:
        pr=existing[0]
    else:
        pr=gh.request("POST","pulls",
            {"title":"Archive Fantasy "+meta["report_date_taipei"]+" ("+meta["status"]+")",
             "head":branch,"base":"main","draft":True,
             "body":"Immutable daily report snapshot. Data status: "+meta["status"]+
                    ". Review scoring, ownership and provenance before merging. "+
                    "Do not change roster/scoring files."})
    return {"state":"PR_PENDING","pr_url":pr["html_url"],"branch":branch,
            "path":path,"sha256":digest,"main_archived":False}

def verify_main(gh, artifact):
    path,content,meta=read_artifact(artifact)
    verify_snapshot_sources(gh,meta)
    source_head=gh.request("GET","git/ref/heads/main")["object"]["sha"]
    digest=_readback(gh,path,"main",content)
    return {"state":"ARCHIVED","path":path,"sha256":digest,"main_readback_commit":source_head,"main_archived":True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("artifact",type=Path)
    p.add_argument("--verify-main",action="store_true")
    p.add_argument("--repo",default=REPO)
    args=p.parse_args()
    gh=Github(os.getenv("GITHUB_TOKEN"),args.repo)
    result=verify_main(gh,args.artifact) if args.verify_main else stage_draft_pr(gh,args.artifact)
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    main()
