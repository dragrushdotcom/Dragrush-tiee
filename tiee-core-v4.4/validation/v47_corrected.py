import datetime,hashlib,json,pathlib,sys
import v47_round as original
R=pathlib.Path('results/v47/corrected');P=R/'plan.json'
def own_hash():return hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
if __name__=='__main__':
 if sys.argv[1]=='freeze':
  p=json.loads(pathlib.Path('results/v47/plan.json').read_text());p.update(version='v47-corrected-regression-1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256=original.hashes(),runner_sha256=own_hash(),base_commit='a7abc0ecc330af583c5a85ccee13c6d59d104a28',comparison='Exact prior workload/order repeat after Gateway backlog 5 to 128; diagnostic regression, not independent held-out confirmation',acceptance='No HTTP/poll/drain errors, unresolved HELD or missing terminal timing; per-condition exact one-sided Clopper-Pearson 95% valid-loss bound <=1% under synthetic IID assumption')
  raw=json.dumps(p,indent=2)+chr(10);P.write_text(raw);(R/'plan.sha256').write_text(hashlib.sha256(raw.encode()).hexdigest()+chr(10));print('CORRECTED_FROZEN',len(p['jobs']))
 else:
  assert json.loads(P.read_text())['runner_sha256']==own_hash()
  original.R=R;original.P=P
  try:original.collect()
  except Exception as e:
   import traceback
   (R/'round_failure.json').write_text(json.dumps(dict(status='FAILED_OR_INCOMPLETE',error=str(e),traceback=traceback.format_exc()),indent=2)+chr(10));raise
