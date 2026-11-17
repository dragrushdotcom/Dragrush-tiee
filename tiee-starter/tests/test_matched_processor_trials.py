"""Contract tests for the local matched processor experiment."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.matched_processor_trials import measure


class MatchedProcessorTrialsTests(unittest.TestCase):
    def test_repeated_real_processor_outputs_are_identical(self):
        result = measure(count=100, repetitions=3, warmups=1, iterations=4)
        self.assertEqual(result["scope"], "actual starter processor, local in-process only")
        self.assertFalse(result["service_evidence"])
        self.assertFalse(result["production_speedup_claim"])
        self.assertEqual(len(result["measurements_ns"]["baseline"]), 3)
        self.assertEqual(len(result["measurements_ns"]["treatment"]), 3)
        self.assertTrue(all(v > 0 for values in result["measurements_ns"].values() for v in values))

    def test_deterministic_input_output_hashes(self):
        first = measure(count=100, repetitions=3, warmups=0, iterations=2)
        second = measure(count=100, repetitions=3, warmups=0, iterations=2)
        self.assertEqual(first["input_sha256"], second["input_sha256"])
        self.assertEqual(first["output_sha256"], second["output_sha256"])

    def test_rejects_invalid_config(self):
        for kwargs in ({"count": 99}, {"repetitions": 2}, {"warmups": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                measure(**kwargs)


if __name__ == "__main__":
    unittest.main()
