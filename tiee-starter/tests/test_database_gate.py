from types import SimpleNamespace
import unittest
from tools.database_gate import gate_passed


class GateTests(unittest.TestCase):
    def result(self, n=49, success=True, skipped=()):
        return SimpleNamespace(testsRun=n, wasSuccessful=lambda: success, skipped=skipped)

    def test_all_checks_required(self):
        self.assertTrue(gate_passed(self.result()))

    def test_skip_is_not_a_pass(self):
        self.assertFalse(gate_passed(self.result(skipped=[('db','missing')])))

    def test_empty_suite_is_not_a_pass(self):
        self.assertFalse(gate_passed(self.result(n=0)))

    def test_failed_test_fails_gate(self):
        self.assertFalse(gate_passed(self.result(success=False)))
