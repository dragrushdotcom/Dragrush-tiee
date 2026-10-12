# TiEE Core v4.9 Admission Profile

Date: 2026-10-12
Branch: `tiee-core-v49-admission-profile`
Parent: v4.8 report correction `46a5e37869926581016c76e0a8ccee4b28365d3e`

## Scope and result

This round added opt-in Gateway timing instrumentation and ran one private synthetic Redis/PostgreSQL profile workload. It did not implement an optimization, compare TiEE with a conventional asynchronous baseline, or establish a performance advantage. Measurements are diagnostic only.

## Environment and method

Used the existing `scaling potato` Codespace and a separate worktree at `/workspaces/Dragrush-tiee-v49`. The private Compose stack used Redis, PostgreSQL, Gateway, relay, worker, and probe on the repository validation network namespace topology. No host ports were forwarded. The workload sent 120 seeded benchmark traces at target rate 40 requests/s with concurrency 8. Each request used a unique trace id. Raw per-request Gateway timing samples are in `results/v49/admission_samples.jsonl`; the computed summary is in `results/v49/admission_summary.json`.

Gateway instrumentation is disabled unless `TIEE_ADMISSION_PROFILE=1`. It records connection/begin time, advisory-lock wait, total transaction time, and elapsed time from acquiring the advisory lock until transaction commit returns. The last measure is an **upper bound** for lock-held duration because it includes commit return; it is not a direct measurement of PostgreSQL lock release. Logging runs after commit and does not change the HTTP response.

## Actual result

| Measure | Mean ms | p50 ms | p95 ms | p99 ms | Max ms |
|---|---:|---:|---:|---:|---:|
| Connection and begin | 2.127 | 0.644 | 16.840 | 22.721 | 24.534 |
| Advisory lock wait | 48.838 | 40.416 | 96.609 | 115.713 | 116.614 |
| Lock to commit upper bound | 7.307 | 5.751 | 15.368 | 23.740 | 34.657 |
| Whole transaction | 58.272 | 47.622 | 111.250 | 132.071 | 132.713 |

HTTP responses: 118 x 202 and 2 x 200. PostgreSQL reconciled to 120 event rows (118 ACCEPT, 2 REJECT) and 118 result rows. This matches the response outcome and result accounting for this workload. These counts do not by themselves validate crash recovery, Redis AOF, stream loss, or all v4.5 acceptance cases.

## Test and setup record

- **Passed:** Compose configuration validation on the documented private validation topology; Gateway/client/analyzer Python compilation; `git diff --check`; 120-request workload completed; PostgreSQL event/result accounting reconciled (120 / 118 accepted / 2 rejected / 118 results).
- **Failed setup attempt, corrected:** an initial Compose validation omitted `compose.validation.yml`, which left the probe service without an image/build definition. A subsequent initial stack attempt used the wrong network topology and could not reach PostgreSQL. No conclusion was drawn from those attempts. The documented validation topology was applied, services rebuilt, and the workload above completed.
- **Not run in v4.9:** candidate-vs-control benchmark, repeated randomized runs, held-out confirmation, CPU/RAM/storage/queue-depth measurement, crash/restart and AOF tests, broad recovery/integration suite, or an optimization. v4.8's 18/18 integration checks remain the prior round's result, not a v4.9 rerun.

## Interpretation and next experiment
### Safe-candidate review

Connection pooling was considered because connection and transaction begin averaged 2.127 ms, about 3.65% of the 58.272 ms mean transaction time in this single run. That is only an estimate of the measured component, not a projected pooling gain. The runtime does not currently include `psycopg_pool`, and a persistent-connection pool would add connection lifecycle and restart behavior that needs its own correctness and crash tests. Given advisory-lock wait averaged 48.838 ms, this profile does not justify introducing that complexity. **Decision: defer connection pooling; no performance optimization was implemented or tested in v4.9.** A matched randomized benchmark is required before revisiting it.


The largest observed component in this single profiled run was advisory-lock wait. Because all requests contend on capacity accounting and this run used concurrency 8, the result is consistent with serialization being a bottleneck. The sample is small and instrumented; it has no matched baseline and no uncertainty interval. It is not enough to estimate the production bottleneck or justify removing capacity serialization. Keep the durable 202 behavior and serialization intact.

Next, run paired randomized baseline and candidate workloads on identical private infrastructure, with multiple independent runs and a held-out workload. Measure useful throughput, terminal latency, CPU/RAM, queue depth, storage, error rates, and recovery duration; report confidence intervals. Any candidate must retain durable acknowledgments and capacity safety.

## Reproduction

From `/workspaces/Dragrush-tiee-v49/tiee-core-v4.4`, with the existing private validation environment file available at the path below (do not print it or enable shell tracing):

```bash
ENV_FILE=/workspaces/Dragrush-tiee-v47/tiee-core-v4.4/.env.v47
DC='docker compose -p tiee49admission --env-file'
$DC "$ENV_FILE" -f docker-compose.yml -f compose.v47.yml -f compose.validation.yml -f compose.v48.yml -f compose.v49.profile.yml config --quiet
$DC "$ENV_FILE" -f docker-compose.yml -f compose.v47.yml -f compose.validation.yml -f compose.v48.yml -f compose.v49.profile.yml up -d --build
$DC "$ENV_FILE" -f docker-compose.yml -f compose.v47.yml -f compose.validation.yml -f compose.v48.yml -f compose.v49.profile.yml exec -T probe python /validation/v49_admission_client.py
$DC "$ENV_FILE" -f docker-compose.yml -f compose.v47.yml -f compose.validation.yml -f compose.v48.yml -f compose.v49.profile.yml logs --no-color --no-log-prefix gateway | sed -n 's/^.*TIEE_ADMISSION_PROFILE //p' > results/v49/admission_samples.jsonl
python validation/v49_admission_analyze.py
$DC "$ENV_FILE" -f docker-compose.yml -f compose.v47.yml -f compose.validation.yml -f compose.v48.yml -f compose.v49.profile.yml stop -t 5
```

