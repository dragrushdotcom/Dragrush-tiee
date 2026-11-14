import unittest
from analyze_pairs import paired_summary


class TestPairedSummary(unittest.TestCase):
    def test_exact_twofold_ratio(self):
        result = paired_summary([2.0, 4.0, 6.0], [1.0, 2.0, 3.0], resamples=100)
        self.assertEqual(result["ratio"], 2.0)
        self.assertEqual(result["bootstrap_95_interval"], [2.0, 2.0])
        self.assertFalse(result["production_evidence"])

    def test_reproducible_seeded_bootstrap(self):
        first = paired_summary([1, 3, 5], [2, 2, 2])
        second = paired_summary([1, 3, 5], [2, 2, 2])
        self.assertEqual(first, second)

    def test_invalid_design_and_samples(self):
        cases = [
            ([1, 2, 3], [1, 2]),
            ([0, 2, 3], [1, 2, 3]),
            ([float("nan"), 2, 3], [1, 2, 3]),
            ([1, 2, 3], [1, 2, float("inf")]),
        ]
        for baseline, candidate in cases:
            with self.subTest(baseline=baseline, candidate=candidate):
                with self.assertRaises(ValueError):
                    paired_summary(baseline, candidate)
        with self.assertRaises(ValueError):
            paired_summary([1, 2, 3], [1, 2, 3], resamples=True)


if __name__ == "__main__":
    unittest.main()
