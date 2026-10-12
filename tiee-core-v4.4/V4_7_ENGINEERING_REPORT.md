# TiEE Core v4.7 acceptance pilot report

Completed development experiment. Performance superiority and a distinct TiEE advantage are **NOT ESTABLISHED**.

## Result

27/27 randomized matched runs completed; 6,480 events accounted. All 18 real Redis/PostgreSQL integration checks passed across pool 0 and 8; a 2,000-example A3/A4 policy parity check passed. IID acceptance screening: **FAILED**. Clustered production risk and superiority power remain unestablished.

## Useful-work guardrails

| Condition | Valid events | Rejected | Not DONE | Loss / exact upper 95% | IID screen |
|---|---:|---:|---:|---|---|
| normal | 496 | 1 | 1 | 0.202% / 0.953% | PASSED |
| shift | 373 | 0 | 0 | 0.000% / 0.800% | PASSED |
| burst | 486 | 0 | 0 | 0.000% / 0.615% | PASSED |

All-cause loss includes valid rejections, expired events, HTTP refusals and unfinished obligations. Do not reinterpret deferral as successful execution. One-sided exact Clopper-Pearson 95% intervals are reported under the synthetic IID validity assumption. The frozen plan named Wilson bounds; this final analysis additionally requires stricter exact bounds, a conservative reporting amendment rather than preregistered confirmation. The largest per-trace losses and counts are retained in analysis.json; three trace blocks per condition cannot establish a production-level clustered loss bound.

## Measured execution

| Arm | Useful/s mean | Net utility/CPU mean | Engine CPU s/run | HTTP / poll errors | Drain failures | Missing terminal times | RAM peak MiB | Queue peak |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| A1 | 19.875 | 4.074 | 10.330 | 0 / 0 | 0 | 0 | 332.23 | 146 |
| A3 | 19.497 | 4.777 | 10.449 | 0 / 0 | 0 | 0 | 333.63 | 144 |
| A4 | 19.372 | 4.806 | 10.564 | 3 / 0 | 0 | 0 | 333.41 | 150 |

| Arm | Offered observed p50/p95/p99 ms | Dispatch observed p50/p95/p99 ms | ACK p50/p95/p99 ms | SQL/WAL/AOF mean growth KiB |
|---|---|---|---|---|
| A1 | 1736.16 / 6338.47 / 7236.12 | 1440.34 / 4609.37 / 5055.03 | 336.83 / 612.27 / 1018.47 | 1519.11 / 2106.39 / 132.89 |
| A3 | 1778.08 / 6449.32 / 7375.39 | 1581.91 / 4590.30 / 5062.55 | 376.57 / 642.88 / 714.49 | 1953.78 / 2596.12 / 131.11 |
| A4 | 1986.67 / 6176.73 / 7001.59 | 1645.62 / 4585.64 / 5074.77 | 356.81 / 578.48 / 779.12 | 1952.00 / 2583.06 / 131.56 |

Observed terminal latency is an upper observation bound from polling or the final committed SQL snapshot. SQL terminal_at is written atomically with terminal state/audit/results before transaction commit; terminal_state_write_seconds is a separate server-side interval, not a measured fsync completion time. Neither uses ingestion ACK as completion. Expired and rejected outcomes are in the distributions; useful DONE counts and losses are separately reported.

## Exploratory paired differences

| Contrast | Net utility/CPU difference | Bonferroni 97.5% interval |
|---|---:|---|
| A3 minus A4 | -0.029 | [-0.300, 0.246] |
| A3 minus A1 | 0.703 | [0.403, 1.018] |

20,000 paired trace-block resamples, independently within condition, equal condition weights. Two planned comparisons use Bonferroni 97.5% intervals; 95% descriptive intervals are retained. Only three blocks/condition: these are exploratory estimates, not a powered confirmation. A4 uses the exact A3 rules. Model/admission differences may explain gains against A1; names do not create a separate mechanism.

## Profile and optimization decision

| Arm | Largest CPU component | Share | Scoring p95 ms | Admission-lock wait p95 ms | Prewrite transaction p95 ms | Recorded digest CPU share |
|---|---|---:|---:|---:|---:|---:|
| A1 | postgres | 42.82% | 1.921 | 162.992 | 587.064 | 14.94% |
| A3 | postgres | 43.20% | 2.021 | 162.068 | 618.906 | 14.50% |
| A4 | postgres | 43.37% | 2.176 | 158.111 | 546.167 | 14.31% |

Admission timing profiles come from first committed decision_history rows retrieved after measurement; the raw terminal ledger is unchanged. Component cgroup CPU, admission lock wait, scoring time and prewrite transaction time are measurements. They are not isolated causal speedups: probe polling, database operations, serialization, WAL and audit share these costs. Prewrite timing excludes the remaining SQL write and commit. Host Docker CLI CPU is unmeasured. Recorded digest CPU includes completed attempts; abandoned attempt CPU can remain only in cgroup totals. RAM samples can miss peaks and shared database/AOF history can affect later runs.

Next optimization should target the measured dominant component with an isolated conventional-control experiment. Test reduced polling and, if SQL cost remains dominant, transactional batching that retains per-event receipts, idempotence and lease fencing. Batching and infrastructure scheduling ablations are **UNEXECUTED** this round; no speed claim is made for them.

## Recovery and preservation

The original robotics workspace stays at 6e12b5098699ba636cdb1112dd192da74d8f9bb3 with its pending work preserved. The 20261010T100752Z and v4.6 preservation backups remain. v4.6 commit 5c811e7467f66097fd1de88d7d3d4ed252828728 and its worktree are unchanged. v4.7 uses separate source modules and tiee47pilot internal services/volumes; no additional Codespace, production exposure or deployment. Private environment files are ignored.

Passed real tests: durable 202 receipts across PG/Gateway SIGKILL; immutable duplicates/conflicts; terminal marker/audit replay; bounded uncertainty release; Destructive/scorer expiry without indefinite HELD; legacy HELD deadline expiry; XADD transaction rollback; atomic result/marker rollback; stale lease fencing; Redis AOF restart plus stream loss; Gateway/relay/worker/PG recovery; capacity/auth/spoof/safe retry; delayed receipt with disabled polling; low-probability REJECT marker; scorer refusal; audit-trigger failure rollback. Test details and recovery durations are in tests/integration.jsonl.

## Limits and reproduction

The 27-run pilot uses rates 40/s normal and 80/s shift/burst, 12-second deadlines, two workers, PG pool8, AOF always, synchronous durable SQL, a fresh database/run and 24 warmup events. This differs from v4.6 overload rates and short deadlines. Cross-round latency, throughput and loss differences are not isolated causal effects of the policy. Calibration used only seed470002 and unchanged coefficients; held-out seeds470100/470200/470300 plus block index were frozen with source/model/trace hashes before collection. The 0.02 cap was selected on calibration Wilson bounds <=0.25%; final held-out rejection and all-cause losses use more conservative exact bounds.

Physical power loss, disk corruption, durable-volume loss, production failover, GPU/robotics integration, automatic learning/hysteresis, large powered confirmation and the entire unchanged v4.5 regression suite rerun under v4.7 are **UNEXECUTED**. Historical v4.6 tests/results are preserved, not counted as newly executed v4.7 passes. The initial source-generator quoting error was corrected before compilation/build/tests; it was an orchestration failure, not a passing test. No failing measurement is silently excluded.

REPRODUCE_V4_7.md contains setup, tests, freeze, collection, analysis and figure commands. Raw runs, terminal ledger, resources, queue samples, storage and profile values are preserved as JSON/CSV. Scientific figures are generated by Matplotlib 3.11.2. All artifact hashes are recorded in artifact_manifest.json.


## Post-pilot HTTP backlog correction

The frozen 27-run pilot remains at commit 721e3bf36f1eaf7fffdca3cc7818f86a7a0cd0bb. Its three A4 connection resets and overall FAILED screen are retained. The Gateway listen backlog was then changed from 5 to 128 without changing the handler, admission model, SQL durability, worker count or lease/result logic. The source hashes and pre-fix gateway are retained in http_followup/.

A separate 96-request simultaneous burst on pool8 reproduced 5 connection resets before the correction. Corrected-source pool0 and pool8 regressions each accepted and completed 96 events, independently verified all digests, and returned 96 identical duplicate receipts with exactly one DONE audit per ID. Regression status: PASSED. A further patched-Gateway PG/Gateway SIGKILL test verified durable receipts and replay markers. These finite burst checks do not establish sustained overload capacity or general performance superiority. Larger socket backlog can increase queued connections; production concurrency/resource bounds remain unvalidated.

The full matched 27-run benchmark after this transport correction is UNEXECUTED. The original useful-work screen passed all A3 per-condition exact bounds, but overall pilot acceptance remains FAILED because of the preserved A4 HTTP errors. Reproduce the original pilot from its immutable commit; do not label current-source reruns as the identical frozen experiment.
