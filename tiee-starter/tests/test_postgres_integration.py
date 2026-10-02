"""Opt-in tests against a dedicated pre-migrated test database; no deletes."""
from concurrent.futures import ThreadPoolExecutor
import copy
import os
import unittest
from unittest.mock import patch
import uuid

from benchmark.generator import generate
from shared.processor import canonical
from storage.postgres import PostgresStore, Run, IdentityConflict, RunConflict

DSN = os.environ.get('TIEE_TEST_DSN')


@unittest.skipUnless(DSN, 'PostgreSQL integration not run: set TIEE_TEST_DSN to a dedicated migrated test database')
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.store = PostgresStore.from_dsn(DSN)
        self.run = Run('test_' + uuid.uuid4().hex, 'T', 0)
        self.store.register(self.run)
        self.event = next(generate(count=100))['event']
        self.event['payload']['quality'] = .8

    def submit(self, event=None):
        return self.store.submit(self.run, canonical(event or self.event))

    def rows(self, table):
        if table not in ('tiee_events', 'tiee_outputs', 'tiee_audit'):
            raise ValueError('unsupported test table')
        with self.store.connect() as c:
            order = 'audit_id' if table == 'tiee_audit' else 'event_id'
            return c.execute(f'SELECT * FROM {table} WHERE run_id=%s ORDER BY {order}', (self.run.run_id,)).fetchall()

    def test_accept_and_replay(self):
        first, second = self.submit(), self.submit()
        self.assertEqual(first['state'], 'COMPLETED')
        self.assertFalse(first['replayed']); self.assertTrue(second['replayed'])
        self.assertEqual(first['output'], second['output'])
        self.assertEqual(len(self.rows('tiee_outputs')), 1)
        self.assertEqual(len(self.rows('tiee_audit')), 3)

    def test_rejection_is_persisted(self):
        self.event['payload']['quality'] = .79
        self.assertEqual(self.submit()['state'], 'REJECTED')
        self.assertTrue(self.submit()['replayed'])
        self.assertEqual(len(self.rows('tiee_outputs')), 0)

    def test_conflict_is_audited(self):
        self.submit()
        changed = copy.deepcopy(self.event); changed['payload']['quality'] = .79
        with self.assertRaises(IdentityConflict): self.submit(changed)
        self.assertEqual(len(self.rows('tiee_outputs')), 1)
        self.assertEqual(self.rows('tiee_audit')[-1][3], 'CONFLICT')

    def test_concurrent_retries(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.submit(), range(4)))
        self.assertEqual(sum(not r['replayed'] for r in results), 1)
        self.assertEqual(len(self.rows('tiee_outputs')), 1)

    def test_pinned_run_conflict(self):
        with self.assertRaises(RunConflict):
            self.store.register(Run(self.run.run_id, 'B0', 0))

    def test_failed_calculation_leaves_recoverable_intent(self):
        with patch('storage.postgres.calculate', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError): self.submit()
        self.assertEqual(self.rows('tiee_events')[0][3], 'PENDING')
        self.assertEqual(len(self.rows('tiee_outputs')), 0)
        self.assertEqual(self.submit()['state'], 'COMPLETED')

    def test_audit_failure_rolls_back_output(self):
        original = self.store._audit
        def fail_terminal(conn, run, eid, action, reason):
            if action == 'COMPLETED': raise RuntimeError('injected audit failure')
            original(conn, run, eid, action, reason)
        with patch.object(self.store, '_audit', side_effect=fail_terminal):
            with self.assertRaises(RuntimeError): self.submit()
        self.assertEqual(len(self.rows('tiee_outputs')), 0)
        self.assertEqual(self.rows('tiee_events')[0][3], 'PENDING')
        self.assertEqual(self.submit()['state'], 'COMPLETED')

    def test_unknown_run_creates_no_intent(self):
        with self.assertRaises(RunConflict):
            self.store.submit(Run('absent_' + uuid.uuid4().hex), canonical(self.event))

    def test_runtime_role_cannot_rewrite_audit(self):
        import psycopg
        self.submit()
        with self.store.connect() as c:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                c.execute('UPDATE tiee_audit SET reason=%s WHERE run_id=%s', ('tampered',self.run.run_id))

    def test_runtime_role_cannot_delete_outputs(self):
        import psycopg
        self.submit()
        with self.store.connect() as c:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                c.execute('DELETE FROM tiee_outputs WHERE run_id=%s', (self.run.run_id,))
