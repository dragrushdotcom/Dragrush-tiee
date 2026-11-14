"""Tests for authenticated GitHub provider run attestation (no network needed)."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts" / "github_run_attestor.py"
spec = importlib.util.spec_from_file_location("github_run_attestor", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

REPO = "dragrushdotcom/Dragrush-tiee"
SHA = "a" * 40
NEWER = "b" * 40
RUN_ID = 1200345


def run_data():
    return {
        "id": RUN_ID, "name": "Engineering receipt and progress gates",
        "path": ".github/workflows/engineering-contract-gate.yml",
        "event": "push", "head_branch": "main", "head_sha": SHA,
        "repository": {"full_name": REPO},
        "head_repository": {"full_name": REPO},
        "run_attempt": 1, "status": "completed", "conclusion": "success",
        "html_url": f"https://github.com/{REPO}/actions/runs/{RUN_ID}",
    }


def jobs_data():
    return [{
        "id": 7654321, "run_id": RUN_ID,
        "name": "engineering-contract-regression",
        "status": "completed", "conclusion": "success",
        "html_url": f"https://github.com/{REPO}/actions/runs/{RUN_ID}/job/7654321",
    }]


class AttestorTests(unittest.TestCase):
    def check(self, run=None, jobs=None, head=SHA):
        if run is None:
            run = run_data()
        if jobs is None:
            jobs = jobs_data()
        return module.evaluate_run(run, jobs, head, REPO, RUN_ID, "2026-11-13T23:00:00Z")

    def test_exact_current_main_workflow_success(self):
        r = self.check()
        self.assertEqual(r["status"], "CURRENT_MAIN_CI_PASS")
        self.assertTrue(r["provider_authenticated"])
        self.assertFalse(r["source_progress_accepted"])
        self.assertFalse(r["author_approval_inferred"])
        self.assertFalse(r["external_publication_inferred"])
        self.assertFalse(r["mutex_modified"])

    def test_replaced_main_head_is_historical_not_current(self):
        r = self.check(head=NEWER)
        self.assertEqual(r["status"], "HISTORICAL_CI_PASS")

    def test_failed_provider_run_remains_failure(self):
        run = run_data()
        run["conclusion"] = "failure"
        self.assertEqual(self.check(run)["status"], "FAILED_CI")

    def test_missing_job_fails_closed(self):
        self.assertEqual(self.check(jobs=[])["status"], "UNKNOWN")

    def test_job_skipped_fails_closed(self):
        jobs = jobs_data()
        jobs[0]["conclusion"] = "skipped"
        self.assertEqual(self.check(jobs=jobs)["status"], "FAILED_CI")

    def test_job_from_unrelated_run_rejected(self):
        jobs = jobs_data()
        jobs[0]["run_id"] = RUN_ID + 1
        self.assertEqual(self.check(jobs=jobs)["status"], "UNKNOWN")

    def test_job_name_required(self):
        jobs = jobs_data()
        jobs[0]["name"] = "not-the-check"
        self.assertEqual(self.check(jobs=jobs)["status"], "FAILED_CI")

    def test_duplicate_job_names_rejected(self):
        jobs = jobs_data() + jobs_data()
        self.assertEqual(self.check(jobs=jobs)["status"], "FAILED_CI")

    def test_pull_request_cannot_be_promoted_to_production(self):
        run = run_data()
        run["event"] = "pull_request"
        self.assertEqual(self.check(run)["status"], "UNTRUSTED")

    def test_different_head_branch_rejected(self):
        run = run_data()
        run["head_branch"] = "feature/test"
        self.assertEqual(self.check(run)["status"], "UNTRUSTED")

    def test_wrong_repository_rejected(self):
        run = run_data()
        run["repository"] = {"full_name": "other/name"}
        self.assertEqual(self.check(run)["status"], "UNTRUSTED")

    def test_wrong_fork_head_repository_rejected(self):
        run = run_data()
        run["head_repository"] = {"full_name": "other/name"}
        self.assertEqual(self.check(run)["status"], "UNTRUSTED")

    def test_unlisted_workflow_rejected(self):
        run = run_data()
        run["name"] = "untrusted"
        self.assertEqual(self.check(run)["status"], "UNTRUSTED")

    def test_forged_workflow_path_rejected(self):
        run = run_data()
        run["path"] = ".github/workflows/unknown.yml"
        self.assertEqual(self.check(run)["status"], "UNTRUSTED")

    def test_wrong_run_id_rejected(self):
        run = run_data()
        run["id"] += 1
        self.assertEqual(self.check(run)["status"], "UNTRUSTED")

    def test_run_still_running_not_successful(self):
        run = run_data()
        run["status"] = "in_progress"
        run["conclusion"] = None
        self.assertEqual(self.check(run)["status"], "PENDING")

    def test_other_job_failure_rejected(self):
        jobs = jobs_data()
        jobs.append({"id": 5, "run_id": RUN_ID, "name": "other",
                     "status": "completed", "conclusion": "failure"})
        self.assertEqual(self.check(jobs=jobs)["status"], "FAILED_CI")

    def test_provider_data_pagination(self):
        run = run_data()
        ref = {"object": {"sha": SHA}}
        one = {"total_count": 101, "jobs": [
            {"id": i, "run_id": RUN_ID, "name": f"j{i}"} for i in range(100)
        ]}
        two = {"total_count": 101, "jobs": [
            {"id": 100, "run_id": RUN_ID, "name": "j100"}
        ]}
        with patch.object(module, "provider_get", side_effect=[run, ref, one, two]) as mocked:
            r, jobs, sha = module.acquire_provider_data(REPO, RUN_ID, "token")
        self.assertEqual((len(jobs), sha, mocked.call_count), (101, SHA, 4))

    def test_provider_pagination_truncation_fails(self):
        run = run_data()
        ref = {"object": {"sha": SHA}}
        one = {"total_count": 101, "jobs": [{}] * 100}
        with patch.object(module, "provider_get", side_effect=[run, ref, one,
                                                                {"total_count": 101, "jobs": []}]):
            with self.assertRaises(ValueError):
                module.acquire_provider_data(REPO, RUN_ID, "token")

    def test_cli_fails_closed_when_provider_access_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "receipt.json"
            with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": ""}):
                code = module.main(["--run-id", str(RUN_ID), "--output", str(output)])
            self.assertEqual(code, 2)
            saved = json.loads(output.read_text())
            self.assertEqual(saved["status"], "UNKNOWN")
            self.assertFalse(saved["source_progress_accepted"])


if __name__ == "__main__":
    unittest.main()
