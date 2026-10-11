# TiEE Core v4.5 reproduction

Experimental non-production Redis Streams / PostgreSQL pilot. Run from this directory in the existing Codespace. The original worktree remains on robotics-v01; engineering work is in /workspaces/Dragrush-tiee-v45. Preserve existing work before changing branches.

## Test credentials and isolation

Generate local test credentials without printing them:

    python - <<'PY'
    from pathlib import Path
    import secrets
    p=Path('.env.v45')
    assert not p.exists(), 'Reuse existing credentials; do not overwrite them'
    p.write_text('POSTGRES_PASSWORD='+secrets.token_hex(24)+'\nAPI_KEY='+secrets.token_hex(24)+'\nPOLICY=tiee\n')
    p.chmod(0o600)
    PY
    set -a
    . ./.env.v45
    set +a
    export COMPOSE_PROJECT_NAME=tiee45pilot
    mkdir -p results/v45

The credential file is ignored by Git. Compose validation overrides remove Gateway host ports, place services on an internal network, and use a shared isolated network namespace. Validation intentionally kills/restarts pilot containers, removes only the pilot Redis stream, injects temporary SQL triggers, and creates disposable test databases. It preserves database volumes and prior results; it does not deploy or interact with external systems.

## Recovery and correctness

    docker compose -p "$COMPOSE_PROJECT_NAME" -f docker-compose.yml -f compose.validation.yml up -d --build
    mkdir -p results/v45
    python -m unittest discover -s tests -v >results/v45/unit-tests-final.log 2>&1
    python -m py_compile app/*.py validation/*.py
    python validation/validate.py integration >results/v45/integration-fixed.log 2>&1
    python validation/v45_extended.py >results/v45/extended.log 2>&1
    python validation/v45_regression.py >results/v45/regression-final-default.log 2>&1

For the connection-reuse candidate, recreate application services and rerun all real-service suites:

    export PG_POOL_SIZE=8
    docker compose -p "$COMPOSE_PROJECT_NAME" -f docker-compose.yml -f compose.validation.yml up -d --force-recreate gateway relay worker
    python validation/validate.py integration >results/v45/pool-integration.log 2>&1
    python validation/v45_extended.py >results/v45/pool-extended.log 2>&1
    python validation/v45_regression.py >results/v45/pool-regression.log 2>&1
    unset PG_POOL_SIZE

## Performance and analysis

    python validation/v45_benchmark.py
    python validation/v45_optimize.py
    python -m venv /tmp/tiee45-analysis
    /tmp/tiee45-analysis/bin/pip install -r results/v45/chart-requirements.txt
    /tmp/tiee45-analysis/bin/python validation/v45_analyze.py
    /tmp/tiee45-analysis/bin/python validation/v45_opt_analyze.py

The first script prespecifies 30 randomized runs: three paired repetitions for each of three training and two held-out workloads. Both arms reject identical bot-labelled events and use one worker process, matching Redis appendfsync=always and PostgreSQL commits. Fresh databases, warmups, hashes and independent output digests establish matching and accounting. A separate probe container hosts the load generator and oracle, excluded from service CPU measurements.

Latency runs from HTTP dispatch through observed SQL completion. Thread-pool scheduling before dispatch is excluded. Completion polls approximately every 20 ms and yields an upper-bound observation; Docker stats sampling is coarse, supplemented by endpoint cgroup memory.

The second script compares ordinary baseline processing with/without bounded PostgreSQL connection reuse (maximum eight connections per application process), using separate randomized pairs and held-out seeds. Any gain belongs to ordinary connection reuse, not the neutral TiEE policy label.

CPU values are cgroup usage differences in seconds for Gateway, relay, worker, Redis and PostgreSQL. RAM is in bytes, with endpoints and sampled peaks. Queue samples include SQL unresolved events and Redis stream length. Storage includes SQL table/index growth, WAL bytes and Redis AOF disk allocation changes. Database and broker volumes are shared across archived trials; background maintenance and coarse AOF allocation may affect deltas.

These commands replace the named final acceptance logs with fresh results. Preserve a copy of results/v45 before rerunning if you need to retain this execution.

Raw evidence, trial plans, metrics, latencies, resource samples, CSV, summaries and figures are in results/v45/. Initial failures remain in separate logs; integration.jsonl retains earlier failures. Read the report's final matrix for current status.

Two behaviorally identical policy arms cannot establish an advantage from a distinct TiEE algorithm. Bootstrap intervals with three pairs per workload are descriptive, not production guarantees.

Generate the verified report and non-secret runtime/hash manifest after the final suites and both analyses:

    python validation/v45_report.py
    python validation/v45_finalize.py

The final manifest hashes source, reports and raw artifacts. Existing archived trial databases are retained; fresh benchmark databases isolate each trial.
