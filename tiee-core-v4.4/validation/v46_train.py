import hashlib,json,math,pathlib,statistics,time
from v46_data import trace
rows=trace(460001,6000); coeff=[0.,0.,0.,0.]
for epoch in range(250):
    grad=[0.]*4
    for row in rows:
        b=json.loads(row['event']['body']);x=[1.,b['signal'],b['noise'],b['signal']*b['noise']]
        p=1/(1+math.exp(-sum(a*c for a,c in zip(x,coeff))));err=p-int(row['valid'])
        for j in range(4): grad[j]+=err*x[j]/len(rows)
    coeff=[a-.3*g for a,g in zip(coeff,grad)]
# Training-only cost timings, independent identical digest executor.
cost=[]
for item in rows[:50]:
    e=item['event'];h=json.dumps(e,sort_keys=True,separators=(',',':')).encode();start=time.process_time()
    for _ in range(e['rounds']): h=hashlib.sha256(h).digest()
    cost.append((time.process_time()-start)/e['rounds'])
m=dict(coefficients=coeff,cpu_seconds_per_round=statistics.median(cost),utility_per_cpu_second=.1,confidence_margin=.005,training_seed=460001,calibration_seed=460002,primary_system='Nominal',maximum_wait_seconds=.5,deferral_seconds=.25,maximum_deferrals=3,claim_lease_seconds=3,utility_missed_fraction=.25)
pathlib.Path('policies/v46/model.json').write_text(json.dumps(m,indent=2)+chr(10))
cal=trace(460002,3000);prev=sum(x['valid'] for x in rows)/len(rows);brier=[];reference=[];ll=[]
for row in cal:
    b=json.loads(row['event']['body']);x=[1,b['signal'],b['noise'],b['signal']*b['noise']];p=1/(1+math.exp(-sum(a*c for a,c in zip(x,coeff))));y=int(row['valid']);brier.append((p-y)**2);reference.append((prev-y)**2);ll.append(-math.log(p if y else 1-p))
pathlib.Path('results/v46/training/model_fit.json').write_text(json.dumps(dict(model=m,cost_samples=cost,calibration_brier=statistics.mean(brier),prevalence_brier=statistics.mean(reference),log_loss=statistics.mean(ll),calibration_count=len(cal)),indent=2))
print('TRAINED',coeff,'calibration Brier',statistics.mean(brier),'reference',statistics.mean(reference))
