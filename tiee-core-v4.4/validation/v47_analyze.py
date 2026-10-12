import collections,csv,gzip,hashlib,json,math,pathlib,random,statistics
from v47_round import hashes
R=pathlib.Path('results/v47')
def pct(values,p):
 v=sorted(x for x in values if x is not None);return v[min(len(v)-1,int((len(v)-1)*p))] if v else None
def upper95(k,n):
 if k==n:return 1.
 if k==0:return -math.expm1(math.log(.05)/n)
 lo,hi=k/n,1.
 for _ in range(70):
  p=(lo+hi)/2;cdf=sum(math.exp(math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)+i*math.log(p)+(n-i)*math.log1p(-p)) for i in range(k+1))
  if cdf>.05:lo=p
  else:hi=p
 return hi
def bootstrap(groups,alpha=.025):
 rng=random.Random(470070);values=[]
 for _ in range(20000):values.append(statistics.mean(statistics.mean(rng.choices(g,k=len(g))) for g in groups))
 return [pct(values,alpha/2),pct(values,1-alpha/2)]
def main():
 rows=[json.loads(x) for x in (R/'runs.jsonl').read_text().splitlines()];p=json.loads((R/'plan.json').read_text());assert len(rows)==len(p['jobs'])==27;assert sorted(x['index'] for x in rows)==list(range(27));assert hashes()==p['source_sha256'];pairs=collections.defaultdict(dict)
 for r in rows:
  j=p['jobs'][r['index']]
  assert all(r[k]==j[k] for k in j);assert r['workload_hash']==r['trace_sha256'];assert len(r['ledger'])==240 and len({x['id'] for x in r['ledger']})==240
  assert set(r['resources_before'])==set(r['resources_after']);deltas=[r['resources_after'][k]['cpu_seconds']-v['cpu_seconds'] for k,v in r['resources_before'].items()];assert min(deltas)>=0 and abs(sum(deltas)-r['service_cpu_seconds'])<1e-6
  pairs[r['condition'],r['block']][r['arm']]=r
 for v in pairs.values():
  assert set(v)=={'A1','A3','A4'};assert len({x['trace_sha256'] for x in v.values()})==1;assert len({tuple(x['id'] for x in r['ledger']) for r in v.values()})==1
 admissions=json.loads((R/'admission_profiles.json').read_text())['by_run']
 stats={};profiles={};conditions=('normal','shift','burst')
 for arm in ('A1','A3','A4'):
  rr=[x for x in rows if x['arm']==arm];ledger=[x for r in rr for x in r['ledger']];terminal=[x for x in ledger if x['state'] in ('DONE','EXPIRED','REJECTED')];cpu=sum(x['service_cpu_seconds'] for x in rr);service=collections.Counter()
  for r in rr:
   for cid,before in r['resources_before'].items():
    name=r['service_names'][cid];category='worker' if '-worker-' in name else name.split('-')[-2];service[category]+=r['resources_after'][cid]['cpu_seconds']-before['cpu_seconds']
  metric=dict(runs=len(rr),useful_throughput_mean=statistics.mean(r['useful_throughput'] for r in rr),net_utility_per_cpu_mean=statistics.mean(r['net_utility_per_cpu'] for r in rr),cpu_seconds_mean=cpu/len(rr),valid_count=sum(x['valid'] for x in ledger),valid_rejected=sum(x['valid'] and x['state']=='REJECTED' for x in ledger),valid_not_done=sum(x['valid'] and x['state']!='DONE' for x in ledger),http_errors=sum(r['http_errors'] for r in rr),poll_errors=sum(len(r['poll_errors']) for r in rr),drain_failures=sum(not r['drain_pass'] for r in rr),missing_terminal_timing=sum(x['terminal_observed_monotonic'] is None or x['terminal_state_write_seconds'] is None for x in terminal),held=sum(x['state']=='HELD' for x in ledger),offered_observed_ms={str(q):pct([x['offered_terminal_ms'] for x in terminal],q) for q in (.5,.95,.99)},dispatch_observed_ms={str(q):pct([x['dispatch_terminal_ms'] for x in terminal],q) for q in (.5,.95,.99)},ack_ms={str(q):pct([(x['receipt']['ack']-x['receipt']['dispatch'])*1000 for x in ledger],q) for q in (.5,.95,.99)},terminal_state_write_ms={str(q):pct([1000*x['terminal_state_write_seconds'] for x in terminal],q) for q in (.5,.95,.99)},ram_working_set_peak_bytes=max(sum(v['working_set_bytes'] for v in s['services'].values()) for r in rr for s in r['resource_samples']),queue_peak=max(r['sql_pending_peak'] for r in rr),table_growth_mean=statistics.mean(r['table_growth_bytes'] for r in rr),wal_growth_mean=statistics.mean(r['wal_growth_bytes'] for r in rr),aof_growth_mean=statistics.mean(r['aof_growth_bytes'] for r in rr),recorded_digest_cpu_fraction=sum(r['execution_cpu_seconds'] for r in rr)/cpu)
  metric['http_error_classes']=dict(collections.Counter(str(x['receipt']['response'][0])+':'+x['receipt']['response'][1].get('error','unspecified') for x in ledger if x['receipt']['response'][0] not in (200,202)))
  decisions=[d for r in rr for d in admissions[str(r['index'])].values()];metric['scoring_ms']={str(q):pct([1000*d['decision_seconds'] for d in decisions],q) for q in (.5,.95,.99)};metric['admission_lock_wait_ms']={str(q):pct([1000*d['admission_lock_wait_seconds'] for d in decisions],q) for q in (.5,.95,.99)};metric['admission_prewrite_ms']={str(q):pct([1000*d['admission_prewrite_seconds'] for d in decisions],q) for q in (.5,.95,.99)};stats[arm]=metric;profiles[arm]={k:dict(cpu_seconds=v,fraction=v/cpu) for k,v in service.items()}
 gates={};sensitivity={}
 for c in conditions:
  rr=[r for r in rows if r['condition']==c and r['arm']=='A3'];ll=[x for r in rr for x in r['ledger']];n=sum(x['valid'] for x in ll);reject=sum(x['valid'] and x['state']=='REJECTED' for x in ll);lost=sum(x['valid'] and x['state']!='DONE' for x in ll);ru=upper95(reject,n);lu=upper95(lost,n);gates[c]=dict(valid_count=n,valid_rejected=reject,valid_not_done=lost,rejection_rate=reject/n,loss_rate=lost/n,rejection_upper95=ru,loss_upper95=lu,iid_screen_pass=ru<=.01 and lu<=.01);sensitivity[c]=[dict(block=r['block'],valid_count=r['valid_count'],valid_not_done=sum(x['valid'] and x['state']!='DONE' for x in r['ledger'])) for r in rr]
 contrasts={}
 for control in ('A4','A1'):
  groups=[[pair['A3']['net_utility_per_cpu']-pair[control]['net_utility_per_cpu'] for (c,b),pair in pairs.items() if c==condition] for condition in conditions];differences=[x for g in groups for x in g];contrasts[control]=dict(paired_difference=statistics.mean(differences),ci_adjusted975=bootstrap(groups),ci95=bootstrap(groups,.05),pairs=len(differences),raw_points=differences)
 clean=all(x['http_errors']==0 and x['poll_errors']==0 and x['drain_failures']==0 and x['missing_terminal_timing']==0 and x['held']==0 for x in stats.values());result=dict(status='COMPLETE',planned_runs=27,events_accounted=6480,paired_blocks=9,source_freeze_verified=True,guardrails=gates,trace_sensitivity=sensitivity,operational_gates_pass=clean,iid_screen_pass=clean and all(x['iid_screen_pass'] for x in gates.values()),production_cluster_rate_certification='NOT ESTABLISHED: three trace blocks per condition',superiority_power='UNEXECUTED; this is a small acceptance pilot',performance_claim='NOT ESTABLISHED',contrasts=contrasts,metrics=stats,component_profiles=profiles,statistical_method='one-sided exact Clopper-Pearson 95% bounds under synthetic IID validity; independently stratified paired trace bootstrap, 20000 draws, Bonferroni 97.5% intervals for two contrasts; exploratory only')
 (R/'analysis.json').write_text(json.dumps(result,indent=2)+chr(10))
 keys=['index','condition','block','arm','net_total_utility','net_utility_per_cpu','service_cpu_seconds','wall_seconds','useful_throughput','valid_count','valid_rejected','http_errors','drain_pass','table_growth_bytes','wal_growth_bytes','aof_growth_bytes','sql_pending_peak']
 with (R/'runs.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,keys,lineterminator=chr(10));w.writeheader();w.writerows({k:r[k] for k in keys} for r in rows)
 keys=['condition','block','arm','id','valid','state','utility','execution_cpu','queue_seconds','db_latency_seconds','terminal_state_write_seconds','terminal_observed_monotonic','terminal_observation_source','offered_terminal_ms','dispatch_terminal_ms']
 with (R/'terminal_ledger.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,keys,lineterminator=chr(10));w.writeheader()
  for r in rows:
   for x in r['ledger']:w.writerow({k:r[k] if k in ('condition','block','arm') else x[k] for k in keys})
 keys=['condition','block','arm','at','container','cpu_seconds','memory_bytes','working_set_bytes']
 with (R/'resource_samples.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,keys,lineterminator=chr(10));w.writeheader()
  for r in rows:
   for s in r['resource_samples']:
    for cid,v in s['services'].items():w.writerow(dict(condition=r['condition'],block=r['block'],arm=r['arm'],at=s['at'],container=r['service_names'][cid],**v))
 with gzip.GzipFile(filename=str(R/'runs.jsonl.gz'),mode='wb',mtime=0) as f:f.write((R/'runs.jsonl').read_bytes())
 print(json.dumps(dict(status=result['status'],iid_screen_pass=result['iid_screen_pass'],guardrails=gates,metrics=stats,component_profiles=profiles,contrasts={k:{n:v for n,v in x.items() if n!='raw_points'} for k,x in contrasts.items()}),indent=2))
if __name__=='__main__':main()
