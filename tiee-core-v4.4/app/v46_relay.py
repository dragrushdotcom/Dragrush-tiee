import time
from .v46_store import migrate,relay_once
if __name__=='__main__':
    migrate()
    while True:
        try: relay_once();time.sleep(.005)
        except Exception as exc: print('v46 relay retry',type(exc).__name__,flush=True);time.sleep(.1)
