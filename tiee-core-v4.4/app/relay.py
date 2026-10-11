import os,time
from .common import pg,rd,STREAM,ensure_schema
from .reconciliation import should_relay

if __name__=='__main__':
    ensure_schema()
    r=rd()
    interval=int(os.environ.get('RELAY_RETRY_SECONDS','10'))
    if interval < 1:raise ValueError('RELAY_RETRY_SECONDS must be positive')
    while True:
        try:
            with pg() as c:
                # Independent of Redis PEL: reconstruct lost messages from SQL truth.
                # Row locks prevent competing relay instances from selecting the same
                # work at the same instant. Duplicate publishes remain possible after
                # crashes and are safe because results commit idempotently.
                items=c.execute("""SELECT id,state,last_relay_at FROM events
                    WHERE disposition='ACCEPT' AND state IN ('PENDING','ENQUEUED')
                      AND (state='PENDING' OR last_relay_at IS NULL
                           OR last_relay_at <= now() - (%s * interval '1 second'))
                    ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED""",(interval,)).fetchall()
                for eid,state,last in items:
                    r.xadd(STREAM,{'id':eid})
                    c.execute("UPDATE events SET state='ENQUEUED',last_relay_at=now() WHERE id=%s AND state!='DONE'",(eid,))
            time.sleep(.05)
        except Exception as exc:
            print('relay retry',repr(exc),flush=True);time.sleep(1)
