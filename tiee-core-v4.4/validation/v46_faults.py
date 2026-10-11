import concurrent.futures,hashlib,json,pathlib,time,traceback
import v46_harness as h
OUT=pathlib.Path('results/v46/tests');OUT.mkdir(parents=True,exist_ok=True)
def isolated(pool,tag):
    h.dc('up','-d','--no-deps','postgres','redis')
    database='v46_gate_'+tag+'_'+str(time.time_ns())[-10:];h.dc('exec','-T','postgres','createdb','-U','tiee',database);h.configure(pool=pool,database=database);return database
def stop():h.dc('stop','-t','1','relay','worker')
def start():h.dc('up','-d','--no-deps','--scale','worker=2','relay','worker')
def digest(e):
    x=json.dumps(e,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    for _ in range(e['rounds']):x=hashlib.sha256(x).digest()
    return x.hex()
def assert_done(e):
    seconds=h.wait(e);assert h.sql('SELECT digest FROM results WHERE id=%s',e['id'])==[[digest(e)]]
    assert h.sql("SELECT count(*) FROM audit WHERE id=%s AND action='DONE'",e['id'])==[[1]];return seconds
def durable():
    stop();e=h.ev('durable');r=h.send(e);assert r[0]==202
    h.dc('kill','-s','SIGKILL','gateway','postgres');h.dc('up','-d','--no-deps','postgres');h.ready();h.dc('up','-d','--no-deps','gateway');time.sleep(.3)
    assert h.send(e)==[200,r[1]];start();return dict(recovery_seconds=assert_done(e))
def retries():
    for signal in (2,-2):
        e=h.ev('retry',signal);r=h.send(e);assert r[0] in (200,202);assert h.send(e)==[200,r[1]]
        changed=dict(e,rounds=4000);assert h.send(changed)[0]==409
    # Mutate only the isolated container model; receipt identity must remain frozen.
    code="import json,pathlib;p=pathlib.Path('/srv/policies/v46/model.json');m=json.loads(p.read_text());m['coefficients']=[0,0,0,0];p.write_text(json.dumps(m))"
    h.dc('exec','-T','gateway','python','-c',code);assert h.send(e)==[200,r[1]];assert h.send(changed)[0]==409
    return dict(immutable_model_version=r[1]['model_version'])
def capacity():
    h.configure(pool=CURRENT_POOL,system='Destructive',capacity=2,database=CURRENT);stop();events=[h.ev('capacity') for _ in range(3)]
    receipts=[h.send(e) for e in events];assert [x[0] for x in receipts]==[202,202,503]
    assert all(x[1]['decision']=='DEFER' for x in receipts[:2]);assert h.sql('SELECT count(*) FROM events')==[[2]]
    assert h.send(events[0])==[200,receipts[0][1]]
    return dict(receipts=receipts,accepted_count=2)
def deferral():
    h.configure(pool=CURRENT_POOL,system='Destructive',database=CURRENT);stop();e=h.ev('defer');r=h.send(e);assert r[1]['decision']=='DEFER'
    h.call('loss');h.configure(pool=CURRENT_POOL,system='Nominal',database=CURRENT);assert_done(e);assert h.send(e)==[200,r[1]]
    h.configure(pool=CURRENT_POOL,system='Destructive',database=CURRENT);e=h.ev('held');assert h.send(e)[0]==202;h.wait(e,'HELD')
    assert h.sql('SELECT deferrals FROM events WHERE id=%s',e['id'])==[[3]]
    short=h.ev('expire',deadline=100);assert h.send(short)[0]==202;h.wait(short,'EXPIRED')
    return dict(held_retained=True,deadline_accounted=True)
def fencing():
    stop();e=h.ev('fence');assert h.send(e)[0]==202
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(lambda _:h.call('claim',id=e['id']),range(2)))
    owned=[x for x in claims if x is not None];assert len(owned)==1;g=owned[0][1]
    h.sql("UPDATE events SET lease_until=now()-interval '1 second' WHERE id=%s",e['id']);h.call('relay');second=h.call('claim',id=e['id']);assert second[1]>g
    assert h.call('commit',id=e['id'],generation=g,digest=digest(e)) is False
    assert h.call('commit',id=e['id'],generation=second[1],digest=digest(e)) is True
    assert_done(e);return dict(old_generation=g,new_generation=second[1])
def rollback():
    stop();e=h.ev('rollback');assert h.send(e)[0]==202;assert h.call('relay',fail=True)=='rolled_back'
    assert h.sql('SELECT state FROM events WHERE id=%s',e['id'])==[['PENDING']]
    owned=h.call('claim',id=e['id'])
    try:h.call('commit',id=e['id'],generation=owned[1],digest=digest(e),fail=True)
    except RuntimeError:pass
    else:raise AssertionError('expected result rollback')
    assert h.sql('SELECT count(*) FROM results WHERE id=%s',e['id'])==[[0]]
    assert h.sql("SELECT count(*) FROM audit WHERE id=%s AND action='DONE'",e['id'])==[[0]]
    assert h.call('commit',id=e['id'],generation=owned[1],digest=digest(e)) is True;start();return dict(rollback_obligation_retained=True)
def replay():
    e=h.ev('reject-replay',-2);assert h.send(e)[1]['decision']=='REJECT';h.call('replay',id=e['id']);time.sleep(.3)
    assert h.sql('SELECT count(*) FROM results WHERE id=%s',e['id'])==[[0]]
    done=h.ev('done-replay');assert h.send(done)[0]==202;assert_done(done)
    for _ in range(10):h.call('replay',id=done['id'])
    time.sleep(.3);assert_done(done);return dict(replays=11)
def scorer():
    e=h.ev('nan');b=json.loads(e['body']);b['signal']=float('nan');e['body']=json.dumps(b);assert h.send(e)[0]==400
    code="import pathlib;p=pathlib.Path('/srv/app/v46_policy.py');s=p.read_text();s=s.replace('def config():','def config():'+chr(10)+'    time.sleep(.1)');p.write_text(s)"
    h.dc('exec','-T','gateway','python','-c',code);h.dc('restart','gateway');time.sleep(.3)
    delayed=h.ev('slow-scorer');assert h.send(delayed)[0]==503;assert h.sql('SELECT count(*) FROM events WHERE id=%s',delayed['id'])==[[0]]
    code="import pathlib;p=pathlib.Path('/srv/app/v46_policy.py');s=p.read_text().replace('    time.sleep(.1)'+chr(10),'');p.write_text(s)"
    h.dc('exec','-T','gateway','python','-c',code);h.dc('restart','gateway');time.sleep(.3)
    e=h.ev('bad-model');h.dc('exec','-T','gateway','python','-c',"from pathlib import Path;Path('/srv/policies/v46/model.json').write_text('{}')");assert h.send(e)[0]==503
    assert h.sql('SELECT count(*) FROM events WHERE id=%s',e['id'])==[[0]];return dict(invalid_model_refused=True,nonfinite_refused=True)
def spoof():
    e=h.ev('spoof');b=json.loads(e['body']);b['priority']=999;b['p_valid']=1.;e['body']=json.dumps(b);assert h.send(e)[0]==400
    good=h.ev('auth');assert h.call('send',event=good,key='wrong-key')[0]==403
    assert h.sql('SELECT count(*) FROM events')==[[0]]
    return dict(spoof_refused=True,unauthorized_refused=True)
def fairness():
    stop();low=h.ev('aged',cls='bulk');assert h.send(low)[0]==202;time.sleep(.55)
    high=[h.ev('valuable',cls='critical') for _ in range(4)]
    for e in high:assert h.send(e)[0]==202
    h.call('relay');assert h.sql('SELECT state FROM events WHERE id=%s',low['id'])==[['ENQUEUED']]
    start();assert_done(low)
    for e in high:assert_done(e)
    return dict(aged_fifo_lane=True,admitted_count=5)
def audit_failure():
    h.sql("CREATE OR REPLACE FUNCTION fail_v46_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected audit failure'; END $$")
    h.sql("CREATE TRIGGER fail_v46 BEFORE INSERT ON decision_history FOR EACH ROW EXECUTE FUNCTION fail_v46_audit()")
    e=h.ev('audit-fail');assert h.send(e)[0]==503;assert h.sql('SELECT count(*) FROM events WHERE id=%s',e['id'])==[[0]]
    h.sql('DROP TRIGGER fail_v46 ON decision_history');assert h.call('migrate')=='eight concurrent migrations committed'
    return dict(no_false_receipt=True,concurrent_migrations=8)
def crashes():
    times={}
    for service in ('redis','gateway','relay','worker','postgres'):
        stop();e=h.ev('crash-'+service);r=h.send(e);assert r[0]==202;h.call('relay')
        if service=='worker':start();h.dc('kill','-s','SIGKILL','worker')
        else:h.dc('kill','-s','SIGKILL',service)
        t=time.monotonic();h.dc('up','-d','--no-deps',service);h.ready();start();assert_done(e);times[service]=time.monotonic()-t
        assert h.send(e)==[200,r[1]]
    stop();e=h.ev('stream-loss');assert h.send(e)[0]==202;h.call('relay');assert h.call('loss')==1;start();assert_done(e)
    return dict(recovery_seconds=times,stream_loss_recovered=True,aof=h.dc('exec','-T','redis','redis-cli','CONFIG','GET','appendonly').stdout.strip())
TESTS=[('durable_receipt_crash',durable),('immutable_retry_conflict',retries),('deferred_capacity',capacity),('deferred_restart_held_expiry',deferral),('overlapping_claim_fence',fencing),('relay_result_rollback',rollback),('terminal_replay_idempotence',replay),('corrupt_model_nonfinite',scorer),('spoof_authorization',spoof),('aging_fairness',fairness),('audit_failure_migration',audit_failure),('all_service_crashes_stream_loss',crashes)]
if __name__=='__main__':
    for pool in (0,8):
        for index,(name,fn) in enumerate(TESTS):
            start_time=time.monotonic();result=dict(test=name,pool=pool,command='python validation/v46_faults.py',status='FAILED')
            try:
                CURRENT_POOL=pool;CURRENT=isolated(pool,str(index));result['database']=CURRENT;result['detail']=fn();result['status']='PASSED'
            except Exception as exc:result['error']=str(exc);result['traceback']=traceback.format_exc()
            result['elapsed_seconds']=time.monotonic()-start_time
            with (OUT/'v46_faults.jsonl').open('a') as f:f.write(json.dumps(result)+chr(10))
            print(json.dumps(result),flush=True)
    print('FAULT MATRIX FINISHED',flush=True)
