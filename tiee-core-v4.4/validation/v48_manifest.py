import datetime,gzip,hashlib,json,pathlib,subprocess,tarfile
R=pathlib.Path('results/v48')
def git(*a):return subprocess.check_output(['git']+list(a),text=True)
def main():
 previous=json.loads((pathlib.Path('results/v47')/'preservation.json').read_text());assert git('-C','/workspaces/Dragrush-tiee','status','--porcelain')==previous['original_status'];assert git('-C','/workspaces/Dragrush-tiee','rev-parse','HEAD').strip()==previous['original_head'];assert git('-C','/workspaces/Dragrush-tiee-v46','rev-parse','HEAD').strip()==previous['base_commit'];assert not git('-C','/workspaces/Dragrush-tiee-v46','status','--porcelain');assert pathlib.Path('/workspaces/tiee-backup-20261010T100752Z').is_dir()
 archive=pathlib.Path('/workspaces/tiee-preserve-v46-20261011T090841Z/repository.tar.gz');checked=0
 with tarfile.open(archive) as tar:
  for member in tar:
   if not member.isfile():continue
   parts=list(pathlib.PurePosixPath(member.name).parts)
   if parts and parts[0]=='Dragrush-tiee':parts=parts[1:]
   assert '..' not in parts
   if '.git' in parts:continue
   target=pathlib.Path('/workspaces/Dragrush-tiee').joinpath(*parts);assert target.is_file(),str(target);assert hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(tar.extractfile(member).read()).digest(),str(target);checked+=1
 assert checked>=400
 (R/'preservation_final.json').write_text(json.dumps(dict(status='PASSED',original_status_unchanged=True,original_head_verified=True,v46_head_verified=True,v46_clean=True,backups_retained=True,original_files_byte_verified=checked,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+chr(10))
 private=[]
 for line in pathlib.Path('.env.v47').read_text().splitlines():
  if '=' in line:
   k,v=line.split('=',1)
   if k in ('API_KEY','POSTGRES_PASSWORD'):private.append(v.encode())
 names=git('ls-files','--cached','--others','--exclude-standard','.').splitlines();hashes={};archives={}
 for name in names:
  p=pathlib.Path(name)
  if not p.is_file() or name=='results/v48/artifact_manifest.json':continue
  raw=p.read_bytes();plain=gzip.decompress(raw) if p.suffix=='.gz' else raw;assert not any(s in plain for s in private),name;assert len(raw)<95*1048576,name;hashes[name]=hashlib.sha256(raw).hexdigest()
  if p.name=='runs.jsonl.gz':archives[name]=dict(raw_sha256=hashlib.sha256(plain).hexdigest(),runs=len(plain.splitlines()))
 (R/'artifact_manifest.json').write_text(json.dumps(dict(sha256=hashes,raw_archives=archives,private_values_scan='PASSED'),indent=2)+chr(10));print('PRESERVATION_AND_ARTIFACTS_VERIFIED',len(hashes))
if __name__=='__main__':main()
