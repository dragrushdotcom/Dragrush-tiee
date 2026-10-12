import json,os,pathlib,sys,time
import psycopg
root=pathlib.Path('/results/v48');stop=root/'observer.stop';ready=root/'observer.ready';samples=[]
with psycopg.connect(os.environ['PG_DSN'],autocommit=True,application_name='v48observer') as c:
 ready.write_text('READY');start=time.monotonic()
 while not stop.exists() and time.monotonic()-start<45:
  rows=c.execute("SELECT application_name,state,wait_event_type,wait_event,count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name!='v48observer' GROUP BY 1,2,3,4").fetchall();samples.append(dict(at=time.monotonic(),states=rows));time.sleep(.02)
(root/'baseline_wait_samples.json').write_text(json.dumps(dict(scope='20ms service wait sampling; diagnostic overhead, not performance comparison',samples=samples),indent=2)+chr(10))
print('WAIT_SAMPLES',len(samples))
