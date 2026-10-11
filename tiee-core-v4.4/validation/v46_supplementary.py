import hashlib,json,pathlib,time
import v46_harness as h
from v46_faults import isolated,stop,start,assert_done
OUT=pathlib.Path('results/v46/tests/supplementary.jsonl')
def deferred_crash(pool):
    db=isolated(pool,'deferred-durable');h.configure(pool=pool,system='Destructive',database=db);stop();e=h.ev('deferred-durable');r=h.send(e);assert r[0]==202 and r[1]['decision']=='DEFER'
    h.dc('kill','-s','SIGKILL','postgres','gateway');h.dc('up','-d','--no-deps','postgres');h.ready();h.dc('start','gateway');time.sleep(.3);assert h.send(e)==[200,r[1]]
    h.configure(pool=pool,system='Nominal',database=db);seconds=assert_done(e);assert h.send(e)==[200,r[1]];return dict(recovery_seconds=seconds,receipt_retained=True)
def aof_without_relay(pool):
    db=isolated(pool,'aof');stop();e=h.ev('aof');r=h.send(e);assert r[0]==202;h.call('relay');before=h.dc('exec','-T','redis','redis-cli','XRANGE','tiee:events','-','+').stdout;assert e['id'] in before
    settings=h.dc('exec','-T','redis','redis-cli','CONFIG','GET','appendonly','appendfsync').stdout.strip();t=time.monotonic();h.dc('kill','-s','SIGKILL','redis');h.dc('up','-d','--no-deps','redis')
    for _ in range(100):
        p=h.dc('exec','-T','redis','redis-cli','XRANGE','tiee:events','-','+',check=False)
        if e['id'] in p.stdout:break
        time.sleep(.1)
    assert e['id'] in p.stdout;assert h.sql('SELECT receipt FROM events WHERE id=%s',e['id'])==[[r[1]]];start();assert_done(e);return dict(settings=settings,recovery_seconds=time.monotonic()-t,reconciler_stopped_during_observation=True)
def mixed_data(pool):
    db=isolated(pool,'mixed');stop();e=dict(id=h.ev('legacy')['id'],kind='valid',rounds=2000,body='legacy-v45-body');fp=hashlib.sha256(json.dumps(e,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    h.sql("INSERT INTO events(id,fingerprint,payload,disposition,state) VALUES(%s,%s,%s,'ACCEPT','PENDING')",e['id'],fp,json.dumps(e));assert h.call('migrate')=='eight concurrent migrations committed';assert h.send(e)==[200,dict(status='ACCEPT',legacy=True)];start();assert_done(e)
    new=h.ev('mixed-new');assert h.send(new)[0]==202;assert_done(new);return dict(old_and_new_results_verified=True)
def competing_schedulers(pool):
    import concurrent.futures
    isolated(pool,'schedulers');stop();events=[h.ev('schedule') for _ in range(4)]
    for e in events:assert h.send(e)[0]==202
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:res=list(p.map(lambda _:h.call('relay'),range(2)))
    assert h.sql("SELECT count(*) FROM events WHERE state='ENQUEUED'")==[[2]];start()
    for e in events:assert_done(e)
    return dict(two_schedulers=True,authoritative_delivery_bound=2)
if __name__=='__main__':
    success=True
    for pool in (0,8):
        for name,fn in [('deferred_receipt_pg_gateway_crash',deferred_crash),('v46_AOF_without_reconciliation',aof_without_relay),('mixed_legacy_new_migration',mixed_data),('competing_schedulers',competing_schedulers)]:
            t=time.monotonic();r=dict(test=name,pool=pool,status='FAILED')
            try:r['detail']=fn(pool);r['status']='PASSED'
            except Exception as exc:r['error']=str(exc);success=False
            r['elapsed_seconds']=time.monotonic()-t
            with OUT.open('a') as f:f.write(json.dumps(r)+chr(10))
            print(json.dumps(r),flush=True)
    raise SystemExit(0 if success else 1)
