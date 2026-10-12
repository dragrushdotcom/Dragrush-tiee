import datetime,json,pathlib,subprocess,sys,time,traceback
R=pathlib.Path('results/v47')
def state(status,**kwargs):
 (R/'progress.json').write_text(json.dumps(dict(status=status,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kwargs),indent=2)+chr(10));print(status,flush=True)
def cli(script,*args):
 p=subprocess.run([sys.executable,'validation/'+script]+list(args),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 (R/(script+'.log')).write_text(p.stdout);assert p.returncode==0,(script,p.stdout[-1000:])
try:
 pid=int(sys.argv[1]);start=time.monotonic();state('WAITING_FOR_INTEGRATION')
 while pathlib.Path('/proc',str(pid)).exists():
  if time.monotonic()-start>600:raise RuntimeError('integration wait exceeded')
  time.sleep(5)
 tests=[json.loads(x) for x in (R/'tests/integration.jsonl').read_text().splitlines()];assert len(tests)==14 and all(x['status']=='PASSED' for x in tests)
 state('SUPPLEMENTARY_CHECKS');cli('v47_supplementary.py');state('FREEZING');cli('v47_round.py','freeze');state('COLLECTING',planned_runs=27);cli('v47_round.py','collect');state('COLLECTION_COMPLETE',runs=27)
except Exception as e:state('BLOCKED_OR_FAILED',error=str(e),traceback=traceback.format_exc());raise
