import json,pathlib,sys,time,subprocess
import v47_harness as h
from v47_benchmark import run
R=pathlib.Path('results/v48');h.COMPOSE+=['-f','compose.v48.profile.yml']
def sql_db(db,q):return h.dc('exec','-T','postgres','psql','-U','tiee','-d',db,'-At','-c',q).stdout
base_configure=h.configure
def configure(*a,**kw):
 base_configure(*a,**kw)
 db=kw.get('database')
 if db:
  sql_db(db,'CREATE EXTENSION IF NOT EXISTS pg_stat_statements');sql_db(db,'SELECT pg_stat_statements_reset()')
h.configure=configure
Q="SELECT COALESCE(json_agg(row_to_json(t)),'[]'::json) FROM (SELECT queryid,query,calls,total_exec_time,mean_exec_time,rows,shared_blks_hit,shared_blks_read,shared_blks_dirtied,shared_blks_written,shared_blk_read_time,shared_blk_write_time,wal_records,wal_bytes FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) ORDER BY total_exec_time DESC) t"
if __name__=='__main__':
 h.dc('up','-d','--no-build','--scale','worker=2');h.ready()
 job=dict(stage='profile',condition='normal',block=0,seed=480100,arm='A3',n=240,rate=40)
 base_call=h.call
 def observed_call(op,**a):
  if op!='bench' or not a.get('prefix','').startswith('v47-'):return base_call(op,**a)
  for n in ('observer.stop','observer.ready'):
   f=R/n
   if f.exists():f.unlink()
  process=subprocess.Popen(h.COMPOSE+['exec','-T','probe','python','/validation/v48_observer.py'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  for _ in range(100):
   if (R/'observer.ready').exists():break
   time.sleep(.02)
  assert (R/'observer.ready').exists()
  try:return base_call(op,**a)
  finally:
   (R/'observer.stop').write_text('STOP');stdout,stderr=process.communicate(timeout=10);assert process.returncode==0,stderr;print(stdout.strip(),flush=True)
 h.call=observed_call
 row=run(job,0);(R/'baseline_profile_run.json').write_text(json.dumps(row)+chr(10))
 data=json.loads(sql_db(row['database'],Q));(R/'baseline_statements.json').write_text(json.dumps(dict(scope='24 warm-up events plus 240 measurement events; statement instrumentation enabled',statements=data),indent=2)+chr(10))
 for s in data[:10]:print(json.dumps({k:s[k] for k in ('query','calls','total_exec_time','mean_exec_time')}),flush=True)
 print('BASELINE_PROFILE_COMPLETE',flush=True)
