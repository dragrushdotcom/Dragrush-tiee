# PostgreSQL storage slice v0.2

Status: implementation supplied; real PostgreSQL integration NOT RUN in the authoring environment. PostgreSQL, Docker, and psycopg were unavailable. Offline contract tests do not prove SQL execution, concurrency behavior, restart durability, or database correctness.

## Design

Register a run with fixed arm, iteration count, processor version, and policy version. A matching event replay uses `(run_id,event_id)`; a different canonical body under the same identity is an audited conflict. Different JSON whitespace/key order is accepted as the same body. Numeric lexical differences such as `1` and `1.0` are deliberately distinct in this first canonical encoding.

Transaction 1 inserts and commits PENDING plus INTENT. Transaction 2 locks that event row, performs synthetic work, and commits the output, terminal state, and terminal audit together. Concurrent same-event requests are designed to serialize on the row. Final success is returned only after commit. Processing failures leave the intent pending; a retry with the original body can finish it. An uncertain commit outcome propagates as an exception: retry the same identity, do not invent a new one.

Raw payload is not persisted. Recovery of a PENDING intent therefore requires the original producer or broker to replay the body; the database alone cannot reconstruct it. There is no automatic recovery worker yet. This is suitable only for the declared synthetic CPU work plus database outputs, not irreversible external actions or general host execution.

No exactly-once delivery claim is made. Unique database outputs and transactional effects are the intended guarantee; they require integration verification.

## Prepare a test database

Use an existing, authorized, disposable PostgreSQL test database. Never point tests at production. Tests create uniquely named runs and intentionally leave their evidence; they perform no deletion. Database credentials must remain outside source files.

Install psycopg 3 in your own virtual environment using `python -m pip install 'psycopg[binary]>=3.2,<4'`. This is a development compatibility range, not a frozen dependency lock. Before publishing performance results, pin the actually tested driver version and hashes and the PostgreSQL image digest.

Set `TIEE_TEST_DSN` in your environment through your normal secret mechanism. Use a migration role for:

```sh
psql "$TIEE_TEST_DSN" -v ON_ERROR_STOP=1 --single-transaction -f storage/schema.sql
python3 -m unittest discover -s tests -v
```

The migration creates new tables and fails on existing ones rather than hiding schema drift. Do not rerun it on a populated schema. Runtime connections must use a dedicated application role with SELECT/INSERT on the four tables, UPDATE on tiee_events only, and sequence usage for audit IDs. Do not grant UPDATE/DELETE on audit or output tables. Role creation and grants are deployment-specific and are not executed by this starter. A migration-owner connection in tests does not prove least-privilege enforcement.

Connections default to the driver's tuple row factory, autocommit enabled, and explicit READ COMMITTED transactions. The adapter sets synchronous_commit on, plus 5-second statement and lock timeouts inside transactions. Synchronous commit alone cannot establish power-loss safety; storage, WAL, server settings, and hardware must be measured and recorded.

## Usage

```python
import os
from storage.postgres import PostgresStore, Run
store = PostgresStore.from_dsn(os.environ['TIEE_TEST_DSN'])
run = Run('my_run_B1', 'B1', 100)
store.register(run)
# raw is a validated-format request byte string from the workload file.
result = store.submit(run, raw)
```

The adapter intentionally opens a connection per call for clarity. Pooling, HTTP routes, connection budget enforcement, attempt-level audit for malformed requests, broker arms, server crash tests, and throughput measurement remain future work. Do not benchmark this path as final production architecture.

## Reference semantics

The implementation follows explicit transaction contexts described in [Psycopg transaction management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html), unique-key conflict handling in [PostgreSQL INSERT](https://www.postgresql.org/docs/current/sql-insert.html), and row locking described in [PostgreSQL locking](https://www.postgresql.org/docs/current/explicit-locking.html). These sources explain the design; they are not verification of this implementation.
