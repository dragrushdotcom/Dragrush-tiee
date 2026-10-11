"""Real-service gate. Run on Codespace host; clients/oracle run inside gateway.
Only project-scoped disposable pilot containers are faulted. No volume deletion.
"""
import concurrent.futures, hashlib, json, os, pathlib, random, statistics
import subprocess, sys, threading, time, urllib.request, urllib.error, uuid

def oracle(e):
    value=json.dumps(e,sort_keys=True,separators=(',', ':'),ensure_ascii=False).encode()
    for _ in range(e['rounds']): value=hashlib.sha256(value).digest()
    return value.hex()

def http(e, key=None):
    req=urllib.request.Request('http://127.0.0.1:8087/ingest',json.dumps(e).encode(),
        headers={'X-API-Key':os.environ['API_KEY'] if key is None else key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as r: return r.status,json.load(r)
    except urllib.error.HTTPError as r: return r.code,json.load(r)

def inside(op,a):
    import psycopg, redis
    if op=='sql':
        with psycopg.connect(os.environ['PG_DSN']) as c:
            cur=c.execute(a['q'],a.get('args',[]))
            return cur.fetchall() if cur.description else []
    if op=='redis_loss':
        r=redis.Redis.from_url(os.environ['REDIS_URL'])
        # Delete only this disposable pilot's stream, reproducing loss of group too.
        return {'deleted':r.delete('tiee:events')}
    if op=='send': return http(a['event'],a.get('key'))
    if op=='bench':
        rng=random.Random(a['seed']); prefix=a['prefix']; n=a['n']
        events=[dict(id=f'{prefix}-{i}',kind='bot' if rng.random()<a['noise'] else 'valid',
            rounds=a['rounds'],body=hashlib.sha256(str((a['seed'],i)).encode()).hexdigest()) for i in range(n)]
        sent={}; ack=[]; codes={}; lock=threading.Lock(); observed={}; poll_stop=threading.Event(); poll_errors=[]
        def poll_commits():
            try:
                with psycopg.connect(os.environ['PG_DSN'],autocommit=True) as c:
                    while not poll_stop.is_set():
                        found=c.execute('SELECT id FROM results WHERE id LIKE %s',(prefix+'-%',)).fetchall()
                        now=time.time()
                        for (eid,) in found: observed.setdefault(eid,now)
                        poll_stop.wait(.02)
            except Exception as ex: poll_errors.append(str(ex))
        poller=threading.Thread(target=poll_commits); poller.start()
        def send(e):
            t=time.time(); sent[e['id']]=t
            status,result=http(e)
            with lock:
                ack.append((time.time()-t)*1000); codes[str(status)]=codes.get(str(status),0)+1
            assert status==202,(status,result)
        start=time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: list(ex.map(send,events))
        admission_elapsed=time.perf_counter()-start
        expected={e['id']:e for e in events if e['kind']=='valid'}
        with psycopg.connect(os.environ['PG_DSN'],autocommit=True) as c:
            deadline=time.monotonic()+90
            while True:
                rows=c.execute('SELECT id,digest,extract(epoch from completed_at)::float FROM results WHERE id LIKE %s',(prefix+'-%',)).fetchall()
                if len(rows)==len(expected): break
                if time.monotonic()>deadline: raise AssertionError(('completion_timeout',len(rows),len(expected)))
                time.sleep(.02)
            elapsed=time.perf_counter()-start
            states=c.execute('SELECT state,count(*) FROM events WHERE id LIKE %s GROUP BY state',(prefix+'-%',)).fetchall()
        actual={row[0]:row[1] for row in rows}
        assert actual=={eid:oracle(e) for eid,e in expected.items()},'independent digest/output set mismatch'
        assert dict(states).get('REJECTED',0)==n-len(expected),states
        deadline=time.monotonic()+5
        while len(observed)<len(expected) and time.monotonic()<deadline: time.sleep(.02)
        poll_stop.set(); poller.join(); assert not poll_errors,poll_errors
        assert len(observed)==len(expected), 'missing commit observations'
        lat=[(observed[row[0]]-sent[row[0]])*1000 for row in rows]
        def pct(v,p): return sorted(v)[min(len(v)-1,int((len(v)-1)*p))] if v else None
        return dict(**a,accepted=len(expected),rejected=n-len(expected),http_statuses=codes,
            admission_seconds=admission_elapsed,drain_seconds=elapsed,ingress_rps=n/admission_elapsed,
            useful_completion_rps=len(expected)/elapsed,ack_p50_ms=pct(ack,.5),ack_p95_ms=pct(ack,.95),ack_p99_ms=pct(ack,.99),
            completion_p50_ms=pct(lat,.5),completion_p95_ms=pct(lat,.95),completion_p99_ms=pct(lat,.99),
            integrity_pass=True,states=states,completion_latencies_ms=lat,ack_latencies_ms=ack,
            workload_hash=hashlib.sha256(json.dumps([{k:v for k,v in e.items() if k!='id'} for e in events],sort_keys=True).encode()).hexdigest())
    raise ValueError(op)

PROJECT='tiee44pilot'
COMPOSE=['docker','compose','-p',PROJECT,'-f','docker-compose.yml','-f','compose.validation.yml']
OUT=pathlib.Path('results'); OUT.mkdir(exist_ok=True)
def run(args,check=True,**kw):
    p=subprocess.run(args,text=True,capture_output=True,**kw)
    if check and p.returncode: raise RuntimeError(f'{args[:5]} exited {p.returncode}: {p.stderr[-1500:]}')
    return p
def dc(*args,**kw): return run(COMPOSE+list(args),**kw)
def call(op,**args):
    p=dc('exec','-T','gateway','python','/validation/validate.py','--inside',op,json.dumps(args))
    return json.loads(p.stdout)
def sql(q,*args): return call('sql',q=q,args=list(args))
def ev(tag): return dict(id='gate-'+tag+'-'+uuid.uuid4().hex[:10],kind='valid',rounds=2000,body='deterministic-gate')
def wait_state(e,state='DONE',timeout=20):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        rows=sql('SELECT state FROM events WHERE id=%s',e['id'])
        if rows and rows[0][0]==state:
            if state=='DONE':
                assert sql('SELECT digest FROM results WHERE id=%s',e['id'])==[[oracle(e)]]
            return time.monotonic()-start
        time.sleep(.2)
    raise AssertionError('timeout waiting '+state+' '+e['id'])
def admission(e): assert call('send',event=e)==[202,{'status':'ACCEPT'}]
def test(name,fn):
    t=time.monotonic()
    try: detail=fn(); result=dict(test=name,pass_=True,seconds=time.monotonic()-t,detail=detail)
    except Exception as ex: result=dict(test=name,pass_=False,seconds=time.monotonic()-t,error=str(ex))
    with (OUT/'integration.jsonl').open('a') as f: f.write(json.dumps(result)+'\n')
    print(json.dumps(result),flush=True); return result['pass_']
def contracts():
    e=ev('contracts'); admission(e); wait_state(e)
    assert call('send',event=e)==[200,{'status':'ACCEPT','duplicate':True}]
    altered=dict(e,body='conflict'); assert call('send',event=altered)[0]==409
    assert call('send',event={'id':'missing'})[0]==400
    assert call('send',event=e,key='invalid')[0]==403
    b=dict(ev('bot'),kind='bot'); assert call('send',event=b)==[202,{'status':'REJECT'}]
    assert sql('SELECT state FROM events WHERE id=%s',b['id'])==[['REJECTED']]
    assert sql('SELECT count(*) FROM results WHERE id=%s',b['id'])==[[0]]
    return {'valid_duplicate_conflict_malformed_auth_rejection':'PASS'}
def relay_crash():
    dc('kill','-s','SIGKILL','relay'); e=ev('relay'); admission(e); wait_state(e,'PENDING')
    start=time.monotonic(); dc('start','relay'); wait_state(e)
    return {'recovery_seconds':time.monotonic()-start}
def worker_crash():
    # Stop before admission, then SIGSTOP after start catches a pending delivery.
    dc('stop','worker'); e=dict(ev('worker'),rounds=20000); admission(e); wait_state(e,'ENQUEUED')
    dc('start','worker'); dc('kill','-s','SIGKILL','worker')
    start=time.monotonic(); dc('start','worker'); wait_state(e)
    return {'recovery_seconds':time.monotonic()-start,'note':'kill timing nondeterministic; additional deterministic pending test below'}
def pending_reclaim():
    dc('stop','worker'); e=ev('pending'); admission(e); wait_state(e,'ENQUEUED')
    dc('stop','relay')
    p=dc('exec','-T','redis','redis-cli','XREADGROUP','GROUP','workers','dead-test-consumer','COUNT','100','STREAMS','tiee:events','>')
    assert e['id'] in p.stdout,'target not delivered to dead consumer'
    start=time.monotonic(); dc('start','worker'); wait_state(e)
    dc('start','relay')
    return {'recovery_seconds':time.monotonic()-start,'target_confirmed_in_dead_consumer_delivery':True}
def redis_loss():
    dc('stop','worker'); e=ev('redis-loss'); admission(e); wait_state(e,'ENQUEUED')
    dc('start','worker'); dc('pause','worker')
    # A separate event remains unresolved while worker is paused.
    e=ev('lost'); admission(e); wait_state(e,'ENQUEUED')
    lost=call('redis_loss'); dc('unpause','worker')
    start=time.monotonic()
    try: wait_state(e,timeout=12)
    finally:
        (OUT/'redis-loss-worker.log').write_text(dc('logs','--no-color','--tail','25','worker').stdout)
    return {'recovery_seconds':time.monotonic()-start,**lost}
def redis_restart():
    dc('stop','worker'); e=ev('restart'); admission(e); wait_state(e,'ENQUEUED')
    dc('kill','-s','SIGKILL','redis'); start=time.monotonic(); dc('start','redis'); dc('start','worker'); wait_state(e)
    return {'recovery_seconds':time.monotonic()-start}
def pg_restart():
    dc('stop','worker'); e=ev('pg'); admission(e); wait_state(e,'ENQUEUED')
    dc('kill','-s','SIGKILL','postgres'); start=time.monotonic(); dc('start','postgres'); time.sleep(2)
    dc('start','worker'); wait_state(e)
    return {'recovery_seconds':time.monotonic()-start}
def gateway_restart():
    e=ev('gateway'); admission(e); dc('kill','-s','SIGKILL','gateway'); dc('start','gateway'); time.sleep(1)
    wait_state(e); assert call('send',event=e)[0]==200
    return {'admitted_event_survived':True}
def metrics():
    data={}
    for s in ['gateway','relay','worker','redis','postgres']:
        p=dc('exec','-T',s,'sh','-c','cat /sys/fs/cgroup/cpu.stat; cat /sys/fs/cgroup/memory.current')
        lines=p.stdout.strip().splitlines(); cpu=dict(x.split() for x in lines[:-1])
        data[s]={'cpu_seconds':int(cpu['usage_usec'])/1e6,'memory_bytes':int(lines[-1])}
    return data
def bench():
    rows=[]
    for noise in [0,.5,.9]:
        for rep in range(3):
            for arm in (['baseline','tiee'] if rep%2==0 else ['tiee','baseline']):
                database='trial_'+uuid.uuid4().hex[:12]
                dc('exec','-T','postgres','createdb','-U','tiee',database)
                env=dict(os.environ,POLICY=arm,PILOT_DATABASE=database)
                # Fresh SQL database per trial; archive it instead of deleting data.
                dc('stop','gateway','relay','worker')
                dc('up','-d','--no-deps','--force-recreate','gateway',env=env); time.sleep(.6)
                dc('up','-d','--no-deps','--force-recreate','relay','worker',env=env); time.sleep(.6)
                call('bench',prefix='warm-'+uuid.uuid4().hex[:8],n=30,noise=noise,rounds=1000,seed=900+rep)
                before=metrics(); samples=[]; stop=threading.Event()
                def sample():
                    while not stop.is_set():
                        p=run(['docker','stats','--no-stream','--format','{{json .}}']+[PROJECT+'-'+s+'-1' for s in ['gateway','relay','worker','redis','postgres']],check=False)
                        samples.append({'at':time.time(),'lines':p.stdout.splitlines()})
                        stop.wait(.2)
                thread=threading.Thread(target=sample); thread.start()
                try: row=call('bench',prefix=f'b-{noise}-{rep}-{arm}',n=300,noise=noise,rounds=2000,seed=100+rep)
                finally: stop.set(); thread.join()
                after=metrics(); row.update(arm=arm,repetition=rep,database=database,resources_before=before,resources_after=after,stats_samples=samples,
                    total_service_cpu_seconds=sum(after[s]['cpu_seconds']-before[s]['cpu_seconds'] for s in before))
                rows.append(row); (OUT/'benchmark.json').write_text(json.dumps(rows,indent=2))
                print(json.dumps({k:v for k,v in row.items() if k not in ['completion_latencies_ms','ack_latencies_ms','stats_samples','resources_before','resources_after']}),flush=True)
    return rows

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--inside':
        print(json.dumps(inside(sys.argv[2],json.loads(sys.argv[3])),default=str)); sys.exit()
    mode=sys.argv[1] if len(sys.argv)>1 else 'integration'
    if mode=='integration':
        passed=[test(n,f) for n,f in [('admission_contracts',contracts),('relay_SIGKILL',relay_crash),('worker_SIGKILL',worker_crash),('pending_reclaim',pending_reclaim),('redis_SIGKILL_AOF',redis_restart),('postgres_SIGKILL',pg_restart),('gateway_SIGKILL',gateway_restart),('redis_stream_and_group_loss',redis_loss)]]
        sys.exit(0 if all(passed) else 1)
    elif mode=='loss': sys.exit(0 if test('redis_stream_and_group_loss',redis_loss) else 1)
    elif mode=='benchmark': bench()
