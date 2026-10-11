import hashlib
import json
import os
import time

STREAM = 'tiee:events'
GROUP = 'workers'

def pg():
    import psycopg
    return psycopg.connect(os.environ['PG_DSN'])

def rd():
    import redis
    return redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)

def canonical(event):
    return json.dumps(event, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def fingerprint(event):
    return hashlib.sha256(canonical(event).encode()).hexdigest()

def ensure_schema():
    with pg() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload JSONB NOT NULL,
          disposition TEXT NOT NULL CHECK (disposition IN ('ACCEPT','REJECT')),
          state TEXT NOT NULL CHECK (state IN ('PENDING','ENQUEUED','DONE','REJECTED')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          last_relay_at TIMESTAMPTZ)''')
        c.execute('ALTER TABLE events ADD COLUMN IF NOT EXISTS last_relay_at TIMESTAMPTZ')
        c.execute('''CREATE TABLE IF NOT EXISTS results (
          id TEXT PRIMARY KEY REFERENCES events(id), digest TEXT NOT NULL,
          completed_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
        c.execute('''CREATE TABLE IF NOT EXISTS audit (
          seq BIGSERIAL PRIMARY KEY, id TEXT NOT NULL, action TEXT NOT NULL,
          at TIMESTAMPTZ NOT NULL DEFAULT now())''')

def eligible(event, policy):
    # Deliberately simple and identical noise recognition in both policies.
    if event['kind'] == 'bot':
        return False
    if policy == 'tiee':
        # Neutral EV policy in this infrastructure-isolation experiment:
        # no client-provided trust scores and no discretionary work loss.
        return True
    return True

def digest_work(event):
    h = canonical(event).encode()
    rounds = int(event['rounds'])
    for _ in range(rounds):
        h = hashlib.sha256(h).digest()
    return h.hex()
