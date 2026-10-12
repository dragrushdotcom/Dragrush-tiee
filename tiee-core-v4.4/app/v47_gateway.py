import json,os,time
from http.server import ThreadingHTTPServer
from .gateway import Handler as LegacyHandler
from .common import pg,fingerprint
from .v47_policy import decide,features
from .v47_store import migrate,audit,ACTIVE
class Server(ThreadingHTTPServer):
    request_queue_size=128

class Handler(LegacyHandler):
    def do_POST(self):
        if self.path!='/ingest' or self.headers.get('X-API-Key')!=os.environ['API_KEY']: return self.respond(403,dict(error='forbidden'))
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=65536: raise ValueError('length')
            event=json.loads(self.rfile.read(length));fp=fingerprint(event)
            if not isinstance(event,dict) or set(event)!={'id','kind','rounds','body'} or not isinstance(event['id'],str): raise ValueError('envelope')
        except Exception: return self.respond(400,dict(error='malformed'))
        try:
            receipt=None;status=202
            transaction_start=time.perf_counter()
            with pg() as c:
                lock_start=time.perf_counter();c.execute('SELECT pg_advisory_xact_lock(73421)');lock_wait=time.perf_counter()-lock_start;lock_acquired=time.perf_counter()
                old=c.execute('SELECT fingerprint,receipt,disposition FROM events WHERE id=%s',(event['id'],)).fetchone()
                if old:
                    if old[0]!=fp: status=409;receipt=dict(error='id_conflict')
                    else: status=200;receipt=old[1] or dict(status=old[2],legacy=True)
                else:
                    # Model errors refuse safely; duplicate receipts do not depend on a working model.
                    try: features(event)
                    except Exception: status=400;receipt=dict(error='malformed')
                    try:
                        if receipt is None: d=decide(event)
                    except Exception: status=503;receipt=dict(error='scorer_unavailable',retry_after=1)
                    if receipt is None:
                        d['admission_lock_wait_seconds']=lock_wait;d['admission_prewrite_seconds']=time.perf_counter()-transaction_start
                        accepted=d['decision']!='REJECT'
                        count=c.execute('SELECT count(*) FROM events WHERE state IN '+ACTIVE).fetchone()[0]
                        if accepted and count>=int(os.environ.get('QUEUE_CAPACITY','1000')):
                            status=503;receipt=dict(error='capacity_retry',retry_after=1)
                        else:
                            disposition='ACCEPT' if accepted else 'REJECT';state={'ALLOW':'PENDING','DEFER':'DEFERRED','REJECT':'REJECTED'}[d['decision']]
                            receipt=dict(status=disposition,decision=d['decision'],receipt_id=event['id'],policy_version=d['policy_version'],model_version=d['model_version'],payload_hash=fp)
                            status=202 if accepted else 200
                            c.execute("INSERT INTO events(id,fingerprint,payload,disposition,state,receipt,decision,deadline,next_at,priority) VALUES(%s,%s,%s,%s,%s,%s,%s,now()+(%s*interval '1 millisecond'),now()+interval '0.25 seconds',%s)",(event['id'],fp,json.dumps(event),disposition,state,json.dumps(receipt),json.dumps(d),d['deadline_ms'],d['net_ev']/max(event['rounds'],1)))
                            c.execute('INSERT INTO decision_history(id,decision) VALUES(%s,%s)',(event['id'],json.dumps(d)));audit(c,event['id'],d['decision'])
            commit_complete=time.perf_counter()
            if os.environ.get("TIEE_ADMISSION_PROFILE") == "1": print("TIEE_ADMISSION_PROFILE "+json.dumps({"status":status,"connection_and_begin_seconds":lock_start-transaction_start,"advisory_lock_wait_seconds":lock_wait,"lock_to_commit_upper_bound_seconds":commit_complete-lock_acquired,"transaction_total_seconds":commit_complete-transaction_start},sort_keys=True),flush=True)
            # Never write the response until SQL context has successfully committed.
            return self.respond(status,receipt)
        except Exception as exc:
            print('v46 admission transaction failed',type(exc).__name__,flush=True);return self.respond(503,dict(error='database_unavailable',retry_after=1))
if __name__=='__main__':
    migrate();Server(('0.0.0.0',8087),Handler).serve_forever()
