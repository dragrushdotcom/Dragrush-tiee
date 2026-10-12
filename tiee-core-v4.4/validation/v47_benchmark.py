import hashlib,json,pathlib,random,statistics,subprocess,time,threading
import v47_harness as h
from v47_data import trace
def run(job,index):
    database='v47_'+job['stage'][:1]+'_'+str(time.time_ns())[-13:];h.dc('exec','-T','postgres','createdb','-U','tiee',database);h.configure(job['arm'],database=database)
    warm=h.call('bench',seed=470999,n=24,condition='normal',rate=120,prefix='warm-'+str(index));before=h.metrics();disk=h.storage()
    ids=h.dc('ps','-q','gateway','relay','worker','postgres','redis','network_anchor').stdout.split();service_names={x['Id']:x['Name'].lstrip('/') for x in json.loads(subprocess.check_output(['docker','inspect']+ids,text=True))}
    samples=[];stop=threading.Event()
    def sample():
        while not stop.is_set():
            samples.append(dict(at=time.monotonic(),services=h.metrics()));stop.wait(.25)
    thread=threading.Thread(target=sample);thread.start()
    try: row=h.call('bench',**{k:v for k,v in job.items() if k in ('seed','n','condition','rate')},prefix='v47-'+job['stage']+'-'+job['condition']+'-'+str(job['block']))
    finally: stop.set();thread.join()
    assert row['workload_hash']==hashlib.sha256(json.dumps(trace(job['seed'],job['n'],job['condition'],job['rate']),sort_keys=True).encode()).hexdigest()
    after=h.metrics();disk_after=h.storage();cpu=sum(after[k]['cpu_seconds']-before[k]['cpu_seconds'] for k in before);raw_utility=row['total_utility'];net=raw_utility-.1*cpu
    row.update(job,service_names=service_names,database=database,index=index,resources_before=before,resources_after=after,resource_samples=samples,storage_before=disk,storage_after=disk_after,service_cpu_seconds=cpu,net_total_utility=net,net_utility_per_cpu=net/cpu,utility_per_wall_second=net/row['wall_seconds'],useful_throughput=row['useful_completions']/row['wall_seconds'],table_growth_bytes=sum(disk_after['tables'].values())-sum(disk['tables'].values()),wal_growth_bytes=disk_after['wal_bytes']-disk['wal_bytes'],aof_growth_bytes=disk_after['aof_bytes']-disk['aof_bytes'],sql_pending_peak=max((sum(n for s,n in x['states'].items() if s in ('PENDING','ENQUEUED','RUNNING','DEFERRED','HELD')) for x in row['queue_samples']),default=0))
    return row
