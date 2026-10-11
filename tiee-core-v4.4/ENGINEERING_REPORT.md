# TiEE Core v4.4 integration and validation

Date: 2026-10-11. Branch: robotics-v01.

## Outcome

The v4.4 pilot was integrated additively and exercised on the existing scaling potato Codespace. Redis 7.4, PostgreSQL 17, gateway, relay, worker, and the private network anchor started. No production deployment occurred.

## Correctness and recovery

Executed admission contracts, relay SIGKILL, worker SIGKILL, pending-event reclaim, Redis SIGKILL with AOF recovery, PostgreSQL SIGKILL recovery, gateway SIGKILL, Redis stream/group loss and reconstruction, plus a capacity-2 backpressure test. The integration log records pass outcomes. Capacity test: two events admitted at capacity, third returned 503 capacity_retry, and retry after draining was admitted; all three reached DONE. These are pilot-level tests, not a production certification.

## Matched benchmark

18 trials: baseline and TiEE arms × noise rates 0, 0.5, 0.9 × three repetitions. Each trial used 300 events, eight HTTP clients, 2,000 SHA-256 rounds, fixed seeds, 30 warmups, alternating arm order, and an isolated retained PostgreSQL database. Integrity hashes were checked against canonical event payloads; all trial integrity_pass flags are true. Useful completions/s and end-to-end completion p50/p95/p99, acknowledgement latency, CPU deltas, and available resource snapshots are in benchmark.json and trials.csv. Summary statistics are in summary.json; throughput chart is throughput.svg.

## Limits

This bundle has no separate Quantum EV Logic Engine service or calibrated EV implementation. Its shared eligibility filter only rejects bot-kind events; it cannot support claims about complete filtration or EV overhead. Queue-depth telemetry was not captured reliably during benchmark trials (capacity/backpressure was verified separately). Redis was shared, so per-arm Redis storage overhead cannot be isolated; per-trial PostgreSQL sizes and peak RAM were not collected. CPU deltas include the client/oracle/poller in the gateway container. Results therefore compare this pilot harness only and establish no architectural advantage.

## Reproduction and evidence

From tiee-core-v4.4: `docker compose -f compose.validation.yml --env-file .env up -d --build`; `python3 -m unittest discover -s tests -v`; `python3 validation/validate.py integration`; `python3 validation/validate.py benchmark`. See results/benchmark-run.log, results/integration.jsonl, results/backpressure.json, results/benchmark.json, results/trials.csv, and results/summary.json. Credentials stay in ignored `.env`.
