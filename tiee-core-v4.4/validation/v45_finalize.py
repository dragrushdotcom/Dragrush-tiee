"""Record non-secret runtime metadata and hash the final engineering evidence."""
import datetime,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/v45'
DC=['docker','compose','-p','tiee45pilot','-f','docker-compose.yml','-f','compose.validation.yml']
def run(*args):return subprocess.check_output(args,text=True,stdin=subprocess.DEVNULL).strip()
def main():
 data={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base_commit':run('git','rev-parse','6e12b50'),'branch':run('git','branch','--show-current'),'services':{}}
 for service in ['gateway','relay','worker','redis','postgres','probe']:
  cid=run(*DC,'ps','-q',service)
  image=run('docker','inspect','--format','{{.Image}}',cid)
  data['services'][service]={'image_id':image,'status':run('docker','inspect','--format','{{.State.Status}}',cid),'restart_count':int(run('docker','inspect','--format','{{.RestartCount}}',cid))}
 data['application_options']=json.loads(run(*DC,'exec','-T','gateway','python','-c',"import os,json;print(json.dumps({k:os.environ.get(k) for k in ['POLICY','PG_POOL_SIZE','QUEUE_CAPACITY','PILOT_DATABASE']}))"))
 data['application_packages']=run(*DC,'exec','-T','gateway','python','-m','pip','freeze').splitlines()
 data['redis_version']=run(*DC,'exec','-T','redis','redis-server','--version')
 data['postgres_version']=run(*DC,'exec','-T','postgres','postgres','--version')
 data['redis_aof_config']=run(*DC,'exec','-T','redis','redis-cli','CONFIG','GET','appendonly','appendfsync').splitlines()
 data['postgres_durability']=run(*DC,'exec','-T','postgres','psql','-U','tiee','-d','postgres','-Atc',"SELECT name||'='||setting FROM pg_settings WHERE name IN ('fsync','synchronous_commit','full_page_writes') ORDER BY name").splitlines()
 data['published_ports']={s:run('docker','inspect','--format','{{json .NetworkSettings.Ports}}',run(*DC,'ps','-q',s)) for s in ['gateway','redis','postgres']}
 (OUT/'final-runtime.json').write_text(json.dumps(data,indent=2)+'\n')
 files=list((ROOT/'app').glob('*.py'))+list((ROOT/'validation').glob('*.py'))+list((ROOT/'validation').glob('v45_*.sh'))+list(OUT.rglob('*'))+[ROOT/'requirements.txt',ROOT/'docker-compose.yml',ROOT/'compose.validation.yml',ROOT/'REPRODUCE_V4_5.md',ROOT/'V4_5_ENGINEERING_REPORT.md',ROOT.parent/'README.md']
 hashes={str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file() and p.name!='artifact-sha256.json' and '__pycache__' not in p.parts}
 (OUT/'artifact-sha256.json').write_text(json.dumps(hashes,indent=2,sort_keys=True)+'\n')
 print('FINAL_METADATA_AND_HASHES_PASS',len(hashes))
if __name__=='__main__':main()
