"""Deterministic regression gates for startup and worker group loss."""
import time,uuid,sys
import validate as v
from validate import dc,sql,call,ev,admission,wait_state

def cold_schema_race():
    database='schema_'+uuid.uuid4().hex[:12]
    dc('exec','-T','postgres','createdb','-U','tiee',database)
    return call('schema_race',database=database)
def deterministic_stream_loss():
    dc('kill','-s','SIGKILL','relay')
    assert 'workers' in dc('exec','-T','redis','redis-cli','XINFO','GROUPS','tiee:events').stdout
    dc('pause','worker'); e=ev('deterministic-loss'); admission(e)
    try:
        assert call('redis_loss')['deleted']==1
    finally: dc('unpause','worker')
    t=time.monotonic(); dc('start','relay'); wait_state(e)
    return {'recovery_seconds':time.monotonic()-t,'worker_not_restarted':True,'initialized_group_deleted':True}
def rejected_duplicate_conflict():
    e=dict(ev('rejected-conflict'),kind='bot');assert call('send',event=e)==[202,{'status':'REJECT'}]
    assert call('send',event=e)==[200,{'status':'REJECT','duplicate':True}]
    assert call('send',event=dict(e,body='conflicting-body'))[0]==409
    call('redis_replay',id=e['id'],count=1);time.sleep(1)
    assert sql('SELECT count(*) FROM results WHERE id=%s',e['id'])==[[0]]
    assert sql('SELECT state FROM events WHERE id=%s',e['id'])==[['REJECTED']]
    return {'rejected_identity_is_protected':True,'broker_replay_cannot_execute_rejected_event':True}
def concurrent_idempotence():
    dc('kill','-s','SIGKILL','worker');e=ev('concurrent-duplicate');admission(e);wait_state(e,'ENQUEUED')
    dc('kill','-s','SIGKILL','relay');call('redis_replay',id=e['id'],count=40)
    sql("CREATE FUNCTION v45_slow_result() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.id='"+e['id']+"' THEN PERFORM pg_sleep(1); END IF; RETURN NEW; END $$")
    sql('CREATE TRIGGER v45_slow_result BEFORE INSERT ON results FOR EACH ROW EXECUTE FUNCTION v45_slow_result()')
    try:
        dc('up','-d','--no-deps','--scale','worker=2','worker');wait_state(e);time.sleep(2)
        assert sql('SELECT count(*) FROM results WHERE id=%s',e['id'])==[[1]]
        assert sql("SELECT count(*) FROM audit WHERE id=%s AND action='DONE'",e['id'])==[[1]]
    finally:
        sql('DROP TRIGGER v45_slow_result ON results');sql('DROP FUNCTION v45_slow_result()')
        dc('up','-d','--no-deps','--scale','worker=1','worker');dc('start','relay')
    return {'worker_processes':2,'duplicate_publications':40,'result_rows':1,'done_audits':1}
def deterministic_aof_restart():
    dc('kill','-s','SIGKILL','worker');e=ev('aof-proof');admission(e);wait_state(e,'ENQUEUED')
    dc('kill','-s','SIGKILL','relay')
    assert e['id'] in dc('exec','-T','redis','redis-cli','XRANGE','tiee:events','-','+').stdout
    config=dc('exec','-T','redis','redis-cli','CONFIG','GET','appendonly','appendfsync').stdout
    assert 'yes' in config and 'always' in config
    dc('kill','-s','SIGKILL','redis');t=time.monotonic();dc('start','redis')
    for _ in range(100):
        if 'PONG' in dc('exec','-T','redis','redis-cli','PING',check=False).stdout:break
        time.sleep(.1)
    # Relay remains stopped: SQL reconciliation cannot create the observed entry.
    assert e['id'] in dc('exec','-T','redis','redis-cli','XRANGE','tiee:events','-','+').stdout
    assert 'workers' in dc('exec','-T','redis','redis-cli','XINFO','GROUPS','tiee:events').stdout
    dc('start','worker');wait_state(e);dc('start','relay')
    return {'recovery_seconds':time.monotonic()-t,'entry_and_group_persisted_without_relay':True,'redis_config':config.splitlines()}
if __name__=='__main__':
    passed=[v.test('deterministic_AOF_without_reconciliation',deterministic_aof_restart),v.test('rejected_duplicate_conflict',rejected_duplicate_conflict),v.test('concurrent_idempotent_commits',concurrent_idempotence),v.test('cold_schema_concurrency',cold_schema_race),v.test('deterministic_stream_group_loss',deterministic_stream_loss)]
    sys.exit(0 if all(passed) else 1)
