import math,os,time
from .v47_store import migrate,relay_once

def poll_seconds():
 value=float(os.environ.get('RELAY_POLL_SECONDS','0.005'))
 if not math.isfinite(value) or not 0.005<=value<=0.1:raise ValueError('RELAY_POLL_SECONDS must be finite and 0.005..0.1')
 return value

if __name__=='__main__':
 interval=poll_seconds();migrate()
 while True:
  try:relay_once();time.sleep(interval)
  except Exception as exc:print('v48 relay retry',type(exc).__name__,flush=True);time.sleep(.1)
