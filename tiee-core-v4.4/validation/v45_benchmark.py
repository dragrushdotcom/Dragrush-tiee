"""Prespecified randomized paired benchmark; matched ordinary filtering vs TiEE label."""
import os,json,pathlib,random,time,threading,uuid
import validate as v
def client_call(op,**args):
    p=v.dc('exec','-T','probe','python','/validation/validate.py','--inside',op,json.dumps(args))
    return json.loads(p.stdout)
v.call=client_call
OUT=v.OUT
SERVICES=['gateway','relay','worker','redis','postgres']
def storage():
    db=v.sql("SELECT pg_database_size(current_database()),pg_wal_lsn_diff(pg_current_wal_lsn(),'0/0')::bigint")[0]
    tables=v.sql("SELECT relname,pg_total_relation_size(oid) FROM pg_class WHERE relname IN ('events','results','audit') ORDER BY relname")
    aof=v.dc('exec','-T','redis','sh','-c','du -sk /data/appendonlydir').stdout.split()[0]
    return {'database_bytes':db[0],'wal_position_bytes':db[1],'table_bytes':dict(tables),'redis_aof_disk_bytes':int(aof)*1024}
def wait_ready():
    for _ in range(100):
        try:v.sql('SELECT 1'); return
        except Exception: time.sleep(.1)
    raise RuntimeError('gateway/schema not ready')
def make_plan():
    rng=random.Random(451011)
    stages=[('training',[(0,400,2000),(.5,400,2000),(.9,400,2000)],101),('held_out',[(.25,600,8000),(.75,450,4000)],7001)]
    jobs=[]
    for stage,specs,seedbase in stages:
        pairs=[dict(stage=stage,noise=noise,n=n,rounds=rounds,repetition=rep,seed=seedbase+rep,pair_id=f'{stage}-{noise}-{rep}') for noise,n,rounds in specs for rep in range(3)]
        rng.shuffle(pairs)
        for pair in pairs:
            arms=['baseline','tiee'];rng.shuffle(arms)
            jobs.extend(dict(pair,arm=arm) for arm in arms)
    return jobs
def main():
    plan=make_plan();(OUT/'benchmark-plan.json').write_text(json.dumps(plan,indent=2)); rows=[]
    for index,job in enumerate(plan):
        database='v45_'+uuid.uuid4().hex[:12]
        v.dc('exec','-T','postgres','createdb','-U','tiee',database)
        env=dict(os.environ,POLICY=job.get('policy',job['arm']),PILOT_DATABASE=database,PG_POOL_SIZE=str(job.get('pool_size',0)))
        v.dc('stop','-t','1','gateway','relay','worker','probe')
        v.dc('up','-d','--no-deps','--force-recreate','gateway',env=env)
        v.dc('up','-d','--no-deps','--force-recreate','relay','worker','probe',env=env);wait_ready()
        v.call('bench',prefix='warm-'+uuid.uuid4().hex[:8],n=30,noise=job['noise'],rounds=1000,seed=9001)
        before=v.metrics();disk_before=storage();stop=threading.Event();samples=[]
        def sample():
            while not stop.is_set():
                p=v.run(['docker','stats','--no-stream','--format','{{json .}}']+[v.PROJECT+'-'+s+'-1' for s in SERVICES],check=False)
                samples.append({'at':time.time(),'rows':[json.loads(x) for x in p.stdout.splitlines() if x.startswith('{')]})
                stop.wait(.2)
        thread=threading.Thread(target=sample);thread.start()
        try:
            row=v.call('bench',prefix=f'v45-{index}',n=job['n'],noise=job['noise'],rounds=job['rounds'],seed=job['seed'])
        finally:stop.set();thread.join()
        after=v.metrics();disk_after=storage()
        row.update(job,index=index,database=database,resources_before=before,resources_after=after,stats_samples=samples,storage_before=disk_before,storage_after=disk_after,
            total_service_cpu_seconds=sum(after[s]['cpu_seconds']-before[s]['cpu_seconds'] for s in SERVICES),
            resident_memory_before_bytes=sum(before[s]['memory_bytes'] for s in SERVICES),resident_memory_after_bytes=sum(after[s]['memory_bytes'] for s in SERVICES),
            sql_table_growth_bytes=sum(disk_after['table_bytes'].values())-sum(disk_before['table_bytes'].values()),
            wal_growth_bytes=disk_after['wal_position_bytes']-disk_before['wal_position_bytes'],
            redis_aof_disk_growth_bytes=disk_after['redis_aof_disk_bytes']-disk_before['redis_aof_disk_bytes'])
        rows.append(row);(OUT/'randomized-benchmark.json').write_text(json.dumps(rows,indent=2))
        print(json.dumps({k:row[k] for k in ['index','stage','arm','noise','accepted','useful_completion_rps','completion_p95_ms','total_service_cpu_seconds','sql_pending_peak','integrity_pass']}),flush=True)
    for pair in {x['pair_id'] for x in rows}:
        r=[x for x in rows if x['pair_id']==pair]
        assert len(r)==2 and r[0]['workload_hash']==r[1]['workload_hash'] and r[0]['accepted']==r[1]['accepted']
    print(f'ALL_{len(rows)}_RANDOMIZED_MATCHED_RUNS_PASS',flush=True)
if __name__=='__main__':main()
