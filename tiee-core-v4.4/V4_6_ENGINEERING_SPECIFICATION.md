# TiEE Core v4.6 execution contract

This repository specification records the implementation contract for the October 11, 2026 round. The longer planning document is `TiEE_Core_v4_6_Engineering_Specification.md`, delivered before execution. Actual status and evidence belong in `V4_6_ENGINEERING_REPORT.md`; this file does not certify completion.

## Operating scope

Use only the existing scaling potato Codespace, preserve `/workspaces/Dragrush-tiee`, work on `tiee-core-v46-ev-validation` in `/workspaces/Dragrush-tiee-v46`, and retain archives and test databases. Starting revision: `0a0334569d5767902d34752fdafedcee4eb3b94c`; original robotics revision: `6e12b5098699ba636cdb1112dd192da74d8f9bb3`. No production deployment, public ports, paid upgrades, destructive cleanup, or robotics actuation.

## Policy and durable state

Estimate validity from observable signal/noise features with a logistic model trained on seed 460001 and calibration seed 460002. Hidden truth is confined to the independent probe. Reward/penalty values come from the authorized application task-class map, never arbitrary client values.

`Base_EV = p*reward - (1-p)*penalty`; `Weighted_EV = Base_EV*omega`; `Net_EV = Weighted_EV - expected execution cost`. The cost subtraction is an explicit engineering extension. Harmony/Nominal/Destructive weights are 1.5/1/0; primary comparisons fix Nominal. Positive confident work is ALLOW; uncertainty or Destructive state is DEFER; confident non-positive work is REJECT. Mandatory critical work bypasses experimental rejection.

HTTP 202 is sent only after the SQL receipt and initial decision commit. Recorded rejection returns 200. Retries return the original receipt; payload conflicts return 409; malformed input 400; unauthorized input 403; capacity/scorer/database refusal 503. SQL bounds include DEFERRED/PENDING/ENQUEUED/RUNNING/HELD. Model and feature versions, numeric values, reasons, and history remain auditable.

SQL is authoritative. Accepted lifecycle is DEFERRED or PENDING → ENQUEUED → RUNNING → DONE, with audited EXPIRED and retained HELD states. Deferrals are 250ms, at most three, bounded by deadline. Aging forces a FIFO lane after 500ms. Claims have an increasing generation and 3-second lease. Stale generations cannot commit. Result and DONE audit commit together before Redis ACK/delete. Lost streams/groups, overdue work, expired claims, and unpublished events reconcile from SQL.

## Experimental comparisons

| Arm | Admission | Ordering |
|---|---|---|
| A0 | Conventional fixed application filter | FIFO |
| A1 | Same filter | Deadline with aging |
| A2 | Calibrated EV | FIFO |
| A3 | Calibrated EV | Value/cost with aging |
| A4 | Conventional identical observable EV rule | Identical value/cost rule |

A4 deliberately shares A3's rule and implementation. No additional TiEE mechanism is implemented. All arms share private Redis/PostgreSQL, checked pool8, two workers, durability, bounds, audit schema, and digest verification. Fixed-admission runs authorize every synthetic event as critical work to isolate ordering on identical admissions.

Training uses low/medium/high invalid fractions and mixed costs. Confirmation uses disjoint normal, distribution-shift, and valuable-long-work burst traces. Plan generation freezes seeds, randomized paired arm order, model/source hashes, repetitions, deadlines, resource costs, and statistical comparisons before confirmation. At least ten blocks per condition; training variability determines a requirement, capped at twenty within the bounded round. If the requirement exceeds the budget, results remain exploratory and the confirmatory power gate does not pass.

Primary outcome is realized net utility per measured engine CPU second, including missed-value penalties over every submitted event. Use paired trace analysis and multiplicity-adjusted uncertainty. Report useful throughput, offered/dispatch/stage latency, engine/probe CPU, sampled RAM, queue/pending state, SQL/WAL/AOF overhead, errors, recovery, and a complete utility ledger.

## Acceptance and limits

Pass final real-service recovery gates and exact digest/accounting checks. A positive EV-policy claim additionally requires better held-out calibration than a prevalence predictor, valid rejection no greater than 1% with a one-sided 95% trace-dependent upper bound, no utility reduction, and the prespecified efficiency improvement. A4 reproduction credits the shared conventional EV rule; it cannot establish TiEE-specific superiority.

Explicitly distinguish passing, failed, unexecuted, exploratory, and inconclusive results. Automated system-state hysteresis, general preemptive scorer cancellation, physical power failure, simultaneous durable-volume loss, production scale, real GPU inference, and physical robotics require separate work. The optional soak and any scheduling ablations that are not executed must remain labeled unexecuted.
