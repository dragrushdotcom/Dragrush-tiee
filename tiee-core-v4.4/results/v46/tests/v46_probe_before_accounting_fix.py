import concurrent.futures,hashlib,json,math,os,statistics,sys,threading,time,urllib.request,urllib.error
sys.path.insert(0,'/srv')
from app.common import pg,rd,STREAM,GROUP
from v46_data import trace
def sql(q,args=()):
    with pg() as c:
        cur=c.execute(q,args);return cur.fetchall() if cur.description else []
def send(e,key=None):
    req=urllib.request.Request('http://127.0.0.1:8087/ingest',json.dumps(e).encode(),headers={'X-API-Key':os.environ['API_KEY'] if key is None else key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=5) as r: return [r.status,json.load(r)]
    except urllib.error.HTTPError as r: return [r.code,json.load(r)]
def event(eid,signal=2,cls='standard',deadline=60000):
    return dict(id=eid,kind='valid',rounds=2000,body=json.dumps(dict(signal=signal,noise=0,**{'class':cls},deadline_ms=deadline)))
def oracle(e):
    h=json.dumps(e,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    for _ in range(e['rounds']):h=hashlib.sha256(h).digest()
    return h.hex()
def bench(a):
    rows=trace(a['seed'],a.get('n',240),a.get('condition','normal'),a.get('rate',120));trace_hash=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest();prefix=a['prefix']
    for row in rows: row['event']['id']=prefix+'-'+row['event']['id']
    samples=[];observed={};stop=threading.Event();poll_errors=[]
    def poll():
        while not stop.is_set():
            try:
                with pg() as c:
                    done=c.execute("SELECT id,state FROM events WHERE id LIKE %s AND state IN ('DONE','REJECTED','EXPIRED','HELD')",(prefix+'%',)).fetchall()
                    for eid,state in done:observed.setdefault(eid,time.monotonic())
                    counts=c.execute('SELECT state,count(*) FROM events WHERE id LIKE %s GROUP BY state',(prefix+'%',)).fetchall()
                r=rd();pending=0
                try:pending=r.xpending(STREAM,GROUP)['pending']
                except Exception:pass
                samples.append(dict(at=time.monotonic(),states=dict(counts),stream=r.xlen(STREAM),pending=pending))
            except Exception as exc:poll_errors.append(type(exc).__name__)
            stop.wait(.02)
    cpu_start=time.process_time();start=time.monotonic();thread=threading.Thread(target=poll);thread.start();receipts={}
    def dispatch(row):
        target=start+row['scheduled_offset'];delay=target-time.monotonic()
        if delay>0:time.sleep(delay)
        now=time.monotonic()
        try:response=send(row['event'])
        except Exception as exc:response=[0,dict(error=type(exc).__name__)]
        receipts[row['event']['id']]=dict(dispatch=now,ack=time.monotonic(),response=response,scheduled=target)
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:list(pool.map(dispatch,rows))
    arrival_end=start+max(x['scheduled_offset'] for x in rows);limit=arrival_end+5
    while time.monotonic()<limit:
        states=sql("SELECT state,count(*) FROM events WHERE id LIKE %s GROUP BY state",(prefix+'%',));unresolved=sum(n for state,n in states if state in ('PENDING','ENQUEUED','RUNNING','DEFERRED'))
        if not unresolved:break
        time.sleep(.02)
    end=time.monotonic();stop.set();thread.join()
    db={x[0]:x[1:] for x in sql('SELECT e.id,e.state,e.decision,r.digest,e.execution_cpu,extract(epoch from (e.claimed_at-e.created_at)),extract(epoch from (r.completed_at-e.created_at)) FROM events e LEFT JOIN results r USING(id) WHERE e.id LIKE %s',(prefix+'%',))}
    ledger=[];lat=[];dispatch_lat=[];acks=[];valid_reject=0;brier=[];logloss=[];execution_cpu=0
    for row in rows:
        e=row['event'];eid=e['id'];receipt=receipts[eid];state,d,digest,cpu,queue,db_latency=db.get(eid,('REFUSED',None,None,None,None,None));b=json.loads(e['body']);reward,penalty={'standard':(1,2),'bulk':(.5,1),'critical':(8,8)}[b['class']]
        if state=='DONE':
            assert digest==oracle(e),eid
            utility=reward if row['valid'] else -penalty
        else:utility=-.25*reward if row['valid'] else 0
        if row['valid'] and state=='REJECTED':valid_reject+=1
        if d: p=d['p_valid'];brier.append((p-int(row['valid']))**2);logloss.append(-math.log(max(1e-12,p if row['valid'] else 1-p)))
        terminal=observed.get(eid,receipt['ack']);offered=(terminal-receipt['scheduled'])*1000;dispatched=(terminal-receipt['dispatch'])*1000
        if state in ('DONE','REJECTED','EXPIRED','HELD'):lat.append(offered);dispatch_lat.append(dispatched)
        acks.append((receipt['ack']-receipt['dispatch'])*1000);execution_cpu+=cpu or 0
        ledger.append(dict(id=eid,valid=row['valid'],event=e,state=state,decision=d,receipt=receipt,utility=utility,execution_cpu=cpu,queue_seconds=float(queue) if queue is not None else None,db_latency_seconds=float(db_latency) if db_latency is not None else None,offered_terminal_ms=offered,dispatch_terminal_ms=dispatched))
    def pct(v,p):return sorted(v)[min(len(v)-1,int((len(v)-1)*p))] if v else None
    return dict(**a,ledger=ledger,queue_samples=samples,wall_seconds=end-start,total_utility=sum(x['utility'] for x in ledger),execution_cpu_seconds=execution_cpu,probe_cpu_seconds=time.process_time()-cpu_start,states=dict(states),valid_count=sum(x['valid'] for x in rows),valid_rejected=valid_reject,brier=statistics.mean(brier) if brier else None,log_loss=statistics.mean(logloss) if logloss else None,offered_latency_ms={str(p):pct(lat,p) for p in (.5,.95,.99)},dispatch_latency_ms={str(p):pct(dispatch_lat,p) for p in (.5,.95,.99)},ack_latency_ms={str(p):pct(acks,p) for p in (.5,.95,.99)},useful_completions=sum(x['state']=='DONE' and x['valid'] for x in ledger),http_errors=sum(x['response'][0] not in (200,202) for x in receipts.values()),poll_errors=poll_errors,drain_pass=all(x['state'] not in ('PENDING','ENQUEUED','RUNNING','DEFERRED','HELD') for x in ledger),workload_hash=trace_hash)
def op(name,a):
    if name=='sql':return sql(a['q'],a.get('args',[]))
    if name=='send':return send(a['event'],a.get('key'))
    if name=='bench':return bench(a)
    if name=='claim':
        from app.v46_store import claim
        return claim(a['id'])
    if name=='commit':
        from app.v46_store import commit_result
        return commit_result(a['id'],a['generation'],a['digest'],fail=a.get('fail',False))
    if name=='relay':
        from app.v46_store import relay_once
        try:relay_once(a.get('fail',False));return 'committed'
        except RuntimeError:return 'rolled_back'
    if name=='migrate':
        from app.v46_store import migrate
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda _:migrate(),range(8)))
        return 'eight concurrent migrations committed'
    if name=='loss':return rd().delete(STREAM)
    if name=='replay':return rd().xadd(STREAM,{'id':a['id']})
    if name=='policy':
        from app.v46_policy import decide
        return decide(a['event'],a.get('arm'),a.get('system'))
    raise ValueError(name)
if __name__=='__main__':print(json.dumps(op(sys.argv[1],json.loads(sys.argv[2])),default=str))
