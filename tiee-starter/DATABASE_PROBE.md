# Exploratory database probe v1

This additive probe uses the existing B0 late-filter, B1 early-filter and T
deterministic-EV PostgreSQL adapter. It does not change Benchmark Specification
v1.0, the processor, policy, database schema, or the existing correctness gate.
It is not the five-arm HTTP/broker benchmark and cannot qualify publication
performance claims. A PASS means all measured trials reconciled, not that T won.

Run from tiee-starter:

```
python3 -m tools.run_database_probe --out results/db-probe-001
```

The launcher creates an isolated database, limited application role, and internal
network. The runner shares the DB network namespace, matching the proven
Codespaces workaround. No host ports are published. It stops its project after
the run and retains the database volume and evidence. It does not delete previous
results. The JSON Compose file contains credential placeholders, not passwords.

Default: 100 events, useful ratios 100/50/10 percent, hash iterations 0/1000,
five seeds, three arms = 90 trials and 9,000 measured submissions. Each trial
has ten untimed warmup events. Same seed/mix bytes are reused across arms;
arm order rotates by seed. The database starts fresh once per launch; warmup
and trial rows remain under distinct run IDs. Caches and growing table size are
limitations of this diagnostic, not controlled production benchmark conditions.

One request is outstanding at a time. Existing adapter overhead includes a new
connection per submission and two transactions, identically for all arms.
Timing includes submit, durable commit acknowledgment, and connection close.
Registration, warmup, fixture generation, evaluation, and report writing are
outside the timed interval. Actual output rows, states and audit actions are
queried after each trial and compared with the independent oracle.

Useful-completion and rejection latency are separate. Small sample p99 values
are exploratory; samples are not independent experimental replications.
Useful completion rate is observed under sequential load, NOT sustainable
capacity. CPU is runner-process CPU only; PostgreSQL CPU and total-system RAM
are not measured. Peak RSS is cumulative for the runner, not a per-arm memory
comparison. Logical row counts are not physical writes, WAL bytes or I/O.
Expected logical rows may be identical across arms because the existing adapter
audits every input and stores only useful outputs for all three arms.

All raw samples and failed-trial evidence are retained. An error inside a trial
stops further submissions in that trial, records its incomplete cohort, and
fails the result. Launch/migration errors also fail. Never interpret faster
incomplete trials as improvement. No aggregate speedup is automatically claimed.
Environment, source hashes, workload hashes and Compose configuration accompany
results; mutable base-image tags remain a reproducibility limitation.

Before any capacity or commercial claim: implement and verify HTTP and broker
arms, resolve bridge connectivity, measure whole-system resources, run frozen
scheduled workloads and failure tests, and obtain independent reproduction.
Robotics follows with a specified 2D warehouse baseline and simple-filter control.

Local validation of this addition covers probe statistics/reconciliation and
Python compilation. Its Docker/PostgreSQL execution must be verified in Codespaces.
