"""Mocked GitHub publishing contract: no live GitHub writes or secrets."""
import base64
import importlib.util
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"publish_daily_report_github.py"
spec=importlib.util.spec_from_file_location("publish_daily",SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

MAIN="a"*40
ROSTERS="b"*40
LEAGUE="c"*40
def artifact(folder, status="VALIDATED"):
    date="2026-10-22"
    meta={"season":"2026-27","report_date_taipei":date,"status":status,
          "roster_commit_sha":MAIN,"rosters_blob_sha":ROSTERS,
          "league_blob_sha":LEAGUE}
    prefix="\n".join(["---"]+[f"{k}: "+json.dumps(v) for k,v in meta.items()]+["---","","# 戰報"])
    suffix=".provisional" if status=="PROVISIONAL" else ""
    path=Path(folder)/(date+suffix+".md")
    path.write_text(prefix,encoding="utf-8")
    return path

class FakeGitHub(module.Github):
    repo=module.REPO
    def __init__(self):
        self.refs={"main":MAIN}
        self.files={}
        self.prs={}
        self.calls=[]
    def request(self,method,path,payload=None):
        self.calls.append((method,path))
        if method=="GET" and path=="git/ref/heads/main":
            return {"object":{"sha":self.refs["main"]}}
        if method=="GET" and path.startswith("contents/"):
            key,_,query=path.partition("?ref=")
            ref=urllib.parse.unquote(query)
            file=urllib.parse.unquote(key[len("contents/"):])
            if ref=="main":
                if file.endswith("rosters.json"):
                    return {"sha":ROSTERS}
                if file.endswith("league.json"):
                    return {"sha":LEAGUE}
            content=self.files.get((file,ref))
            if content is None:
                raise module.GithubError(404,"no file")
            return {"content":base64.b64encode(content).decode("ascii")}
        if method=="POST" and path=="git/refs":
            ref=payload["ref"].removeprefix("refs/heads/")
            if ref in self.refs:
                raise module.GithubError(422,"branch exists")
            self.refs[ref]=payload["sha"]
            return {"ref":ref}
        if method=="PUT" and path.startswith("contents/"):
            file=urllib.parse.unquote(path[len("contents/"):])
            key=(file,payload["branch"])
            if key in self.files:
                raise module.GithubError(422,"file exists")
            self.files[key]=base64.b64decode(payload["content"])
            return {"commit":{"sha":"d"*40}}
        if method=="GET" and path.startswith("pulls?"):
            q=urllib.parse.parse_qs(path.partition("?")[2])
            b=q["head"][0].split(":",1)[1]
            return [self.prs[b]] if b in self.prs else []
        if method=="POST" and path=="pulls":
            pr={"html_url":"https://github.com/"+self.repo+"/pull/999","draft":True}
            self.prs[payload["head"]]=pr
            return pr
        raise AssertionError(f"unsupported fake request {method} {path}")

class PublisherTests(unittest.TestCase):
    def test_draft_only_idempotent_and_main_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp)
            gh=FakeGitHub()
            first=module.stage_draft_pr(gh,f)
            self.assertEqual(first["state"],"PR_PENDING")
            self.assertFalse(first["main_archived"])
            self.assertEqual(first["pr_url"],"https://github.com/"+gh.repo+"/pull/999")
            again=module.stage_draft_pr(gh,f)
            self.assertEqual(first,again)
            self.assertEqual(len(gh.prs),1)
            with self.assertRaises(module.GithubError):
                module.verify_main(gh,f)
            gh.files[(first["path"],"main")]=f.read_bytes()
            verified=module.verify_main(gh,f)
            self.assertTrue(verified["main_archived"])
            self.assertEqual(verified["sha256"],first["sha256"])
    def test_stale_repo_commit_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp)
            gh=FakeGitHub()
            gh.refs["main"]="0"*40
            with self.assertRaises(ValueError):
                module.stage_draft_pr(gh,f)
            self.assertFalse(any(m in ("POST","PUT") for m,_ in gh.calls))
    def test_provisional_is_a_distinct_archive_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp,"PROVISIONAL")
            path,_,meta=module.read_artifact(f)
            self.assertTrue(path.endswith(".provisional.md"))
            self.assertEqual(meta["status"],"PROVISIONAL")
    def test_path_and_status_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp)
            wrong=Path(tmp)/"2026-10-23.md"
            wrong.write_bytes(f.read_bytes())
            with self.assertRaises(ValueError):
                module.read_artifact(wrong)
            f2=Path(tmp)/"2026-10-22.provisional.md"
            f2.write_bytes(f.read_bytes())
            with self.assertRaises(ValueError):
                module.read_artifact(f2)
    def test_archive_version_10_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp)
            high=Path(tmp)/"2026-10-22.v10.md"
            high.write_bytes(f.read_bytes())
            path,content,meta=module.read_artifact(high)
            self.assertTrue(path.endswith("2026-10-22.v10.md"))
            self.assertEqual(meta["status"],"VALIDATED")
if __name__=="__main__":
    unittest.main()
