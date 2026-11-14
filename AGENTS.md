# AGENTS.md — Dragrush TiEE engineering collaboration policy

This file is a **project-specific instruction contract** for assistants or coding agents that intentionally read it. It does not modify ChatGPT model weights, activate any scheduled task, provide credentials, or prove that an external agent actually ran. These directives apply only to repository `dragrushdotcom/Dragrush-tiee`.

## Mission

Advance the Toroidal Information Execution Engine (TiEE) as a testable system that filters and prioritizes low-value work before expensive processing while preserving important exceptions, reliability and privacy. Measure **actual outcomes**, not design ambition. Treat advertised latency, throughput, CPU/GPU utilization and filtration numbers as targets until current comparable benchmarks independently prove them.

## Working loop

1. Inspect the current `main` HEAD, open PRs, workflow status, issues, previous benchmark artifacts and source configuration. Do not infer that a prior assistant statement is current.
2. Identify the highest-leverage defect or experiment and write a falsifiable hypothesis with intended metric improvement, risk and rollback plan.
3. Keep changes narrow and versioned; use feature branches and PRs, not bulk unreviewed main rewrites. Protect secrets and user data; no unapproved paid services or API spending.
4. Build baseline and candidate under the **same** environment, workload, warm-up, concurrency, data mix, repetitions and statistical summaries. Record versions, hardware and exact commands for reproducibility.
5. Test correctness first, then throughput/latency distributions (p50/p95/p99), error/timeout rates, dropped high-value/rare events, queue contention, backpressure, memory/CPU/GPU and cost. Include failure injection, restart/replay, data durability and integrity.
6. Check workflow and test results, review diff, merge only under authorized CI and repository policy, and verify main readback. A CI green check does not by itself prove real-world superiority.
7. Record evidence links to exact commit, benchmark dataset/parameters, raw outputs, assumptions, failure regressions and next experiment; report verified, unverified and blocked work separately.

## Scientific and technical boundaries

- Distinguish `concept`, `design target`, `simulated result`, `local measured result`, `replicated result`, `production result`.
- No self-reported 10/10 score, percentage gain, or claim of independent multi-agent operation without auditable evidence.
- Preserve rare valuable signals even when a filter would otherwise drop them; assess false negatives and false positives by cost, not only percentages.
- Separate async/event throughput from batch throughput; test end-to-end latency and resource contention.
- Prevent duplicate-run side effects with idempotent keys and checkpoints; enforce explicit scopes for workers sharing the same mutable resources.
- Favor reversible work and tools already available in the user's ChatGPT plan or free ecosystem; do not assume commercial API access.
- If an operation cannot be verified due to tool permissions, retain a precise checkpoint and report it rather than saying completed.

## Communication contract

Deliver the actionable result first. Identify evidence and exact changed files/PRs. State what failed or remains unproven and propose the single next experiment. Ask only for essential missing authorizations or irreversible commitments. Do not imply background execution unless an actual scheduled/delegated task was created.

## Project boundaries

Do not conflate TiEE engineering evidence with the theological or narrative claims in The Pure Essence of Existence. Do not alter TPEOE manuscript-writing schedules, chapter approvals or source files. TiEE is an independently evaluated engineering project.

## Measured engineering receipt gate

Apply `docs/ENGINEERING_HARNESS_POLICY.md` and the bounded project contract in `ops/engineering_contracts/tiee_benchmark.json` for new TiEE experiments. Use `scripts/engineering_contract_gate.py` for consistency checks with a trusted exact checkout SHA. Record independent CI/artifact readback and measured baseline/new/delta; do not confuse a passing receipt or a benchmark experiment count with verified performance improvement. Use read-only stall classification without automatically replaying possible in-flight jobs.
