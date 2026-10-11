"""Training-only counterfactual decisions/order; no infrastructure performance claims."""
import hashlib,json,pathlib,statistics,sys,time
sys.path.insert(0,'.')
from app import v46_policy as p
from v46_data import trace
p.MODEL=pathlib.Path('policies/v46/model.json')
rows=trace(460090,3000);baseline=[];ablations={}
for row in rows:baseline.append(p.decide(row['event'],'A3'))
for name in ('no_deferral','no_cost','harmony','destructive','no_aging'):
    start=time.process_time();decisions=[]
    for row,d in zip(rows,baseline):
        score=d['net_ev'];decision=d['decision']
        if name=='no_deferral' and decision=='DEFER':decision='ALLOW' if score>0 else 'REJECT'
        if name=='no_cost':score=d['base_ev']*d['omega'];decision='ALLOW' if score>0 else 'REJECT'
        if name in ('harmony','destructive'):decision=p.decide(row['event'],'A3',name.title())['decision']
        if d['mandatory']:decision='ALLOW'
        decisions.append(decision)
    ablations[name]=dict(counts={s:decisions.count(s) for s in ('ALLOW','DEFER','REJECT')},decision_changes=sum(a!=b['decision'] for a,b in zip(decisions,baseline)),probe_cpu_seconds=time.process_time()-start,scope='offline policy counterfactual; scheduling throughput unexecuted')
pathlib.Path('results/v46/ablations/policy_counterfactuals.json').write_text(json.dumps(dict(seed=460090,n=len(rows),model_hash=hashlib.sha256(p.MODEL.read_bytes()).hexdigest(),variants=ablations,no_aging_limitation='At initial arrival ages are equal; actual sustained scheduling ablation is not supplied by this offline diagnostic.'),indent=2));print(json.dumps(ablations,indent=2))
