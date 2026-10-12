import collections, concurrent.futures, json, os, urllib.error, urllib.request
from v47_data import trace
rows=trace(490049,120,'normal',40)
key=os.environ['API_KEY']
def send(row):
    req=urllib.request.Request('http://127.0.0.1:8087/ingest',data=json.dumps(row['event']).encode(),headers={'X-API-Key':key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    codes=list(pool.map(send,rows))
summary={'seed':490049,'events':len(codes),'http_codes':dict(collections.Counter(codes)),'workers':8}
assert len(codes)==120 and all(code in (200,202) for code in codes),summary
print(json.dumps(summary,sort_keys=True))