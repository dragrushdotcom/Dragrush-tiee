import datetime,hashlib,json,os,pathlib,random,sys,time,traceback
import v48_profile as p
from v47_round import hashes as base_hashes
from v47_benchmark import run
from v47_data import trace
h=p.h;h.COMPOSE+=['-f','compose.v48.yml'];R=pathlib.Path('results/v48');P=R/'plan.json'
def hashes():
 result=base_hashes()
 for n in ['compose.v48.yml','compose.v48.profile.yml','validation/v48_profile.py','validation/v48_observer.py','validation/v48_tests.py','validation/v48_round.py','validation/v48_analyze.py','V4_8_ENGINEERING_SPECIFICATION.md']:
  result[n]=hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest()
 return result

def freeze():
 tests=[json.loads(s) for s in (R/'tests/integration.jsonl').read_text().splitlines()];assert len(tests)==18 and all(x['status']=='PASSED' for x in tests)
 rng=random.Random(480020);jobs=[]
 for stage,seedbase in [('training',480200),('heldout',481200)]:
  blocks=[(c,b) for c in ('normal','shift','burst') for b in range(3)];rng.shuffle(blocks)
  for c,b in blocks:
   variants=['baseline','candidate'];rng.shuffle(variants)
   for variant in variants:
    j=dict(stage=stage,condition=c,block=b,seed=seedbase+{'normal':0,'shift':100,'burst':200}[c]+b,arm='A3',variant=variant,poll_seconds=.005 if variant=='baseline' else .020,n=240,rate=40 if c=='normal' else 80)
    j['trace_sha256']=hashlib.sha256(json.dumps(trace(j['seed'],j['n'],j['condition'],j['rate']),sort_keys=True).encode()).hexdigest();jobs.append(j)
 plan=dict(version='v48-polling-1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_commit='e064eec5a1c2202d28dca6971ab47e371edde940',jobs=jobs,source_sha256=hashes(),maximum_stage_seconds=1800,observer='OFF during matched performance runs; pg_stat_statements and track_io_timing identical in both variants',primary_endpoint='engine CPU seconds/useful DONE event; target >=5% mean reduction',guardrails='zero operational errors/missing timing/HELD; no additional paired valid loss; useful/s >=95% baseline; offered-terminal p95 <=110% baseline',intervals='20000 stratified paired bootstrap; three endpoint Bonferroni 98.333% intervals; exploratory',adoption='both stage mean targets and held-out CPU interval upper <0, throughput lower >=-5%, latency upper <=10%; otherwise retain 5ms default',superiority='Distinct TiEE advantage NOT ESTABLISHED; generic relay cadence experiment')
 raw=json.dumps(plan,indent=2)+chr(10);P.write_text(raw);(R/'plan.sha256').write_text(hashlib.sha256(raw.encode()).hexdigest()+chr(10));print('FROZEN',len(jobs),flush=True)

def collect():
 plan=json.loads(P.read_text());assert hashes()==plan['source_sha256'];assert not (R/'runs.jsonl').exists(),'do not silently overwrite/resume attempts';stage_started=time.monotonic();stage='training'
 for i,j in enumerate(plan['jobs']):
  if j['stage']!=stage:stage=j['stage'];stage_started=time.monotonic()
  assert time.monotonic()-stage_started<plan['maximum_stage_seconds'];assert hashes()==plan['source_sha256'];os.environ['RELAY_POLL_SECONDS']=str(j['poll_seconds']);r=run(j,i)
  with (R/'runs.jsonl').open('a') as f:f.write(json.dumps(r)+chr(10))
  q="SELECT COALESCE(json_agg(row_to_json(t)),'[]'::json) FROM (SELECT DISTINCT ON(id) id,decision FROM decision_history ORDER BY id,seq) t"
  data=json.loads(p.sql_db(r['database'],q));first={x['id']:x['decision'] for x in data};profiles={x['id']:first[x['id']] for x in r['ledger'] if x['id'] in first};assert all(x['id'] in profiles for x in r['ledger'] if x['state']!='REFUSED')
  stats=json.loads(p.sql_db(r['database'],p.Q))
  with (R/'profiles.jsonl').open('a') as f:f.write(json.dumps(dict(index=i,admissions=profiles,statements=stats,statement_scope='warmup plus measurement and immediate postmeasurement read; not pure measurement CPU'))+chr(10))
  print(json.dumps(dict(index=i,stage=stage,condition=j['condition'],variant=j['variant'],drain=r['drain_pass'],http_errors=r['http_errors'],useful=r['useful_completions'])),flush=True)
 assert hashes()==plan['source_sha256'];print('V48_COMPLETE',len(plan['jobs']),flush=True)
if __name__=='__main__':
 try:freeze() if sys.argv[1]=='freeze' else collect()
 except Exception as e:
  (R/'round_failure.json').write_text(json.dumps(dict(status='FAILED_OR_INCOMPLETE',error=str(e),traceback=traceback.format_exc()),indent=2)+chr(10));raise
