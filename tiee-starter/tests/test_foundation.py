import copy
import hashlib
import inspect
import json
import unittest
import subprocess
import sys
import tempfile
from pathlib import Path

from benchmark.generator import generate, encoded
from benchmark import oracle
from benchmark.__main__ import check
from shared.processor import decode, canonical, eligible, ev, process, score_policy


class FoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = list(generate(count=100))

    def event(self):
        return copy.deepcopy(self.records[0]["event"])

    def test_deterministic_bytes(self):
        self.assertEqual(encoded(self.records), encoded(list(generate(count=100))))

    def test_golden_workload_hash(self):
        self.assertEqual(hashlib.sha256(encoded(self.records)).hexdigest(),
                         "923097fccfaf68b9889c7b04478da61d340a079c16f8d81d9034f69f8554b5fa")

    def test_cli_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "run"
            command = [sys.executable, "-m", "benchmark", "--out", str(out),
                       "--count", "100", "--iterations", "0"]
            first = subprocess.run(command, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = (out / "summary.json").read_bytes()
            self.assertFalse(json.loads(original)["benchmark_executed"])
            second = subprocess.run(command, capture_output=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(original, (out / "summary.json").read_bytes())
            for line in (out / "checksums.sha256").read_text().splitlines():
                digest, filename = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((out / filename).read_bytes()).hexdigest(), digest)

    def test_seed_changes_bytes(self):
        self.assertNotEqual(encoded(self.records), encoded(list(generate(seed=202, count=100))))

    def test_exact_mixes_per_block(self):
        for mix in (10, 25, 50, 75, 100):
            rows = list(generate(count=300, useful_percent=mix))
            for start in range(0, 300, 100):
                self.assertEqual(sum(eligible(r["event"]) for r in rows[start:start+100]), mix)

    def test_unique_opaque_ids(self):
        rows = list(generate(count=300))
        self.assertEqual(len({r["event"]["event_id"] for r in rows}), 300)
        for row in rows:
            self.assertRegex(row["event"]["event_id"], "^[0-9a-f]{64}$")

    def test_schedule(self):
        self.assertEqual([r["scheduled_ns"] for r in self.records], [i*100000000 for i in range(100)])

    def test_invalid_generation_arguments(self):
        for kwargs in ({"count": 1}, {"count": 0}, {"rate": 0}, {"seed": -1}, {"useful_percent": 12}, {"count": True}):
            with self.assertRaises(ValueError): list(generate(**kwargs))

    def test_valid_schema(self):
        for row in self.records: self.assertEqual(decode(canonical(row["event"])), row["event"])

    def test_quality_boundary(self):
        for quality, allowed in ((.79, False), (.80, True), (.81, True)):
            event = self.event(); event["payload"]["quality"] = quality
            self.assertEqual(eligible(decode(canonical(event))), allowed)
            self.assertEqual(bool(oracle.expected([{"event": event}], 0)), allowed)

    def test_quality_invalid(self):
        for q in (-.01, 1.01, True, "0.8", None, float("nan"), float("inf")):
            event = self.event(); event["payload"]["quality"] = q
            with self.assertRaises(ValueError): decode(json.dumps(event).encode())

    def test_malformed_and_oversized(self):
        for raw in (b"{", b"[]", b"null", b" "*65537, b'{"a":1,"a":2}'):
            with self.assertRaises(ValueError): decode(raw)

    def test_missing_and_unknown_fields(self):
        event = self.event(); del event["payload"]["quality"]
        with self.assertRaises(ValueError): decode(canonical(event))
        event = self.event(); event["ground_truth"] = "valid"
        with self.assertRaises(ValueError): decode(canonical(event))

    def test_invalid_sample(self):
        for value in ("!!!", "YQ==", 123):
            event = self.event(); event["payload"]["sample_bytes"] = value
            with self.assertRaises(ValueError): decode(canonical(event))

    def test_score_boundaries(self):
        for score, outcome in ((-1,"REJECT"),(0,"REJECT"),(1,"ALLOW"),(None,"INDETERMINATE"),(True,"INDETERMINATE"),(float("nan"),"INDETERMINATE"),(float("inf"),"INDETERMINATE")):
            self.assertEqual(score_policy(score), outcome)

    def test_ev_parity(self):
        for row in self.records:
            event = row["event"]
            self.assertEqual(ev(event)["disposition"] == "ALLOW", eligible(event))

    def test_processor_oracle_parity(self):
        event = self.event(); event["payload"]["quality"] = .8
        for k in (0, 1, 100, 1000, 10000):
            self.assertEqual([process(event,k)], oracle.expected([{"event":event}],k))

    def test_known_digest_vector(self):
        event = self.event(); event["payload"]["sample_bytes"] = "YQ=="
        # Processor has a known primitive vector; public decode rejects short payloads.
        self.assertEqual(process(event,0)["digest"], "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb")

    def test_invalid_processing_cost(self):
        for k in (-1, True, 10001, 1.5):
            with self.assertRaises(ValueError): process(self.event(), k)

    def test_reconcile_detects_all_error_classes(self):
        expected = oracle.expected(self.records,0)
        changed = copy.deepcopy(expected[1:]); changed[0]["digest"] = "bad"
        changed.append(changed[1]); changed.append({"event_id":"unknown","digest":"x"})
        result = oracle.reconcile(expected,changed)
        self.assertFalse(result["pass"])
        for field in ("missing", "unexpected", "wrong", "duplicate_ids"):
            self.assertTrue(result[field])

    def test_equal_counts_not_sufficient(self):
        expected = oracle.expected(self.records,0)
        altered = copy.deepcopy(expected); altered[0]["digest"] = "bad"
        self.assertFalse(oracle.reconcile(expected,altered)["pass"])

    def test_duplicate_oracle_source_rejected(self):
        with self.assertRaises(ValueError): oracle.expected([self.records[0]]*2,0)

    def test_oracle_has_no_service_imports(self):
        self.assertNotIn("from shared", inspect.getsource(oracle))
        self.assertNotIn("import shared", inspect.getsource(oracle))

    def test_no_hidden_label_fields(self):
        for row in self.records:
            self.assertEqual(set(row["event"]), {"schema_version","event_id","payload"})
            self.assertEqual(set(row["event"]["payload"]), {"sensor_id","sequence","quality","sample_bytes"})

    def test_functional_cases(self):
        for mix in (100,50,10):
            _, _, _, _, reports = check(mix,101,100,0,10)
            for report in reports.values(): self.assertTrue(report["pass"])
            self.assertEqual(reports["B0"]["processing_calls"],100)
            for arm in ("B1","T"):
                self.assertEqual(reports[arm]["processing_calls"],mix)


if __name__ == "__main__":
    unittest.main()
