import datetime,json,pathlib,subprocess,time
import v47_harness as h
from v47_tests import receipt_crash
R=pathlib.Path('results/v47');F=R/'http_followup';assert json.loads((F/'burst_regression.json').read_text())['status']=='PASSED'
start=time.monotonic();detail=receipt_crash(8);(F/'receipt_crash.json').write_text(json.dumps(dict(test='patched_gateway_durable_receipt_crash',pool=8,status='PASSED',detail=detail,seconds=time.monotonic()-start),indent=2)+chr(10));print('PATCHED_GATEWAY_RECEIPT_CRASH_PASSED')
dbs=h.dc('exec','-T','postgres','psql','-U','tiee','-At','-c',"SELECT datname FROM pg_database WHERE datname LIKE 'v47_test_%'").stdout.splitlines();snapshots={}
query="SELECT COALESCE(json_agg(row_to_json(t)),'[]'::json) FROM (SELECT e.id,e.payload,e.receipt,e.decision,e.state,e.terminal_at,r.digest,(SELECT count(*) FROM audit a WHERE a.id=e.id AND a.action='DONE') AS done_audit_count FROM events e LEFT JOIN results r USING(id) WHERE e.id LIKE 'backlog-%') t"
for db in dbs:
 rows=json.loads(h.dc('exec','-T','postgres','psql','-U','tiee','-d',db,'-At','-c',query).stdout)
 if rows:snapshots[db]=rows
assert sum(len(rows)==96 for rows in snapshots.values())==2;assert all(x['done_audit_count']==1 for rows in snapshots.values() if len(rows)==96 for x in rows);(F/'database_snapshots.json').write_text(json.dumps(snapshots,indent=2)+chr(10));print('POST_FIX_RAW_LEDGER_SAVED')
settings=dict(h.sql("SELECT name,setting FROM pg_settings WHERE name IN ('fsync','full_page_writes','synchronous_commit')"));assert settings=={'fsync':'on','full_page_writes':'on','synchronous_commit':'on'}
ids=h.dc('ps','-q').stdout.split();inspect=json.loads(subprocess.check_output(['docker','inspect']+ids,text=True));safe=[dict(name=x['Name'],image=x['Image'],command=x['Config']['Cmd'],memory_limit=x['HostConfig']['Memory'],nano_cpus=x['HostConfig']['NanoCpus'],ports=x['NetworkSettings']['Ports']) for x in inspect];assert all(not x['ports'] for x in safe)
nets=subprocess.check_output(['docker','network','ls','--filter','label=com.docker.compose.project=tiee47pilot','-q'],text=True).split();network=json.loads(subprocess.check_output(['docker','network','inspect']+nets,text=True));assert all(x['Internal'] for x in network)
aof=h.dc('exec','-T','redis','redis-cli','CONFIG','GET','appendonly','appendfsync').stdout;assert 'yes' in aof and 'always' in aof
runtime=int(h.dc('exec','-T','gateway','python','-c','from app.v47_gateway import Server;print(Server.request_queue_size)').stdout);assert runtime==128
(R/'environment_final.json').write_text(json.dumps(dict(postgres=settings,redis_aof=aof,gateway_request_queue_size=runtime,services=safe,networks=[dict(name=x['Name'],internal=x['Internal']) for x in network],host_cores=int(subprocess.check_output(['nproc'],text=True)),utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+chr(10))
h.dc('stop','-t','1');assert not h.dc('ps','-q','--status','running').stdout.strip();(R/'shutdown.json').write_text(json.dumps(dict(project='tiee47pilot',status='STOPPED',volumes_retained=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+chr(10));print('PRIVATE_SERVICES_STOPPED_VOLUMES_RETAINED')
