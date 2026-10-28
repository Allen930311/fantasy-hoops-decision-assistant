"""Mocked GitHub publishing contract: no live GitHub writes or secrets."""
import base64
import importlib.util
import json
import os
import sys
import subprocess
import tempfile
import unittest
import urllib.parse
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"publish_daily_report_github.py"
sys.path.insert(0,str(SCRIPT.parent))
spec=importlib.util.spec_from_file_location("publish_daily",SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

MAIN="a"*40
ROSTERS="b"*40
LEAGUE="c"*40
OWNERSHIP="e"*40
def artifact(folder, status="VALIDATED"):
    date="2026-10-22"
    meta={"season":"2026-27","report_date_taipei":date,"status":status,
          "roster_commit_sha":MAIN,"rosters_blob_sha":ROSTERS,
          "league_blob_sha":LEAGUE,"ownership_blob_sha":OWNERSHIP,
          "data_rights_status":"AUTHORIZED_FOR_GITHUB"}
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
        self.comparison_status="ahead"
        self.current_source_changes=False
    def request(self,method,path,payload=None):
        self.calls.append((method,path))
        if method=="GET" and path=="git/ref/heads/main":
            return {"object":{"sha":self.refs["main"]}}
        if method=="GET" and path.startswith("compare/"):
            return {"status":self.comparison_status}
        if method=="GET" and path.startswith("contents/"):
            key,_,query=path.partition("?ref=")
            ref=urllib.parse.unquote(query)
            file=urllib.parse.unquote(key[len("contents/"):])
            if ref in ("main",MAIN):
                if file.endswith("rosters.json"):
                    return {"sha":"1"*40 if ref=="main" and self.current_source_changes else ROSTERS}
                if file.endswith("league.json"):
                    return {"sha":"2"*40 if ref=="main" and self.current_source_changes else LEAGUE}
                if file.endswith("ownership/current-state.json"):
                    return {"sha":"3"*40 if ref=="main" and self.current_source_changes else OWNERSHIP}
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
            gh.comparison_status="behind"
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

    def test_unrelated_main_commit_is_allowed_when_source_blobs_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp);gh=FakeGitHub();gh.refs["main"]="0"*40
            gh.comparison_status="ahead"
            self.assertEqual(module.stage_draft_pr(gh,f)["state"],"PR_PENDING")

    def test_snapshot_commit_must_contain_recorded_source_blobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp);f.write_text(f.read_text().replace(ROSTERS,"f"*40))
            gh=FakeGitHub()
            with self.assertRaisesRegex(ValueError,"does not match snapshot commit"):
                module.stage_draft_pr(gh,f)
            self.assertFalse(any(m in ("POST","PUT") for m,_ in gh.calls))

    def test_symbolic_snapshot_ref_is_not_an_immutable_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp)
            f.write_text(f.read_text().replace(MAIN,"main"))
            gh=FakeGitHub()
            with self.assertRaisesRegex(ValueError,"immutable 40-character Git SHA-1"):
                module.stage_draft_pr(gh,f)
            self.assertEqual(gh.calls,[])

    def test_non_sha_source_blob_is_rejected_before_remote_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp)
            f.write_text(f.read_text().replace(ROSTERS,"not-a-blob-sha"))
            gh=FakeGitHub()
            with self.assertRaisesRegex(ValueError,"immutable 40-character Git SHA-1"):
                module.stage_draft_pr(gh,f)
            self.assertEqual(gh.calls,[])

    def test_archived_readback_survives_later_source_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp);gh=FakeGitHub()
            gh.files[(f"seasons/2026-27/report/daily/{f.name}","main")]=f.read_bytes()
            gh.current_source_changes=True
            result=module.verify_main(gh,f)
            self.assertEqual(result["state"],"ARCHIVED")
            self.assertEqual(result["main_readback_commit"],MAIN)

    def test_historical_version_provisional_filename_roundtrip(self):
        self.assertEqual(module.parse_archive_filename("2026-10-27.v2.provisional.md"),
                         ("2026-10-27","PROVISIONAL",2))

    def test_unverified_publication_rights_block_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp)
            body=f.read_text().replace('"AUTHORIZED_FOR_GITHUB"','"PRIVATE_RESEARCH_ONLY"')
            f.write_text(body)
            with self.assertRaisesRegex(module.ArchiveBlockedError,"PRIVATE_RESEARCH_ONLY"):
                module.read_artifact(f)
        self.assertEqual(module.parse_archive_filename("2026-10-27.provisional.v2.md"),
                         ("2026-10-27","PROVISIONAL",2))

    def test_cli_reports_rights_block_before_token_or_remote_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=artifact(tmp)
            f.write_text(f.read_text().replace('"AUTHORIZED_FOR_GITHUB"','"PRIVATE_RESEARCH_ONLY"'))
            env=os.environ.copy()
            env.pop("GITHUB_TOKEN",None)
            result=subprocess.run([sys.executable,str(SCRIPT),str(f)],capture_output=True,
                                  text=True,env=env,check=False)
            self.assertEqual(result.returncode,0,result.stderr)
            body=json.loads(result.stdout)
            self.assertEqual(body["state"],"ARCHIVE_BLOCKED")
            self.assertIn("PRIVATE_RESEARCH_ONLY",body["reason"])
            self.assertFalse(body["github_request_made"])

    def test_writer_filename_roundtrips_through_publisher_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft=artifact(tmp,"PROVISIONAL")
            writer_style=Path(tmp)/"2026-10-22.provisional.v12.md"
            writer_style.write_bytes(draft.read_bytes())
            self.assertEqual(module.parse_archive_filename(writer_style.name),
                             ("2026-10-22","PROVISIONAL",12))
            path,content,meta=module.read_artifact(writer_style)
            self.assertTrue(path.endswith(writer_style.name))
            self.assertEqual(meta["status"],"PROVISIONAL")
if __name__=="__main__":
    unittest.main()
