import unittest
from benchmark import events, baseline, candidate, percentile, evaluate


class SyntheticBenchmarkTests(unittest.TestCase):
    def test_reproducible_inputs(self):
        self.assertEqual(events(100, 4), events(100, 4))

    def test_equivalent_decisions(self):
        sample = events(1000, 6)
        self.assertEqual(baseline(sample), candidate(sample))

    def test_rare_important_events_survive(self):
        self.assertEqual(candidate([(True, 0), (True, 49), (False, 0)]), [True, True, False])

    def test_percentile(self):
        self.assertEqual(percentile([4, 2, 3, 1], .5), 3)

    def test_reject_invalid_input(self):
        with self.assertRaises(ValueError):
            evaluate(n=0)

    def test_measurement_schema(self):
        result = evaluate(n=100, repetitions=3, warmups=1)
        self.assertTrue(result["correctness"]["equal_outputs"])
        self.assertEqual(result["correctness"]["important_dropped"], 0)
        self.assertEqual(len(result["measurements"]["candidate"]["raw_ms"]), 3)


if __name__ == "__main__":
    unittest.main()
