import datetime,hashlib,json,pathlib,random,sys,time,traceback
from v47_data import trace
from v47_benchmark import run
R=pathlib.Path('results/v47');P=R/'plan.json'
def hashes():
 files=sorted(pathlib.Path('app').glob('*.py'))+[pathlib.Path(x) for x in ('Dockerfile','requirements.txt','docker-compose.yml','compose.validation.yml','compose.v47.yml','policies/v47/model.json','validation/v46_data.py','validation/v47_data.py','validation/v47_probe.py','validation/v47_harness.py','validation/v47_benchmark.py','validation/v47_round.py')]
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
def freeze():
 tests=[json.loads(x) for x in (R/'tests/integration.jsonl').read_text().splitlines()];assert len(tests)==18 and all(x['status']=='PASSED' for x in tests)
 rng=random.Random(470020);blocks=[(c,b) for c in ('normal','shift','burst') for b in range(3)];rng.shuffle(blocks);jobs=[]
 for c,b in blocks:
  arms=['A1','A3','A4'];rng.shuffle(arms)
  for arm in arms:
   j=dict(stage='pilot',condition=c,block=b,seed=470100+{'normal':0,'shift':100,'burst':200}[c]+b,arm=arm,n=240,rate=40 if c=='normal' else 80);j['trace_sha256']=hashlib.sha256(json.dumps(trace(j['seed'],j['n'],j['condition'],j['rate']),sort_keys=True).encode()).hexdigest();jobs.append(j)
 plan=dict(version='v47-acceptance-pilot-1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),jobs=jobs,source_sha256=hashes(),maximum_collection_seconds=1800,deadline_ms=12000,blocks_per_condition=3,performance_claim='NOT ESTABLISHED',acceptance='complete accounting, no unresolved/HELD, no HTTP/poll errors, complete terminal timing; A3 per-condition Wilson upper95 valid rejection and all-cause valid loss <=1%; exploratory synthetic IID screening only',changes_from_v46='conservative admission, complete terminal observation, lower offered rates, longer deadlines; no cross-round causal speed claim')
 raw=json.dumps(plan,indent=2)+chr(10);P.write_text(raw);(R/'plan.sha256').write_text(hashlib.sha256(raw.encode()).hexdigest()+chr(10));print('FROZEN',len(jobs))
def collect():
 p=json.loads(P.read_text());assert hashes()==p['source_sha256'];done={json.loads(s)['index'] for s in (R/'runs.jsonl').read_text().splitlines()} if (R/'runs.jsonl').exists() else set();started=time.monotonic()
 for i,j in enumerate(p['jobs']):
  if i in done:continue
  if time.monotonic()-started>p['maximum_collection_seconds']:raise RuntimeError('bounded collection budget exhausted')
  assert hashes()==p['source_sha256'];row=run(j,i)
  with (R/'runs.jsonl').open('a') as f:f.write(json.dumps(row)+chr(10))
  print(json.dumps(dict(index=i,arm=j['arm'],condition=j['condition'],drain=row['drain_pass'],http_errors=row['http_errors'],useful=row['useful_completions'])),flush=True)
 assert hashes()==p['source_sha256'];print('PILOT_COMPLETE',len(p['jobs']),flush=True)
if __name__=='__main__':
 try:freeze() if sys.argv[1]=='freeze' else collect()
 except Exception as e:
  (R/'round_failure.json').write_text(json.dumps(dict(status='FAILED_OR_INCOMPLETE',error=str(e),traceback=traceback.format_exc()),indent=2)+chr(10));raise
