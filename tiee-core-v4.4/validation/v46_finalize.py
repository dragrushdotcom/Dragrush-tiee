import datetime,gzip,hashlib,json,os,pathlib,subprocess,sys,time,traceback
ROOT=pathlib.Path(__file__).resolve().parents[1];os.chdir(ROOT);R=ROOT/'results/v46'
def cli(*a):return subprocess.run(a,capture_output=True,text=True,check=True)
def state(**v):
 v['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(R/'finish_state.json').write_text(json.dumps(v,indent=2)+chr(10));print(json.dumps(v),flush=True)
def count():return len((R/'confirmation/runs.jsonl').read_text().splitlines())
def main():
 pid=int(sys.argv[1]);started=time.monotonic();state(status='WAITING',benchmark_pid=pid,runs=count())
 while pathlib.Path('/proc',str(pid)).exists():
  if time.monotonic()-started>7500:raise RuntimeError('finalizer bounded wait exhausted')
  time.sleep(20)
 plan=json.loads((R/'confirmation/plan.json').read_text());assert count()==len(plan['jobs']),f'Confirmation incomplete: {count()}/{len(plan["jobs"])}; resume frozen jobs before finalization'
 bad=[name for name,h in plan['source_sha256'].items() if hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()!=h];assert not bad,bad
 assert hashlib.sha256(pathlib.Path('policies/v46/model.json').read_bytes()).hexdigest()==plan['model_sha256']
 assert cli('git','branch','--show-current').stdout.strip()=='tiee-core-v46-ev-validation'
 state(status='ANALYZING',runs=count())
 for script in ('v46_analyze.py','v46_report.py'):
  p=cli(sys.executable,'validation/'+script);(R/('final-'+script+'.log')).write_text(p.stdout+p.stderr)
 preservation=json.loads((R/'preservation_final.json').read_text());assert not preservation['changed_paths'] and preservation['original_status_unchanged']
 original='/workspaces/Dragrush-tiee';previous=json.loads((R/'preservation.json').read_text());assert cli('git','-C',original,'status','--porcelain').stdout==previous['original_status']
 assert cli('git','-C',original,'rev-parse','HEAD').stdout.strip()=='6e12b5098699ba636cdb1112dd192da74d8f9bb3'
 elapsed=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.strptime(plan['created_utc'],'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)).total_seconds()
 (R/'finalization.json').write_text(json.dumps(dict(status='COMPLETE_PLANNED_RUNS',confirmation_runs=count(),frozen_source_verified=True,model_verified=True,preservation_verified=True,confirmation_elapsed_including_stop_seconds=elapsed,cumulative_live_budget_compliance='UNVERIFIED',performance_claim='NOT ESTABLISHED'),indent=2)+chr(10))
 names=cli('git','ls-files','--cached','--others','--exclude-standard','.').stdout.splitlines();secrets=[];hashes={};archives={}
 for line in pathlib.Path('.env.v46').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1)
   if ('PASSWORD' in k or k=='API_KEY') and len(v)>16:secrets.append(v.encode())
 for name in names:
  p=pathlib.Path(name)
  if not p.is_file() or p.name=='artifact_manifest.json':continue
  raw=p.read_bytes();plain=gzip.decompress(raw) if p.suffix=='.gz' else raw
  assert not any(s in plain for s in secrets),f'Private value in {name}'
  assert p.stat().st_size<95*1048576,f'Artifact too large: {name}'
  hashes[name]=hashlib.sha256(raw).hexdigest()
  if p.name=='runs.jsonl.gz':archives[name]=dict(raw_sha256=hashlib.sha256(plain).hexdigest(),runs=len(plain.splitlines()))
 (R/'artifact_manifest.json').write_text(json.dumps(dict(sha256=hashes,raw_archives=archives),indent=2)+chr(10))
 cli('git','add','.');assert all(x.startswith('tiee-core-v4.4/') for x in cli('git','diff','--cached','--name-only').stdout.splitlines())
 cli('git','diff','--cached','--check');cli('git','commit','-m','Record completed v4.6 confirmation and conservative engineering analysis')
 cli('git','push','origin','tiee-core-v46-ev-validation');head=cli('git','rev-parse','HEAD').stdout.strip();remote=cli('git','ls-remote','origin','refs/heads/tiee-core-v46-ev-validation').stdout.split()[0];assert head==remote
 state(status='COMPLETE_COMMITTED_PUSHED',runs=count(),commit=head,performance_claim='NOT ESTABLISHED')
if __name__=='__main__':
 try:main()
 except Exception as e:state(status='BLOCKED_OR_INCOMPLETE',error=str(e),runs=count());traceback.print_exc();sys.exit(1)
