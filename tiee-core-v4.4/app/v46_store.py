import json,os,time
from .common import pg,ensure_schema,rd,STREAM
from .v46_policy import rank_sql
ACTIVE="('DEFERRED','PENDING','ENQUEUED','RUNNING','HELD')"
def migrate():
    ensure_schema()
    with pg() as c:
        c.execute('SELECT pg_advisory_xact_lock(73420)')
        c.execute('ALTER TABLE events DROP CONSTRAINT IF EXISTS events_state_check')
        c.execute("ALTER TABLE events ADD CONSTRAINT events_state_check CHECK(state IN ('PENDING','ENQUEUED','DONE','REJECTED','DEFERRED','RUNNING','EXPIRED','HELD'))")
        c.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS receipt JSONB, ADD COLUMN IF NOT EXISTS decision JSONB, ADD COLUMN IF NOT EXISTS deadline TIMESTAMPTZ, ADD COLUMN IF NOT EXISTS next_at TIMESTAMPTZ, ADD COLUMN IF NOT EXISTS deferrals INT NOT NULL DEFAULT 0, ADD COLUMN IF NOT EXISTS generation BIGINT NOT NULL DEFAULT 0, ADD COLUMN IF NOT EXISTS lease_until TIMESTAMPTZ, ADD COLUMN IF NOT EXISTS priority DOUBLE PRECISION NOT NULL DEFAULT 0, ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ, ADD COLUMN IF NOT EXISTS execution_cpu DOUBLE PRECISION")
        c.execute("CREATE TABLE IF NOT EXISTS decision_history(seq BIGSERIAL PRIMARY KEY,id TEXT NOT NULL REFERENCES events(id),decision JSONB NOT NULL,at TIMESTAMPTZ NOT NULL DEFAULT now())")
        c.execute("CREATE INDEX IF NOT EXISTS events_v46_active ON events(state,next_at,deadline) WHERE state IN ('DEFERRED','PENDING','ENQUEUED','RUNNING','HELD')")
def audit(c,eid,action): c.execute('INSERT INTO audit(id,action) VALUES(%s,%s)',(eid,action))
def claim(eid):
    with pg() as c:
        row=c.execute('SELECT payload,state,generation,deadline FROM events WHERE id=%s FOR UPDATE',(eid,)).fetchone()
        if not row or row[1] not in ('PENDING','ENQUEUED'): return None
        if row[3] is not None and row[3].timestamp()<=time.time():
            c.execute("UPDATE events SET state='EXPIRED' WHERE id=%s",(eid,));audit(c,eid,'EXPIRED');return None
        generation=row[2]+1
        c.execute("UPDATE events SET state='RUNNING',generation=%s,claimed_at=now(),lease_until=now()+interval '3 seconds' WHERE id=%s",(generation,eid));audit(c,eid,'CLAIM')
        return row[0],generation
def commit_result(eid,generation,digest,cpu=0.,fail=False):
    with pg() as c:
        row=c.execute("SELECT state,generation,lease_until>now(),deadline>now() FROM events WHERE id=%s FOR UPDATE",(eid,)).fetchone()
        if not row or row[0]!='RUNNING' or row[1]!=generation or not row[2]: return False
        if row[3] is False:
            c.execute("UPDATE events SET state='EXPIRED',execution_cpu=%s WHERE id=%s",(cpu,eid));audit(c,eid,'EXPIRED');return False
        c.execute('INSERT INTO results(id,digest) VALUES(%s,%s) ON CONFLICT(id) DO NOTHING',(eid,digest))
        c.execute("UPDATE events SET state='DONE',execution_cpu=%s,lease_until=NULL WHERE id=%s",(cpu,eid));audit(c,eid,'DONE')
        if fail: raise RuntimeError('test result rollback')
        return True
def relay_once(fail_after_publish=False):
    r=rd();arm=os.environ.get('V46_ARM','A3')
    with pg() as c:
        # One authoritative order across schedulers; publication rollback stays recoverable.
        c.execute('SELECT pg_advisory_xact_lock(73422)')
        rows=c.execute("SELECT id FROM events WHERE state IN ('DEFERRED','PENDING','ENQUEUED','RUNNING') AND deadline<=now() FOR UPDATE SKIP LOCKED").fetchall()
        for (eid,) in rows:
            c.execute("UPDATE events SET state='EXPIRED',generation=generation+1 WHERE id=%s",(eid,));audit(c,eid,'EXPIRED')
        rows=c.execute("SELECT id FROM events WHERE state='RUNNING' AND lease_until<=now() FOR UPDATE SKIP LOCKED").fetchall()
        for (eid,) in rows:
            c.execute("UPDATE events SET state='PENDING',lease_until=NULL,generation=generation+1 WHERE id=%s",(eid,));audit(c,eid,'LEASE_EXPIRED')
        rows=c.execute("SELECT id,payload,deferrals FROM events WHERE state='DEFERRED' AND next_at<=now() FOR UPDATE SKIP LOCKED").fetchall()
        from .v46_policy import decide
        for eid,event,count in rows:
            if count>=3:
                c.execute("UPDATE events SET state='HELD' WHERE id=%s",(eid,));audit(c,eid,'HELD');continue
            try: d=decide(event)
            except Exception: d=dict(decision='DEFER',reason='conservative scorer failure')
            c.execute('INSERT INTO decision_history(id,decision) VALUES(%s,%s)',(eid,json.dumps(d)))
            state='PENDING' if d['decision']=='ALLOW' else 'DEFERRED'
            # A durable accepted obligation never becomes an unaudited admission reject.
            c.execute("UPDATE events SET state=%s,decision=%s,deferrals=deferrals+1,next_at=LEAST(deadline,now()+interval '0.25 seconds') WHERE id=%s",(state,json.dumps(d),eid))
        # At most one delivery pending per worker, so SQL ranking remains meaningful.
        inflight=c.execute("SELECT count(*) FROM events WHERE state IN ('ENQUEUED','RUNNING')").fetchone()[0]
        limit=max(0,int(os.environ.get('V46_WORKERS','2'))-inflight)
        rows=c.execute("SELECT id FROM events WHERE state='ENQUEUED' AND last_relay_at<now()-interval '2 seconds' FOR UPDATE SKIP LOCKED").fetchall()
        for (eid,) in rows: r.xadd(STREAM,{'id':eid});c.execute('UPDATE events SET last_relay_at=now() WHERE id=%s',(eid,))
        if limit:
            rows=c.execute("SELECT id FROM events WHERE state='PENDING' ORDER BY "+rank_sql(arm)+' LIMIT %s FOR UPDATE SKIP LOCKED',(limit,)).fetchall()
            for (eid,) in rows:
                r.xadd(STREAM,{'id':eid})
                if fail_after_publish: raise RuntimeError('test relay rollback after XADD')
                c.execute("UPDATE events SET state='ENQUEUED',last_relay_at=now() WHERE id=%s",(eid,))
