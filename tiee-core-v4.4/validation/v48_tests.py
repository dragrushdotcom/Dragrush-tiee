import json,os,pathlib,subprocess,time,traceback
import v48_profile as p
import v47_tests as core
import v47_supplementary as extra
h=p.h;h.COMPOSE+=['-f','compose.v48.yml'];os.environ['RELAY_POLL_SECONDS']='0.020'
R=pathlib.Path('results/v48/tests');R.mkdir(parents=True,exist_ok=True);core.R=R;extra.R=R
if __name__=='__main__':
 failed=0
 for pool in (0,8):
  for fn in (core.receipt_crash,core.bounded_defer,core.destructive_expiry,core.rollback_fence,core.recovery,core.capacity_auth,core.recorder,extra.reject_and_scorer,extra.audit_marker_rollback):
   start=time.monotonic()
   try:detail=fn(pool);status='PASSED'
   except Exception as e:detail=dict(error=str(e),traceback=traceback.format_exc());status='FAILED';failed+=1
   row=dict(test=fn.__name__,pool=pool,status=status,detail=detail,seconds=time.monotonic()-start,poll_seconds=.020)
   with (R/'integration.jsonl').open('a') as f:f.write(json.dumps(row)+chr(10))
   print(json.dumps(dict(test=fn.__name__,pool=pool,status=status,seconds=row['seconds'])),flush=True)
 if failed:raise RuntimeError(str(failed)+' v48 candidate integration checks failed')
 print('V48_CANDIDATE_INTEGRATION_COMPLETE',flush=True)
