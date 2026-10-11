"""Conventional connection reuse experiment; no TiEE-specific policy difference."""
import random,pathlib
import v45_benchmark as b
b.OUT=pathlib.Path('results/v45/optimization');b.OUT.mkdir(parents=True,exist_ok=True)
def plan():
    rng=random.Random(451013);jobs=[]
    for stage,noise,n,rounds,seedbase in [('training',.5,400,2000,801),('held_out',.25,600,8000,8801)]:
        reps=list(range(3));rng.shuffle(reps)
        for rep in reps:
            arms=['baseline','pooled'];rng.shuffle(arms)
            for arm in arms:
                jobs.append(dict(stage=stage,noise=noise,n=n,rounds=rounds,seed=seedbase+rep,repetition=rep,pair_id=f'{stage}-{rep}',arm=arm,policy='baseline',pool_size=0 if arm=='baseline' else 8))
    return jobs
b.make_plan=plan
if __name__=='__main__':b.main()
