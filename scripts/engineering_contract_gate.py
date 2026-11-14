#!/usr/bin/env python3
"""Read-only, dependency-free engineering receipt and progress gates.

This tool does not modify GitHub, automation state, source content, or approval.
Receipt consistency is NOT independent proof that a remote CI job/artifact exists.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

UTC = timezone.utc
SHA = re.compile(r"^[0-9a-f]{40}$")
STATUSES = frozenset({"verified_progress", "no_progress", "blocked", "proposed"})
EVIDENCE = frozenset({"verified", "proposed", "synthetic", "not_measured"})


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone is required")
    return parsed.astimezone(UTC)


def https_url(value):
    if not isinstance(value, str):
        return False
    p = urlparse(value)
    return p.scheme == "https" and bool(p.netloc) and not p.username and not p.password


def validate(contract, receipt, expected_sha=None):
    """Return stable error codes; fail closed on mismatched or missing evidence."""
    e = []
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        return ["INVALID_CONTRACT"]
    if not isinstance(receipt, dict) or receipt.get("schema_version") != 1:
        return ["INVALID_RECEIPT"]
    if not isinstance(contract.get("task_id"), str) or not contract["task_id"].strip():
        e.append("CONTRACT_TASK_MISSING")
    if receipt.get("task_id") != contract.get("task_id"):
        e.append("TASK_MISMATCH")
    if not isinstance(receipt.get("invocation_id"), str) or not receipt["invocation_id"].strip():
        e.append("INVOCATION_MISSING")
    if not isinstance(receipt.get("operation"), str) or not receipt["operation"].strip():
        e.append("OPERATION_MISSING")
    try:
        timestamp(receipt.get("recorded_at_utc"))
    except (ValueError, TypeError, OverflowError):
        e.append("TIMESTAMP_INVALID")
    status = receipt.get("status")
    if status not in STATUSES:
        e.append("STATUS_INVALID")
    if receipt.get("evidence_class") not in EVIDENCE:
        e.append("EVIDENCE_CLASS_INVALID")
    if not SHA.fullmatch(str(receipt.get("input_sha", ""))):
        e.append("INPUT_SHA_INVALID")
    if not SHA.fullmatch(str(receipt.get("output_sha", ""))):
        e.append("OUTPUT_SHA_INVALID")

    metric = contract.get("metric")
    progress = receipt.get("progress")
    if not isinstance(metric, dict) or not isinstance(progress, dict):
        e.append("METRIC_MISSING")
    else:
        if progress.get("name") != metric.get("name"):
            e.append("METRIC_NAME_MISMATCH")
        if metric.get("direction") not in {"increase", "decrease"}:
            e.append("DIRECTION_INVALID")
        minimum = metric.get("minimum_delta")
        before, after = progress.get("before"), progress.get("after")
        if (isinstance(before, bool) or isinstance(after, bool) or
                not isinstance(before, (int, float)) or
                not isinstance(after, (int, float))):
            e.append("METRIC_VALUE_INVALID")
        elif not isinstance(minimum, (int, float)) or isinstance(minimum, bool) or minimum <= 0:
            e.append("MINIMUM_DELTA_INVALID")
        else:
            delta = after - before if metric["direction"] == "increase" else before - after
            if status == "verified_progress" and delta < minimum:
                e.append("NO_VERIFIED_DELTA")
            if status == "no_progress" and before != after:
                e.append("NO_PROGRESS_METRIC_CHANGED")

    verification = receipt.get("verification")
    if not isinstance(verification, dict):
        e.append("VERIFICATION_MISSING")
        verification = {}
    if verification.get("ci_status") not in {"passed", "failed", "pending", "not_available"}:
        e.append("CI_STATUS_INVALID")
    if status == "verified_progress":
        if receipt.get("evidence_class") != "verified":
            e.append("PROGRESS_NOT_VERIFIED")
        if not SHA.fullmatch(str(expected_sha or "")):
            e.append("TRUSTED_HEAD_REQUIRED")
        elif receipt.get("output_sha") != expected_sha:
            e.append("TRUSTED_HEAD_MISMATCH")
        if verification.get("ci_status") != "passed":
            e.append("CI_NOT_PASSED")
        if verification.get("ci_head_sha") != receipt.get("output_sha"):
            e.append("CI_HEAD_MISMATCH")
        if verification.get("readback_confirmed") is not True:
            e.append("READBACK_UNVERIFIED")
        if not https_url(verification.get("ci_run_url")):
            e.append("CI_URL_MISSING")
        if not https_url(verification.get("artifact_url")):
            e.append("ARTIFACT_MISSING")
        if contract.get("author_approval_required") is True:
            if verification.get("author_approved") is not True:
                e.append("AUTHOR_APPROVAL_MISSING")
            if not https_url(verification.get("author_approval_url")):
                e.append("AUTHOR_APPROVAL_EVIDENCE_MISSING")
    if status in {"blocked", "no_progress"}:
        blocker = receipt.get("blocker")
        if (not isinstance(blocker, dict) or
                not isinstance(blocker.get("next_step"), str) or
                not blocker["next_step"].strip()):
            e.append("NEXT_STEP_MISSING")
    safety = receipt.get("safety")
    if not isinstance(safety, dict) or safety.get("mutex_unchanged") is not True:
        e.append("MUTEX_SAFETY_MISSING")
    if not isinstance(safety, dict) or safety.get("approvals_preserved") is not True:
        e.append("APPROVAL_SAFETY_MISSING")
    if receipt.get("external_publication") is True:
        e.append("EXTERNAL_PUBLICATION_REQUIRES_SEPARATE_GATE")
    return sorted(set(e))


def assess_progress(previous, current, now, threshold_minutes=90):
    """Read-only diagnostic. Unknown/stale evidence never authorizes lock recovery."""
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return "UNKNOWN"
    try:
        old_time = timestamp(previous.get("observed_at_utc"))
        new_time = timestamp(current.get("observed_at_utc"))
        last_progress = timestamp(current.get("last_verified_progress_utc"))
        if not isinstance(threshold_minutes, int) or threshold_minutes <= 0:
            return "UNKNOWN"
        if not isinstance(previous.get("metric_value"), (int, float)) or isinstance(previous["metric_value"], bool):
            return "UNKNOWN"
        if not isinstance(current.get("metric_value"), (int, float)) or isinstance(current["metric_value"], bool):
            return "UNKNOWN"
        if previous.get("task_id") != current.get("task_id") or not current.get("task_id"):
            return "UNKNOWN"
        if new_time <= old_time or new_time > now or last_progress > new_time:
            return "UNKNOWN"
        if now - new_time > timedelta(minutes=threshold_minutes):
            return "MONITOR_STALE"
        if current["metric_value"] < previous["metric_value"]:
            return "REGRESSION"
        if current["metric_value"] > previous["metric_value"]:
            return "PROGRESS"
        if now - last_progress > timedelta(minutes=threshold_minutes):
            return "STALLED"
        return "NO_CHANGE_WITHIN_THRESHOLD"
    except (ValueError, TypeError, OverflowError):
        return "UNKNOWN"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="check a task receipt against its contract")
    v.add_argument("--contract", required=True, type=Path)
    v.add_argument("--receipt", required=True, type=Path)
    v.add_argument("--expected-sha", help="trusted exact checkout SHA; required for verified_progress")
    s = sub.add_parser("stall", help="compare two immutable observations")
    s.add_argument("--previous", required=True, type=Path)
    s.add_argument("--current", required=True, type=Path)
    s.add_argument("--now", required=True, help="UTC ISO8601 timestamp")
    s.add_argument("--minutes", type=int, default=90)
    args = p.parse_args()
    try:
        if args.command == "validate":
            result = validate(json.loads(args.contract.read_text()),
                              json.loads(args.receipt.read_text()), args.expected_sha)
            print(json.dumps({"result": "PASS" if not result else "FAIL", "errors": result}))
            return 0 if not result else 2
        status = assess_progress(json.loads(args.previous.read_text()),
                                 json.loads(args.current.read_text()),
                                 timestamp(args.now), args.minutes)
        print(json.dumps({"result": status, "changes_lock": False}))
        return 2 if status in {"STALLED", "REGRESSION", "UNKNOWN", "MONITOR_STALE"} else 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "ERROR", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
