import json,os,pathlib
from app.v48_relay import poll_seconds
cases=[]
for value in ('0.005','0.02','0.1','0','-1','0.004','0.101','nan','inf','-inf','invalid'):
 os.environ['RELAY_POLL_SECONDS']=value
 try:result=poll_seconds();valid=True
 except ValueError:result=None;valid=False
 assert valid==(value in ('0.005','0.02','0.1'));cases.append(dict(value=value,accepted=valid,result=result,status='PASSED'))
os.environ.pop('RELAY_POLL_SECONDS');assert poll_seconds()==.005
pathlib.Path('results/v48/poll_config.json').write_text(json.dumps(dict(status='PASSED',default_seconds=.005,cases=cases),indent=2)+chr(10));print('POLL_CONFIG_BOUNDS_PASSED',len(cases))
