# Reproduce TiEE Core v4.6

This is a private synthetic CPU-digest experiment, not a deployment. Use the existing scaling potato Codespace and `/workspaces/Dragrush-tiee-v46/tiee-core-v4.4` on `tiee-core-v46-ev-validation`. Preserve the original robotics checkout and all pilot volumes. Never use `down -v`, prune unrelated Docker data, or merge this branch automatically.

## Private credentials and build

Generate `.env.v46` locally with independent random `API_KEY` and `POSTGRES_PASSWORD`, and `PG_POOL_SIZE=8`. Set permissions to 0600. This file is ignored and must never be committed or printed.

```bash
python - <<'PY'
import pathlib,secrets
p=pathlib.Path('.env.v46')
if not p.exists():
    p.write_text('API_KEY='+secrets.token_hex(24)+chr(10)+'POSTGRES_PASSWORD='+secrets.token_hex(24)+chr(10)+'PG_POOL_SIZE=8'+chr(10))
    p.chmod(0o600)
PY
DOCKER_BUILDKIT=0 docker build -t tiee46pilot-gateway .
python - <<'PY'
import subprocess
for s in ('relay','worker','probe','network_anchor'):
    subprocess.run(['docker','tag','tiee46pilot-gateway','tiee46pilot-'+s],check=True)
PY
docker compose -p tiee46pilot --env-file .env.v46 -f docker-compose.yml -f compose.validation.yml -f compose.v46.yml up -d --no-build --scale worker=2
```

Classic build avoids the observed BuildKit missing-layer and missing-parent-snapshot errors. It does not delete caches, archives, or volumes. The validation overlay removes the Gateway port binding and uses an internal Docker network. Redis AOF and PostgreSQL durability settings must be checked from running services.

## Correctness

```bash
python -m unittest discover -s tests
python validation/v46_legacy.py
python validation/v46_faults.py
python validation/v46_supplementary.py
```

The legacy script runs the original 20 gates in each connection profile against the compatible legacy modules. The v4.6 fault script runs 12 new gates in each profile. Supplementary tests target deferred receipts, AOF without reconciliation, mixed old/new data, and competing schedulers. All tests use real private Redis/PostgreSQL and archived trial databases. Append-only evidence includes failures; use a fresh evidence directory or archive previous files before a new independent round.

## Training and confirmation

Keep the committed model to reproduce the recorded plan. Regenerating it changes CPU cost measurements and its hash, requiring a new plan and fresh untouched confirmation seeds.

```bash
python validation/v46_train.py
python validation/v46_ablations.py
python validation/v46_benchmark.py training
python validation/v46_benchmark.py fixed_admission
python validation/v46_benchmark.py freeze
python validation/v46_benchmark.py confirmation
python validation/v46_analyze.py
```

`v46_round.py` waits for completed passing recovery matrices, runs supplementary gates, then invokes the benchmark stages sequentially with time limits. The benchmark creates a fresh SQL database per run and keeps it. Resume only an interrupted frozen plan: completed indexes are skipped. An independent rerun must use an archived/new evidence destination and the original frozen policy.

Training, calibration, and confirmation seeds are disjoint. Hidden truth is held only by the probe. Open-loop scheduled and actual dispatch times are both recorded. A3 and A4 intentionally execute the same observable mathematical rule; no additional TiEE mechanism is implemented. Fixed-admission workloads authorize every event through the mandatory critical task class, giving all arms the same admitted set while preserving identical rewards and scoring overhead.

## Contract and rollback

The only authorized application values are the predefined task classes: standard `(reward=1, penalty=2)`, bulk `(0.5,1)`, critical `(8,8)`. The pilot API key authorizes those classes, including mandatory critical work. Arbitrary client reward, probability, priority, or system-weight fields are refused. This is not a production role system.

Migration is transactional and protected by PostgreSQL advisory lock 73420. Existing payload fingerprints, results, and audit rows stay intact. New columns and `decision_history` retain versions, receipts, claims, deadlines, and numeric EV decisions. Legacy rows can complete through v4.6 workers without new features.

To roll back, stop admission, drain all PENDING/ENQUEUED/RUNNING/DEFERRED events, investigate HELD events, archive SQL with `pg_dump`, and stop only the pilot project. Then omit `compose.v46.yml` to select the legacy modules. Keep the expanded schema and all history; do not drop new columns or rewrite accepted receipts. Legacy HTTP response shapes differ from v4.6 receipt shapes, so retain the v4.6 read interface for clients that require original versioned receipts. No destructive schema downgrade is supplied.

Primary trials fix the system to Nominal. Harmony/Destructive are explicit test inputs; automated observed-state hysteresis is not implemented. The 50ms scorer budget refuses an over-budget decision after returning from bounded local model evaluation; it is not a general preemptive deadline for arbitrary inference or filesystem hangs.

## Evidence limits

Cgroup CPU endpoints bracket storage snapshots, submission, drain, verification, and resource sampling. Engine CPU includes the gateway, relay, both workers, PostgreSQL, Redis, network anchor, and sampler processes executed inside their cgroups. Probe/oracle CPU is separate; host Docker CLI overhead is unmeasured. Memory samples include working set estimates, with actual timestamps and unobserved peaks between samples.

No physical power-loss, simultaneous durable-volume-loss, GPU, production-scale, external-side-effect, or physical-robotics test is implied. Offline ablations do not establish infrastructure speed improvements. A failed valid-rejection guardrail or insufficient confirmation power blocks a positive performance acceptance claim.

Raw run JSONL archives are committed as runs.jsonl.gz. Decompress before analysis or resume:

    python -c "import gzip,pathlib; [p.with_suffix('').write_bytes(gzip.decompress(p.read_bytes())) for p in pathlib.Path('results/v46').glob('*/runs.jsonl.gz')]"

After analysis, run python validation/v46_report.py to export stage/resource CSV metrics, regenerate the report, and produce deterministic lossless raw archives.
