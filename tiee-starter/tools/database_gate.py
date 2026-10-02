"""Container-only gate: fresh dedicated database, migration, limited app role."""
import hashlib
import json
import os
from pathlib import Path
import platform
import unittest


def gate_passed(result):
    return result.testsRun >= 49 and result.wasSuccessful() and not result.skipped


def main():
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    evidence = Path('/evidence')
    summary = {'status': 'ERROR', 'database_integration_executed': False}
    try:
        common = dict(host='127.0.0.1', dbname='tiee_test', connect_timeout=5)
        admin = make_conninfo(**common, user='tiee_migrator', password=os.environ['TIEE_ADMIN_PASSWORD'])
        app_password = os.environ['TIEE_APP_PASSWORD']
        with psycopg.connect(admin, autocommit=True) as conn:
            with conn.transaction():
                # Fresh database required: repeated migration is an error, not an overwrite.
                conn.execute(Path('storage/schema.sql').read_text())
                conn.execute(sql.SQL('CREATE ROLE tiee_app LOGIN PASSWORD {}').format(sql.Literal(app_password)))
                conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
                conn.execute('GRANT USAGE ON SCHEMA public TO tiee_app')
                conn.execute('GRANT SELECT, INSERT ON tiee_runs,tiee_events,tiee_outputs,tiee_audit TO tiee_app')
                conn.execute('GRANT UPDATE ON tiee_events TO tiee_app')
                conn.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tiee_app')
        os.environ['TIEE_TEST_DSN'] = make_conninfo(**common, user='tiee_app', password=app_password)
        os.environ.pop('TIEE_ADMIN_PASSWORD', None)
        os.environ.pop('TIEE_APP_PASSWORD', None)
        with psycopg.connect(os.environ['TIEE_TEST_DSN']) as conn:
            db_version = conn.execute('SELECT version()').fetchone()[0]
            sync_commit = conn.execute('SHOW synchronous_commit').fetchone()[0]
        with (evidence / 'tests.log').open('x') as log:
            suite = unittest.defaultTestLoader.discover('tests')
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        summary = {'status': 'PASS' if gate_passed(result) else 'FAIL',
                   'database_integration_executed': True, 'tests_run': result.testsRun,
                   'failures': len(result.failures), 'errors': len(result.errors),
                   'skipped': len(result.skipped), 'postgres': db_version,
                   'synchronous_commit': sync_commit, 'psycopg': psycopg.__version__,
                   'python': platform.python_version(), 'runtime_role': 'tiee_app',
                   'power_loss_tested': False, 'server_restart_tested': False,
                   'performance_benchmark': False,
                   'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for folder in ('shared','storage','benchmark','tests','tools')
                                     for p in sorted(Path(folder).rglob('*')) if p.suffix in ('.py','.sql')}}
    except Exception as exc:
        # Avoid connection strings/passwords in diagnostics. Tests use no SQL containing secrets.
        summary['error_type'] = type(exc).__name__
    with (evidence / 'database-gate.json').open('x') as f:
        json.dump(summary, f, indent=2)
    print(json.dumps({'status': summary['status']}))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
