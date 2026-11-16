"""Durable SQLite restart/replay proof for the real starter processor.

Local file persistence only: NOT gateway/queue recovery or a production service.
"""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.generator import generate
from shared.processor import canonical, decode, eligible, process


def deliver(db_path, payloads, iterations=37, interrupt_after_commit=None):
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS outputs (event_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        committed = 0
        for raw in payloads:
            event = decode(raw)
            if not eligible(event):
                continue
            output = process(event, iterations)
            encoded = json.dumps(output, sort_keys=True, separators=(",", ":"))
            old = conn.execute("SELECT payload FROM outputs WHERE event_id=?", (output["event_id"],)).fetchone()
            if old is not None and old[0] != encoded:
                raise ValueError("conflicting replay")
            if old is None:
                conn.execute("INSERT INTO outputs VALUES (?,?)", (output["event_id"], encoded))
                conn.commit()  # intentionally commit before simulated acknowledgement
                committed += 1
                if interrupt_after_commit is not None and committed == interrupt_after_commit:
                    raise InterruptedError("after durable commit, before acknowledgement")
        return conn.execute("SELECT event_id,payload FROM outputs ORDER BY event_id").fetchall()


class DurableProcessorReplayTests(unittest.TestCase):
    def setUp(self):
        self.events = [canonical(item["event"]) for item in generate(seed=101, count=100, useful_percent=50)]

    def test_reopen_and_replay_after_committed_interruption(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "processor.sqlite"
            with self.assertRaises(InterruptedError):
                deliver(db, self.events, interrupt_after_commit=13)
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM outputs").fetchone()[0], 13)
            recovered = deliver(db, self.events)
            self.assertEqual(len(recovered), 50)
            self.assertEqual(deliver(db, self.events), recovered)
            other = Path(temp) / "uninterrupted.sqlite"
            self.assertEqual(deliver(other, self.events), recovered)

    def test_version_conflict_preserves_committed_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "processor.sqlite"
            expected = deliver(db, self.events, iterations=37)
            with self.assertRaisesRegex(ValueError, "conflicting replay"):
                deliver(db, self.events, iterations=38)
            with sqlite3.connect(db) as conn:
                observed = conn.execute("SELECT event_id,payload FROM outputs ORDER BY event_id").fetchall()
            self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
