import hashlib,json,math,pathlib,random,statistics,sys,time,threading
import v46_harness as h
from v46_data import trace
OUT=pathlib.Path('results/v46');ARMS=['A0','A1','A2','A3','A4']
def jobs(stage,reps):
    rng=random.Random(460010 if stage=='training' else 460020);conditions=('train_low','normal','train_high') if stage=='training' else ('fixed_admission',) if stage=='fixed_admission' else ('normal','shift','burst');blocks=[(c,b) for c in conditions for b in range(reps)];rng.shuffle(blocks);out=[]
    for condition,block in blocks:
        seed=(460100 if stage=='training' else 461000)+{'normal':0,'shift':100,'burst':200,'train_low':300,'train_high':400,'fixed_admission':500}[condition]+block
        arms=ARMS.copy();rng.shuffle(arms)
        for arm in arms:out.append(dict(stage=stage,condition=condition,block=block,seed=seed,arm=arm,n=240,rate=120 if condition=='normal' else 240))
    return out
def freeze():
    training=[json.loads(s) for s in (OUT/'training/runs.jsonl').read_text().splitlines()];pairs=[]
    for c in ('train_low','normal','train_high'):
        for b in range(3):
            p={x['arm']:x for x in training if x['condition']==c and x['block']==b};pairs.append(p['A3']['net_utility_per_cpu']-p['A1']['net_utility_per_cpu'])
    sd=statistics.stdev(pairs);scale=statistics.mean(abs(x['net_utility_per_cpu']) for x in training if x['arm']=='A1');delta=max(.1*scale,.01);required=math.ceil(((2.394+0.842)*sd/delta)**2);reps=max(10,min(20,required))
    plan=dict(version='v46-confirmation-1',created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),jobs=jobs('confirmation',reps),model_sha256=hashlib.sha256(pathlib.Path('policies/v46/model.json').read_bytes()).hexdigest(),primary='paired absolute difference in net utility per service CPU second, A3 minus A1',attribution='A3 minus A4',secondary='A3 minus A0',minimum_effect_absolute=delta,training_stdev=sd,training_power_required_blocks=required,blocks_per_condition=reps,power_budget_sufficient=required<=20,intervals='paired block bootstrap, 20000 resamples, Bonferroni 98.333% two-sided intervals for 3 contrasts; 95% descriptive intervals also',pooled='equal condition weights; independently resample paired blocks within condition',warmup_events=24,drain_limit_seconds=5,measurement_boundary='engine cgroup endpoints bracket storage snapshots, submission, drain, verification, and sampling; probe CPU includes oracle verification; host Docker CLI CPU is unmeasured',memory_polling='sequential cgroup reads, then 250ms wait; actual timestamps retained; peaks between samples unobserved',resource_cost_utility_per_cpu_second=.1,missed_valid_reward_fraction=.25,maximum_experiment_wall_seconds=7200,exclusions='none; integrity, HTTP, unresolved and HELD failures remain in denominator',false_rejection_gate='one-sided 95% trace-cluster bootstrap upper bound <=0.01',calibration_gate='paired trace Brier difference upper 95% bound <0',primary_relative_claim='absolute contrast requires >10% reference scale estimate and adjusted lower bound >5% reference scale; no total utility loss; all guardrails')
    for job in plan['jobs']:
        job['trace_sha256']=hashlib.sha256(json.dumps(trace(job['seed'],job['n'],job['condition'],job['rate']),sort_keys=True).encode()).hexdigest()
    plan['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(list(pathlib.Path('app').glob('*.py'))+[pathlib.Path('Dockerfile'),pathlib.Path('requirements.txt'),pathlib.Path('docker-compose.yml'),pathlib.Path('compose.validation.yml'),pathlib.Path('compose.v46.yml'),pathlib.Path('validation/v46_data.py'),pathlib.Path('validation/v46_probe.py'),pathlib.Path('validation/v46_harness.py')])}
    raw=json.dumps(plan,indent=2)+chr(10);(OUT/'confirmation/plan.json').write_text(raw);(OUT/'confirmation/plan.sha256').write_text(hashlib.sha256(raw.encode()).hexdigest()+chr(10));return plan['jobs']
def run(job,index):
    database='v46_'+job['stage'][:1]+'_'+str(time.time_ns())[-13:];h.dc('exec','-T','postgres','createdb','-U','tiee',database);h.configure(job['arm'],database=database)
    warm=h.call('bench',seed=460999,n=24,condition='normal',rate=120,prefix='warm-'+str(index));before=h.metrics();disk=h.storage()
    samples=[];stop=threading.Event()
    def sample():
        while not stop.is_set():
            samples.append(dict(at=time.monotonic(),services=h.metrics()));stop.wait(.25)
    thread=threading.Thread(target=sample);thread.start()
    try: row=h.call('bench',**{k:v for k,v in job.items() if k in ('seed','n','condition','rate')},prefix='v46-'+job['stage']+'-'+job['condition']+'-'+str(job['block']))
    finally: stop.set();thread.join()
    assert row['workload_hash']==hashlib.sha256(json.dumps(trace(job['seed'],job['n'],job['condition'],job['rate']),sort_keys=True).encode()).hexdigest()
    after=h.metrics();disk_after=h.storage();cpu=sum(after[k]['cpu_seconds']-before[k]['cpu_seconds'] for k in before);raw_utility=row['total_utility'];net=raw_utility-.1*cpu
    row.update(job,database=database,index=index,resources_before=before,resources_after=after,resource_samples=samples,storage_before=disk,storage_after=disk_after,service_cpu_seconds=cpu,net_total_utility=net,net_utility_per_cpu=net/cpu,utility_per_wall_second=net/row['wall_seconds'],useful_throughput=row['useful_completions']/row['wall_seconds'],table_growth_bytes=sum(disk_after['tables'].values())-sum(disk['tables'].values()),wal_growth_bytes=disk_after['wal_bytes']-disk['wal_bytes'],aof_growth_bytes=disk_after['aof_bytes']-disk['aof_bytes'],sql_pending_peak=max((sum(n for s,n in x['states'].items() if s in ('PENDING','ENQUEUED','RUNNING','DEFERRED','HELD')) for x in row['queue_samples']),default=0))
    return row
def main(stage):
    if stage in ('training','fixed_admission'):
        (OUT/stage).mkdir(exist_ok=True);plan=jobs(stage,3);(OUT/stage/'plan.json').write_text(json.dumps(plan,indent=2))
    elif stage=='freeze':print('FROZEN',len(freeze()));return
    else:plan=json.loads((OUT/'confirmation/plan.json').read_text())['jobs']
    dest=OUT/stage/'runs.jsonl';done={json.loads(s)['index'] for s in dest.read_text().splitlines()} if dest.exists() else set();start=time.monotonic()
    for index,job in enumerate(plan):
        if index in done:continue
        if time.monotonic()-start>7200:raise RuntimeError('bounded experiment budget exhausted')
        row=run(job,index)
        with dest.open('a') as f:f.write(json.dumps(row)+chr(10))
        print(json.dumps({k:row[k] for k in ('index','condition','arm','net_total_utility','net_utility_per_cpu','service_cpu_seconds','drain_pass','http_errors')}),flush=True)
    print('COMPLETED',stage,len(plan),flush=True)
if __name__=='__main__':main(sys.argv[1])
