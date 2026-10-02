# TiEE Benchmark Specification v1.0

Dragrush AI · September 2026  
Status: proposed experimental contract, ready for implementation review  
Target: TiEE Core v0.1  
Evidence status: no implementation or performance results are established by this document.

## 1 Purpose and authority

Determine when early filtering, asynchronous transport, and EV scoring reduce total downstream resource consumption while preserving useful outputs. Measure where those mechanisms add overhead or fail. This benchmark does not test quantum computation, GPU utilization, robot battery life, or enterprise suitability.

MUST indicates a required behavior. Numeric limits below are proposed benchmark settings, not measured capacities. Freeze this document, generator code, configurations, and control implementations by content hash before comparative runs. Do not tune them after seeing TiEE results without a new benchmark revision.

The original technical specification remains a draft. Section 2 records amendments that this benchmark requires; it does not silently overwrite the previously delivered Word file.

## 2 Required technical specification amendments

| ID | Issue in the technical draft | Benchmark resolution |
|---|---|---|
| A01 | Literal rejection threshold of −6.666 was introduced without justification | Retain “−6.666 Protocol” as the policy name. For this experiment, reject score ≤ 0; allow score > 0 after safety and capacity checks. This restores the earlier project rule. |
| A02 | Event example exposed ground_truth | Ground truth belongs only in an evaluator-side file. No label, case index encoding a label, or evaluator mount reaches a service. |
| A03 | Client response latency could compare synchronous completion with queue acknowledgment | Report acknowledgment and durable completion separately. Primary latency is useful-event durable completion, not HTTP acceptance. |
| A04 | Audit was described only after execution | Persist an execution intent before a side effect and its result afterward. Unknown outcomes require reconciliation. |
| A05 | A feedback loop could be read as automatic learning | v0.1 records outcomes with a fixed policy. It is feedback-instrumented, not demonstrated self-learning. |
| A06 | Illustrative ./benchmark command conflicts with benchmark/ directory | Proposed commands are make test, make smoke, and make benchmark. They are not available until implemented. |

The threshold and score scale are experimental choices, not physical constants. Tests MUST cover negative, zero, positive, non-finite, and missing scores. Non-finite or missing scores produce INDETERMINATE, never implicit ALLOW.

## 3 Experimental arms

All arms use the same runtime, canonical parser, safety validation, processing function, output schema, instrumentation, and durability settings. Malformed input is rejected before expensive processing in every arm. Do not manufacture an advantage by disabling basic validation in the baseline.

| Arm | Early utility filter | Durable broker | EV evaluation | Purpose |
|---|---|---|---|---|
| B0 conventional | No | No | No | Synchronous reference |
| B1 filter only | Yes | No | No | Isolate early filtering |
| B2 queue only | No | Yes | No | Isolate asynchronous transport |
| B3 filter plus queue | Yes | Yes | No | Strong control for the EV layer |
| T full TiEE | Yes | Yes | Yes | Measure complete implementation |

B0 and B2 apply utility eligibility after the expensive work; B1, B3, and T apply it before. Every arm MUST produce the same final useful output set. Late-filtered work is a counted resource cost, not a useful completion.

B3 is necessary: T beating B0 alone does not establish any incremental value from EV. Compare T against B3 explicitly. Initial deterministic EV is expected to reproduce the early predicate; this measures its overhead, not intelligent discrimination.

Run arms sequentially on the same host. Do not run competing arms concurrently. Each arm receives the same payload bytes, ordered schedule, seed, and resource budget. Clear only run-owned state between runs; record cache reset policy. Use equal warm-up procedures, not claims of perfectly identical hardware state.

## 4 First workload and correctness oracle

### 4.1 Domain

Use synthetic telemetry with an explicit retention contract. A useful event is structurally valid and has `quality >= 0.80`. Valid events below that threshold are designated non-useful by this artificial contract. They are not malicious and this rule is not a general-purpose detector of semantic value.

Each event has an opaque ID and payload containing sensor_id, sequence, quality, and sample_bytes. quality is a legitimate input feature. Ground truth is the evaluator's independently derived expected disposition, never an input field. The first suite tests execution architecture around an easy known rule; it cannot establish classifier generalization.

### 4.2 Deterministic generation

- Seeds: 101, 202, 303, 404, 505 for the five measured repetitions.
- Generate each 100-event block with an exact useful count: 100, 75, 50, 25, or 10.
- Derive ordering from sorting SHA-256(seed, block index, opaque event ID), using a documented unambiguous byte encoding. Commit golden fixtures to catch generator drift.
- For useful records, choose quality from {0.80, 0.85, 0.90, 0.95, 1.00}; for non-useful records choose from {0.00, 0.20, 0.40, 0.60, 0.79}. Derive choices from independent hash bytes.
- Generate sample_bytes as exactly 1,024 deterministic bytes, encoded as base64 in JSON. Record actual serialized request sizes; do not call the whole request a 1 KB payload.
- Event IDs are independently hash-derived, opaque identifiers. Do not encode useful/noise class in their prefixes.
- Store requests and relative scheduled send times in an immutable workload artifact. Store expected outputs separately, inaccessible to services.

The evaluator MUST independently implement the retention rule and output digest calculation rather than calling the service's classifier. Include handwritten boundary fixtures at 0.79, 0.80, and 0.81.

### 4.3 Downstream work

Processing hashes decoded sample_bytes repeatedly: h0 = SHA-256(sample_bytes); hi = SHA-256(h[i−1]) for i from 1 through K. Persist event_id, final digest, and processor version for useful records only. K is identical across arms.

Cost profiles: K = 0, 100, 1,000, and 10,000. These are work counts, not millisecond targets. K = 0 still incurs decoding, initial hashing, and storage overhead. Never use sleep to represent CPU computation. Database delay injection is labeled separately.

After drain, compare actual useful rows against the exact expected ID and digest set. Missing rows, wrong digests, unexpected rows, and duplicate external effects are separate failures. Do not infer correctness from equal row counts alone.

## 5 EV contract for the first experiment

For T, the deterministic eligibility rule supplies p = 1 for quality ≥ 0.80 and p = 0 otherwise. These endpoints are rule outputs, not calibrated probability estimates.

```text
V_anchor = 1 utility unit
V_crucible = 1 utility unit
omega = 1
Base_EV = p × V_anchor − (1 − p) × V_crucible
score = Base_EV × omega
score > 0 → ALLOW, subject to authorization and capacity
score ≤ 0 → REJECT with recorded reason
```

Do not claim that this arithmetic improves classification over B3. A later learned-scoring experiment requires a separate version, training/validation/test split, frozen model, calibrated probabilities, and an independently labeled held-out workload. It MUST compare against a simple rule-based filter as well as B0.

All ingestion-processing authority is limited to the isolated benchmark database and topics. No hosts-file edits, process killing outside run-owned containers, privileged endpoint actions, or public-computer modifications are permitted.

## 6 Execution and durability

Use FastAPI/Python, a Kafka-compatible Redpanda broker, PostgreSQL, Docker Compose, and k6 for the first implementation. Pin dependency versions and container digests in the implementation manifest. This document does not prescribe unverified current version numbers.

### 6.1 Status and delivery

- Direct arms report completed only after a PostgreSQL transaction commits.
- Broker arms report accepted only after the configured durable producer acknowledgment. HTTP 202 is not completion.
- A consumer commits its broker offset only after its output or terminal rejection record has committed.
- Enforce unique run_id + event_id for outputs and terminal processing records. A crash after database commit but before offset commit must not duplicate effects.
- Retry unknown enqueue outcomes using the same event_id and idempotency key.
- Do not claim exactly-once delivery. Require idempotent effects under at-least-once delivery and demonstrate reconciliation.
- Persist a minimal reason record for every rejection. Keep rejected payload contents out of routine logs. Include the cost of this persistence in measurements.
- If required audit persistence fails, do not report a durable terminal rejection.

Use a single-broker development profile with persistence enabled, producer acknowledgments configured explicitly, and PostgreSQL synchronous_commit enabled. Record broker flush/acknowledgment settings. This profile tests restart recovery under its declared fault model; it does not establish survival of host, disk, or power loss. A replicated durability claim needs a separate profile.

### 6.2 Limits

Proposed limits: request body 64 KiB, server in-flight admission 256 events, worker concurrency 2, event processing attempts 5, retry delays 0.1/0.2/0.4/0.8 seconds, database operation timeout 5 seconds. Direct arms use the same maximum processing concurrency.

Queue policy: admission stops at 10,000 outstanding accepted events or oldest outstanding age 60 seconds. Bound queued storage to 256 MiB with admission control; retention MUST NOT silently delete unprocessed accepted work. Admission accounting includes pending producer reservations so concurrency cannot bypass the limit. Capacity refusal is retryable 429/503, not semantic REJECT. Retention, retries, and failures remain observable.

Deferred or failed work MUST retain a recoverable identity; exhaustion creates FAILED or review-required state, not success. Do not expire useful events during the core correctness suite. Any expiry experiment is separately labeled and counted as loss of useful work.

## 7 Resource profile and scope

Proposed smoke target: a host with 2 logical CPUs and 8 GiB RAM; this is a planning target, not a provider entitlement or performance promise. Record actual available resources and refuse the profile if limits cannot be enforced or measured.

For the measured system, cap combined services at 1.5 CPU equivalents and 5 GiB RAM using a parent resource group where available. Include Gateway, scorer, worker, broker, database, and audit storage. Keep generator/evaluator outside that group and record their resource use separately. If aggregate limits cannot be enforced, report per-service limits and label cross-arm resource fairness unverified; do not publish a resource-normalized superiority claim.

Report whole-host metrics alongside service-group totals. Same-host generator contention is a limitation even when reported separately. No payment, account creation, external deployment, or cloud subscription is authorized by this specification. Public-computer work must remain within the owner's permitted browser workflow.

## 8 Measurement boundaries

### 8.1 Latency

The evaluator uses its own monotonic clock for scheduled send, actual send, HTTP response, and first observation of durable completion. Observe completion using fixed 100 ms batched status checks, identical across arms, and include their server cost. This yields completion-observation latency with up to approximately one polling interval plus query delay; it cannot substantiate a 5 ms completion claim.

Record scheduled-send-to-completion and actual-send-to-completion separately. Publish generator scheduling delay so overload is not hidden. Cross-process wall-clock differences MUST NOT be treated as precise duration without a documented synchronization error bound.

Report useful-completion p50/p95/p99 separately from rejection response latency and enqueue acknowledgment latency. Never average fast rejections into useful-work latency. Unfinished work is counted as censored/failed with a completion fraction; it must not disappear from latency interpretation.

### 8.2 Throughput and resources

| Metric | Definition |
|---|---|
| Offered rate | Scheduled arrivals divided by offer-window seconds |
| Actual send rate | Actual attempts divided by offer-window seconds |
| Useful completion rate | Unique correct useful completions during the offer window divided by window duration |
| Batch useful throughput | Correct useful completions divided by time from first scheduled arrival to last terminal completion, including drain |
| False rejection rate | Useful originals receiving a semantic rejection divided by all useful originals |
| Useful non-completion | Useful originals without correct completion by deadline divided by all useful originals |
| Waste-processing rate | Non-useful unique inputs that entered expensive processing divided by non-useful originals |
| CPU cost | Total service-group CPU seconds through drain divided by correct useful completions |
| Memory | Peak and time-average service-group memory, with measurement definition |
| Queue behavior | Outstanding count, oldest age, and consumer lag at 1-second intervals |
| DB activity | Output writes, audit writes, dedup checks, and total transactions separately |

Also record disk bytes, network bytes, timeouts, HTTP errors, producer errors, retries, and duplicate attempts. Zero-denominator ratios are null with a reason, never infinity presented as a win. RAM savings are not automatically cost savings; energy savings require energy measurements.

## 9 Run procedure

1. Freeze configuration, resource allocation, workload bytes, seeds, oracle, and code hashes. Mark dirty source trees and retain the diff.
2. Run preflight schema, boundary, idempotency, telemetry, and dependency checks.
3. Create a fresh run namespace and verify no prior workload records remain there.
4. Warm up for 30 seconds with separate IDs and the same mix, then drain warm-up completely. Exclude warm-up counters by snapshot deltas.
5. Offer scheduled arrivals for 120 seconds. Baseline rate grid: 10, 50, 100, 250, 500, and 1,000 events/second. Each rate is a separate run.
6. Stop new arrivals and drain for at most 120 seconds. Record remaining work instead of clearing it to produce a passing result.
7. Reconcile all IDs and collect resources through the drain deadline. Preserve evidence before run-owned teardown.
8. Repeat with all five seeds. Rotate five-arm execution order by one position per repetition, starting B0, B1, B2, B3, T.

Use an open-loop arrival schedule; stalled responses must not lower scheduled offered load invisibly. Disable automatic client retries for steady-state capacity runs. Fault runs may retry with a separate recorded attempt ID and stable logical event ID, using the bounded policy above.

Record k6 dropped iterations and achieved scheduling. More than 1% unsent scheduled arrivals makes the run invalid for the intended offered-rate claim. Preserve it as generator-limited evidence. Do not rerun only unfavorable arms.

Smoke profile: T01/T03/T05, K=100, rate=10/s, 10-second warm-up, 30-second offer, 60-second drain, seed=101, all five arms. This is a correctness check, not a publication performance result.

Full matrix is intentionally larger than smoke. If compute is limited, select a balanced subset before results, label it partial, and do not imply every scenario ran.

## 10 Workload and failure matrix

Unless stated otherwise, fault tests use 50% useful input, K=1,000, 50/s, 30-second warm-up, 120-second offer, and 120-second drain. Fault times are relative to the measured offer window. Faults affect only explicitly named benchmark-owned services.

| ID | Workload or intervention | Required observation |
|---|---|---|
| T01 | 100% useful | Pure overhead and control equivalence |
| T02 | 75% useful | Low-noise benefit boundary |
| T03 | 50% useful | Balanced filtering opportunity |
| T04 | 25% useful | High-noise behavior |
| T05 | 10% useful | Extreme noise with useful recall preserved |
| T06 | 50/s for 30s, 250/s for 30s, 50/s for 60s | Backlog growth, latency, and recovery |
| T07 | Add 100 ms per database operation from t=30 to t=60 | Labeled application-side DB-delay simulation; not a claim of actual DB server failure |
| T08 | Limit broker arm producer in-flight sends to 1 and inject 200 ms acknowledgment delay, t=30–60 | Controlled enqueue bottleneck; direct arms N/A |
| T09 | Stop then restart ingress, t=30–45 | Client errors, retries, accepted-record reconciliation |
| T10 | Stop broker-arm consumer, t=30–45; separately kill just after DB commit before offset commit | Recovery without duplicate effect; direct arms N/A |
| T11 | Queue cap 100; pause consumers t=30–60 | Refusal before silent loss or unbounded growth; direct arms N/A |
| T12 | Separate runs: DB stop t=30–45; broker stop t=30–45 | Recovery time and accepted-work reconciliation; no broker fault for direct arms |

T08 and T11 change declared test configurations for all applicable arms identically. They must not be pooled with steady-state results. Execute DB and broker recovery as separate interventions to identify causes.

Define recovery as the first point after restoration when outstanding work returns to its pre-fault level and subsequent 10-second windows meet pre-fault completion rate within 10% for 30 consecutive seconds. If not observed by deadline, report recovery > observation window.

Additional correctness fixtures MUST cover invalid JSON, missing required fields, non-finite or out-of-range quality, oversized requests, repeated same-ID same-body events, and same-ID different-body conflicts. Repeat retries must not duplicate outputs; conflicting identity reuse must return an explicit error, not reuse a cached success. Duplicate fixtures are separate from the useful-percentage capacity mixes.

## 11 Falsification and interpretation

| ID | Question | Experiment |
|---|---|---|
| F01 | When is filtering more expensive than saved work? | Cross useful fraction with K and offered rate |
| F02 | Does all-useful input favor the conventional arm? | T01 across all arms |
| F03 | Can payload features mislead scoring? | Boundary/tampering fixtures; learned-model attacks deferred |
| F04 | Is ingress the bottleneck? | Rate sweep with component CPU and queue delay |
| F05 | Does queueing worsen completion latency? | B0 vs B2 and B1 vs B3 |
| F06 | Does apparent benefit come from lost useful work? | Exact output oracle and false-rejection accounting |
| F07 | Are accepted events lost during faults? | T09–T12 reconciliation |
| F08 | Is cost shifted to broker, audit, or network? | Full-system resources through drain |
| F09 | Can retries repeat effects? | Duplicate and commit-before-offset crash fixtures |
| F10 | Does benefit generalize? | Independent operator/workload later; report NOT TESTED until done |

Supportable early conclusions concern only this synthetic retention task. Record the winning and losing regions by mix, K, rate, and resource profile. A result can support early filtering without supporting EV or queueing. A fixed heuristic is not evidence of learning.

## 12 Validity and acceptance gates

Separate measurement validity from system success:

- VALID: instrumentation, workload fidelity, and environment controls met their contract.
- INVALID: harness or evidence problems prevent interpreting the intended comparison; retain reason and raw data.
- PASS/FAIL: system correctness and reliability under a valid run.
- NOT RUN / UNSUPPORTED: unavailable scenario or infrastructure; never treated as a pass.

A system failure with intact measurement is a valid negative result, not an excuse to exclude it.

Smoke gate: every offered useful event completes correctly; no useful semantic rejections; no unexpected output rows; no duplicate effects; every disposition has a reason record; no unauthorized side effects. All required IDs reconcile after drain.

For a proposed sustainable-rate designation, require all five repetitions to have at least 99% useful originals complete within 5 seconds of scheduled arrival, zero useful semantic rejection, zero wrong or duplicate outputs, and zero unresolved durable acceptances after drain. Report backlog slope and all error counts. These thresholds are engineering choices, not application-derived SLAs.

A maximum sustainable rate is only the highest tested passing grid point, not an extrapolated capacity. If all points pass, report capacity ≥ highest tested point. If none pass, report below tested range or unresolved, as appropriate.

A benefit claim requires equal correctness/durability gates and favorable measured resources or useful throughput; it must also disclose any latency regressions. Faster rejection alone is not higher useful throughput. A lower CPU/event value caused by rejecting useful inputs fails the benefit gate.

## 13 Statistical reporting and claim limits

Pair arm results by seed, configuration, and repetition. Report all five values, median, minimum, maximum, and paired ratios; five runs are preliminary evidence. Do not pool every event as an independent experimental replication.

Throughput ratio = T useful completion rate / control useful completion rate. Resource saving fraction = 1 − T CPU cost / control CPU cost. Completion-latency ratio = control latency / T latency, only with matching cohort and boundary.

Report confidence intervals only with a documented run-level resampling or statistical method and sufficient repetitions; otherwise explicitly say none estimated. Freeze additional sample counts before rerunning comparisons. Preserve negative effects, failed runs, and generator limitations.

“20×” requires an identified metric, tested condition, absolute values, fair comparator, uncertainty, and correctness constraints. It cannot mean the entire AI system. No CPU benchmark substantiates 99.4% GPU utilization, 36.8% universal savings, or improved robot battery life.

## 14 Evidence package

Each immutable run directory MUST contain:

| Artifact | Contents |
|---|---|
| manifest.json | run ID, spec versions, arm, timestamps, commit, dirty diff reference, hashes |
| environment.json | CPU, RAM, OS, runtime, quotas, disk, image digests, dependency versions, topology |
| workload.json | seed, mix, K, schedule hash, request hash, oracle hash |
| attempts.jsonl | logical ID, attempt ID, scheduled/send/response times, response class |
| completions.jsonl | logical ID, observed durable completion time, terminal state |
| resources.jsonl | timestamped service and host measurements |
| decisions.jsonl | event ID, score where applicable, disposition, policy/model versions, reason |
| correctness.json | expected/actual set comparison, missing/unexpected/wrong/duplicate counts |
| failures.json | planned and actual injection times, restoration, recovery, retry exhaustion |
| summary.json | metrics, denominators, validity, gate outcomes, null reasons |
| checksums.sha256 | integrity hashes of retained evidence files |

Cross-arm comparison.json references complete run IDs instead of copying unverifiable numbers. Evidence schema fields have explicit units and distinguish absent, zero, and not applicable. No secrets or authentic personal telemetry are allowed in published fixtures.

## 15 Implementation handoff and exit criteria

Build in this order:

1. Independent generator/oracle, event schema, threshold boundary tests, and golden fixtures.
2. Shared processor, PostgreSQL schema, idempotency constraints, and intent/result records.
3. B0 and B1 direct arms with correctness tests.
4. B2 and B3 broker arms with crash/replay tests.
5. T scoring/policy wrapper using the fixed rule; no hidden tuning.
6. Measurement harness and machine-readable evidence validator.
7. Smoke runs for T01/T03/T05 across all arms.
8. Full load sweep and failure suite only after smoke passes.

Repository responsibilities: spec/ owns contracts; shared/ owns equivalent work; baseline/ owns controls; gateway/, scoring/, policy/, broker/, processor/, storage/, and telemetry/ own TiEE components; benchmark/ owns generator, private oracle, schedules, harness, and results; tests/ owns unit, integration, failure, and falsification checks.

Expected future commands:

```sh
make test
make smoke
make benchmark
make verify-results RUN_ID=<recorded-run-id>
```

These are implementation requirements, not commands verified by this document. The first completion milestone is a runnable five-arm smoke comparison with exact output correctness and complete evidence, whether TiEE wins or loses. Independent verification, learned scoring, GPUs, endpoint executors, and public deployment remain later work.
