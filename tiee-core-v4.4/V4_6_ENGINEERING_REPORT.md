# TiEE Core v4.6 engineering report

**Performance superiority and a distinct TiEE advantage are not established.** This synthetic pilot implements expected-value admission and scheduling on a conventional durable asynchronous outbox. A4 implements exactly the A3 admission and priority rules; branding supplies no additional mechanism. Correctness passes do not override performance guardrails.

## Preservation and implementation

The existing scaling potato Codespace was reused. Original /workspaces/Dragrush-tiee remains on robotics-v01 at 6e12b5098699ba636cdb1112dd192da74d8f9bb3, with pending work preserved. The backup /workspaces/tiee-backup-20261010T100752Z/ and fresh /workspaces/tiee-preserve-v46-20261011T090841Z/ archive are retained. Preservation comparisons/hashes are in results/v46/preservation*.json. Development uses tiee-core-v46-ev-validation and /workspaces/Dragrush-tiee-v46, based on verified v4.5 commit 0a0334569d5767902d34752fdafedcee4eb3b94c. Private test projects have separate volumes and internal networking. No unrelated work was removed, no additional Codespace created and no production deployment performed.

Observable-only logistic validity estimates feed server-owned rewards, penalties and predicted CPU cost. Immutable SQL receipts and decision history accompany durable ALLOW/DEFER HTTP 202 responses after transaction commit; REJECT returns 200. Duplicates retain original receipts, conflicts return 409, capacity/scorer/database failures return 503. Deferred decisions are durable, bounded to three reevaluations, and expire or become explicit HELD backlog. Generation-fenced SQL leases prevent stale result commits. Results, completion audit and DONE commit atomically. SQL reconciliation republishes lost Redis work. Priority arms include an aged FIFO escape lane. Model files are bounded regular files with finite coefficient validation and a 50 ms post-evaluation scoring budget, which is not a general preemptive inference timeout.

## Tests and limitations

Final executed suites: **24 recovery gates passed; 8 supplementary gates passed; 40 unchanged v4.5 regression gates passed; 13 unit tests passed.** Integration suites cover both PG pool 0 and 8. Evidence is in results/v46/tests/v46_faults.jsonl, supplementary.jsonl, legacy_pool*/integration.jsonl and unit.log. Historical initial_failed_attempt, startup_failure and orchestration_attempt files record failed attempts separately; they are not final passing results.

Coverage includes durable ALLOW/DEFER across PG/Gateway SIGKILL; immutable duplicates/conflicts; capacity/retries; defer bounds/restarts; overlapping/expired claims; XADD/SQL and result rollback; replay/idempotent audit; NaN and slow scorers; spoofed/unauthorized input; aged scheduling; audit failure; concurrent migrations; mixed legacy/new recovery; concurrent relays; AOF recovery without reconciliation; stream loss; and individual PG, Redis, Gateway, relay and worker crashes.

Physical power loss, disk corruption, durable-volume loss, production failover, GPU/robotics integration and automated system-state hysteresis were **UNEXECUTED**. Offline no-cost/no-deferral/Harmony/Destructive/no-aging diagnostics were executed, but their infrastructure throughput, latency and sustained scheduling ablations were **UNEXECUTED**. Fresh labels and larger realistic workloads are needed for external validity.

## Benchmark protocol and accounting

45 randomized training runs, 15 fixed-admission runs, then five arms on held-out normal, shifted-validity and valuable-long-job burst conditions. Frozen confirmation uses 20 paired blocks per condition and 240 events/run. Equal trace hashes and event IDs within paired blocks are recorded. All arms use the same image, PG/Redis durability, pool 8, two workers, reward classes, audit requirements and private infrastructure. Fixed-admission makes every event mandatory critical. Each run has a fresh SQL database and 24 warmup events.

| Arm | Admission | Scheduling |
|---|---|---|
| A0 | Conventional fixed bot filter | FIFO |
| A1 | Conventional fixed bot filter | Deadline and aging |
| A2 | Expected value | FIFO |
| A3 | Expected value | Value/cost and aging |
| A4 | Conventional exact A3 rule | Exact A3 scheduler |

All benchmark kinds pass the fixed bot filter, so A0/A1 are simple controls; A4 is the strong equivalence control. Hidden synthetic validity is generated independently in the probe, never sent to the engine. Training/calibration and confirmation seeds are disjoint. All rejection, expiry, HTTP errors and unresolved/HELD states remain in accounting. Valuable work not completed receives a 25% missed-reward penalty. Net utility subtracts 0.1 units per measured engine CPU second. Synthetic reward units are assumptions, not customer value measurements.

Engine CPU sums gateway, relay, two workers, PG, Redis and network-anchor cgroup deltas. Warmup is excluded, but storage snapshots, submission, drain, verification waits and resource sampling are inside endpoint boundaries. Probe/oracle CPU is separately recorded. Host Docker CLI CPU and energy are unmeasured. Sequential memory samples miss between-sample peaks. Shared PG/Redis history affects memory and storage: fresh databases isolate event accounting, but retained databases/cache and persistent AOF history can affect later runs. Randomization limits this effect. SQL table growth, WAL advancement and allocated AOF growth are recorded; AOF rewrites can produce negative growth.

The Codespace stopped after 48 saved confirmation runs. The interrupted unsaved attempt was retried on a fresh database under unchanged frozen hashes. This is documented in resume_checkpoint.json. The first resume failed before submission while PG was recovering; its startup-attempt log remains. Restart segmentation is a measurement limitation.

Bootstrap intervals use 20,000 paired trace-block resamples, independent within condition with equal condition weights. Three planned efficiency contrasts use Bonferroni 98.333% intervals; 95% intervals are descriptive. Valid-rejection acceptance requires one-sided 95% upper bound at most 1%; calibration requires paired Brier-difference upper 95% below zero against frozen training prevalence. Any failed power, rejection, calibration, drain or utility guard prevents performance acceptance. A3/A4 exact numerical decisions were checked over 2,000 unit examples; timing variation between them is not a distinct TiEE causal benefit.

## Analysis, optimization and next decisions

Scoring, worker digest CPU, queue and SQL-completion timings are retained. Small digest jobs, durable per-event transactions/audit, polling and the admission advisory lock can dominate useful worker computation. A component-level causal speedup is not established without an isolated ablation. This implementation adds bounded publication, pooled connections, SQL fencing and aged FIFO escape, verifies correctness and compares complete algorithms; it does not prove each change's isolated speed contribution.

The next experiment should profile admission serialization and durable SQL/audit cost, then test batching and reduced polling without weakening receipts or durability. Keep a conventional calibrated-filter control. Tune thresholds under explicit valid-rejection constraints; implement and validate drift monitoring with independently labeled traces. Specify a final HELD disposition. Freeze a larger useful-CPU workload separately and budget adequate power. Offline policy counterfactuals cannot establish throughput benefits.

## Reproduction and evidence

REPRODUCE_V4_6.md contains private credential setup, classic Docker-build fallback, isolated suites and training/freeze/confirmation commands. The frozen plan lists randomized jobs, source/model hashes and trace hashes. Raw runs are losslessly gzip-compressed with deterministic metadata to stay below GitHub file limits; decompress to runs.jsonl before analysis or resume. All charts derive from measured data. Artifact hashes are in results/v46/artifact_manifest.json. Private .env and credentials are excluded. This is development work; no PR merge or deployment was performed.

All private containers have the same unconstrained CPU/RAM configuration (no per-container quotas), sharing the existing two-core host; two workers run per arm. Probe/oracle and host orchestration contend for this host despite exclusion from engine cgroup CPU. Redis appendonly=yes/appendfsync=always and PG fsync/full_page_writes/synchronous_commit=on were verified in environment_verified.json. These results apply to this shared-host pilot, not dedicated production resources.

Report preparation and checkpoint compression occurred on the shared host during resumed confirmation, adding uncontrolled host contention. Results are therefore exploratory even apart from failed acceptance gates. The per-stage timer restarts on process resume; cumulative live Codespace wall-time budget compliance was not measured and is UNVERIFIED. Confirmation elapsed time including the stop is separately recorded. No billing plan, paid limit, machine size or resource allocation was changed.

## Recorder defect and protocol failure

After 213 completed measurements, confirmation job 213 (A2, shifted validity, block 13) failed in the recorder after submission exceeded the drain window: an uninitialized state summary raised UnboundLocalError. The database snapshot, decision history, audit and driver traceback remain in tests/confirmation_failed_recorder_attempt.json and confirmation-resume-driver.log. The snapshot contains 236 SQL event rows from 240 submitted events. Original HTTP timings, engine CPU endpoints and full resource samples are unavailable for this failed attempt; they are not fabricated or silently counted as measured success.

A minimal recorder-only fix initializes the state summary and derives it from the already-fetched database rows when no drain poll occurred, with no extra I/O. The engine, model, workload generator, trace hashes, admission rules and worker execution were unchanged. observation_amendment.json preserves both recorder hashes and the amendment boundary. A real Redis/PostgreSQL regression delayed client receipt handling for six seconds; all six submitted events completed with verified digests and correct state accounting. This additional recorder regression PASSED in pool 8. The original frozen-observation/no-exclusion recording protocol therefore FAILED; the 300 completed planned measurements include a fresh-database retry of the missing job and remain exploratory. The failed measurement attempt is counted separately and must accompany interpretation of completed-run statistics.

## Terminal timing coverage

The raw recorder uses ACK time as a fallback when its SQL poller did not observe a terminal state. For DONE/EXPIRED this can misstate completion latency. Final summaries mark those timings as missing by detecting the unchanged ACK fallback; raw JSON is preserved. HELD remains backlog and is excluded from completed terminal-latency distributions. REJECT is terminal after its durable SQL receipt, so its ACK can bound rejection latency. The valuable-DONE table contains observed completion timings only; metrics_by_arm.json reports missing DONE timing counts and known timing coverage. stage_metrics.csv keeps the raw estimates alongside known/missing flags. These conditional observations do not remove unsuccessful work from utility or throughput accounting. SQL intervals remain available for committed results; these are database transaction timestamps, not client acknowledgment timestamps. Incomplete terminal coverage is a FAILED measurement gate, not evidence of lower latency.

Useful throughput uses recorder wall_seconds from submission start to drain stop, excluding post-drain ledger retrieval and digest verification. Engine cgroup CPU brackets those additional operations and verification waits. These boundaries differ and are reported explicitly; this pilot does not measure production full-pipeline wall throughput or energy. Recorded per-event digest CPU covers committed results; expired/abandoned attempt CPU remains in engine cgroup CPU but may be missing from that subtotal. The utility-ledger CSV marks original recorder latency fields with raw_ names, and stage_metrics.csv carries the timing-coverage flags. Descriptive latency percentiles are conditional observations, not whole-workload latency claims.

## Performance gate status

```json
{
  "confirmation_complete": "PASSED",
  "power": "FAILED",
  "valid_rejection": {
    "normal": "FAILED",
    "shift": "FAILED",
    "burst": "FAILED"
  },
  "calibration": {
    "normal": "PASSED",
    "shift": "PASSED",
    "burst": "PASSED"
  },
  "A3_drain": "FAILED",
  "all_arm_http": "FAILED",
  "performance_acceptance": "NOT ESTABLISHED",
  "recording_protocol": "FAILED original frozen-observation/no-exclusion requirement; recorder amended after one missing measurement",
  "complete_terminal_latency": "FAILED"
}
```

Performance acceptance is distinct from the final correctness suites. HTTP/overload failures and HELD backlog remain in raw accounting.

## Final measured results

Confirmation completed: 300 runs, 60 paired blocks.

| Arm | Useful/s | Net utility/CPU s | CPU s/run | Sampled peak MiB | Queue peak | Drain failures | HTTP errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0 | 13.569 | -4.546 | 8.188 | 446.582 | 138 | 30 | 7 |
| A1 | 13.723 | -4.534 | 8.280 | 448.672 | 146 | 28 | 6 |
| A2 | 20.912 | 11.705 | 7.282 | 450.918 | 81 | 19 | 8 |
| A3 | 20.779 | 12.282 | 7.286 | 446.277 | 74 | 16 | 17 |
| A4 | 20.821 | 11.931 | 7.259 | 447.969 | 79 | 16 | 3 |

Throughput and CPU columns are means across runs; memory and queue columns are maxima. Useful throughput counts completed valuable events. All metrics are in metrics_by_arm.json/CSV; stage and resource timing exports accompany them.

| Arm | Offered p50/p95/p99 ms | Dispatch p50/p95/p99 ms | ACK mean-run p50/p95/p99 ms | SQL/WAL/AOF mean growth KiB |
|---|---|---|---|---|
| A0 | 3177.458 / 4985.634 / 5289.703 | 1954.276 / 3421.560 / 3553.949 | 485.187 / 732.330 / 920.975 | 1051.467 / 1610.615 / 117.067 |
| A1 | 3140.467 / 4987.714 / 5212.509 | 1928.240 / 3412.742 / 3536.098 | 473.804 / 697.034 / 888.479 | 1051.200 / 1614.160 / 117.400 |
| A2 | 1939.446 / 4052.962 / 4633.576 | 827.424 / 1918.423 / 2075.470 | 468.611 / 689.967 / 888.964 | 914.000 / 1349.298 / 83.067 |
| A3 | 1934.364 / 4014.660 / 4485.957 | 802.603 / 1935.685 / 2084.330 | 471.913 / 712.792 / 933.064 | 923.467 / 1380.679 / 83.133 |
| A4 | 1971.398 / 4082.112 / 4568.330 | 819.987 / 1938.889 / 2132.032 | 468.702 / 702.831 / 964.717 | 914.667 / 1428.202 / 82.667 |

### Conditional valuable-completion latency

| Arm | Valuable DONE offered p50/p95/p99 ms | Valuable DONE dispatch p50/p95/p99 ms | Recorded completed digest CPU / engine CPU |
|---|---|---|---|
| A0 | 2481.920 / 4770.783 / 5197.501 | 1810.657 / 3263.083 / 3435.730 | 10.99% |
| A1 | 2438.533 / 4760.944 / 5156.497 | 1756.555 / 3274.801 / 3426.575 | 11.09% |
| A2 | 2099.080 / 3931.529 / 4549.069 | 1130.712 / 1877.335 / 2332.750 | 12.26% |
| A3 | 2122.540 / 3912.945 / 4433.030 | 1147.510 / 1910.738 / 2129.802 | 12.39% |
| A4 | 2175.191 / 4008.429 / 4552.685 | 1167.771 / 1942.408 / 2236.338 | 12.42% |

Valuable DONE latency is conditional on successful completion; failures remain in the utility ledger and guardrails. Recorded digest CPU covers committed valid and invalid completions; expired or abandoned attempt CPU remains in engine cgroup CPU but may be absent from per-event digest CPU.


Offered/dispatch percentiles include observed DONE/EXPIRED timing and durable REJECT acknowledgments; unobserved completion timing is omitted as missing, HELD backlog is excluded, and all failures remain in utility accounting. ACK entries are means of run percentiles. Known timing coverage and unobserved DONE counts are in metrics_by_arm.json; raw ACK-fallback estimates are retained with flags in stage_metrics.csv.

Training required 107 blocks/condition for the frozen 10% minimum effect; only 20 were budgeted. Power gate FAILED.

| Contrast | Utility/CPU difference | Adjusted interval | Total utility difference/run |
|---|---:|---|---:|
| A3 - A1 | 16.815 | [15.392, 18.319] | 125.641 |
| A3 - A4 | 0.350 | [-0.671, 1.283] | 3.133 |
| A3 - A0 | 16.828 | [15.130, 18.442] | 125.163 |

| Condition | Valid rejection rate / upper 95% | Brier difference / 95% interval | A3 drain failures |
|---|---|---|---:|
| normal | 16.81% / 18.17% | -0.1225 / [-0.1298, -0.1152] | 6 |
| shift | 10.71% / 11.91% | -0.1148 / [-0.1202, -0.1092] | 6 |
| burst | 13.58% / 14.57% | -0.1213 / [-0.1265, -0.1158] | 4 |

## Measured crash recovery

| Pool | Service | Seconds |
|---|---|---:|
| 0 | durable receipt crash verification | 0.765 |
| 0 | redis | 4.853 |
| 0 | gateway | 5.422 |
| 0 | relay | 4.637 |
| 0 | worker | 3.601 |
| 0 | postgres | 12.076 |
| 8 | durable receipt crash verification | 0.613 |
| 8 | redis | 2.692 |
| 8 | gateway | 2.816 |
| 8 | relay | 2.676 |
| 8 | worker | 2.707 |
| 8 | postgres | 8.071 |

Recovery duration includes test restart and terminal-result verification, not a production SLA.

Performance superiority and a distinct TiEE advantage remain NOT ESTABLISHED. Complete raw accounting and multiplicity-adjusted paired intervals are in analysis.json and efficiency.svg.
