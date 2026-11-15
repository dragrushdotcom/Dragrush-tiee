"""Deterministic interruption/replay contract for the real starter processor.

This is an in-process restart simulation, NOT a durable queue or gateway recovery test.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.generator import generate
from shared.processor import canonical, decode, eligible, process


def run(events, iterations, stop_after=None, sink=None):
    """Replay entire input into an idempotent simulated sink; fail on conflicts."""
    if sink is None:
        sink = {}
    for index, raw in enumerate(events):
        if stop_after is not None and index == stop_after:
            raise InterruptedError("injected process interruption")
        event = decode(raw)
        if not eligible(event):
            continue
        output = process(event, iterations)
        event_id = output["event_id"]
        if event_id in sink and sink[event_id] != output:
            raise AssertionError("replayed event produced conflicting output")
        sink[event_id] = output
    return sink


class ProcessorInterruptionTests(unittest.TestCase):
    def setUp(self):
        self.events = [canonical(x["event"]) for x in generate(seed=101, count=100, useful_percent=50)]

    def test_interruption_and_full_replay_matches_uninterrupted(self):
        expected = run(self.events, iterations=37)
        persisted = {}
        with self.assertRaises(InterruptedError):
            run(self.events, iterations=37, stop_after=43, sink=persisted)
        self.assertGreater(len(persisted), 0)
        self.assertLess(len(persisted), len(expected))
        self.assertEqual(run(self.events, iterations=37, sink=persisted), expected)
        self.assertEqual(len(persisted), 50)
        self.assertEqual(run(self.events, iterations=37, sink=persisted), expected)

    def test_changed_processing_version_fails_closed_on_replay(self):
        persisted = run(self.events, iterations=37)
        with self.assertRaisesRegex(AssertionError, "conflicting output"):
            run(self.events, iterations=38, sink=persisted)

    def test_rejected_events_never_appear_in_sink(self):
        sink = run(self.events, iterations=0)
        eligible_ids = {decode(raw)["event_id"] for raw in self.events if eligible(decode(raw))}
        self.assertEqual(set(sink), eligible_ids)


if __name__ == "__main__":
    unittest.main()
