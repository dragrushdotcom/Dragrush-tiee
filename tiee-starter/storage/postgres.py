"""Synchronous PostgreSQL slice. External effects are limited to these tables.

Each call owns a fresh autocommit connection. Explicit transactions use
READ COMMITTED; commit failures propagate, so clients retry the same identity.
"""
from dataclasses import dataclass
import hashlib
import re

from shared.processor import VERSION, canonical, decode, eligible, ev, process

POLICY = 'deterministic-eligibility-v1'


class IdentityConflict(ValueError):
    pass


class RunConflict(ValueError):
    pass


@dataclass(frozen=True)
class Run:
    run_id: str
    arm: str = 'B1'
    iterations: int = 100

    def __post_init__(self):
        if not isinstance(self.run_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', self.run_id):
            raise ValueError('invalid run ID')
        if self.arm not in ('B0', 'B1', 'T'):
            raise ValueError('unsupported synchronous arm')
        if type(self.iterations) is not int or not 0 <= self.iterations <= 10000:
            raise ValueError('iterations must be integer 0..10000')


def prepare(raw):
    event = decode(raw)
    # JSON key ordering and whitespace are not part of the logical identity.
    return event, hashlib.sha256(canonical(event)).hexdigest()


def calculate(event, run):
    result = process(event, run.iterations) if run.arm == 'B0' else None
    decision = ev(event) if run.arm == 'T' else {
        'disposition': 'ALLOW' if eligible(event) else 'REJECT',
        'reason': 'QUALITY_ELIGIBLE' if eligible(event) else 'QUALITY_BELOW_THRESHOLD',
        'score': None}
    if decision['disposition'] == 'ALLOW':
        if result is None:
            result = process(event, run.iterations)
        return 'COMPLETED', decision, result
    return 'REJECTED', decision, None


class PostgresStore:
    def __init__(self, connection_factory):
        self.connect = connection_factory

    @classmethod
    def from_dsn(cls, dsn):
        # Optional driver: offline foundation tests require no packages.
        import psycopg
        return cls(lambda: psycopg.connect(dsn, autocommit=True, connect_timeout=5))

    @staticmethod
    def _settings(conn):
        if not conn.autocommit:
            raise ValueError('connection must be autocommit; this adapter owns transactions')
        conn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
        conn.execute("SET LOCAL synchronous_commit = on")
        conn.execute("SET LOCAL statement_timeout = '5s'")
        conn.execute("SET LOCAL lock_timeout = '5s'")

    @staticmethod
    def _audit(conn, run, event_id, action, reason):
        conn.execute('INSERT INTO tiee_audit(run_id,event_id,action,reason) VALUES (%s,%s,%s,%s)',
                     (run.run_id, event_id, action, reason))

    def register(self, run):
        with self.connect() as conn:
            with conn.transaction():
                self._settings(conn)
                conn.execute('''INSERT INTO tiee_runs(run_id,arm,iterations,processor_version,policy_version)
                    VALUES (%s,%s,%s,%s,%s) ON CONFLICT (run_id) DO NOTHING''',
                             (run.run_id, run.arm, run.iterations, VERSION, POLICY))
                self._verify_run(conn, run)

    @staticmethod
    def _verify_run(conn, run):
        row = conn.execute('SELECT arm,iterations,processor_version,policy_version FROM tiee_runs WHERE run_id=%s',
                           (run.run_id,)).fetchone()
        if row != (run.arm, run.iterations, VERSION, POLICY):
            raise RunConflict('run missing or pinned configuration differs')

    def submit(self, run, raw):
        event, body_hash = prepare(raw)
        event_id = event['event_id']
        with self.connect() as conn:
            # Durable intent survives failures during calculation or final transaction.
            with conn.transaction():
                self._settings(conn)
                self._verify_run(conn, run)
                inserted = conn.execute('''INSERT INTO tiee_events(run_id,event_id,body_hash,state)
                    VALUES (%s,%s,%s,'PENDING') ON CONFLICT (run_id,event_id) DO NOTHING
                    RETURNING event_id''', (run.run_id, event_id, body_hash)).fetchone()
                existing_hash = conn.execute('SELECT body_hash FROM tiee_events WHERE run_id=%s AND event_id=%s',
                                             (run.run_id, event_id)).fetchone()[0]
                conflict = existing_hash != body_hash
                if conflict:
                    self._audit(conn, run, event_id, 'CONFLICT', 'IDENTITY_BODY_MISMATCH')
                elif inserted:
                    self._audit(conn, run, event_id, 'INTENT', 'PROCESSING_REQUESTED')
            # Raise after committing the conflict record, never overwrite existing state.
            if conflict:
                raise IdentityConflict('same event ID used with different canonical content')

            with conn.transaction():
                self._settings(conn)
                state, reason, score = conn.execute('''SELECT state,reason,score FROM tiee_events
                    WHERE run_id=%s AND event_id=%s FOR UPDATE''', (run.run_id, event_id)).fetchone()
                replay = state != 'PENDING'
                if replay:
                    self._audit(conn, run, event_id, 'REPLAY', 'RETURN_EXISTING_TERMINAL_RESULT')
                else:
                    state, decision, output = calculate(event, run)
                    reason, score = decision['reason'], decision['score']
                    if output is not None:
                        conn.execute('''INSERT INTO tiee_outputs(run_id,event_id,digest,processor_version)
                            VALUES (%s,%s,%s,%s)''', (run.run_id, event_id, output['digest'], VERSION))
                    conn.execute('''UPDATE tiee_events SET state=%s,reason=%s,score=%s,finished_at=clock_timestamp()
                        WHERE run_id=%s AND event_id=%s''', (state, reason, score, run.run_id, event_id))
                    self._audit(conn, run, event_id, state, reason)
                output_row = conn.execute('SELECT digest,processor_version FROM tiee_outputs WHERE run_id=%s AND event_id=%s',
                                          (run.run_id, event_id)).fetchone()
                response = {'event_id': event_id, 'state': state, 'reason': reason, 'score': score,
                            'replayed': replay, 'output': None if output_row is None else {
                                'event_id': event_id, 'digest': output_row[0], 'processor_version': output_row[1]}}
            # No success response before the transaction context commits.
            return response
