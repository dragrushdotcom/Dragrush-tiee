# v4.8 PostgreSQL coordination experiment

Base commit e064eec5a1c2202d28dca6971ab47e371edde940, existing scaling potato Codespace only. Original robotics and all prior evidence remain preserved. No production exposure, deployment, paid infrastructure or durability reduction.

Profile normalized PostgreSQL statements and 20ms service wait snapshots on a separate diagnostic run. Record observer overhead and failed setup/export attempts. Do not equate cumulative SQL wall time with CPU time; normalized advisory-lock statements merge lock IDs and service wait samples identify the service.

One frozen candidate: relay polling 20ms versus unchanged 5ms baseline. Same relay_once SQL, admission policy, worker count, worker leases, atomic result commits, retries, Redis AOF appendfsync always and PostgreSQL synchronous commits. A bounded validated environment setting allows 5..100ms; default remains 5ms unless evidence justifies changing it.

Run 18 real candidate integration gates across pools 0/8 before performance collection: durable receipts and PostgreSQL/Gateway kill recovery, bounded deferral/expiry, legacy HELD expiry, publication rollback and worker fencing/idempotency, five-service/AOF/stream-loss recovery, capacity/authentication/conflict/retry, delayed terminal observation, missing-scorer rejection/expiry, and atomic audit/result/terminal-marker rollback. Record every outcome and elapsed recovery evidence.

Freeze 36 paired runs: 18 training and 18 fresh held-out confirmation, each with three trace blocks in normal/shift/burst and two randomized variants. 240 offered events per run, identical paired payload IDs/trace hashes, rates 40 normal and 80 shift/burst, 12s deadlines, 13s drain allowance, 24 warmup events, two workers, pool size 8. Freeze both stage job orders and seeds before collection; do not tune or select another candidate from held-out results. Collection bound 1800s per stage. Include all refusals, expiry, errors and unresolved obligations.

Primary efficiency endpoint: engine CPU seconds per useful completed event. Candidate target at least 5% mean reduction. Guardrails: zero HTTP/poll/drain failures or missing terminal timing/HELD; no additional valid event loss within any paired trace; useful throughput no worse than 5%, offered-terminal p95 no worse than 10%. Confirm with 20,000 stratified paired bootstrap draws and familywise Bonferroni intervals for CPU/useful, useful throughput and offered p95 (98.333% each). Adoption requires both stages' mean targets and held-out interval guardrails; otherwise retain default 5ms. This is a generic infrastructure optimization, not a test of distinct TiEE superiority. Nine paired traces per stage remain exploratory, not production certification.

Save source, real tests, frozen hashes, raw JSON/CSV, SQL profiles, charts, reproduction commands and passed/failed/unexecuted report. Stop only private test services and retain volumes after verification.
