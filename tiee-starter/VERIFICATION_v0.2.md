# Verification record for v0.2

Executed in the authoring environment:

```sh
python3 -m unittest discover -s tests -v
python3 -m benchmark --out results/verified-foundation-v02 --count 300 --iterations 100
python3 -m compileall -q storage tests
```

- 43 tests discovered: 35 passed, 8 skipped, 0 failures.
- All eight skips are explicitly PostgreSQL integration tests. PostgreSQL server/client, Docker, and psycopg were unavailable; no database connection or migration was attempted.
- All nine offline output-set comparisons still passed for 300 events per traffic mix (100%, 50%, 10%) across three function paths.
- Python source compilation passed. SQL has not been executed or validated by a PostgreSQL server.

The database adapter, row locking, unique-key conflict behavior, atomic rollback, and durable intent design are implemented but NOT integration-verified. Offline tests cover configuration validation, canonical body hashing, processing/filter behavior, and existing generator/oracle behavior only. There are no database throughput, restart durability, broker, or GPU results.

The earlier VERIFICATION.md and results/verified-foundation/ remain historical v0.1 evidence. The latest offline evidence is results/verified-foundation-v02/. Source hashes in each run identify its tested Python snapshot.

Next gate: run the eight real database tests on a dedicated authorized PostgreSQL environment, with a tested/pinned driver and database version, before treating this storage slice as working integration.
