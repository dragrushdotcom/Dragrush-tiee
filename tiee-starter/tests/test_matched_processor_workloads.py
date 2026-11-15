import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from matched_processor_workloads import matched

class MatchedWorkloadsTests(unittest.TestCase):
    def test_matching_and_no_speedup_claim(self):
        result=matched(count=20,repeats=3,warmups=1,baseline_iterations=0,treatment_iterations=3)
        self.assertEqual(len(result["pairs"]),3)
        self.assertEqual(len(result["fixture_sha256"]),64)
        self.assertEqual(len(result["processor_sha256"]),64)
        self.assertFalse(result["production_speedup_evidence"])
        self.assertFalse(result["service_recovery_evidence"])
        self.assertTrue(all(p["elapsed_ratio_treatment_over_baseline"]>0 for p in result["pairs"]))
    def test_same_workload_rejected(self):
        with self.assertRaises(ValueError):
            matched(baseline_iterations=2,treatment_iterations=2)

if __name__=="__main__":
    unittest.main()
