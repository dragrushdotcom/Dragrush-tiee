import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from measure_processor import measure

class ProcessorMeasurementTests(unittest.TestCase):
    def test_real_processor_samples_and_provenance(self):
        result=measure(count=100,iterations=0,repeats=3,warmups=1)
        self.assertEqual(len(result["runs"]),3)
        self.assertEqual([x["eligible"] for x in result["runs"]],[50]*3)
        self.assertEqual(len(result["fixture_sha256"]),64)
        self.assertFalse(result["production_speedup_evidence"])
        self.assertTrue(all(x["p99_ms"]>=x["p50_ms"]>=0 for x in result["runs"]))
    def test_reject_invalid_repeats(self):
        with self.assertRaises(ValueError): measure(repeats=2)
        with self.assertRaises(ValueError): measure(warmups=0)

if __name__=="__main__": unittest.main()
