import collections,json,time
import v46_probe as probe
base=probe.send
def delayed(event,key=None):
 response=base(event,key);time.sleep(6);return response
probe.send=delayed
row=probe.bench(dict(seed=460099,n=6,condition='normal',rate=120,prefix='recorder-regression-'+str(time.time_ns())))
assert row['wall_seconds']>5.1
assert len(row['ledger'])==6 and sum(row['states'].values())==6
assert row['states']==dict(collections.Counter(x['state'] for x in row['ledger']))
assert row['states']=={'DONE':6} and row['http_errors']==0
print(json.dumps(dict(test='recorder_submission_exceeds_drain_window',pool=8,status='PASSED',wall_seconds=row['wall_seconds'],states=row['states'],http_errors=row['http_errors'],oracle_verified_completions=len(row['ledger']),raw=row)))
