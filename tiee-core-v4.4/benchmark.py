"""Local reproducible HTTP benchmark. Both arms use identical workload generator."""
import argparse, hashlib, json, random, statistics, time, urllib.request, urllib.error

def send(event,key,base):
    payload=json.dumps(event).encode()
    req=urllib.request.Request(base+'/ingest',payload,headers={'Content-Type':'application/json','X-API-Key':key},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=42);p.add_argument('--events',type=int,default=500);p.add_argument('--noise',type=float,default=.5);p.add_argument('--rounds',type=int,default=1000);p.add_argument('--key',default='dev-only-change-me');p.add_argument('--url',default='http://127.0.0.1:8087');p.add_argument('--output',default='results/benchmark.json');a=p.parse_args()
    r=random.Random(a.seed); events=[{'id':f'{a.seed}-{i}','kind':'bot' if r.random()<a.noise else 'valid','rounds':a.rounds,'body':hashlib.sha256(str((a.seed,i)).encode()).hexdigest()} for i in range(a.events)]
    statuses={}; start=time.perf_counter();accepted=[]
    for e in events:
        for attempt in range(120):
            status,result=send(e,a.key,a.url)
            if status==503:time.sleep(.05);continue
            statuses[status]=statuses.get(status,0)+1
            if status==202 and result['status']=='ACCEPT':accepted.append(e['id'])
            break
        else:raise RuntimeError('capacity retries exhausted')
    publish_seconds=time.perf_counter()-start
    # Request completions are NOT claimed until externally verified in PostgreSQL.
    report={'seed':a.seed,'source_events':a.events,'noise':a.noise,'rounds':a.rounds,'accepted':len(accepted),'http_statuses':statuses,'publish_seconds':publish_seconds,'publish_rate':a.events/publish_seconds,'note':'producer-only measurement; query DB to verify completed results'}
    with open(a.output,'w') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
