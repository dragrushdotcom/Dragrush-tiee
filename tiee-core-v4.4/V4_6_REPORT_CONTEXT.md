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
