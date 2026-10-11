"""Additional real-service failure tests. Run only in isolated pilot project."""
import os,time,sys,uuid
import validate as v
from validate import dc,sql,call,ev,admission,wait_state

def ready():
    for _ in range(100):
        try:
            sql('SELECT 1'); return
        except Exception: time.sleep(.2)
    raise AssertionError('DB not ready')
def eventually(fn,timeout=20):
    t=time.monotonic()
    while time.monotonic()-t<timeout:
        if fn(): return
        time.sleep(.2)
    raise AssertionError('eventual assertion timed out')
def durable_202():
    dc('kill','-s','SIGKILL','relay'); e=ev('durable'); admission(e)
    assert sql('SELECT state FROM events WHERE id=%s',e['id'])==[['PENDING']]
    dc('kill','-s','SIGKILL','postgres'); t=time.monotonic(); dc('start','postgres'); ready()
    assert sql('SELECT state FROM events WHERE id=%s',e['id'])==[['PENDING']]
    dc('start','relay'); wait_state(e)
    return {'recovery_seconds':time.monotonic()-t,'acknowledged_row_survived_db_crash':True}
def backpressure():
    eventually(lambda: sql("SELECT count(*) FROM events WHERE disposition='ACCEPT' AND state!='DONE'")==[[0]])
    dc('kill','-s','SIGKILL','worker','relay')
    env=dict(os.environ,QUEUE_CAPACITY='32')
    dc('up','-d','--no-deps','--force-recreate','gateway',env=env); time.sleep(1)
    events=[dict(ev('capacity'),rounds=1) for _ in range(32)]
    for e in events: admission(e)
    retry=ev('safe-retry'); assert call('send',event=retry)[0]==503
    assert sql('SELECT count(*) FROM events WHERE id=%s',retry['id'])==[[0]]
    assert call('send',event=events[0])[0]==200
    dc('start','worker','relay')
    eventually(lambda: sql("SELECT count(*) FROM events WHERE disposition='ACCEPT' AND state!='DONE'")==[[0]],60)
    admission(retry); wait_state(retry)
    dc('up','-d','--no-deps','--force-recreate','gateway'); time.sleep(1)
    return {'capacity':32,'503_not_admitted':True,'same_id_retry_completed':True}
def publish_failure():
    dc('kill','-s','SIGKILL','redis'); e=ev('publish-fail'); admission(e); time.sleep(2)
    assert sql('SELECT state FROM events WHERE id=%s',e['id'])==[['PENDING']]
    t=time.monotonic(); dc('start','redis'); wait_state(e)
    return {'recovery_seconds':time.monotonic()-t,'failed_publish_remained_pending':True}
def install_fault(table,e,when):
    sql("CREATE OR REPLACE FUNCTION v45_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.id='"+e['id']+"' "+when+" THEN RAISE EXCEPTION 'v45 injected rollback'; END IF; RETURN NEW; END $$")
    sql('CREATE TRIGGER v45_fault BEFORE '+('UPDATE' if table=='events' else 'INSERT')+' ON '+table+' FOR EACH ROW EXECUTE FUNCTION v45_fault()')
def clear_fault(table):
    sql('DROP TRIGGER IF EXISTS v45_fault ON '+table)
    sql('DROP FUNCTION IF EXISTS v45_fault()')
def relay_rollback():
    dc('kill','-s','SIGKILL','relay','worker'); e=ev('relay-rollback'); admission(e)
    install_fault('events',e,"AND NEW.state='ENQUEUED'")
    dc('start','relay')
    try:
        eventually(lambda:e['id'] in dc('exec','-T','redis','redis-cli','XRANGE','tiee:events','-','+').stdout)
        assert sql('SELECT state FROM events WHERE id=%s',e['id'])==[['PENDING']]
    finally: clear_fault('events')
    dc('start','worker'); wait_state(e)
    assert sql('SELECT count(*) FROM results WHERE id=%s',e['id'])==[[1]]
    return {'xadd_observed_before_sql_rollback':True,'idempotent_recovery':True}
def result_rollback():
    dc('kill','-s','SIGKILL','worker'); e=ev('result-rollback'); admission(e); wait_state(e,'ENQUEUED')
    install_fault('results',e,'')
    dc('start','worker')
    try:
        eventually(lambda: 'v45 injected rollback' in dc('logs','--no-color','--tail','20','worker').stdout)
        assert sql('SELECT count(*) FROM results WHERE id=%s',e['id'])==[[0]]
        assert sql('SELECT state FROM events WHERE id=%s',e['id'])==[['ENQUEUED']]
    finally: clear_fault('results')
    t=time.monotonic(); wait_state(e)
    return {'recovery_seconds':time.monotonic()-t,'uncommitted_result_not_acknowledged':True}
def db_unavailable():
    dc('kill','-s','SIGKILL','postgres'); e=ev('db-down')
    assert call('send',event=e)[0]==500
    dc('start','postgres'); ready()
    assert sql('SELECT count(*) FROM events WHERE id=%s',e['id'])==[[0]]
    admission(e); wait_state(e)
    return {'no_false_202':True,'safe_retry':True}
def accounting():
    eventually(lambda:sql("SELECT count(*) FROM events WHERE disposition='ACCEPT' AND state!='DONE'")==[[0]],60)
    assert sql("SELECT count(*) FROM events e LEFT JOIN results r ON e.id=r.id WHERE (e.disposition='ACCEPT' AND (e.state!='DONE' OR r.id IS NULL)) OR (e.disposition='REJECT' AND r.id IS NOT NULL)")==[[0]]
    assert sql("SELECT count(*) FROM (SELECT id FROM audit WHERE action='DONE' GROUP BY id HAVING count(*)!=1) x")==[[0]]
    return {'events':sql('SELECT disposition,state,count(*) FROM events GROUP BY disposition,state'),'results':sql('SELECT count(*) FROM results'),'terminal_accounting':True}
if __name__=='__main__':
    tests=[('durable_202_pg_crash',durable_202),('backpressure_safe_retry',backpressure),('redis_publish_failure',publish_failure),('relay_transaction_rollback_after_xadd',relay_rollback),('result_transaction_rollback',result_rollback),('postgres_unavailable_no_false_ack',db_unavailable),('final_accounting_idempotent_audit',accounting)]
    passed=[]
    for name,fn in tests:
        passed.append(v.test(name,fn))
        dc('start','postgres','redis','gateway','relay','worker',check=False); ready()
    sys.exit(0 if all(passed) else 1)
