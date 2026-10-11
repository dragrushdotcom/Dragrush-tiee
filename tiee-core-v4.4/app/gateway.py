import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .common import pg, ensure_schema, fingerprint, eligible

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/ingest' or self.headers.get('X-API-Key') != os.environ['API_KEY']:
            return self.respond(403, {'error':'forbidden'})
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 65536: raise ValueError('invalid payload size')
            event = json.loads(self.rfile.read(length))
            if not isinstance(event,dict) or set(event)!={'id','kind','rounds','body'}: raise ValueError('invalid keys')
            if not isinstance(event['id'],str) or not 0 < len(event['id']) <= 128: raise ValueError('invalid id')
            if event['kind'] not in ('valid','bot'): raise ValueError('invalid kind')
            if type(event['rounds']) is not int or not 1 <= event['rounds'] <= 20000: raise ValueError('invalid rounds')
            if not isinstance(event['body'],str) or len(event['body'])>10000: raise ValueError('invalid body')
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.respond(400, {'error':'malformed'})
        fp=fingerprint(event)
        decision='ACCEPT' if eligible(event,os.environ.get('POLICY','baseline')) else 'REJECT'
        try:
            with pg() as c:
                # Serializes capacity check and admission across parallel HTTP handlers.
                c.execute('SELECT pg_advisory_xact_lock(73421)')
                old=c.execute('SELECT fingerprint,disposition FROM events WHERE id=%s',(event['id'],)).fetchone()
                if old:
                    if old[0]!=fp: return self.respond(409,{'error':'id_conflict'})
                    return self.respond(200,{'status':old[1], 'duplicate':True})
                count=c.execute("SELECT count(*) FROM events WHERE disposition='ACCEPT' AND state!='DONE'").fetchone()[0]
                if decision=='ACCEPT' and count>=int(os.environ.get('QUEUE_CAPACITY','1000')):
                    return self.respond(503,{'error':'capacity_retry'})
                state='PENDING' if decision=='ACCEPT' else 'REJECTED'
                c.execute('INSERT INTO events (id,fingerprint,payload,disposition,state) VALUES (%s,%s,%s,%s,%s)',(event['id'],fp,json.dumps(event),decision,state))
                c.execute('INSERT INTO audit(id,action) VALUES(%s,%s)',(event['id'],decision))
            return self.respond(202,{'status':decision})
        except Exception as e:
            print('gateway error:',repr(e),flush=True)
            return self.respond(500,{'error':'internal'})
    def respond(self,status,obj):
        payload=json.dumps(obj).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def log_message(self,*args): pass

if __name__=='__main__':
    ensure_schema()
    ThreadingHTTPServer(('0.0.0.0',8087),Handler).serve_forever()
