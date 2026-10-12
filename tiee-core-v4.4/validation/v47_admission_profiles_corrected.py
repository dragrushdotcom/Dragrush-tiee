import json,pathlib
import v47_harness as h
R=pathlib.Path('results/v47/corrected');rows=[json.loads(x) for x in (R/'runs.jsonl').read_text().splitlines()];assert len(rows)==27;profiles={}
query="SELECT COALESCE(json_agg(row_to_json(t)),'[]'::json) FROM (SELECT DISTINCT ON (id) id,decision FROM decision_history ORDER BY id,seq) t"
for r in rows:
 data=json.loads(h.dc('exec','-T','postgres','psql','-U','tiee','-d',r['database'],'-At','-c',query).stdout);first={x['id']:x['decision'] for x in data};selected={x['id']:first[x['id']] for x in r['ledger'] if x['id'] in first};assert all('admission_lock_wait_seconds' in d and 'admission_prewrite_seconds' in d for d in selected.values());assert all(x['id'] in selected for x in r['ledger'] if x['state']!='REFUSED');profiles[str(r['index'])]=selected
(R/'admission_profiles.json').write_text(json.dumps(dict(source='first committed SQL decision_history record; read after measurement; no raw ledger replacement',by_run=profiles),indent=2)+chr(10));print('ADMISSION_HISTORY_VERIFIED',sum(len(x) for x in profiles.values()))
