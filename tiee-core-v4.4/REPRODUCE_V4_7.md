# Reproduce v4.7 acceptance pilot

Use the existing scaling potato Codespace, same 2-core resources, and a separate development worktree. Do not run alongside another pilot. Published evidence is under results/v47; preserve it by moving that directory to results/v47-published before a new test execution, then recreate results/v47/tests. Keep all original robotics work and backups. Do not regenerate source using the preparation scripts after freezing; final source and the calibrated model are already included.

From the tiee-core-v4.4 directory, create an ignored private .env.v47 with mode 0600. Set API_KEY and POSTGRES_PASSWORD to independently generated secrets, PG_POOL_SIZE=8. Never print or commit secrets.

    python -c "import pathlib,secrets; p=pathlib.Path('.env.v47'); p.write_text('API_KEY='+secrets.token_hex(32)+chr(10)+'POSTGRES_PASSWORD='+secrets.token_hex(32)+chr(10)+'PG_POOL_SIZE=8'+chr(10)); p.chmod(0o600)"
    DOCKER_BUILDKIT=0 docker build -t tiee47pilot-gateway .
    python -c "import subprocess; [subprocess.run(['docker','tag','tiee47pilot-gateway','tiee47pilot-'+name],check=True) for name in ('relay','worker','probe','network_anchor')]"
    docker compose -p tiee47pilot --env-file .env.v47 -f docker-compose.yml -f compose.validation.yml -f compose.v47.yml up -d --no-build --scale worker=2
    python validation/v47_policy_checks.py
    python validation/v47_tests.py
    python validation/v47_supplementary.py
    python validation/v47_round.py freeze
    python validation/v47_round.py collect
    python validation/v47_admission_profiles.py
    python validation/v47_analyze.py

Freeze refuses to continue unless all 18 current integration records passed. Collection verifies source/model hashes before every job. It saves all completed jobs, errors and unresolved accounting. Retain any interrupted/failed attempt and mark it explicitly; do not silently overwrite evidence or tune against held-out results.

Calibration is recorded in calibration.json: seed470002, 6000 observable/hidden-label synthetic examples, unchanged v4.6 coefficients, candidate cap grid fixed in v47_prepare.py, one-sided Wilson upper<=0.25%, selected cap0.02. Calibration-only selection does not certify held-out validity risk. Final analysis additionally applies conservative exact Clopper-Pearson one-sided 95% bounds to valid rejections and all-cause losses. The frozen pilot plan names Wilson; exact-bound analysis is a stricter reporting requirement, not a claim of preregistered confirmatory statistics.

The workload uses separate held-out seeds, rates40/80 per second, all deadlines12 seconds, three blocks per condition, A1/A3/A4, fresh DB/run, 24 warmups and two workers. This is an acceptance pilot, not directly comparable to v4.6 overload runs. Hidden labels remain exclusively in the probe. A3 and conventional A4 implement identical decision/ranking rules.

Use a reporting virtual environment and validation/requirements-report-v46.txt for exact plotting dependencies, then run:

    /workspaces/tiee-v46-report-venv/bin/python validation/v47_report.py

It creates PNG/PDF/SVG charts and V4_7_ENGINEERING_REPORT.md from analysis.json. SQL terminal marker time is before commit; observed terminal latency comes from a poll/final committed SQL snapshot and is an upper observation bound. ACK is measured separately. Raw runs.jsonl and its deterministic gzip archive, runs.csv, terminal_ledger.csv and resource_samples.csv retain measurements and accounting.

After verification, stop only this private project; retain its volumes:

    docker compose -p tiee47pilot --env-file .env.v47 -f docker-compose.yml -f compose.validation.yml -f compose.v47.yml stop -t 1

No production deployment, machine upgrade, new Codespace, PR merge or physical robotics work is part of this reproduction. Batching, physical power loss, volume loss, production failover and large powered confirmation remain unexecuted.

## Frozen pilot versus final transport correction

The published 27-run pilot used immutable commit 721e3bf36f1eaf7fffdca3cc7818f86a7a0cd0bb. Re-analyze its raw data from that commit/worktree so source hashes match plan.json. Final development source adds a Gateway backlog of 128 after collection; its tests are separate. For the final-source burst check, run validation/v47_http_regression.py with the corrected image; retain before.json, backlog_fix.json and gateway_before_fix.py. The matched 27-run experiment has not been repeated on the post-pilot transport patch.
