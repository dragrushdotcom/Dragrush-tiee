import hashlib
import json
import os
import time
import threading
_POOL = None
_POOL_LOCK = threading.Lock()

STREAM = 'tiee:events'
GROUP = 'workers'

def pg():
    import psycopg
    size=int(os.environ.get('PG_POOL_SIZE','0'))
    if size == 0:
        return psycopg.connect(os.environ['PG_DSN'])
    if not 1 <= size <= 16:
        raise ValueError('PG_POOL_SIZE must be 0..16')
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                from psycopg_pool import ConnectionPool
                _POOL=ConnectionPool(os.environ['PG_DSN'],min_size=1,max_size=size,timeout=2,kwargs={'connect_timeout':2},check=ConnectionPool.check_connection)
    return _POOL.connection()

def rd():
    import redis
    return redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)

def canonical(event):
    return json.dumps(event, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def fingerprint(event):
    return hashlib.sha256(canonical(event).encode()).hexdigest()

def ensure_schema():
    with pg() as c:
        # Serialize concurrent first-start DDL across services.
        c.execute('SELECT pg_advisory_xact_lock(73420)')
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
