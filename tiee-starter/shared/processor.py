"""Synthetic benchmark wire contract and shared work; not a host executor."""
import base64
import hashlib
import json
import math
import re

VERSION = "hash-chain-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > 65536:
        raise ValueError("request must be bytes of at most 64 KiB")
    event = json.loads(raw, object_pairs_hook=_object,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    if not isinstance(event, dict) or set(event) != {"schema_version", "event_id", "payload"}:
        raise ValueError("unexpected envelope fields")
    if event["schema_version"] != "benchmark-wire-1":
        raise ValueError("unsupported schema")
    if not isinstance(event["event_id"], str) or not re.fullmatch("[0-9a-f]{64}", event["event_id"]):
        raise ValueError("invalid ID")
    payload = event["payload"]
    if not isinstance(payload, dict) or set(payload) != {"sensor_id", "sequence", "quality", "sample_bytes"}:
        raise ValueError("unexpected payload fields")
    if not isinstance(payload["sensor_id"], str) or not re.fullmatch(r"s-[0-9]{2}", payload["sensor_id"]):
        raise ValueError("invalid sensor")
    if type(payload["sequence"]) is not int or not 0 <= payload["sequence"] <= 2**53-1:
        raise ValueError("invalid sequence")
    q = payload["quality"]
    if type(q) not in (int, float) or not math.isfinite(q) or not 0 <= q <= 1:
        raise ValueError("invalid quality")
    if not isinstance(payload["sample_bytes"], str):
        raise ValueError("sample must be base64 text")
    data = base64.b64decode(payload["sample_bytes"], validate=True)
    if len(data) != 1024 or base64.b64encode(data).decode("ascii") != payload["sample_bytes"]:
        raise ValueError("sample must encode exactly 1024 bytes canonically")
    return event


def eligible(event):
    return event["payload"]["quality"] >= .80


def score_policy(score):
    if type(score) not in (int, float) or not math.isfinite(score):
        return "INDETERMINATE"
    return "ALLOW" if score > 0 else "REJECT"


def ev(event):
    p = 1 if eligible(event) else 0
    score = p - (1 - p)
    return {"score": score, "disposition": score_policy(score),
            "policy_version": "deterministic-eligibility-v1",
            "reason": "QUALITY_ELIGIBLE" if p else "QUALITY_BELOW_THRESHOLD"}


def process(event, iterations):
    if type(iterations) is not int or not 0 <= iterations <= 10000:
        raise ValueError("iterations must be integer 0..10000")
    value = hashlib.sha256(base64.b64decode(event["payload"]["sample_bytes"], validate=True)).digest()
    for _ in range(iterations):
        value = hashlib.sha256(value).digest()
    return {"event_id": event["event_id"], "digest": value.hex(), "processor_version": VERSION}
