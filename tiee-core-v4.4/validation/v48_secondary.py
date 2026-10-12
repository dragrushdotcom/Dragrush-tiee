import json,pathlib,statistics
R=pathlib.Path('results/v48');rows=[json.loads(s) for s in (R/'runs.jsonl').read_text().splitlines()];profiles={r['index']:r for r in map(json.loads,(R/'profiles.jsonl').read_text().splitlines())};out={}
for stage in ('training','heldout'):
 out[stage]={}
 for variant in ('baseline','candidate'):
  selected=[r for r in rows if r['stage']==stage and r['variant']==variant];counts=[]
  for r in selected:
   statements=[s for s in profiles[r['index']]['statements'] if s['query'].startswith('SELECT id FROM events') and 'lease_until<=now()' in s['query']];assert len(statements)==1;counts.append(statements[0]['calls'])
  out[stage][variant]=dict(relay_recovery_scan_calls_mean=statistics.mean(counts),raw_counts=counts)
 out[stage]['candidate_scan_change']=out[stage]['candidate']['relay_recovery_scan_calls_mean']/out[stage]['baseline']['relay_recovery_scan_calls_mean']-1
(R/'secondary_diagnostics.json').write_text(json.dumps(dict(scope='Exploratory supporting query counters, not adoption endpoints; includes warmup, measurement and immediate postmeasurement read; no wait observer in comparisons',by_stage=out),indent=2)+chr(10));print('SECONDARY_DIAGNOSTICS_WRITTEN')
