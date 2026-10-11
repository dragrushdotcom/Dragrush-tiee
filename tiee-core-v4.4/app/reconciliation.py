"""Deterministic advisory calculation for orphan replay (v4.4).

A Redis stream is not the source of truth: Postgres non-DONE events are.
Resend after a configurable interval because Redis may lose or trim entries.
At-least-once delivery is deliberate; result commits must be idempotent.
"""
from datetime import datetime, timezone

def should_relay(state, last_relay_at, now, interval_seconds=10):
    if interval_seconds <= 0:
        raise ValueError('relay interval must be positive')
    if state == 'PENDING':
        return True
    if state != 'ENQUEUED':
        return False
    if last_relay_at is None:
        return True
    return (now - last_relay_at).total_seconds() >= interval_seconds
