# Run the PostgreSQL verification gate

The v0.3 package includes an isolated Docker Compose test launcher. Docker/Compose must already be installed and permitted on the machine. Do not install it on a public computer without the owner's permission. No cloud account or public port is required.

From the extracted project directory:

```sh
python3 -m tools.run_database_gate --out results/postgres-check-001
```

Use a new output path each time. The launcher creates a uniquely named Docker project, generates disposable random database passwords, builds the test image, waits for PostgreSQL readiness, migrates a fresh database, and runs all tests using a restricted application role. It then stops only its own project. It does not delete database volumes or existing evidence. Retained stopped containers and volumes use disk space; their generated project name is recorded in launcher.json. No automated cleanup is included.

The database has no published host port and uses an internal project network. Image/package downloads occur during setup. The database retains a named volume so this is not a tmpfs durability simulation. Generated credentials are not written into the report but remain visible to an authorized Docker administrator through container metadata; treat this environment as disposable, not production.

PASS requires all discovered tests to succeed, at least 49 tests, and zero skips. Missing dependencies, migration failures, role-permission failures, or skipped database tests cannot produce PASS. The ten database tests now include audit-update and output-delete permission denials, in addition to the original eight behavior tests. Run them as the supplied application role, not a superuser.

Inspect database-gate.json, tests.log, launcher.json, and images.json. If startup/build fails, inspect build.log or up.log instead; absence of database-gate.json means no database gate result. Application failures do not count as a successful test merely because the container started.

Psycopg 3.3.5 and typing-extensions 4.16.0 are pinned. Python/PostgreSQL base image tags are development selections, not digest locks. Record actual images via images.json; pin digests before published comparisons. This is correctness testing, not the five-arm performance benchmark, and does not test server restart or power loss.

## Current verification status

The authoring workspace permitted installing the Python driver in a task-specific virtual environment. PostgreSQL installation failed on operating-system permission restrictions; Docker is absent. Those restrictions were not bypassed. Consequently neither the Compose environment nor the ten PostgreSQL tests has been executed here.

The launcher, gate checks, Python syntax, and offline test suite can be checked without Docker. A successful offline test run with database skips is explicitly not a successful database gate.

Initialization design follows the [official PostgreSQL image documentation](https://hub.docker.com/_/postgres). Driver usage follows [Psycopg transaction management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html). These references do not certify this package.
