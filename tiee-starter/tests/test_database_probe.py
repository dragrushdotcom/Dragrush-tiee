import unittest
from tools.run_database_probe import latency, verify


class Cursor:
    def __init__(self, rows):
        self.rows = rows
    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, outputs, states, audit):
        self.data = iter((outputs, states, audit))
    def execute(self, query, params):
        return Cursor(next(self.data))


class ProbeTests(unittest.TestCase):
    def test_empty_latency_does_not_invent_zero(self):
        self.assertEqual(latency([]), {'count':0, 'p50_ms':None, 'p95_ms':None, 'p99_ms':None})

    def test_nearest_rank(self):
        self.assertEqual(latency(list(range(100, 0, -1))),
                         {'count':100, 'p50_ms':50, 'p95_ms':95, 'p99_ms':99})

    def check_rows(self, states, audit, digest='ok'):
        truth = [{'event_id':'e', 'digest':'ok', 'processor_version':'v'}]
        conn = Connection([('e',digest,'v')], states, audit)
        return verify(conn, 'run', truth, 2)['pass']

    def test_complete_accounting(self):
        self.assertTrue(self.check_rows([('COMPLETED',1),('REJECTED',1)],
                                       [('INTENT',2),('COMPLETED',1),('REJECTED',1)]))

    def test_pending_cannot_pass_with_correct_outputs(self):
        self.assertFalse(self.check_rows([('COMPLETED',1),('PENDING',1)],
                                        [('INTENT',2),('COMPLETED',1)]))

    def test_missing_audit_fails(self):
        self.assertFalse(self.check_rows([('COMPLETED',1),('REJECTED',1)],
                                        [('COMPLETED',1),('REJECTED',1)]))

    def test_bad_digest_fails(self):
        self.assertFalse(self.check_rows([('COMPLETED',1),('REJECTED',1)],
                                        [('INTENT',2),('COMPLETED',1),('REJECTED',1)], 'wrong'))
