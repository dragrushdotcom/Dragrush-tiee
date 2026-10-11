import collections,gzip,hashlib,json,pathlib
R=pathlib.Path('results/v46');p=json.loads((R/'confirmation/plan.json').read_text());rows=[json.loads(x) for x in (R/'confirmation/runs.jsonl').read_text().splitlines()]
assert len(rows)==len(p['jobs'])==300
assert sorted(x['index'] for x in rows)==list(range(300))
counts=collections.Counter();pairs=collections.defaultdict(list)
for r in rows:
 j=p['jobs'][r['index']]
 for k in ('condition','block','seed','arm','n','rate','trace_sha256'):assert r[k]==j[k],(r['index'],k)
 assert r['workload_hash']==r['trace_sha256']
 assert len(r['ledger'])==r['n']==240 and len({x['id'] for x in r['ledger']})==240
 before=r['resources_before'];after=r['resources_after'];assert set(before)==set(after)
 assert all(after[k]['cpu_seconds']>=before[k]['cpu_seconds'] for k in before)
 assert abs(sum(after[k]['cpu_seconds']-before[k]['cpu_seconds'] for k in before)-r['service_cpu_seconds'])<1e-6
 counts[r['condition'],r['arm']]+=1;pairs[r['condition'],r['block']].append(r)
for pair in pairs.values():
 assert {x['arm'] for x in pair}=={'A0','A1','A2','A3','A4'}
 assert len({x['trace_sha256'] for x in pair})==1
 assert len({tuple(y['id'] for y in x['ledger']) for x in pair})==1
assert len(pairs)==60 and set(counts.values())=={20}
archives={}
for stage,n in [('training',45),('fixed_admission',15),('confirmation',300)]:
 raw=(R/stage/'runs.jsonl').read_bytes();compressed=gzip.decompress((R/stage/'runs.jsonl.gz').read_bytes());assert raw==compressed;assert len(raw.splitlines())==n;archives[stage]=dict(runs=n,raw_sha256=hashlib.sha256(raw).hexdigest())
result=dict(status='PASSED',completed_measurements=360,confirmation_blocks=60,events_accounted=72000,paired_traces_and_ids=True,cpu_endpoints_verified=True,archives=archives,failed_recorder_attempts_separately_retained=1)
(R/'export_verification.json').write_text(json.dumps(result,indent=2)+chr(10));print('EXPORT_VERIFICATION_PASSED')
