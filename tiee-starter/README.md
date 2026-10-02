# TiEE experimental starter v0.3

New in v0.3: [an isolated PostgreSQL test launcher](DATABASE_TESTING.md), pinned Python database dependencies, machine-readable gate reporting, and application-role permission tests. The real database gate is still NOT RUN because this workspace cannot install the server or run Docker.

New in v0.2: a PostgreSQL schema and transactional storage adapter, offline storage-contract tests, and eight opt-in database integration tests. **PostgreSQL integration has not been run here.** See [storage instructions](storage/README.md) for setup, limits, and the transaction design. The offline runner below remains unchanged in scope and does not use this database adapter.

First implementation slice for Dragrush AI. Python standard library only; Python 3.10+ syntax. No cloud account, Docker, API key, administrator privileges, or installation is needed for these offline checks. This is not the full TiEE Core and not a performance benchmark.

## Run

From this directory:

```sh
python3 -m unittest discover -s tests -v
python3 -m benchmark --out results/my-first-check
```

Use `python` instead of `python3` if that is the available Python executable. A new output directory is required on every run; existing results are never overwritten. Optional flags: `--count 300 --seed 101 --iterations 100 --rate 10`.

The functional runner checks 100%, 50%, and 10% useful traffic against an independently implemented expected-output calculator. It executes direct in-memory functions corresponding to late filtering (B0), early filtering (B1), and deterministic EV filtering (T). These are functional paths, not deployed benchmark arms. Schedule timestamps are generated but not replayed in real time.

## Implemented

- Deterministic 100-event blocks with exact class proportions and opaque identities.
- Separate request fixtures and evaluator-only expected outputs.
- Strict bounded wire validation, utility threshold, finite-score handling, and hash-chain work.
- Independently written evaluator detecting missing, unexpected, wrong, and duplicate output rows.
- JSON correctness reports, per-event decision traces, source hashes, artifact checksums.

Wire schema `benchmark-wire-1` is a minimal source-event fixture, not the complete internal Core envelope. The later Gateway must add trace ID, received timestamp, payload hash, provenance and idempotency metadata; event ID will be its logical idempotency identity. Never add hidden labels to service inputs.

Hash domains and argument tuples use compact sorted-key ASCII JSON arrays before SHA-256. Class assignment, delivery ordering, quality selection, IDs, and sample bytes use separate domain strings. Seed and sequence features must not be used as label shortcuts.

## Not implemented or established

No running HTTP services, verified PostgreSQL integration, Redpanda, authorization service, B2/B3 queued arms, client retries, verified fault recovery, scheduled load generation, resource measurements, or full five-arm smoke suite. The new storage adapter implements intended transactional idempotency and an intent/result ledger, but these require the real database tests. The source processor assumes validated inputs; only decode is the public wire boundary. Duplicate detection in the oracle is not database idempotency.

The runner deliberately reports `benchmark_executed: false` and `durability_tested: false`. Fewer processing calls under the artificial quality rule are not measured speedup or general AI savings. Deterministic EV reproduces a rule; it is not learned intelligence.

Evaluator separation is organizational at this stage: the offline runner imports both packages. Later service images must contain only `shared/` and service code, and must never mount `evaluator-only/` or import `benchmark/oracle.py`.

## Next implementation stage

Run the PostgreSQL integration suite on an authorized disposable database and resolve any failures. Then build direct HTTP arms, followed by broker arms and restart tests. Only after all five arms produce correct durable outputs should the frozen load test be run.

See the included benchmark specification for the full future contract. This starter does not silently revise its scientific acceptance gates. No external publishing or host configuration changes are performed.
