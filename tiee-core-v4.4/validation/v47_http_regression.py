import concurrent.futures,json,pathlib,sys,time,uuid
import v47_harness as h
from v47_tests import fresh,terminal
R=pathlib.Path('results/v47/http_followup');R.mkdir(exist_ok=True)
def main():
 # This regression runs only AFTER the original frozen 27-run pilot completes.
 phase=json.loads(pathlib.Path('results/v47/progress.json').read_text());assert phase['status']=='COLLECTION_COMPLETE'
 records=[]
 for pool in (0,8):
  fresh(pool);prefix='backlog-'+uuid.uuid4().hex[:8]
  source="import sys,json,concurrent.futures,time;sys.path.insert(0,'/validation');import v47_probe as p;events=[p.event('"+prefix+"-'+str(i)) for i in range(96)];start=time.monotonic();pool=concurrent.futures.ThreadPoolExecutor(max_workers=96);responses=list(pool.map(safe_send,events));pool.shutdown();print(json.dumps(dict(events=events,responses=responses,submission_seconds=time.monotonic()-start)))"
  source=source.replace('start=time.monotonic();',chr(10)+"def safe_send(e):"+chr(10)+" try:return p.send(e)"+chr(10)+" except Exception as ex:return [0,dict(error=type(ex).__name__)]"+chr(10)+"start=time.monotonic();")
  row=json.loads(h.dc('exec','-T','probe','python','-c',source).stdout);assert all(x[0] in (200,202) for x in row['responses']);
  ids=[x['id'] for x in row['events']];deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   completed=h.sql("SELECT count(*) FROM events WHERE id LIKE %s AND state='DONE'",prefix+'%')[0][0]
   if completed==96:break
   time.sleep(.1)
  assert completed==96
  from v47_tests import oracle
  results=h.sql('SELECT e.payload,r.digest FROM events e JOIN results r USING(id) WHERE e.id LIKE %s',prefix+'%');assert len(results)==96 and all(oracle(event)==digest for event,digest in results)
  duplicates=json.loads(h.dc('exec','-T','probe','python','-c',"import sys,json,concurrent.futures;sys.path.insert(0,'/validation');import v47_probe as p;events="+repr(row['events'])+";pool=concurrent.futures.ThreadPoolExecutor(max_workers=96);print(json.dumps(list(pool.map(p.send,events))));pool.shutdown()").stdout)
  assert all(x[0]==200 and x[1]==r[1] for x,r in zip(duplicates,row['responses']));assert h.sql("SELECT count(*) FROM audit WHERE id LIKE %s AND action='DONE'",prefix+'%')==[[96]]
  record=dict(pool=pool,status='PASSED',offered=96,completed=96,duplicate_receipts=96,submission_seconds=row['submission_seconds']);records.append(record);print(json.dumps(record),flush=True)
 (R/'burst_regression.json').write_text(json.dumps(dict(status='PASSED',request_queue_size=128,records=records),indent=2)+chr(10))
if __name__=='__main__':main()
