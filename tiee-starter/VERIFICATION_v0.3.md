# Verification record v0.3

Python 3.12 with psycopg 3.3.5 and typing-extensions 4.16.0 installed in an isolated authoring virtual environment.

- 49 tests discovered: 39 passed, 10 PostgreSQL integration tests skipped, 0 failures.
- Source compilation for tools, storage, and tests passed.
- Launcher preflight returned exit code 2 with “Docker is unavailable; no database tests were run”. It created no test project or database.
- PostgreSQL installation was blocked by operating-system permission errors. No bypass or privilege escalation was attempted.
- Docker build, Compose startup, SQL migration, application-role grants, and all 10 PostgreSQL integration tests remain NOT RUN.

The four new offline tests verify that a gate cannot pass with missing tests, skipped tests, or failures. They do not verify container startup or database behavior. Compose configuration is supplied for execution in an authorized environment, not certified as runtime-tested.

Next action: follow DATABASE_TESTING.md and retain database-gate.json plus tests.log. Do not declare persistence verified unless the real gate reports PASS without skips.
