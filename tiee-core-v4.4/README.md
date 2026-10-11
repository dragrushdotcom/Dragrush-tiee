# TiEE Core v4.3 — Real-service deployment scaffold (NOT benchmark-validated)

This implementation replaces the SQLite queue *design* with a Redis Streams consumer group and PostgreSQL transactional authority. This environment did not contain Docker, Redis, or PostgreSQL, so **no services were started here and no performance results are claimed**. It is a deployment candidate, not a tested release.

## Run where Docker Compose is available

1. Copy `.env.example` to `.env`, set new `POSTGRES_PASSWORD` and `API_KEY` (development defaults are intentionally insecure).
2. `docker compose up --build -d`; check `docker compose ps` and `docker compose logs`.
3. `python benchmark.py --seed 100 --events 500 --noise 0.5 --rounds 1000 --output results/baseline.json`.
4. Query `docker compose exec -T postgres psql -U tiee -d tiee -c "SELECT state,count(*) FROM events GROUP BY state;"` and `SELECT count(*) FROM results;` to independently verify outputs.
5. Run each arm on **fresh volumes** using `POLICY=baseline` and `POLICY=tiee`, respectively, and match every seed/workload. `docker compose down -v` **DELETES TEST DATA** and must be used only for disposable benchmarking.
6. Test crash recovery by terminating relay/worker containers and confirming no accepted results are lost on restart. Validate all idempotent digests and 409 conflicts. Do not use `docker compose down -v` for recovery tests.

## Actual contract and limitations

* PostgreSQL `events` is the source of truth; admission and state mutation occur transactionally. `PENDING` receipts are durable before 202 response.
* Relay publishes `PENDING` events to Redis with `XADD`, then updates Postgres; a crash can produce duplicate stream deliveries, handled by idempotent Postgres `results` insertion.
* Workers use consumer groups, pending-message reclaim after 3s, commit results to Postgres, then `XACK`; this is **at-least-once**, not exactly-once execution.
* Backpressure is a serialized PostgreSQL advisory-locked count; this is deliberately correct but likely bottlenecks throughput.
* Current `tiee` arm is intentionally a **neutral policy** (same output set as baseline). It isolates infrastructure and explicitly **cannot establish an EV advantage**. A calibrated EV policy must be evaluated later.
* `body` is an arbitrary string; no 2KB wire-envelope contract is enforced by this HTTP JSON prototype. No TLS, granular authentication/authorization, multi-tenant fairness, retention/GC, replica failure, independent digest oracle, full end-to-end benchmarking, GPU inference, or production-safe settings.
* Redis AOF `appendfsync always` provides local durability expectations, not a distributed consistency guarantee. PostgreSQL and Redis cannot commit atomically; reconciliation and explicit retry management are still needed.
* User-facing broker performance claims and book claims (20x throughput, 36.8% compute gain, 99.4% GPU) remain unverified.

## Validation in this session

Python syntax compilation; schema/config static validation; four dependency-free policy and fingerprint contract tests. Container startup/integration/performance measurement were not possible here.

## v4.4 recovery extension (source-level validated, not container tested)

The relay now queries the PostgreSQL authority for accepted, unfinished work including
previously `ENQUEUED` rows. Each row is eligible for bounded replay once its
`last_relay_at` is older than `RELAY_RETRY_SECONDS` (default 10 seconds).
This closes the v4.3 orphan condition where an `ENQUEUED` record could become
permanently stuck after the Redis stream entry was lost or trimmed.

Schema initialization migrates existing events with:
`ALTER TABLE events ADD COLUMN IF NOT EXISTS last_relay_at TIMESTAMPTZ`.

This is **at-least-once delivery**, not exactly-once execution. Redis `XADD` and
PostgreSQL commit remain non-atomic and duplicates can occur after a crash or
long-running job. Worker result commits are idempotent. The relay uses PostgreSQL
row locks (`FOR UPDATE SKIP LOCKED`) to reduce collisions between relays.

Before real deployment, test with Docker: publish, wait for event ENQUEUED, stop
worker, erase/truncate disposable Redis stream data (never production data),
restart service, and verify it becomes DONE with exactly one `results` row.
Also verify bounded retry load, crash between XADD and SQL update, multiple
relay instances, long-running jobs, Redis restarts, and PostgreSQL availability.

Local verification: `python -m unittest discover -s tests -v`. No actual Redis or
Postgres server was available, so these unit tests do not prove the end-to-end
recovery behavior or its performance. Both policies remain identical by design;
no TiEE EV advantage is asserted.
