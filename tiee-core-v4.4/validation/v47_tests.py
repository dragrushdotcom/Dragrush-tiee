import hashlib,json,os,pathlib,random,sys,time,traceback,uuid
import v47_harness as h
R=pathlib.Path('results/v47/tests');R.mkdir(parents=True,exist_ok=True)
def oracle(e):
 b=json.dumps(e,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
 for _ in range(e['rounds']):b=hashlib.sha256(b).digest()
 return b.hex()
def fresh(pool=8,system='Nominal',capacity=1000):
 db='v47_test_'+uuid.uuid4().hex[:10];h.dc('exec','-T','postgres','createdb','-U','tiee',db);h.configure('A3',pool=pool,system=system,capacity=capacity,database=db);return db
def terminal(e,state='DONE'):
 elapsed=h.wait(e,state,25);row=h.sql('SELECT state,terminal_at IS NOT NULL FROM events WHERE id=%s',e['id'])[0];assert row==[state,True];return elapsed
def receipt_crash(pool):
 fresh(pool);h.dc('stop','-t','1','relay','worker');e=h.ev('receipt');a=h.send(e);assert a[0]==202
 h.dc('kill','-s','SIGKILL','gateway','postgres');h.dc('start','postgres');h.ready();h.dc('start','gateway','relay','worker');h.ready();terminal(e);assert h.send(e)==[200,a[1]]
 changed=dict(e,rounds=e['rounds']+1);assert h.send(changed)[0]==409
 marker=h.sql('SELECT extract(epoch from terminal_at) FROM events WHERE id=%s',e['id']);h.call('replay',id=e['id']);time.sleep(.4);assert h.sql('SELECT extract(epoch from terminal_at) FROM events WHERE id=%s',e['id'])==marker;assert h.sql("SELECT count(*) FROM audit WHERE id=%s AND action='DONE'",e['id'])==[[1]]
 return dict(receipt_immutable=True,marker_immutable=True)
def bounded_defer(pool):
 fresh(pool);e=h.ev('defer',signal=-.8);a=h.send(e);assert a[0]==202 and a[1]['decision']=='DEFER';terminal(e);row=h.sql('SELECT deferrals,state FROM events WHERE id=%s',e['id'])[0];assert row[0]==4 and row[1]=='DONE';assert h.send(e)==[200,a[1]];return dict(deferrals=row[0],final=row[1])
def destructive_expiry(pool):
 fresh(pool,system='Destructive');e=h.ev('destructive',deadline=1800);assert h.send(e)[1]['decision']=='DEFER';terminal(e,'EXPIRED');assert h.sql("SELECT count(*) FROM events WHERE state='HELD'")==[[0]]
 # A retained legacy HELD row also reaches an explicit deadline outcome.
 e2=h.ev('legacy-held');h.send(e2);h.sql("UPDATE events SET state='HELD',deadline=now()-interval '1 second' WHERE id=%s",e2['id']);terminal(e2,'EXPIRED');return dict(no_held=True)
def rollback_fence(pool):
 fresh(pool);h.dc('stop','-t','1','relay','worker');e=h.ev('rollback');h.send(e);assert h.call('relay',fail=True)=='rolled_back';assert h.sql('SELECT state FROM events WHERE id=%s',e['id'])==[['PENDING']]
 h.call('relay');claim=h.call('claim',id=e['id']);gen=claim[1];digest=oracle(e)
 try:h.call('commit',id=e['id'],generation=gen,digest=digest,fail=True);raise AssertionError('rollback not raised')
 except RuntimeError:pass
 assert h.sql('SELECT terminal_at IS NULL FROM events WHERE id=%s',e['id'])==[[True]];assert h.sql('SELECT count(*) FROM results WHERE id=%s',e['id'])==[[0]]
 h.sql("UPDATE events SET lease_until=now()-interval '1 second' WHERE id=%s",e['id']);h.call('relay');nextgen=h.call('claim',id=e['id'])[1];assert nextgen>gen;assert h.call('commit',id=e['id'],generation=gen,digest=digest) is False;assert h.call('commit',id=e['id'],generation=nextgen,digest=digest) is True;terminal(e);h.dc('start','relay','worker');return dict(stale_fenced=True,atomic_marker=True)
def recovery(pool):
 fresh(pool);h.dc('stop','-t','1','relay','worker');e=h.ev('stream');h.send(e);h.call('relay');h.call('loss');h.dc('kill','-s','SIGKILL','redis');h.dc('start','redis');h.dc('start','relay','worker');terminal(e)
 durations={}
 for service in ('gateway','relay','worker','postgres'):
  e=h.ev('crash-'+service);h.send(e);t=time.monotonic();h.dc('kill','-s','SIGKILL',service);h.dc('start',service);h.ready();terminal(e);durations[service]=time.monotonic()-t
 return dict(recovery_seconds=durations,stream_loss_recovered=True)
def capacity_auth(pool):
 fresh(pool,capacity=1);h.dc('stop','-t','1','relay','worker');e=h.ev('capacity');a=h.send(e);assert a[0]==202;assert h.send(h.ev('capacity2'))[0]==503;assert h.send(e)==[200,a[1]]
 bad=h.ev('spoof');b=json.loads(bad['body']);b['p_valid']=1;bad['body']=json.dumps(b);assert h.send(bad)[0]==400;assert h.call('send',event=h.ev('auth'),key='wrong')[0]==403;h.dc('start','relay','worker');terminal(e);assert h.send(h.ev('retry'))[0]==202;return dict(safe_retry=True,spoof_blocked=True)
def recorder(pool):
 fresh(pool);a=dict(seed=470099,n=6,condition='normal',rate=120,prefix='late-recorder-'+uuid.uuid4().hex[:8],disable_poll=True,drain_limit_seconds=0)
 # Real HTTP submission with deliberately delayed client receipt processing; no polling.
 source="import json,time,v47_probe as p; original=p.send; p.send=lambda e,key=None:(lambda r:(time.sleep(6),r)[1])(original(e,key)); print(json.dumps(p.bench("+repr(a)+")))"
 raw=h.dc('exec','-T','probe','python','-c',"import sys;sys.path.insert(0,'/validation');"+source).stdout;row=json.loads(raw);assert row['wall_seconds']>6 and len(row['ledger'])==6;assert row['states']=={'DONE':6};assert all(x['terminal_observation_source']=='final committed SQL snapshot' and x['terminal_state_write_seconds'] is not None and x['offered_terminal_ms']>6000 for x in row['ledger']);(R/('recorder_pool'+str(pool)+'.json')).write_text(json.dumps(row,indent=2)+chr(10));return dict(real_http=6,missing_terminal_timing=0,ack_not_completion=True)
def main():
 failures=0
 for pool in (0,8):
  for fn in (receipt_crash,bounded_defer,destructive_expiry,rollback_fence,recovery,capacity_auth,recorder):
   start=time.monotonic()
   try:detail=fn(pool);status='PASSED'
   except Exception as e:detail=dict(error=str(e),traceback=traceback.format_exc());status='FAILED';failures+=1
   row=dict(test=fn.__name__,pool=pool,status=status,detail=detail,seconds=time.monotonic()-start)
   with (R/'integration.jsonl').open('a') as f:f.write(json.dumps(row)+chr(10))
   print(json.dumps(row),flush=True)
 if failures:raise RuntimeError(str(failures)+' v47 integration gates failed')
 print('V47_INTEGRATION_COMPLETE',flush=True)
if __name__=='__main__':main()
