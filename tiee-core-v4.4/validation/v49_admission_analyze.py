import collections,json,math,statistics
from pathlib import Path
src=Path('results/v49/admission_samples.jsonl')
rows=[json.loads(line) for line in src.read_text().splitlines() if line.strip()]
assert rows
keys=('connection_and_begin_seconds','advisory_lock_wait_seconds','lock_to_commit_upper_bound_seconds','transaction_total_seconds')
def pct(values,p): return values[math.ceil(p*len(values))-1]
metrics={}
for key in keys:
    values=sorted(row[key]*1000 for row in rows)
    metrics[key.replace('_seconds','_ms')]={'mean':round(statistics.mean(values),3),'p50':round(pct(values,.50),3),'p95':round(pct(values,.95),3),'p99':round(pct(values,.99),3),'max':round(max(values),3)}
summary={'sample_count':len(rows),'status_counts':dict(collections.Counter(str(row['status']) for row in rows)),'percentile_method':'nearest rank','metrics':metrics}
assert len(rows)==120 and all(row['status'] in (200,202) for row in rows)
out=Path('results/v49/admission_summary.json')
out.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,sort_keys=True))