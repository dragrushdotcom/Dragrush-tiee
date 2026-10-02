"""Independent evaluator: deliberately imports no shared service implementation."""
import base64
from collections import Counter
from decimal import Decimal
from hashlib import sha256


def expected(records, iterations):
    if type(iterations) is not int or not 0 <= iterations <= 10000:
        raise ValueError("iterations must be integer 0..10000")
    rows = []
    seen = set()
    for record in records:
        event = record["event"]
        if event["event_id"] in seen:
            raise ValueError("duplicate source identity")
        seen.add(event["event_id"])
        if Decimal(str(event["payload"]["quality"])) < Decimal("0.80"):
            continue
        accumulator = base64.b64decode(event["payload"]["sample_bytes"], validate=True)
        for _ in range(iterations + 1):
            accumulator = sha256(accumulator).digest()
        rows.append({"event_id": event["event_id"], "digest": accumulator.hex(),
                     "processor_version": "hash-chain-v1"})
    return rows


def reconcile(expected_rows, actual_rows):
    want = {r["event_id"]: r for r in expected_rows}
    if len(want) != len(expected_rows):
        raise ValueError("duplicate expected identity")
    counts = Counter(row["event_id"] for row in actual_rows)
    missing = sorted(set(want) - set(counts))
    unexpected = sorted(set(counts) - set(want))
    wrong = sorted({r["event_id"] for r in actual_rows
                    if r["event_id"] in want and r != want[r["event_id"]]})
    duplicates = sorted(k for k, v in counts.items() if v > 1)
    return {"pass": not (missing or unexpected or wrong or duplicates),
            "expected_count": len(want), "actual_count": len(actual_rows),
            "missing": missing, "unexpected": unexpected, "wrong": wrong,
            "duplicate_ids": duplicates,
            "duplicate_rows": sum(v - 1 for v in counts.values())}
