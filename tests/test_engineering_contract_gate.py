"""Fail-closed regression tests for cross-project task receipts and progress gates."""
import copy
import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "engineering_contract_gate.py"
spec = importlib.util.spec_from_file_location("engineering_contract_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

SHA_A = "a" * 40
SHA_B = "b" * 40


def contract():
    return {
        "schema_version": 1, "task_id": "sample-task",
        "metric": {"name": "verified_units", "direction": "increase", "minimum_delta": 1},
        "author_approval_required": False,
    }


def receipt():
    return {
        "schema_version": 1, "task_id": "sample-task", "invocation_id": "sample-task-run42",
        "recorded_at_utc": "2026-11-13T18:00:00Z", "operation": "validate batch",
        "input_sha": SHA_A, "output_sha": SHA_B, "status": "verified_progress",
        "evidence_class": "verified",
        "progress": {"name": "verified_units", "before": 10, "after": 11},
        "verification": {
            "ci_status": "passed", "ci_head_sha": SHA_B, "readback_confirmed": True,
            "ci_run_url": "https://github.com/dragrushdotcom/Dragrush-tiee/actions/runs/42",
            "artifact_url": "https://github.com/dragrushdotcom/Dragrush-tiee/commit/" + SHA_B,
        },
        "safety": {"mutex_unchanged": True, "approvals_preserved": True},
        "external_publication": False,
    }


def observation(at, progress_at, number=10):
    return {
        "task_id": "sample-task", "observed_at_utc": at,
        "last_verified_progress_utc": progress_at, "metric_value": number,
    }


class ReceiptGateTest(unittest.TestCase):
    def test_consistent_receipt(self):
        self.assertEqual(gate.validate(contract(), receipt(), SHA_B), [])

    def test_untrusted_head_cannot_claim_progress(self):
        self.assertIn("TRUSTED_HEAD_REQUIRED", gate.validate(contract(), receipt()))
        self.assertIn("TRUSTED_HEAD_MISMATCH", gate.validate(contract(), receipt(), SHA_A))

    def test_wrong_head_ci_even_when_other_fields_valid(self):
        r = receipt()
        r["verification"]["ci_head_sha"] = SHA_A
        self.assertIn("CI_HEAD_MISMATCH", gate.validate(contract(), r, SHA_B))

    def test_no_delta_cannot_be_progress(self):
        r = receipt()
        r["progress"]["after"] = r["progress"]["before"]
        self.assertIn("NO_VERIFIED_DELTA", gate.validate(contract(), r, SHA_B))

    def test_proposed_not_accepted_as_verified_progress(self):
        r = receipt()
        r["evidence_class"] = "proposed"
        self.assertIn("PROGRESS_NOT_VERIFIED", gate.validate(contract(), r, SHA_B))

    def test_author_approval_requires_explicit_evidence(self):
        c = contract()
        c["author_approval_required"] = True
        self.assertIn("AUTHOR_APPROVAL_MISSING", gate.validate(c, receipt(), SHA_B))
        self.assertIn("AUTHOR_APPROVAL_EVIDENCE_MISSING", gate.validate(c, receipt(), SHA_B))

    def test_no_progress_requires_recovery_action(self):
        r = receipt()
        r["status"] = "no_progress"
        r["evidence_class"] = "not_measured"
        r["progress"]["after"] = r["progress"]["before"]
        self.assertIn("NEXT_STEP_MISSING", gate.validate(contract(), r))
        r["blocker"] = {"code": "BATCH_PENDING", "next_step": "Verify one source record"}
        self.assertEqual(gate.validate(contract(), r), [])

    def test_read_only(self):
        c, r = contract(), receipt()
        old_c, old_r = copy.deepcopy(c), copy.deepcopy(r)
        gate.validate(c, r, SHA_B)
        self.assertEqual((c, r), (old_c, old_r))

    def test_publication_flag_rejected(self):
        r = receipt()
        r["external_publication"] = True
        self.assertIn("EXTERNAL_PUBLICATION_REQUIRES_SEPARATE_GATE", gate.validate(contract(), r, SHA_B))

    def test_untrusted_evidence_url_rejected(self):
        r = receipt()
        r["verification"]["artifact_url"] = "http://example.com/not-a-proof"
        self.assertIn("ARTIFACT_MISSING", gate.validate(contract(), r, SHA_B))


class ProgressWatchTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 13, 20, 0, tzinfo=timezone.utc)
        self.previous = observation("2026-11-13T18:00:00Z", "2026-11-13T17:00:00Z")
        self.current = observation("2026-11-13T19:55:00Z", "2026-11-13T17:00:00Z")

    def test_same_count_over_threshold_is_stalled(self):
        self.assertEqual(gate.assess_progress(self.previous, self.current, self.now), "STALLED")

    def test_not_a_stall_when_count_advances(self):
        self.current["metric_value"] = 11
        self.current["last_verified_progress_utc"] = "2026-11-13T19:50:00Z"
        self.assertEqual(gate.assess_progress(self.previous, self.current, self.now), "PROGRESS")

    def test_unknown_evidence_fails_closed(self):
        self.current["last_verified_progress_utc"] = "invalid"
        self.assertEqual(gate.assess_progress(self.previous, self.current, self.now), "UNKNOWN")

    def test_no_recent_observation_means_monitor_stale(self):
        self.current["observed_at_utc"] = "2026-11-13T18:05:00Z"
        self.assertEqual(gate.assess_progress(self.previous, self.current, self.now), "MONITOR_STALE")

    def test_regression_is_not_progress(self):
        self.current["metric_value"] = 2
        self.assertEqual(gate.assess_progress(self.previous, self.current, self.now), "REGRESSION")

    def test_no_time_elapsed_not_a_stall(self):
        self.current["last_verified_progress_utc"] = "2026-11-13T19:20:00Z"
        self.assertEqual(gate.assess_progress(self.previous, self.current, self.now), "NO_CHANGE_WITHIN_THRESHOLD")

    def test_mismatched_task_is_unknown(self):
        self.current["task_id"] = "unrelated-lane"
        self.assertEqual(gate.assess_progress(self.previous, self.current, self.now), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
