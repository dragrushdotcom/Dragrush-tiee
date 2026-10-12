import collections,csv,gzip,hashlib,json,math,pathlib,random,statistics
from v48_round import hashes
R=pathlib.Path('results/v48');conditions=['normal','shift','burst'];variants=['baseline','candidate']
def pct(xs,q):
 xs=sorted(xs);assert xs;return xs[min(len(xs)-1,max(0,math.ceil(len(xs)*q)-1))]
def bootstrap(groups):
 rng=random.Random(480777);draws=[]
 for _ in range(20000):draws.append(statistics.mean(rng.choice(g) for g in groups for _ in g))
 return [pct(draws,.05/6),pct(draws,1-.05/6)]
def main():
 p=json.loads((R/'plan.json').read_text());assert hashes()==p['source_sha256'];rows=[json.loads(s) for s in (R/'runs.jsonl').read_text().splitlines()];assert len(rows)==36;assert {r['index'] for r in rows}==set(range(36));profiles={r['index']:r for r in map(json.loads,(R/'profiles.jsonl').read_text().splitlines())};assert len(profiles)==36
 for r in rows:
  assert all(r[k]==v for k,v in p['jobs'][r['index']].items());assert len(r['ledger'])==240
  cpu=sum(r['resources_after'][cid]['cpu_seconds']-v['cpu_seconds'] for cid,v in r['resources_before'].items());assert math.isclose(cpu,r['service_cpu_seconds'],rel_tol=1e-10);assert all(r['resources_after'][cid]['cpu_seconds']>=v['cpu_seconds'] for cid,v in r['resources_before'].items())
  r['cpu_per_useful']=r['service_cpu_seconds']/r['useful_completions'];r['offered_p95_ms']=pct([x['offered_terminal_ms'] for x in r['ledger'] if x['offered_terminal_ms'] is not None],.95)
 stages={};pairs_raw=[]
 for stage in ('training','heldout'):
  rr=[r for r in rows if r['stage']==stage];pairs=collections.defaultdict(dict)
  for r in rr:pairs[(r['condition'],r['block'])][r['variant']]=r
  assert len(pairs)==9 and all(set(pair)==set(variants) for pair in pairs.values());additional=[];points={k:collections.defaultdict(list) for k in ('cpu_per_useful','useful_throughput','offered_p95_ms')}
  for (condition,block),pair in pairs.items():
   b,c=pair['baseline'],pair['candidate'];assert b['trace_sha256']==c['trace_sha256'];assert [x['event'] for x in b['ledger']]==[x['event'] for x in c['ledger']];assert [x['valid'] for x in b['ledger']]==[x['valid'] for x in c['ledger']]
   lost=lambda r:{x['id'] for x in r['ledger'] if x['valid'] and x['state']!='DONE'}
   extra=sorted(lost(c)-lost(b));additional+=extra;item=dict(stage=stage,condition=condition,block=block,additional_valid_loss_ids=extra)
   for k in points:
    value=c[k]/b[k]-1;points[k][condition].append(value);item[k+'_relative_change']=value
   pairs_raw.append(item)
  endpoints={k:dict(mean_relative_change=statistics.mean(v for group in groups.values() for v in group),bonferroni98333_interval=bootstrap([groups[c] for c in conditions])) for k,groups in points.items()}
  metrics={}
  for variant in variants:
   selected=[r for r in rr if r['variant']==variant];ll=[x for r in selected for x in r['ledger']];terminal=[x for x in ll if x['state'] in ('DONE','REJECTED','EXPIRED')];cpu=sum(r['service_cpu_seconds'] for r in selected);components=collections.Counter()
   for r in selected:
    for cid,before in r['resources_before'].items():
     name=r['service_names'][cid].rsplit('-',2)[1];components[name]+=r['resources_after'][cid]['cpu_seconds']-before['cpu_seconds']
   decisions=[d for r in selected for d in profiles[r['index']]['admissions'].values()]
   metrics[variant]=dict(runs=9,offered=len(ll),useful=sum(r['useful_completions'] for r in selected),useful_throughput_mean=statistics.mean(r['useful_throughput'] for r in selected),cpu_seconds_mean=cpu/9,cpu_per_useful_mean=statistics.mean(r['cpu_per_useful'] for r in selected),http_errors=sum(r['http_errors'] for r in selected),poll_errors=sum(len(r['poll_errors']) for r in selected),drain_failures=sum(not r['drain_pass'] for r in selected),held=sum(x['state']=='HELD' for x in ll),missing_terminal_timing=sum(x['terminal_observed_monotonic'] is None or x['terminal_state_write_seconds'] is None for x in terminal),valid_count=sum(x['valid'] for x in ll),valid_not_done=sum(x['valid'] and x['state']!='DONE' for x in ll),valid_rejected=sum(x['valid'] and x['state']=='REJECTED' for x in ll),offered_ms={str(q):pct([x['offered_terminal_ms'] for x in terminal],q) for q in (.5,.95,.99)},ack_ms={str(q):pct([(x['receipt']['ack']-x['receipt']['dispatch'])*1000 for x in ll],q) for q in (.5,.95,.99)},ram_peak_bytes=max(sum(v['working_set_bytes'] for v in s['services'].values()) for r in selected for s in r['resource_samples']),queue_peak=max(r['sql_pending_peak'] for r in selected),storage_mean={k:statistics.mean(r[k] for r in selected) for k in ('table_growth_bytes','wal_growth_bytes','aof_growth_bytes')},components={k:dict(cpu_seconds=v,fraction=v/cpu) for k,v in components.items()},admission_lock_p95_ms=pct([d['admission_lock_wait_seconds']*1000 for d in decisions],.95),prewrite_p95_ms=pct([d['admission_prewrite_seconds']*1000 for d in decisions],.95),scoring_p95_ms=pct([d['decision_seconds']*1000 for d in decisions],.95))
  clean=all(all(m[k]==0 for k in ('http_errors','poll_errors','drain_failures','held','missing_terminal_timing')) for m in metrics.values())
  means_pass=endpoints['cpu_per_useful']['mean_relative_change']<=-.05 and endpoints['useful_throughput']['mean_relative_change']>=-.05 and endpoints['offered_p95_ms']['mean_relative_change']<=.10
  stages[stage]=dict(metrics=metrics,endpoints=endpoints,operational_pass=clean,additional_valid_loss_ids=additional,no_additional_valid_loss=not additional,mean_targets_pass=means_pass)
 e=stages['heldout']['endpoints'];interval_pass=e['cpu_per_useful']['bonferroni98333_interval'][1]<0 and e['useful_throughput']['bonferroni98333_interval'][0]>=-.05 and e['offered_p95_ms']['bonferroni98333_interval'][1]<=.10
 adopt=interval_pass and all(x['operational_pass'] and x['no_additional_valid_loss'] and x['mean_targets_pass'] for x in stages.values())
 result=dict(status='COMPLETE',runs=36,offered_accounted=8640,stages=stages,paired_trace_results=pairs_raw,heldout_interval_guardrails_pass=interval_pass,adoption_gate_pass=adopt,default_poll_seconds=.005,recommendation='candidate merits larger confirmation; default remains 5ms pending engineering review' if adopt else 'retain default 5ms; candidate failed frozen adoption gate',performance_claim='Distinct TiEE superiority NOT ESTABLISHED; generic cadence experiment',statistics='20000 stratified paired bootstrap, 98.333% Bonferroni intervals for three endpoints, nine pairs per stage; exploratory')
 (R/'analysis.json').write_text(json.dumps(result,indent=2)+chr(10))
 with gzip.GzipFile(filename=str(R/'runs.jsonl.gz'),mode='wb',mtime=0) as f:f.write((R/'runs.jsonl').read_bytes())
 keys=['index','stage','condition','block','variant','seed','poll_seconds','useful_completions','service_cpu_seconds','cpu_per_useful','useful_throughput','offered_p95_ms','http_errors','drain_pass','table_growth_bytes','wal_growth_bytes','aof_growth_bytes','sql_pending_peak']
 with (R/'runs.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,keys,lineterminator=chr(10));w.writeheader();w.writerows({k:r[k] for k in keys} for r in rows)
 keys=['stage','condition','block','variant','id','valid','state','utility','execution_cpu','queue_seconds','db_latency_seconds','terminal_state_write_seconds','terminal_observed_monotonic','terminal_observation_source','offered_terminal_ms','dispatch_terminal_ms']
 with (R/'terminal_ledger.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,keys,lineterminator=chr(10));w.writeheader()
  for r in rows:
   for x in r['ledger']:w.writerow({k:r[k] if k in ('stage','condition','block','variant') else x[k] for k in keys})
 keys=['stage','condition','block','variant','at','container','cpu_seconds','memory_bytes','working_set_bytes']
 with (R/'resource_samples.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,keys,lineterminator=chr(10));w.writeheader()
  for r in rows:
   for s in r['resource_samples']:
    for cid,v in s['services'].items():w.writerow(dict(stage=r['stage'],condition=r['condition'],block=r['block'],variant=r['variant'],at=s['at'],container=r['service_names'][cid],**v))
 print('V48_ANALYSIS_COMPLETE',adopt,{s:x['endpoints'] for s,x in stages.items()},flush=True)
if __name__=='__main__':main()
