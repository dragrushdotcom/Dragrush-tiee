import json,pathlib,time,traceback
from v47_tests import fresh,terminal,oracle
import v47_harness as h
R=pathlib.Path('results/v47/tests')
def reject_and_scorer(pool):
 fresh(pool);e=h.ev('reject',signal=-3);b=json.loads(e['body']);b['noise']=3;e['body']=json.dumps(b);assert h.send(e)[1]['decision']=='REJECT';terminal(e,'REJECTED')
 e=h.ev('uncertain-scorer',signal=-.8,deadline=1700);assert h.send(e)[1]['decision']=='DEFER';h.dc('exec','-T','relay','python','-c',"import pathlib;pathlib.Path('/srv/policies/v47/model.json').rename('/tmp/v47-model-kept.json')");h.sql("UPDATE events SET deferrals=3,next_at=now() WHERE id=%s",e['id']);terminal(e,'EXPIRED')
 h.dc('exec','-T','gateway','python','-c',"import pathlib;pathlib.Path('/srv/policies/v47/model.json').rename('/tmp/v47-model-kept.json')");assert h.send(h.ev('scorer-missing'))[0]==503
 return dict(reject_marker=True,scorer_failure_never_released=True)
def audit_marker_rollback(pool):
 fresh(pool);h.dc('stop','-t','1','relay','worker');e=h.ev('audit-rollback');h.send(e);generation=h.call('claim',id=e['id'])[1];digest=oracle(e)
 h.sql("CREATE FUNCTION block_done() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.action='DONE' THEN RAISE EXCEPTION 'injected audit fault'; END IF; RETURN NEW; END $$")
 h.sql('CREATE TRIGGER block_done BEFORE INSERT ON audit FOR EACH ROW EXECUTE FUNCTION block_done()')
 try:h.call('commit',id=e['id'],generation=generation,digest=digest);raise AssertionError('audit fault absent')
 except RuntimeError:pass
 assert h.sql('SELECT state,terminal_at IS NULL FROM events WHERE id=%s',e['id'])==[['RUNNING',True]];assert h.sql('SELECT count(*) FROM results WHERE id=%s',e['id'])==[[0]]
 h.sql('DROP TRIGGER block_done ON audit');assert h.call('commit',id=e['id'],generation=generation,digest=digest) is True;terminal(e);h.dc('start','relay','worker');return dict(result_state_marker_audit_atomic=True)
if __name__=='__main__':
 failures=0
 for pool in (0,8):
  for fn in (reject_and_scorer,audit_marker_rollback):
   start=time.monotonic()
   try:detail=fn(pool);status='PASSED'
   except Exception as e:detail=dict(error=str(e),traceback=traceback.format_exc());status='FAILED';failures+=1
   row=dict(test=fn.__name__,pool=pool,status=status,detail=detail,seconds=time.monotonic()-start)
   with (R/'integration.jsonl').open('a') as f:f.write(json.dumps(row)+chr(10))
   print(json.dumps(row),flush=True)
 if failures:raise RuntimeError(str(failures)+' supplementary checks failed')
