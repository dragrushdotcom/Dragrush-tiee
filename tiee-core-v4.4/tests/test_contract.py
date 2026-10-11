import unittest
from app.common import canonical,fingerprint,eligible,digest_work
class Contracts(unittest.TestCase):
    def setUp(self):self.e={'id':'a','kind':'valid','rounds':4,'body':'x'}
    def test_fingerprint_canonical(self):
        self.assertEqual(fingerprint(self.e),fingerprint(dict(reversed(list(self.e.items())))))
    def test_conflict(self):
        e=dict(self.e,body='changed');self.assertNotEqual(fingerprint(e),fingerprint(self.e))
    def test_equal_policy(self):
        for kind in ('valid','bot'):
            e=dict(self.e,kind=kind)
            self.assertEqual(eligible(e,'baseline'),eligible(e,'tiee'))
    def test_deterministic_output(self):self.assertEqual(digest_work(self.e),digest_work(self.e))
if __name__=='__main__':unittest.main()
