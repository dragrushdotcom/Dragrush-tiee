import collections,json,pathlib,time,uuid
import v47_harness as h
from v47_tests import fresh
R=pathlib.Path('results/v47/http_followup');R.mkdir(exist_ok=True)
assert json.loads(pathlib.Path('results/v47/progress.json').read_text())['status']=='COLLECTION_COMPLETE'
fresh(8);prefix='backlog-before-'+uuid.uuid4().hex[:8]
source="import sys,json,concurrent.futures,time;sys.path.insert(0,'/validation');import v47_probe as p;events=[p.event('"+prefix+"-'+str(i)) for i in range(96)];"+chr(10)+"def send(e):"+chr(10)+" try:return p.send(e)"+chr(10)+" except Exception as ex:return [0,dict(error=type(ex).__name__)]"+chr(10)+"start=time.monotonic();pool=concurrent.futures.ThreadPoolExecutor(max_workers=96);responses=list(pool.map(send,events));pool.shutdown();print(json.dumps(dict(events=events,responses=responses,submission_seconds=time.monotonic()-start)))"
raw=json.loads(h.dc('exec','-T','probe','python','-c',source).stdout);accepted=sum(x[0] in (200,202) for x in raw['responses']);size=int(h.dc('exec','-T','gateway','python','-c','from http.server import ThreadingHTTPServer;print(ThreadingHTTPServer.request_queue_size)').stdout)
result=dict(status='MEASURED_BEFORE_FIX',pool=8,offered=96,successful_http=accepted,http_errors=96-accepted,request_queue_size=size,error_types=dict(collections.Counter(str(x[0])+':'+x[1].get('error','unspecified') for x in raw['responses'] if x[0] not in (200,202))),raw=raw)
(R/'before.json').write_text(json.dumps(result,indent=2)+chr(10));print(json.dumps({k:v for k,v in result.items() if k!='raw'}))
