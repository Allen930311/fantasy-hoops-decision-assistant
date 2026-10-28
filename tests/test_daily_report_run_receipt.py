"""Synthetic-only tests for independent report-run status and readback receipts."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from daily_report_run_receipt import (  # noqa: E402
    build_receipt, save_private_report, versioned_report_key,
)
import generate_daily_report  # noqa: E402


class DailyReportRunReceiptTests(unittest.TestCase):
    def setUp(self):
        self.main_sha = "a" * 40
        self.report = "\n".join([
            "---",
            'season: "2026-27"',
            'report_date_taipei: "2026-10-28"',
            'status: "PROVISIONAL"',
            f'roster_commit_sha: "{self.main_sha}"',
            f'rosters_blob_sha: "{"b" * 40}"',
            f'league_blob_sha: "{"c" * 40}"',
            f'ownership_blob_sha: "{"d" * 40}"',
            'schedule_source_url: "https://stats.example.test/scoreboard"',
            'data_cutoff_taipei: "2026-10-28T15:00:00+08:00"',
            'validation_summary: {"owner_coverage_status":"MATCHED_TO_AVAILABLE_FINAL_ROWS","fp_verified_players":1,"fp_partial_players":1,"fp_missing":{"Aaron":"TECH"}}',
            "---", "", "# SYNTHETIC report; not NBA data", "",
        ])
        self.report_sha = hashlib.sha256(self.report.encode("utf-8")).hexdigest()
        self.input = {
            "report": {"owner_players": ["Player A", "Player B"], "quality_gaps": [
                {"game_id": "001", "player_id": "123", "name": "Player B", "missing": ["TECH"]}]},
            "schedule_games": [{"id": "001", "status": "Final"}, {"id": "002", "status": "Live"}],
            "games": [{"id": "001", "status": "final"}],
        }
        self.acquisition = {
            "schedule_provider": "synthetic-test-only",
            "schedule_source_url": "https://example.test/schedule",
            "schedule_status": "COMPLETE",
            "source_records": [{"provider": "synthetic-test-only", "url": "https://example.test/data?api_key=secret", "raw_sha256": "e" * 64}],
            "source_failures": [{"provider": "synthetic-test-only", "url": "https://user:secret@example.test/fallback?client_secret=private&token=secret", "kind": "429", "message": "private detail omitted"}],
        }
        self.common = dict(
            report_text=self.report, input_payload=self.input, acquisition=self.acquisition,
            scheduled_for="2026-10-28T15:00:00+08:00", executed_at="2026-10-28T15:00:02+08:00",
            runtime_status="RUNTIME_INTEGRATION_BLOCKED", delivery_status="DELIVERED",
            delivery_report_sha256=self.report_sha, delivery_result_id="synthetic-result-1",
            delivery_evidence_source="owner_facing_result",
            execution_mode="SYNTHETIC", validator_invoked=False,
        )
        self.authorized = {**self.common, "source_use_status": "AUTHORIZED",
                           "source_use_basis": "synthetic fixture only"}
        self.storage_evidence = dict(storage_location="private-target", storage_backend="synthetic",
            storage_target_id="synthetic-target", storage_readback_source="synthetic-readback",
            storage_owner_accessible=True, storage_durable=True, storage_immutable=True)

    def test_task_history_readback_status_keeps_axes_separate(self):
        receipt = build_receipt(**self.authorized,
            **{**self.storage_evidence, "storage_location": "synthetic-task-history/run-123"},
            storage_readback_text=self.report)
        self.assertEqual(receipt["delivery_status"], "DELIVERED")
        self.assertEqual(receipt["storage_status"], "STORED")
        self.assertTrue(receipt["exact_readback"])
        self.assertEqual(receipt["report_sha256"], receipt["readback_sha256"])
        self.assertEqual(receipt["publication_status"], "PUBLICATION_BLOCKED")
        self.assertEqual(receipt["execution_mode"], "SYNTHETIC")

    def test_unverified_source_use_cannot_be_stored_as_authorized(self):
        receipt = build_receipt(**self.common, **self.storage_evidence,
                                storage_readback_text=self.report)
        self.assertEqual(receipt["storage_status"], "STORAGE_BLOCKED")
        self.assertFalse(receipt["source_use_authorized"])

    def test_storage_failure_does_not_suppress_delivery_or_change_content_status(self):
        receipt = build_receipt(**self.common, storage_error_code="ACCESS_TOKEN_SCOPE_INSUFFICIENT")
        self.assertEqual(receipt["delivery_status"], "DELIVERED")
        self.assertEqual(receipt["storage_status"], "STORAGE_BLOCKED")
        self.assertEqual(receipt["content_status"], "PROVISIONAL")

    def test_no_or_truncated_storage_readback_is_blocked(self):
        missing = build_receipt(**self.authorized, **self.storage_evidence)
        truncated = build_receipt(**self.authorized, **self.storage_evidence,
                                  storage_readback_text=self.report, storage_readback_truncated=True)
        self.assertEqual(missing["storage_status"], "STORAGE_BLOCKED")
        self.assertEqual(truncated["storage_status"], "STORAGE_BLOCKED")
        self.assertFalse(truncated["exact_readback"])

    def test_mismatched_storage_readback_is_blocked(self):
        receipt = build_receipt(**self.authorized, **self.storage_evidence,
                                storage_readback_text=self.report + "extra")
        self.assertEqual(receipt["storage_status"], "STORAGE_BLOCKED")
        self.assertEqual(receipt["error_code"], "READBACK_CONTENT_MISMATCH")

    def test_runtime_blocked_can_still_deliver_and_preserve_game_gaps(self):
        receipt = build_receipt(**self.common)
        self.assertEqual(receipt["runtime_status"], "RUNTIME_INTEGRATION_BLOCKED")
        self.assertEqual(receipt["source_use_status"], "UNVERIFIED")
        self.assertEqual(receipt["delivery_status"], "DELIVERED")
        self.assertEqual(receipt["data"]["missing_final_game_ids"], [])
        self.assertEqual(receipt["data"]["verified_fp"], 1)
        self.assertEqual(receipt["data"]["partial_fp"], 1)
        self.assertEqual(receipt["data"]["final_game_coverage"], 1.0)
        self.assertEqual(receipt["data"]["source_records"][0]["raw_sha256"], "e" * 64)
        self.assertNotIn("api_key", receipt["data"]["source_records"][0]["url"])
        self.assertNotIn("secret", receipt["data"]["source_failures"][0]["url"])
        self.assertNotIn("private", receipt["data"]["source_failures"][0]["url"])
        self.assertNotIn("message", receipt["data"]["source_failures"][0])

    def test_generator_acquisition_shape_is_receipt_compatible(self):
        class SyntheticClient:
            history = []

        schedule_result = {"provider": "nba_stats", "events": [],
            "record": {"url": "https://stats.example.test/scoreboard?api_key=synthetic"}, "errors": []}
        with patch.object(generate_daily_report, "acquire_schedule", return_value=schedule_result):
            payload, acquisition = generate_daily_report.generate_payload(
                root=ROOT, report_date="2026-10-28", nba_date_et="20261027",
                snapshot_dir=ROOT / "synthetic-unused-cache", client=SyntheticClient())
        self.assertEqual(acquisition["schedule_status"], "COMPLETE")
        self.assertEqual(acquisition["schedule_source_url"], schedule_result["record"]["url"])
        receipt = build_receipt(**{**self.common, "input_payload": payload,
                                   "acquisition": acquisition})
        self.assertEqual(receipt["data"]["schedule_status"], "COMPLETE")
        self.assertEqual(receipt["data"]["final_game_coverage"], 1.0)
        self.assertNotIn("synthetic", receipt["data"]["schedule_source_url"])
        self.assertNotIn("api_key", receipt["data"]["schedule_source_url"])

    def test_missing_schedule_evidence_is_unknown_not_full_coverage(self):
        receipt = build_receipt(**{**self.common,
            "acquisition": {"schedule_status": "FAILED", "source_records": [], "source_failures": []}})
        self.assertIsNone(receipt["data"]["final_game_coverage"])

    def test_schedule_coverage_reports_unexpected_final_box_scores(self):
        payload = {**self.input, "games": [*self.input["games"], {"id": "999", "status": "Final"}]}
        receipt = build_receipt(**{**self.common, "input_payload": payload})
        self.assertEqual(receipt["data"]["unexpected_final_box_game_ids"], ["999"])

    def test_url_redaction_removes_userinfo_and_common_secret_keys(self):
        acquisition = {"source_records": [{"provider": "synthetic",
            "url": "https://user:password@example.test/x?client_secret=abc&x-api-key=def&subscription-key=ghi&ok=1"}]}
        receipt = build_receipt(**{**self.common, "acquisition": acquisition})
        url = receipt["data"]["source_records"][0]["url"]
        for secret in ("user", "password", "abc", "def", "ghi"):
            self.assertNotIn(secret, url)
        self.assertIn("ok=1", url)

    def test_canonical_runtime_requires_matching_latest_main_commit(self):
        receipt = build_receipt(**{**self.common,
            "runtime_status": "EXECUTED_CANONICAL", "runtime_commit_sha": self.main_sha,
            "latest_main_commit_sha": self.main_sha, "runtime_evidence_source": "canonical_runner"})
        self.assertEqual(receipt["runtime_commit_sha"], self.main_sha)
        with self.assertRaisesRegex(ValueError, "latest-main"):
            build_receipt(**{**self.common, "runtime_status": "EXECUTED_CANONICAL",
                "runtime_commit_sha": self.main_sha, "runtime_evidence_source": "canonical_runner"})
        with self.assertRaisesRegex(ValueError, "must match"):
            build_receipt(**{**self.common, "runtime_status": "EXECUTED_CANONICAL",
                "runtime_commit_sha": "f" * 40, "latest_main_commit_sha": self.main_sha,
                "runtime_evidence_source": "canonical_runner"})

    def test_scheduled_mode_requires_task_and_execution_ids(self):
        with self.assertRaisesRegex(ValueError, "task/run IDs"):
            build_receipt(**{**self.common, "execution_mode": "SCHEDULED_PRODUCTION"})
        receipt = build_receipt(**{**self.common, "execution_mode": "SCHEDULED_PRODUCTION",
            "execution_id": "synthetic-run-1", "scheduled_task_id": "synthetic-task-1",
            "schedule_timezone": "Asia/Taipei", "execution_evidence_source": "automation_history"})
        self.assertEqual(receipt["execution_mode"], "SCHEDULED_PRODUCTION")
        self.assertEqual(receipt["scheduled_timing"], "LATE")
        previous_day = self.report.replace('report_date_taipei: "2026-10-28"',
                                           'report_date_taipei: "2026-10-27"')
        with self.assertRaisesRegex(ValueError, "report date must match"):
            build_receipt(**{**self.common, "report_text": previous_day,
                "delivery_report_sha256": hashlib.sha256(previous_day.encode()).hexdigest(),
                "execution_mode": "SCHEDULED_PRODUCTION", "execution_id": "synthetic-run-old",
                "scheduled_task_id": "synthetic-task-1", "schedule_timezone": "Asia/Taipei",
                "execution_evidence_source": "automation_history"})
        early = build_receipt(**{**self.common, "executed_at": "2026-10-28T14:38:00+08:00",
            "execution_mode": "SCHEDULED_PRODUCTION", "execution_id": "synthetic-run-2",
            "scheduled_task_id": "synthetic-task-1", "schedule_timezone": "Asia/Taipei",
            "execution_evidence_source": "automation_history"})
        self.assertEqual(early["scheduled_timing"], "EARLY")
        with self.assertRaisesRegex(ValueError, "15:00 Asia/Taipei"):
            build_receipt(**{**self.common, "scheduled_for": "2026-10-28T14:38:00+08:00",
                "execution_mode": "SCHEDULED_PRODUCTION", "execution_id": "synthetic-run-3",
                "scheduled_task_id": "synthetic-task-1", "schedule_timezone": "Asia/Taipei",
                "execution_evidence_source": "automation_history"})

    def test_delivery_requires_matching_report_hash(self):
        with self.assertRaisesRegex(ValueError, "exact report SHA"):
            build_receipt(**{**self.common, "delivery_report_sha256": "0" * 64})
        with self.assertRaisesRegex(ValueError, "exact report SHA"):
            build_receipt(**{**self.common, "delivery_report_sha256": None})

    def test_validated_content_requires_successful_validator_evidence(self):
        validated_report = self.report.replace('status: "PROVISIONAL"', 'status: "VALIDATED"')
        validated_sha = hashlib.sha256(validated_report.encode("utf-8")).hexdigest()
        common = {**self.common, "report_text": validated_report,
                  "delivery_report_sha256": validated_sha}
        with self.assertRaisesRegex(ValueError, "successful canonical validator"):
            build_receipt(**common)
        receipt = build_receipt(**{**common, "validator_invoked": True, "validator_exit_code": 0})
        self.assertEqual(receipt["content_status"], "VALIDATED")
        self.assertEqual(receipt["validator"]["exit_code"], 0)

    def test_published_requires_authorized_source_and_exact_public_readback(self):
        with self.assertRaisesRegex(ValueError, "authorized source-use"):
            build_receipt(**{**self.common, "publication_status": "PUBLISHED",
                "publication_rights_basis_ref": "synthetic", "publication_readback_text": self.report})
        receipt = build_receipt(**{**self.authorized, "publication_status": "PUBLISHED",
            "publication_rights_status": "AUTHORIZED", "publication_rights_basis_ref": "synthetic-fixture-only",
            "publication_remote_location": "https://example.test/report", "publication_remote_ref": "main",
            "publication_remote_commit_sha": "f" * 40, "publication_readback_text": self.report})
        self.assertEqual(receipt["publication_status"], "PUBLISHED")
        self.assertEqual(receipt["publication_rights_basis_ref"], "synthetic-fixture-only")
        with self.assertRaisesRegex(ValueError, "publication-rights bases"):
            build_receipt(**{**self.authorized, "publication_status": "PUBLISHED",
                "publication_rights_basis_ref": "private-only-license",
                "publication_readback_text": self.report})
        with self.assertRaisesRegex(ValueError, "exact remote content readback"):
            build_receipt(**{**self.authorized, "publication_status": "PUBLISHED",
                "publication_rights_status": "AUTHORIZED", "publication_rights_basis_ref": "synthetic-fixture-only",
                "publication_remote_location": "https://example.test/report", "publication_remote_ref": "main",
                "publication_remote_commit_sha": "f" * 40, "publication_readback_text": "changed"})

    def test_pr_pending_is_blocked_until_publication_rights_are_authorized(self):
        with self.assertRaisesRegex(ValueError, "authorized source-use"):
            build_receipt(**self.common, publication_status="PR_PENDING",
                publication_readback_text=self.report)
        receipt = build_receipt(**{**self.authorized, "publication_status": "PR_PENDING",
            "publication_rights_status": "AUTHORIZED", "publication_rights_basis_ref": "synthetic-only",
            "publication_remote_location": "https://user:password@example.test/pull/1?token=secret",
            "publication_remote_ref": "feature/test-branch",
            "publication_remote_commit_sha": "e" * 40, "publication_readback_text": self.report})
        self.assertEqual(receipt["publication_status"], "PR_PENDING")
        self.assertEqual(receipt["publication_remote_ref"], "feature/test-branch")
        self.assertNotIn("password", receipt["publication_remote_location"])
        self.assertNotIn("secret", receipt["publication_remote_location"])

    def test_versioned_key_is_idempotent_and_content_addressed(self):
        self.assertEqual(versioned_report_key("2026-10-28", "1" * 64),
                         "2026-10-28/" + "1" * 64 + ".md")
        self.assertNotEqual(versioned_report_key("2026-10-28", "1" * 64),
                            versioned_report_key("2026-10-28", "2" * 64))

    def test_private_save_is_immutable_and_exactly_read_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "owner-private-store"
            args = dict(report_date="2026-10-28", storage_root=root, repo_root=ROOT,
                owner_accessible=True, durable=True, source_use_authorized=True,
                storage_backend="synthetic-tempdir", storage_target_id="synthetic-owner-store")
            first = save_private_report(self.report, **args)
            second = save_private_report(self.report, **args)
            self.assertEqual(first["storage_status"], "STORED")
            self.assertEqual(first["readback_sha256"], first["report_sha256"])
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["location"], second["location"])
            self.assertEqual(Path(first["location"]).read_text(), self.report)

    def test_private_save_fails_closed_without_authorized_durable_owner_storage(self):
        result = save_private_report(self.report, report_date="2026-10-28",
            storage_root="/tmp/unused", repo_root=ROOT, owner_accessible=True, durable=False,
            source_use_authorized=False, storage_backend="test", storage_target_id="test-only")
        self.assertEqual(result["storage_status"], "STORAGE_BLOCKED")

    def test_private_save_rejects_repository_path(self):
        result = save_private_report(self.report, report_date="2026-10-28",
            storage_root=ROOT / "private", repo_root=ROOT, owner_accessible=True, durable=True,
            source_use_authorized=True, storage_backend="test", storage_target_id="test-only")
        self.assertEqual(result["storage_status"], "STORAGE_BLOCKED")
        self.assertEqual(result["error_code"], "TARGET_INSIDE_REPOSITORY")

    def test_private_save_returns_storage_error_without_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            parent_file = Path(temp) / "not-a-directory"
            parent_file.write_text("synthetic", encoding="utf-8")
            result = save_private_report(self.report, report_date="2026-10-28",
                storage_root=parent_file / "child", repo_root=ROOT, owner_accessible=True, durable=True,
                source_use_authorized=True, storage_backend="test", storage_target_id="test-only")
            self.assertEqual(result["storage_status"], "STORAGE_BLOCKED")

    def test_private_save_rejects_symlink_version_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "store"
            root.mkdir()
            outside = Path(temp) / "outside"
            outside.mkdir()
            (root / "2026-10-28").symlink_to(outside, target_is_directory=True)
            result = save_private_report(self.report, report_date="2026-10-28",
                storage_root=root, repo_root=ROOT, owner_accessible=True, durable=True,
                source_use_authorized=True, storage_backend="test", storage_target_id="test-only")
            self.assertEqual(result["storage_status"], "STORAGE_BLOCKED")
            self.assertEqual(list(outside.iterdir()), [])

    def test_private_save_rejects_group_or_world_accessible_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "shared-store"
            root.mkdir(mode=0o755)
            root.chmod(0o755)
            result = save_private_report(self.report, report_date="2026-10-28",
                storage_root=root, repo_root=ROOT, owner_accessible=True, durable=True,
                source_use_authorized=True, storage_backend="test", storage_target_id="test-only")
            self.assertEqual(result["storage_status"], "STORAGE_BLOCKED")
            self.assertEqual(list(root.iterdir()), [])

    def test_unverified_publication_cannot_be_claimed_as_published(self):
        self.assertEqual(build_receipt(**self.common)["publication_status"], "PUBLICATION_BLOCKED")
        with self.assertRaisesRegex(ValueError, "publication_status"):
            build_receipt(**self.common, publication_status="ARCHIVED")

    def test_receipt_is_json_serializable_without_raw_response_bodies(self):
        encoded = json.dumps(build_receipt(**self.common), ensure_ascii=False)
        self.assertNotIn("raw_response", encoded)
        self.assertNotIn("private detail omitted", encoded)


if __name__ == "__main__":
    unittest.main()
