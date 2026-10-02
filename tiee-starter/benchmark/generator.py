"""Deterministic source fixtures, with exact class ratios per 100 events."""
import base64
import hashlib
import json


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(*parts):
    # Domain-separated JSON array encoding avoids concatenation ambiguity.
    return hashlib.sha256(encoded(list(parts))).digest()


def generate(seed=101, count=300, useful_percent=50, rate=10):
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be an unsigned 32-bit integer")
    if type(count) is not int or count <= 0 or count % 100:
        raise ValueError("count must be a positive multiple of 100")
    if type(useful_percent) is not int or useful_percent not in (10, 25, 50, 75, 100):
        raise ValueError("unsupported mix")
    if type(rate) is not int or rate <= 0:
        raise ValueError("rate must be a positive integer")
    sent = 0
    for block in range(count // 100):
        members = [(digest("event", seed, block, j).hex(), j) for j in range(100)]
        useful_ids = {eid for eid, _ in sorted(members, key=lambda item: digest("class", seed, item[0]))[:useful_percent]}
        for eid, j in sorted(members, key=lambda item: digest("order", seed, block, item[0])):
            choices = (.80, .85, .90, .95, 1.0) if eid in useful_ids else (0., .20, .40, .60, .79)
            quality = choices[digest("quality", seed, eid)[0] % 5]
            sample = b"".join(digest("sample", seed, eid, piece) for piece in range(32))
            event = {"schema_version": "benchmark-wire-1", "event_id": eid,
                     "payload": {"sensor_id": f"s-{j % 16:02d}", "sequence": block * 100 + j,
                                 "quality": quality, "sample_bytes": base64.b64encode(sample).decode("ascii")}}
            yield {"scheduled_ns": sent * 1_000_000_000 // rate, "event": event}
            sent += 1
