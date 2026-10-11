import os,time,redis
from .common import pg,rd,STREAM,GROUP,ensure_schema,digest_work

if __name__=='__main__':
    ensure_schema();r=rd()
    try:r.xgroup_create(STREAM,GROUP,id='0',mkstream=True)
    except redis.exceptions.ResponseError as e:
        if 'BUSYGROUP' not in str(e):raise
    name='w-'+os.uname().nodename
    while True:
        try:
            # Claim expired pending entries first; ensures surviving events after worker death.
            claimed=r.xautoclaim(STREAM,GROUP,name,min_idle_time=3000,start_id='0-0',count=20)
            msgs=claimed[1] if len(claimed)>1 else []
            if not msgs:
                batch=r.xreadgroup(GROUP,name,{STREAM:'>'},count=20,block=1000)
                msgs=[x for _,seq in batch for x in seq]
            for mid,fields in msgs:
                eid=fields['id']
                with pg() as c:
                    row=c.execute('SELECT payload,state FROM events WHERE id=%s',(eid,)).fetchone()
                    if row and row[1]!='DONE':
                        event=row[0]
                        digest=digest_work(event)
                        c.execute('INSERT INTO results(id,digest) VALUES(%s,%s) ON CONFLICT(id) DO NOTHING',(eid,digest))
                        c.execute("UPDATE events SET state='DONE' WHERE id=%s",(eid,))
                        c.execute('INSERT INTO audit(id,action) VALUES(%s,%s)',(eid,'DONE'))
                # ACK only after Postgres transaction commits.
                r.xack(STREAM,GROUP,mid);r.xdel(STREAM,mid)
        except Exception as exc:
            print('worker retry',repr(exc),flush=True);time.sleep(.5)
