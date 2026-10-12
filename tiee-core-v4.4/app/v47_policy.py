"""Observable-only policy; reward classes are explicitly authorized application inputs."""
import hashlib, json, math, os, time, stat
from pathlib import Path
CLASSES={'standard':(1.,2.),'bulk':(.5,1.),'critical':(8.,8.)}
MODEL=Path(os.environ.get('V46_MODEL','/srv/policies/v47/model.json'))
def features(event):
    if set(event)!={'id','kind','rounds','body'}: raise ValueError('keys')
    if not isinstance(event['id'],str) or not 0<len(event['id'])<=128: raise ValueError('id')
    if event['kind'] not in ('valid','bot'): raise ValueError('kind')
    if type(event['rounds']) is not int or not 1<=event['rounds']<=20000: raise ValueError('rounds')
    if not isinstance(event['body'],str) or len(event['body'])>10000: raise ValueError('body')
    b=json.loads(event['body'])
    if set(b)!={'signal','noise','class','deadline_ms'}: raise ValueError('feature keys')
    if b['class'] not in CLASSES: raise ValueError('class')
    if type(b['deadline_ms']) is not int or not 100<=b['deadline_ms']<=60000: raise ValueError('deadline')
    for k in ('signal','noise'):
        if type(b[k]) not in (int,float) or not math.isfinite(b[k]) or not -3<=b[k]<=3: raise ValueError('finite feature')
    return b,[1.,b['signal'],b['noise'],b['signal']*b['noise']]
def config():
    meta=MODEL.stat()
    if not stat.S_ISREG(meta.st_mode) or not 0<meta.st_size<=16384: raise ValueError('bounded regular model file required')
    raw=MODEL.read_bytes(); m=json.loads(raw)
    if len(m['coefficients'])!=4 or any(not math.isfinite(x) for x in m['coefficients']): raise ValueError('model')
    for k in ('cpu_seconds_per_round','utility_per_cpu_second','confidence_margin','reject_probability_threshold'):
        if not math.isfinite(m[k]) or m[k]<0: raise ValueError(k)
    if m['reject_probability_threshold']>1: raise ValueError('probability threshold')
    return m,hashlib.sha256(raw).hexdigest()
def decide(event,arm=None,system=None,release_uncertain=False):
    start=time.perf_counter(); b,x=features(event); m,version=config()
    arm=arm or os.environ.get('V46_ARM','A3'); system=system or os.environ.get('V46_SYSTEM','Nominal')
    if arm not in ('A0','A1','A2','A3','A4'): raise ValueError('arm')
    omega={'Harmony':1.5,'Nominal':1.,'Destructive':0.}[system]
    z=sum(a*c for a,c in zip(x,m['coefficients'])); p=1/(1+math.exp(-max(-40,min(40,z))))
    reward,penalty=CLASSES[b['class']]; cost=event['rounds']*m['cpu_seconds_per_round']*m['utility_per_cpu_second']
    base=p*reward-(1-p)*penalty; net=base*omega-cost
    mandatory=b['class']=='critical'
    if mandatory: decision,reason='ALLOW','authorized mandatory class'
    elif event['kind']=='bot': decision,reason='REJECT','fixed application filter'
    elif arm in ('A0','A1'): decision,reason='ALLOW','fixed admission control'
    elif system=='Destructive': decision,reason='DEFER','temporary destructive state'
    elif p<m['reject_probability_threshold'] and net<=0: decision,reason='REJECT','calibrated conservative rejection'
    elif net<=m['confidence_margin'] and not release_uncertain: decision,reason='DEFER','bounded uncertainty hold'
    else: decision,reason='ALLOW','conservative useful-work protection'
    if time.perf_counter()-start>.05: raise TimeoutError('scoring budget exceeded')
    return dict(decision=decision,reason=reason,arm=arm,policy_version='v47-1',model_version=version,feature_hash=hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest(),p_valid=p,p_corrupt=1-p,reward=reward,penalty=penalty,expected_cost=cost,omega=omega,base_ev=base,net_ev=net,confidence_margin=m['confidence_margin'],deadline_ms=b['deadline_ms'],mandatory=mandatory,decision_seconds=time.perf_counter()-start)
def rank_sql(arm):
    # Deadline scheduler and EV scheduler both age to a forced FIFO lane at 0.5s.
    if arm=='A1': return "CASE WHEN created_at < now()-interval '0.5 seconds' THEN 0 ELSE 1 END, CASE WHEN created_at < now()-interval '0.5 seconds' THEN extract(epoch from created_at) ELSE extract(epoch from deadline) END, created_at,id"
    if arm in ('A3','A4'): return "CASE WHEN created_at < now()-interval '0.5 seconds' THEN 0 ELSE 1 END, CASE WHEN created_at < now()-interval '0.5 seconds' THEN extract(epoch from created_at) ELSE -priority END, created_at,id"
    return 'created_at,id'
