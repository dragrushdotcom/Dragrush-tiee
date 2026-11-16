"""Deterministic actual-processor fault/retry checks; not service recovery evidence."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

PROCESSOR = Path(__file__).resolve().parents[2] / "tiee-starter/shared/processor.py"
spec = importlib.util.spec_from_file_location("tiee_processor", PROCESSOR)
processor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processor)

def request():
    payload = {"sensor_id": "s-01", "sequence": 1, "quality": 0.9,
               "sample_bytes": base64.b64encode(bytes(range(256)) * 4).decode("ascii")}
    event_id = hashlib.sha256(processor.canonical(payload)).hexdigest()
    return processor.canonical({"schema_version": "benchmark-wire-1", "event_id": event_id, "payload": payload})

class ActualProcessorRecovery(unittest.TestCase):
    def test_retry_after_injected_failure_same_digest(self):
        raw = request()
        expected = processor.process(processor.decode(raw), 16)
        attempts = 0
        def interrupted_once():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("injected failure before processor call")
            return processor.process(processor.decode(raw), 16)
        with self.assertRaisesRegex(RuntimeError, "injected failure"):
            interrupted_once()
        self.assertEqual(expected, interrupted_once())
        self.assertEqual(2, attempts)

    def test_corrupted_retry_rejected_before_processing(self):
        obj = json.loads(request())
        obj["payload"]["sample_bytes"] = "not-base64!"
        with self.assertRaises(ValueError):
            processor.decode(processor.canonical(obj))

    def test_duplicate_json_key_rejected(self):
        raw = request()
        with self.assertRaises(ValueError):
            processor.decode(raw[:-1] + b',"event_id":"' + b"0" * 64 + b'"}')

if __name__ == "__main__":
    unittest.main()
