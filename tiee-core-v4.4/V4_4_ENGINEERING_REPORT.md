# TiEE Core v4.4 — PostgreSQL-to-Redis Reconciliation

**Status:** Source-verified recovery candidate; real-service validation pending.

## Problem discovered in v4.3
PostgreSQL accepted an event and eventually recorded `ENQUEUED`, but relay only
forwarded `PENDING` events. If Redis lost its stream after SQL reported
`ENQUEUED`, this event could remain unresolved forever.

## Change
- Schema adds nullable `last_relay_at`, including `ALTER TABLE` migration.
- Relay selects `PENDING` or overdue `ENQUEUED` accepted rows under row locks.
- Redis XADD occurs before SQL update; the relay records an attempt timestamp.
- `RELAY_RETRY_SECONDS` controls bounded periodic retries (default 10).
- Done/rejected items are excluded; worker result commits remain idempotent.

## Verification
- 10 Python contract tests passed (4 inherited, 6 new).
- Python syntax compilation passed for all application files.
- Docker Compose YAML parsed; five services present.
- Redis/PostgreSQL binaries and Docker unavailable, so NO integration, crash,
  throughput, or latency measurement performed in v4.4.

## Limits / risks
- Repeated XADD may occur before a long-running task finishes, increasing stream
  load and duplicate CPU work (although duplicate result rows are prevented).
- Dual-write between Redis and Postgres is not atomic. Duplicate processing is
  explicitly possible, so workers must not perform irreversible external side
  effects without dedicated idempotency controls.
- PostgreSQL row locks are held across the Redis publish operation; a sluggish
  Redis server could cause database lock contention. Production design should
  use transactional outbox claims and short DB transactions.
- No operator-approved destructive recovery or automatic stream trimming is added.
- No verified high-value EV scheduling gain. This release changes resilience only.

## Required next gate
Run disposable Redis/Postgres containers, inject crashes and broker message
loss, verify all admitted event IDs have exactly one final SQL result, and
measure retry amplification, end-to-end latency, CPU, and disk with conventional
and TiEE configurations on identical infrastructure.
