# TiEE — authenticated production CI evidence

This repository deploys `scripts/github_run_attestor.py` and
`.github/workflows/github-provider-attestation.yml` as **read-only** GitHub Actions
provider evidence collection. When the existing `Engineering receipt and progress gates`
workflow completes on `main`, an independent workflow queries that source run ID
through GitHub's REST API using only `actions:read` and `contents:read`.
It validates repository and head identity, allowlisted workflow/path, the
trusted production event/branch, terminal source conclusion, required job,
all job-run identities, and current `main` SHA.

A separate artifact `github-provider-attestation-<run-id>` contains the
run-specific receipt. It distinguishes:
- `CURRENT_MAIN_CI_PASS`: verified required job and exact current main SHA.
- `HISTORICAL_CI_PASS`: verified job, but main has advanced.
- `FAILED_CI`, `PENDING`, `UNTRUSTED`, `UNKNOWN`: no successful evidence.
Failed and unknown conditions produce a failing collector job; the artifact
is still preserved when the provider returned enough information.

**Scope limit:** These artifacts verify GitHub CI execution, not project completion.
The receipt always keeps `source_progress_accepted=false`,
`author_approval_inferred=false`, and
`external_publication_inferred=false`. Passing a CI run does not prove throughput gains or production GPU performance; controlled benchmarks remain required.

No new recurring schedule, network write permissions, credentials, automatic
publishing, paid API usage, money movement or lock recovery were introduced.
Use real user/author approvals and independent domain-specific evidence to
mark a project milestone as complete. CI-provider attestation does not merge
PRs, grant permission or alter task ownership.

Manual read-only reinspection: dispatch the `Independent GitHub run attestation`
workflow with an existing GitHub Actions run ID. Verify the exact result and
stored artifact in that repository's Actions tab. A PR run never counts as a
production main-branch receipt.
