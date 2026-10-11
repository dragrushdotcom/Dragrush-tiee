import json,os,pathlib,subprocess,time,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1];os.chdir(ROOT)
BASE=['docker','compose','-p','tiee46pilot','--env-file','.env.v46','-f','docker-compose.yml','-f','compose.validation.yml']
COMPOSE=BASE+['-f','compose.v46.yml']
def dc(*args,env=None,check=True):
    p=subprocess.run(COMPOSE+list(args),env=env,text=True,capture_output=True,stdin=subprocess.DEVNULL,timeout=90)
    if check and p.returncode:raise RuntimeError(str(args)+': '+p.stderr[-1200:])
    return p
def call(op,**a):
    p=dc('exec','-T','probe','python','/validation/v46_probe.py',op,json.dumps(a));return json.loads(p.stdout)
def sql(q,*args):return call('sql',q=q,args=list(args))
def ev(tag,signal=2,cls='standard',deadline=60000):
    return dict(id='gate46-'+tag+'-'+uuid.uuid4().hex[:8],kind='valid',rounds=2000,body=json.dumps(dict(signal=signal,noise=0,**{'class':cls},deadline_ms=deadline)))
def send(e):return call('send',event=e)
def wait(e,state='DONE',timeout=20):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        rows=sql('SELECT state FROM events WHERE id=%s',e['id'])
        if rows and rows[0][0]==state:return time.monotonic()-start
        time.sleep(.1)
    raise AssertionError('wait '+state+' '+e['id']+' '+str(rows))
def ready():
    for _ in range(80):
        try:
            if sql('SELECT 1')==[[1]]:return
        except Exception:pass
        time.sleep(.1)
    raise AssertionError('services not ready')
def configure(arm='A3',pool=8,system='Nominal',capacity=1000,database=None):
    env=dict(os.environ,V46_ARM=arm,V46_SYSTEM=system,PG_POOL_SIZE=str(pool),QUEUE_CAPACITY=str(capacity))
    if database:env['PILOT_DATABASE']=database
    os.environ.update(env)
    dc('stop','-t','1','gateway','relay','worker','probe')
    dc('up','-d','--no-deps','--force-recreate','--scale','worker=2','gateway','relay','worker','probe',env=env);ready();time.sleep(.25)
def metrics():
    ids=dc('ps','-q','gateway','relay','worker','postgres','redis','network_anchor').stdout.split();out={}
    for cid in ids:
        p=subprocess.run(['docker','exec',cid,'sh','-c','cat /sys/fs/cgroup/cpu.stat; cat /sys/fs/cgroup/memory.current; cat /sys/fs/cgroup/memory.stat'],capture_output=True,text=True,check=True);lines=p.stdout.strip().splitlines();i=next(i for i,x in enumerate(lines) if x.isdigit());cpu=dict(x.split() for x in lines[:i]);mem=dict(x.split() for x in lines[i+1:]);out[cid]=dict(cpu_seconds=int(cpu['usage_usec'])/1e6,memory_bytes=int(lines[i]),working_set_bytes=max(0,int(lines[i])-int(mem.get('inactive_file',0))))
    return out
def storage():
    a=sql("SELECT pg_database_size(current_database()),pg_wal_lsn_diff(pg_current_wal_lsn(),'0/0')::bigint")[0];t=sql("SELECT relname,pg_total_relation_size(oid) FROM pg_class WHERE relname IN ('events','results','audit','decision_history')");r=dc('exec','-T','redis','sh','-c','du -sk /data/appendonlydir').stdout.split()[0]
    return dict(database_bytes=a[0],wal_bytes=a[1],tables=dict(t),aof_bytes=int(r)*1024)
