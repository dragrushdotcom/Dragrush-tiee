#!/usr/bin/env python3
"""Attest actual GitHub Actions runs through authenticated, read-only provider data.

A passing CI run is evidence of that run's tests, NOT independent source-fidelity,
editorial acceptance, manuscript approval, or successful external publication.
Never modifies an issue, a branch, an automation, or a project checkpoint.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
# Explicit allowlist prevents CI on a PR or unrelated workflow being promoted.
PRODUCERS = {
    "Engineering receipt and progress gates":
        (".github/workflows/engineering-contract-gate.yml",
         ("engineering-contract-regression",)),
}
ALLOWED_EVENTS = frozenset({"push", "schedule", "workflow_dispatch"})
SCHEMA = "dragrush.github_provider_run_attestation.v1"


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def evaluate_run(run, jobs, main_sha, repo, expected_run_id, observed_at_utc=None):
    """Pure trust-boundary gate; no guessed fields or side effects."""
    result = {
        "schema": SCHEMA,
        "observed_at_utc": observed_at_utc or utc_now(),
        "repository": repo,
        "requested_run_id": expected_run_id,
        "status": "UNKNOWN",
        "reason": "",
        "provider_authenticated": False,
        "current_main_head": main_sha,
        "source_run": {},
        "required_jobs": [],
        "source_progress_accepted": False,
        "author_approval_inferred": False,
        "external_publication_inferred": False,
        "mutex_modified": False,
    }

    def stop(code, status="UNTRUSTED"):
        result["status"], result["reason"] = status, code
        return result

    if not REPO_RE.fullmatch(repo) or not isinstance(expected_run_id, int) or expected_run_id <= 0:
        return stop("INVALID_REQUEST")
    if not isinstance(run, dict) or not isinstance(jobs, list) or not SHA_RE.fullmatch(str(main_sha)):
        return stop("PROVIDER_FIELDS_MISSING", "UNKNOWN")
    if (run.get("id") != expected_run_id
            or (run.get("repository") or {}).get("full_name") != repo
            or (run.get("head_repository") or {}).get("full_name") != repo):
        return stop("RUN_OR_REPOSITORY_IDENTITY_MISMATCH")
    result["provider_authenticated"] = True
    result["source_run"] = {
        "id": run["id"], "name": run.get("name"), "path": run.get("path"),
        "event": run.get("event"), "head_branch": run.get("head_branch"),
        "head_sha": run.get("head_sha"), "run_attempt": run.get("run_attempt"),
        "status": run.get("status"), "conclusion": run.get("conclusion"),
        "html_url": run.get("html_url"),
    }
    name = run.get("name")
    if name not in PRODUCERS:
        return stop("WORKFLOW_NOT_ALLOWLISTED")
    expected_path, required = PRODUCERS[name]
    if run.get("path") != expected_path:
        return stop("WORKFLOW_PATH_MISMATCH")
    if run.get("event") not in ALLOWED_EVENTS or run.get("head_branch") != "main":
        return stop("NON_PRODUCTION_EVENT_OR_BRANCH")
    if not SHA_RE.fullmatch(str(run.get("head_sha", ""))):
        return stop("INVALID_RUN_SHA")
    if not isinstance(run.get("run_attempt"), int) or run["run_attempt"] < 1:
        return stop("INVALID_RUN_ATTEMPT", "UNKNOWN")
    if run.get("status") != "completed":
        return stop("RUN_NOT_TERMINAL", "PENDING")
    if run.get("conclusion") != "success":
        return stop("SOURCE_RUN_NOT_SUCCESSFUL", "FAILED_CI")
    if not jobs:
        return stop("JOBS_UNAVAILABLE", "UNKNOWN")
    for j in jobs:
        if (not isinstance(j, dict) or j.get("run_id") != expected_run_id
                or j.get("status") != "completed"):
            return stop("JOB_RUN_MISMATCH_OR_PENDING", "UNKNOWN")
    for required_name in required:
        matching = [j for j in jobs if j.get("name") == required_name]
        if len(matching) != 1:
            return stop("REQUIRED_JOB_MISSING_OR_DUPLICATED", "FAILED_CI")
        job = matching[0]
        if job.get("conclusion") != "success":
            return stop("REQUIRED_JOB_NOT_SUCCESSFUL", "FAILED_CI")
        result["required_jobs"].append({
            "id": job.get("id"), "name": job["name"], "conclusion": "success",
            "html_url": job.get("html_url"),
        })
    # Require every job to be a completed non-failing job; GitHub's overall
    # conclusion is still the authoritative aggregate.
    if any(j.get("conclusion") not in ("success", "skipped", "neutral") for j in jobs):
        return stop("OTHER_JOB_NOT_SUCCESSFUL", "FAILED_CI")
    if run["head_sha"] != main_sha:
        return stop("RUN_HEAD_NO_LONGER_CURRENT", "HISTORICAL_CI_PASS")
    return stop("PROVIDER_VERIFIED_CI_ONLY", "CURRENT_MAIN_CI_PASS")


def provider_get(repo, path, token):
    if not REPO_RE.fullmatch(repo):
        raise ValueError("Invalid repository")
    if not token:
        raise ValueError("No GitHub read credential")
    url = "https://api.github.com/repos/" + repo + path
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dragrush-read-only-provider-attestor",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def acquire_provider_data(repo, run_id, token):
    """Require bounded complete job pagination; truncated data fails closed."""
    run = provider_get(repo, "/actions/runs/" + str(run_id), token)
    ref = provider_get(repo, "/git/ref/heads/main", token)
    main_sha = ((ref.get("object") or {}).get("sha"))
    if not SHA_RE.fullmatch(str(main_sha)):
        raise ValueError("Main SHA unavailable")
    jobs = []
    total = None
    for page in range(1, 6):
        payload = provider_get(repo, "/actions/runs/" + str(run_id) +
                               "/jobs?per_page=100&page=" + str(page), token)
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Job result incomplete")
        if total is None:
            total = payload.get("total_count")
            if not isinstance(total, int) or total < 1 or total > 500:
                raise ValueError("Job count unavailable or above bounded limit")
        jobs.extend(payload["jobs"])
        if len(jobs) >= total:
            if len(jobs) != total:
                raise ValueError("Duplicate or excess provider jobs")
            return run, jobs, main_sha
        if not payload["jobs"]:
            raise ValueError("Incomplete job pagination")
    raise ValueError("Job pagination exhausted")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    try:
        run, jobs, main_sha = acquire_provider_data(
            repo, args.run_id, os.environ.get("GITHUB_TOKEN", ""))
        receipt = evaluate_run(run, jobs, main_sha, repo, args.run_id)
    except (ValueError, OSError, urllib.error.URLError, json.JSONDecodeError, KeyError):
        # Don't print bearer tokens, provider URLs, or potentially sensitive responses.
        receipt = {
            "schema": SCHEMA, "observed_at_utc": utc_now(),
            "repository": repo, "requested_run_id": args.run_id,
            "status": "UNKNOWN", "reason": "PROVIDER_FETCH_OR_SCHEMA_FAILURE",
            "provider_authenticated": False, "source_progress_accepted": False,
            "author_approval_inferred": False, "external_publication_inferred": False,
            "mutex_modified": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print("Attestation:", receipt["status"], receipt["reason"])
    print("Source metric / author approval / publishing were NOT inferred.")
    return 0 if receipt["status"] in {"CURRENT_MAIN_CI_PASS", "HISTORICAL_CI_PASS"} else 2


if __name__ == "__main__":
    sys.exit(main())
