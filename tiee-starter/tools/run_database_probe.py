"""Exploratory synchronous DB timing probe; NOT Benchmark v1.0 qualification."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import secrets
import subprocess
import sys
import time
import uuid


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def percentile(values, p):
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(len(values) * p) - 1)]


def latency(values):
    return {'count': len(values), 'p50_ms': percentile(values, .50),
            'p95_ms': percentile(values, .95), 'p99_ms': percentile(values, .99)}


def verify(conn, run_id, truth, count):
    from benchmark.oracle import reconcile
    actual = [dict(zip(('event_id', 'digest', 'processor_version'), row)) for row in
              conn.execute('SELECT event_id,digest,processor_version FROM tiee_outputs WHERE run_id=%s',
                           (run_id,)).fetchall()]
    states = dict(conn.execute('SELECT state,count(*) FROM tiee_events WHERE run_id=%s GROUP BY state',
                               (run_id,)).fetchall())
    audit = dict(conn.execute('SELECT action,count(*) FROM tiee_audit WHERE run_id=%s GROUP BY action',
                              (run_id,)).fetchall())
    expected_states = {k: v for k, v in {'COMPLETED': len(truth), 'REJECTED': count-len(truth)}.items() if v}
    expected_audit = {'INTENT': count, **expected_states}
    report = reconcile(truth, actual)
    report.update(states=states, audit_actions=audit)
    report['pass'] = report['pass'] and states == expected_states and audit == expected_audit
    return report


def inside(args):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from benchmark.generator import generate
    from benchmark.oracle import expected
    from shared.processor import canonical
    from storage.postgres import PostgresStore, Run
    out = Path('/evidence')
    trials = []
    summary = {'status': 'ERROR', 'stage': 'exploratory-synchronous-database-probe-v1',
               'benchmark_v1_qualified': False, 'performance_claim': None,
               'total_system_cpu_measured': False, 'total_system_ram_measured': False,
               'network_mode': 'shared-db-namespace-loopback',
               'load_model': 'one outstanding synchronous submit; no scheduled arrivals',
               'latency_boundary': 'submit call through successful commit and connection close',
               'cache_policy': 'fresh database per launch; retained per-trial rows; 10 warmup events per trial',
               'limitations': ['No HTTP or broker', 'No saturation or arrival-rate claim',
                              'No power-loss or restart test', 'Client CPU excludes PostgreSQL',
                              'Small samples; tail percentiles are exploratory',
                              'T uses deterministic eligibility, not learned probabilities'],
               'config': {'count': args.count, 'iterations': args.iterations, 'seeds': args.seeds,
                          'useful_percentages': [100, 50, 10]}, 'trials': trials}
    try:
        common = dict(host='127.0.0.1', dbname='tiee_test', connect_timeout=5)
        admin = make_conninfo(**common, user='tiee_migrator', password=os.environ['TIEE_ADMIN_PASSWORD'])
        password = os.environ['TIEE_APP_PASSWORD']
        with psycopg.connect(admin, autocommit=True) as conn:
            with conn.transaction():
                conn.execute(Path('storage/schema.sql').read_text())
                conn.execute(sql.SQL('CREATE ROLE tiee_app LOGIN PASSWORD {}').format(sql.Literal(password)))
                conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
                conn.execute('GRANT USAGE ON SCHEMA public TO tiee_app')
                conn.execute('GRANT SELECT, INSERT ON tiee_runs,tiee_events,tiee_outputs,tiee_audit TO tiee_app')
                conn.execute('GRANT UPDATE ON tiee_events TO tiee_app')
                conn.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tiee_app')
        dsn = make_conninfo(**common, user='tiee_app', password=password)
        os.environ.pop('TIEE_ADMIN_PASSWORD', None)
        os.environ.pop('TIEE_APP_PASSWORD', None)
        store = PostgresStore.from_dsn(dsn)
        with psycopg.connect(dsn, autocommit=True) as evaluator:
            write(out/'environment.json', {'python': sys.version, 'platform': platform.platform(),
                  'postgres': evaluator.execute('SELECT version()').fetchone()[0],
                  'synchronous_commit': evaluator.execute('SHOW synchronous_commit').fetchone()[0],
                  'psycopg': psycopg.__version__, 'runtime_role': 'tiee_app'})
            for seed_index, seed in enumerate(args.seeds):
                order = ('B0', 'B1', 'T')
                order = order[seed_index % 3:] + order[:seed_index % 3]
                for mix in (100, 50, 10):
                    records = list(generate(seed, args.count, mix, 10))
                    payloads = [canonical(r['event']) for r in records]
                    fixture = b''.join(p + b'\n' for p in payloads)
                    (out/f'workload-s{seed}-m{mix}.jsonl').write_bytes(fixture)
                    warm = list(generate(seed + 1000000, 100, mix, 10))[:10]
                    for iterations in args.iterations:
                        truth = expected(records, iterations)
                        useful_ids = {r['event_id'] for r in truth}
                        for arm in order:
                            name = f's{seed}-m{mix}-k{iterations}-{arm}'
                            report = {'run_id': name, 'seed': seed, 'useful_percent': mix,
                                      'iterations': iterations, 'arm': arm, 'order': list(order),
                                      'workload_sha256': hashlib.sha256(fixture).hexdigest(),
                                      'status': 'ERROR', 'successful_submissions': 0, 'error_count': 0}
                            trials.append(report)
                            warm_run = Run('warm-' + name, arm, iterations)
                            store.register(warm_run)
                            for r in warm:
                                store.submit(warm_run, canonical(r['event']))
                            warm_report = verify(evaluator, warm_run.run_id, expected(warm, iterations), len(warm))
                            if not warm_report['pass']:
                                raise RuntimeError('warmup correctness failed')
                            run = Run(name, arm, iterations)
                            store.register(run)
                            samples = []
                            cpu_start, start = time.process_time_ns(), time.perf_counter_ns()
                            try:
                                for raw, record in zip(payloads, records):
                                    event_id = record['event']['event_id']
                                    sent = time.perf_counter_ns()
                                    response = store.submit(run, raw)
                                    elapsed = (time.perf_counter_ns() - sent)/1e6
                                    samples.append({'event_id': event_id, 'latency_ms': elapsed,
                                                    'state': response['state'], 'replayed': response['replayed'],
                                                    'expected_useful': event_id in useful_ids})
                            except Exception as exc:
                                report.update(error_count=1, error_type=type(exc).__name__)
                            wall = (time.perf_counter_ns() - start)/1e9
                            client_cpu = (time.process_time_ns() - cpu_start)/1e9
                            with (out/f'{name}-samples.jsonl').open('x') as f:
                                for sample in samples:
                                    f.write(json.dumps(sample) + '\n')
                            correct = verify(evaluator, name, truth, args.count)
                            useful = [r['latency_ms'] for r in samples if r['expected_useful'] and r['state']=='COMPLETED']
                            rejected = [r['latency_ms'] for r in samples if not r['expected_useful'] and r['state']=='REJECTED']
                            ok = correct['pass'] and not report['error_count'] and len(samples)==args.count
                            ok = ok and all(not r['replayed'] and
                                 r['state']==('COMPLETED' if r['expected_useful'] else 'REJECTED') for r in samples)
                            report.update(status='PASS' if ok else 'FAIL', correctness=correct,
                                          successful_submissions=len(samples), wall_seconds=wall,
                                          client_cpu_seconds=client_cpu,
                                          client_process_peak_rss_kib_cumulative=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                          useful_latency=latency(useful), rejection_latency=latency(rejected),
                                          useful_completion_fraction=len(useful)/len(truth),
                                          useful_completions_per_wall_second=len(useful)/wall,
                                          logical_rows={'events': sum(correct['states'].values()),
                                                        'outputs': correct['actual_count'],
                                                        'audit': sum(correct['audit_actions'].values())})
                            write(out/'probe-summary.json', summary)
                            print(json.dumps({'trial': name, 'status': report['status'],
                                              'useful_per_second': report['useful_completions_per_wall_second']}), flush=True)
            summary['status'] = 'PASS' if all(r['status']=='PASS' for r in trials) else 'FAIL'
    except Exception as exc:
        summary['error_type'] = type(exc).__name__
    finally:
        write(out/'probe-summary.json', summary)
    print(json.dumps({'status': summary['status'], 'trials': len(trials)}), flush=True)
    return 0 if summary['status']=='PASS' else 1


def launch(args):
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['docker', 'info'], check=True, capture_output=True)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, TIEE_ADMIN_PASSWORD=secrets.token_hex(24), TIEE_APP_PASSWORD=secrets.token_hex(24))
    project = 'tieeprobe_' + uuid.uuid4().hex[:12]
    compose = {'services': {
        'db': {'image': 'postgres:16-bookworm', 'environment': {
            'POSTGRES_USER': 'tiee_migrator', 'POSTGRES_PASSWORD': '${TIEE_ADMIN_PASSWORD}', 'POSTGRES_DB': 'tiee_test'},
            'volumes': ['probe_data:/var/lib/postgresql/data'],
            'healthcheck': {'test': ['CMD-SHELL', 'pg_isready -h 127.0.0.1 -U tiee_migrator -d tiee_test'],
                            'interval': '2s', 'timeout': '3s', 'retries': 30}, 'networks': ['probe_net']},
        'probe': {'build': {'context': str(root), 'dockerfile': 'Dockerfile.integration'},
                  'user': f'{os.getuid()}:{os.getgid()}',
                  'environment': {'TIEE_ADMIN_PASSWORD': '${TIEE_ADMIN_PASSWORD}', 'TIEE_APP_PASSWORD': '${TIEE_APP_PASSWORD}'},
                  'volumes': [f'{out}:/evidence'], 'network_mode': 'service:db',
                  'depends_on': {'db': {'condition': 'service_healthy'}},
                  'command': ['python', '-m', 'tools.run_database_probe', '--inside', '--count', str(args.count),
                              '--iterations', *map(str, args.iterations), '--seeds', *map(str, args.seeds)]}},
        'networks': {'probe_net': {'internal': True}}, 'volumes': {'probe_data': {}}}
    write(out/'compose.probe.json', compose)
    source = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ('tools', 'shared', 'storage', 'benchmark')
              for p in sorted((root/folder).rglob('*')) if p.suffix in ('.py', '.sql')}
    for file in ('Dockerfile.integration', 'requirements-postgres.txt'):
        source[file] = hashlib.sha256((root/file).read_bytes()).hexdigest()
    write(out/'source-sha256.json', source)
    info = subprocess.run(['docker','info','--format','{{json .}}'], capture_output=True, text=True)
    if info.returncode == 0:
        raw = json.loads(info.stdout)
        write(out/'host.json', {k: raw.get(k) for k in ('NCPU','MemTotal','ServerVersion','KernelVersion','Architecture','OperatingSystem')})
    git = subprocess.run(['git','rev-parse','HEAD'], cwd=root, capture_output=True, text=True)
    base = ['docker','compose','-f',str(out/'compose.probe.json'),'-p',project]
    steps, code = [], 1
    def execute(suffix, label):
        result = subprocess.run(base+suffix, env=env, cwd=root, capture_output=True, text=True)
        log = result.stdout + result.stderr
        for key in ('TIEE_ADMIN_PASSWORD','TIEE_APP_PASSWORD'):
            log = log.replace(env[key], '[redacted]')
        (out/f'{label}.log').write_text(log)
        steps.append({'step':label, 'exit_code':result.returncode})
        print(f'{label}: exit {result.returncode}', flush=True)
        return result.returncode
    try:
        for suffix, label in [(['build','probe'],'build'),
                              (['up','-d','--wait','--wait-timeout','90','db'],'up'),
                              (['run','--rm','-T','probe'],'run')]:
            if execute(suffix, label):
                break
        else:
            code = 0 if json.loads((out/'probe-summary.json').read_text())['status']=='PASS' else 1
        execute(['images','--format','json'], 'images')
    finally:
        stop = execute(['stop'], 'stop')
        write(out/'launcher.json', {'project': project, 'steps': steps, 'exit_code': code,
                                   'stop_exit_code': stop, 'volume_retained': True,
                                   'git_head': git.stdout.strip(), 'source_hashes_authoritative': True})
        print(f'Evidence: {out}; probe exit: {code}', flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--iterations', nargs='+', type=int, default=[0, 1000])
    parser.add_argument('--seeds', nargs='+', type=int, default=[101,202,303,404,505])
    args = parser.parse_args()
    if args.count not in range(100, 10001, 100):
        parser.error('count must be 100..10000 and divisible by 100')
    if any(k < 0 or k > 10000 for k in args.iterations) or len(set(args.iterations))!=len(args.iterations):
        parser.error('iterations must be distinct integers 0..10000')
    if any(not 0 <= s < 2**32-1000000 for s in args.seeds) or len(set(args.seeds))!=len(args.seeds):
        parser.error('seeds must be distinct integers in 0..4293967295 (reserve warmup offset)')
    if not args.inside and args.out is None:
        parser.error('--out is required')
    return inside(args) if args.inside else launch(args)


if __name__ == '__main__':
    raise SystemExit(main())
