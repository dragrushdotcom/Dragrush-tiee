# TiEE engineering receipts and benchmark proof

This repository contains a generic, stdlib Python, read-only validator for task
contracts, progress receipts and stall observations. It is based on the
separately developed engineering gate and contains **no manuscript or private
TPEOE source data**. It never modifies locks, repos or external services.

For each engineering invocation, record a unique invocation ID, exact Git
input/output SHAs, experiment name, standardized controlled baseline and
candidate workload, metric before/after, exact-head CI URLs, output artifacts,
readback, test failures and next step. Match hardware, concurrency, warmup,
input mix and repetitions across comparisons. Evidence classification MUST
separate target, synthetic, locally measured, replicated and production.

The contract `ops/engineering_contracts/tiee_benchmark.json` measures
**verified benchmark experiments**, not throughput speedup or claimed GPU
utilization; it cannot itself establish an improvement. Passing this gate
checks field consistency only, not authenticity of external CI URLs. Confirm
runs and raw benchmark data independently before claiming results.

Use `python3 scripts/engineering_contract_gate.py validate --contract
ops/engineering_contracts/tiee_benchmark.json --receipt /path/to/receipt.json
--expected-sha <trusted-checkout-sha>` on actual receipts. To investigate
unchanged counters, compare two independently observed snapshots with
`scripts/engineering_contract_gate.py stall`; UNKNOWN and MONITOR_STALE
are not equivalent to a stalled worker. No diagnostic authorizes retries
of potentially in-flight writes, external paid deployments or publication.
