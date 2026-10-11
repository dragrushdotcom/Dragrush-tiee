import os,time,redis
from .common import rd,pg,STREAM,GROUP,digest_work
from .v46_store import migrate,claim,commit_result
if __name__=='__main__':
    migrate();r=rd();name='v46-'+os.uname().nodename
    while True:
        try:
            got=r.xautoclaim(STREAM,GROUP,name,min_idle_time=3000,start_id='0-0',count=1);msgs=got[1]
            if not msgs:
                batch=r.xreadgroup(GROUP,name,{STREAM:'>'},count=1,block=100);msgs=[x for _,seq in batch for x in seq]
            for mid,fields in msgs:
                eid=fields['id'];owned=claim(eid)
                if owned:
                    event,generation=owned;start=time.process_time();digest=digest_work(event);cpu=time.process_time()-start
                    commit_result(eid,generation,digest,cpu)
                with pg() as c: row=c.execute('SELECT state FROM events WHERE id=%s',(eid,)).fetchone()
                if row is None or row[0] in ('DONE','REJECTED','EXPIRED','HELD'):
                    r.xack(STREAM,GROUP,mid);r.xdel(STREAM,mid)
        except redis.exceptions.ResponseError as exc:
            if 'NOGROUP' in str(exc):
                try: r.xgroup_create(STREAM,GROUP,id='0',mkstream=True)
                except redis.exceptions.ResponseError as e:
                    if 'BUSYGROUP' not in str(e): print('group retry',type(e).__name__,flush=True)
            else: print('redis retry',type(exc).__name__,flush=True)
            time.sleep(.1)
        except Exception as exc: print('worker retry',type(exc).__name__,flush=True);time.sleep(.1)
