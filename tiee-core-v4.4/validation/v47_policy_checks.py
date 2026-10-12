import json,pathlib,random,sys
sys.path.insert(0,str(pathlib.Path.cwd()));from app import v47_policy as p
p.MODEL=pathlib.Path('policies/v47/model.json');rng=random.Random(470005);count=0
for i in range(2000):
 e=dict(id='parity-'+str(i),kind='valid',rounds=rng.choice([100,2000,20000]),body=json.dumps(dict(signal=rng.uniform(-2,2),noise=rng.uniform(-2,2),**{'class':rng.choice(['standard','bulk','critical'])},deadline_ms=12000)))
 a=p.decide(e,'A3');b=p.decide(e,'A4');assert {k:v for k,v in a.items() if k not in ('arm','decision_seconds')}=={k:v for k,v in b.items() if k not in ('arm','decision_seconds')};count+=1
 if a['mandatory']:assert a['decision']=='ALLOW'
 if a['decision']=='REJECT':assert a['p_valid']<.02
 if a['decision']=='DEFER':assert p.decide(e,'A3',release_uncertain=True)['decision']=='ALLOW'
assert p.decide(e,'A3','Destructive')['decision']=='ALLOW' if a['mandatory'] else p.decide(e,'A3','Destructive',release_uncertain=True)['decision']=='DEFER'
print(json.dumps(dict(status='PASSED',parity_examples=count,calibrated_reject_bound=True,mandatory_protected=True,bounded_release=True)))
