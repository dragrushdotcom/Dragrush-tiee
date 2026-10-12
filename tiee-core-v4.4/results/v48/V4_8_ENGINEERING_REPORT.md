# TiEE Core v4.8 engineering report

**Decision: retain the 5 ms default.** The 20 ms relay polling candidate failed the frozen held-out adoption gate. This experiment changes generic relay cadence within the same A3 execution policy; it does not establish an advantage for TiEE over conventional asynchronous processing.

## Scope and gate results

36 measured runs (18 training, 18 held-out; 9 matched pairs per stage), 0 offered requests, 240 per run. Workloads were normal, shifted, and burst, with 3 randomized blocks and paired baseline/candidate executions. The analysis uses a frozen 20,000-resample stratified paired bootstrap and 98.333% intervals for three endpoints.

Baseline relay poll is 5 ms; candidate is 20 ms. Both used A3, two workers, matched images/resources, PostgreSQL and Redis durability settings, fresh databases, and paired payloads. Poll cadence is the tested change.

| Stage | Operational | Additional valid loss | Mean targets | CPU/useful change (98.333% CI) | Useful/s change (98.333% CI) | Offered p95 change (98.333% CI) |
|---|---|---|---|---|---|---|
| training | PASS | No | PASS | -5.08% (-7.26%, -3.12%) | -3.48% (-5.79%, -0.55%) | +5.67% (+1.72%, +9.36%) |
| heldout | PASS | No | FAIL | -3.69% (-6.97%, -0.86%) | -4.06% (-6.91%, -0.72%) | +7.77% (+1.00%, +13.00%) |

Training means passed the frozen mean targets. Held-out CPU/useful improved 3.69%, below the required 5%. The held-out CPU interval upper bound was below zero, but the throughput interval lower bound (−6.91%) crossed the allowed −5% and the offered p95 interval upper bound (+13.00%) exceeded +10%. The gate failed; the 5 ms default remains.

## Measured performance

Latency percentiles pool offered-request terminal observations in the raw ledger. RAM is mean per-run peak; queue is recorded peak; table, WAL, and AOF are mean per-run storage growth. CPU covers six engine containers and excludes the probe process.

| Stage | Variant | Useful | Useful/s | CPU s/run | CPU s/useful | Terminal p50/p95/p99 ms | Peak RAM MB | Peak queue | Table/WAL/AOF growth bytes/run | HTTP/poll/drain errors | HELD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| training | baseline | 1252 | 18.074 | 10.553 | 0.07726 | 1802.6/6207.7/7325.2 | 37.3 | 142 | 1933312/2713777/134258 | 0/0/0 | 0 |
| training | candidate | 1252 | 17.484 | 10.026 | 0.07359 | 1932.7/6318.4/7356.2 | 37.1 | 158 | 1927851/2754667/133348 | 0/0/0 | 0 |
| heldout | baseline | 1274 | 18.224 | 10.665 | 0.07691 | 1808.1/6187.4/7029.5 | 40.5 | 147 | 2013412/2588933/133348 | 0/0/0 | 0 |
| heldout | candidate | 1274 | 17.501 | 10.269 | 0.07411 | 1991.3/6669.9/7633.6 | 40.3 | 156 | 1987015/2593653/133348 | 0/0/0 | 0 |

All benchmark variants completed drain with zero HTTP, poll, or drain failures and zero HELD events. Training candidate had one valid non-DONE result, with no additional valid loss versus its paired baseline. Exact classifications and observations are retained in analysis.json and terminal_ledger.csv.

## PostgreSQL profile and relay diagnostics

Baseline diagnostics captured 421 pg_stat_activity samples. Normalized pg_advisory_xact_lock($1) had 1,449 calls and 3,714 ms cumulative SQL time; normalization merges lock keys 73421 and 73422, so this cannot be assigned to admission or relay alone. The worker payload/state/generation/deadline FOR UPDATE query had 260 calls and 852 ms cumulative SQL time. These are SQL timings, not CPU time. Wait events included gateway advisory-lock waits and worker WAL sync and transaction-id waits. Full profile is in baseline_statements.json and baseline_wait_samples.json.

Expired-event recovery scan query counts (secondary diagnostic):

| Stage | 5 ms baseline mean calls | 20 ms candidate mean calls | Change |
|---|---:|---:|---:|
| training | 1209.89 | 482.56 | -60.12% |
| heldout | 1208.22 | 488.67 | -59.55% |

This is a query-count diagnostic, not a measurement of end-to-end recovery duration. It shows less repeated scan traffic from the longer poll interval, not architectural TiEE advantage.

## Correctness and recovery

The corrected Redis/PostgreSQL integration suite passed 18/18 checks across pool sizes 0 and 8. Nine checks per pool covered receipt crash recovery, bounded deferral, expired leases, rollback fencing, reconciliation, capacity/authentication, terminal recording, reject/scorer handling, and audit-marker rollback. Raw timings are in tests/integration.jsonl and tests/recorder_pool0.json, tests/recorder_pool8.json.

Redis AOF/appendfsync always, restart and stream-loss recovery; PostgreSQL, Gateway, relay and worker crash/restart paths; duplicate/conflict, safe retry, transaction rollback, lease fencing, durable/idempotent records were exercised. The poll validator passed 11 default and boundary cases (poll_config.json).

The first integration setup attempt is retained in tests_attempt_1: malformed generated Compose blocked 17 cases during setup; one atomic-commit check passed. Those are setup failures, not engine failures. The first PostgreSQL profile export also failed on version-specific column names; the failed attempts and corrected profile are retained.

## Analyzer correction

The pre-collection analyzer source validation/v48_analyze.py was frozen before runs, but its final aggregation summed poll_errors as a scalar although raw records store it as a list. Its failed traceback is retained. validation/v48_analyze_postcollection.py changes only that aggregation to sum list lengths; pairing, data, endpoints, bootstrap, and thresholds are unchanged. Hashes and the correction are in ANALYZER_CORRECTION.md; successful output is analysis-driver-postcollection.log.

Reproduction commands are in REPRODUCE_V4_8.md. plan.json and plan.sha256 record the preregistered source freeze. Lossless raw run records are runs.jsonl.gz and runs.csv; terminal_ledger.csv and resource_samples.csv retain request/resource observations.

## Passed, failed, unexecuted

- **Passed:** 18/18 corrected integration checks; 11/11 poll config cases; 36/36 benchmark runs with paired traces, zero HTTP/poll/drain failures; all 8,640 offered requests retained; source/environment checks recorded.
- **Failed:** frozen adoption gate; initial generated-Compose setup (17 blocked cases); first profiler export (column mismatch); first frozen analysis aggregation (poll_errors type mismatch), corrected in the retained post-collection analyzer.
- **Unexecuted:** physical power-loss, host-loss, disk-corruption tests; powered superiority study; other admission-lock/schema/batching changes; production workload validation. No production deployment.

## Conclusion

On held-out runs, 20 ms polling reduced recovery-scan query calls by about 60% and mean CPU per useful result by 3.69%, but missed the 5% CPU target and failed throughput and latency interval guardrails. This is evidence about generic relay cadence only. TiEE superiority over conventional asynchronous processing remains unestablished; retain the 5 ms default.

![Paired endpoint intervals](paired_endpoints.png)

![Held-out engine component CPU](component_cpu.png)
