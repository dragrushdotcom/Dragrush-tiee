import unittest
from paired_run import receipt


class PairedRunTests(unittest.TestCase):
    def test_receipt_has_real_raw_samples_and_no_production_claim(self):
        r = receipt(n=100, repetitions=5, warmups=1, seed=3)
        self.assertEqual(len(r['measurements']['baseline']['raw_ms']), 5)
        self.assertEqual(r['paired_analysis']['pairs'], 5)
        self.assertFalse(r['paired_analysis']['production_evidence'])
        self.assertTrue(r['not_production_evidence'])
        self.assertEqual(r['correctness']['important_dropped'], 0)

    def test_invalid_parameters_fail_closed(self):
        with self.assertRaises(ValueError):
            receipt(n=0)
        with self.assertRaises(ValueError):
            receipt(repetitions=2)


if __name__ == '__main__':
    unittest.main()
