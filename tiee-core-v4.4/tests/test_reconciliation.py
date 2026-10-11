import unittest
from datetime import datetime,timedelta,timezone
from app.reconciliation import should_relay

class ReconciliationContracts(unittest.TestCase):
    def setUp(self): self.now=datetime(2026,1,1,tzinfo=timezone.utc)
    def test_pending_relay(self):
        self.assertTrue(should_relay('PENDING',None,self.now))
    def test_enqueued_not_early(self):
        self.assertFalse(should_relay('ENQUEUED',self.now-timedelta(seconds=9),self.now))
    def test_enqueued_recovery_after_interval(self):
        self.assertTrue(should_relay('ENQUEUED',self.now-timedelta(seconds=10),self.now))
    def test_old_schema_null_retry(self):
        self.assertTrue(should_relay('ENQUEUED',None,self.now))
    def test_completed_or_rejected_not_relayed(self):
        for s in ('DONE','REJECTED'):
            self.assertFalse(should_relay(s,None,self.now))
    def test_bad_interval_rejected(self):
        with self.assertRaises(ValueError): should_relay('PENDING',None,self.now,0)
