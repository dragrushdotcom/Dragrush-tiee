import json
from v46_data import trace as base_trace
def trace(seed,n,condition='normal',rate=40):
    rows=base_trace(seed,n,condition,rate)
    for row in rows:
        b=json.loads(row['event']['body']);b['deadline_ms']=12000;row['event']['body']=json.dumps(b)
    return rows
