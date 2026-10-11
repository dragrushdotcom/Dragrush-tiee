import json,os,pathlib,subprocess,time
import validate as v
ROOT=pathlib.Path('results/v46/tests');ROOT.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,COMPOSE_PROJECT_NAME='tiee46legacy')
for line in pathlib.Path('.env.v46').read_text().splitlines():
    k,value=line.split('=',1);env[k]=value
base=['docker','compose','-p','tiee46legacy','--env-file','.env.v46','-f','docker-compose.yml','-f','compose.validation.yml']
for service in ('gateway','relay','worker','probe','network_anchor'):subprocess.run(['docker','tag','tiee46pilot-gateway','tiee46legacy-'+service],check=True)
summary=[]
for pool in (0,8):
    env['PG_POOL_SIZE']=str(pool);dest=ROOT/('legacy_pool'+str(pool));dest.mkdir(exist_ok=True);env['VALIDATION_RESULTS']=str(dest)
    subprocess.run(base+['up','-d','--no-build','--force-recreate'],env=env,check=True,capture_output=True,text=True)
    time.sleep(.5)
    for script in ('validate.py','v45_extended.py','v45_regression.py'):
        p=subprocess.run(['python','validation/'+script],env=env,capture_output=True,text=True);(dest/(script+'.log')).write_text(p.stdout+p.stderr);summary.append(dict(pool=pool,script=script,exit=p.returncode));print(summary[-1],flush=True)
subprocess.run(base+['stop','-t','1'],env=env,check=True,capture_output=True)
(ROOT/'legacy_summary.json').write_text(json.dumps(summary,indent=2));print('LEGACY FINISHED',flush=True)
