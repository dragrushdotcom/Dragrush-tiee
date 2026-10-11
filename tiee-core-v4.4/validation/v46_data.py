"""Hidden truth stays in this independent probe, never in the event."""
import json, math, random
def trace(seed,n=240,condition='normal',rate=120):
    r=random.Random(seed); out=[]
    for i in range(n):
        x=r.uniform(-2,2); z=r.uniform(-2,2)
        latent=1.2+2.2*x-.6*z+.3*x*z
        if condition=='shift': latent-=1.25; latent+=.8*z
        if condition=='train_low': latent+=2
        if condition=='train_high': latent-=2
        p=1/(1+math.exp(-latent)); valid=r.random()<p
        cls=r.choices(['standard','bulk','critical'],[.65,.25,.1])[0]
        rounds=r.choice([100,500,2000,6000,20000])
        if condition=='fixed_admission': cls='critical'
        if condition=='burst' and i%7==0: rounds=20000;cls='critical'
        offset=i/rate
        if condition=='burst': offset=(i//60)*.35+(i%60)*.0002
        body=dict(signal=x,noise=z,**{'class':cls},deadline_ms=3000 if condition!='burst' else 1500)
        event=dict(id=f'v46-{seed}-{i}',kind='valid',rounds=rounds,body=json.dumps(body,sort_keys=True,separators=(',',':')))
        out.append(dict(event=event,valid=valid,latent_p=p,scheduled_offset=offset))
    return out
