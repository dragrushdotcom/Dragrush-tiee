"""Bounded sequential round; never benchmark while recovery drivers are active."""
import json,pathlib,subprocess,time
root=pathlib.Path('results/v46');deadline=time.monotonic()+1800
while True:
    p=root/'tests/v46_faults.jsonl';f=[json.loads(s) for s in p.read_text().splitlines()] if p.exists() else [];q=root/'tests/legacy_summary.json'
    if len(f)==24 and q.exists():break
    if time.monotonic()>deadline:raise RuntimeError('validation wait budget exceeded')
    time.sleep(5)
if any(x['status']!='PASSED' for x in f):raise RuntimeError('new fault gates failed: benchmarks blocked')
legacy=json.loads(q.read_text())
if any(x['exit']!=0 for x in legacy):raise RuntimeError('legacy gates failed: benchmarks blocked')
with (root/'tests/supplementary-driver.log').open('w') as log: subprocess.run(['python','validation/v46_supplementary.py'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
for stage in ('training','fixed_admission','freeze','confirmation'):
    with (root/(stage+'-driver.log')).open('a') as log:
        subprocess.run(['python','validation/v46_benchmark.py',stage],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=7200)
with (root/'analysis-driver.log').open('w') as log:subprocess.run(['python','validation/v46_analyze.py'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
print('V46_EXPERIMENTS_FINISHED',flush=True)
