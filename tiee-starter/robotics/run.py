"""Run the S01 baseline and export a self-contained replay. No external packages."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time
from robotics.baseline import simulate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--service-ms',type=int,choices=(10,50,100),default=10)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    wall,cpu=time.perf_counter(),time.process_time()
    config,summary,trace,frames,events=simulate(a.service_ms)
    summary['measured_simulator_wall_seconds']=time.perf_counter()-wall
    summary['measured_simulator_cpu_seconds']=time.process_time()-cpu
    summary['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary['measurement_scope']='whole simulation including sensing, planning, mapping and in-memory recording; file export excluded'
    source=Path(__file__).parent
    manifest={'python':sys.version,'platform':platform.platform(),
              'source_sha256':{str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest()
                               for f in sorted(source.rglob('*')) if f.suffix in ('.py','.html')},
              'spec_sha256':hashlib.sha256((source.parent/'ROBOTICS_SPEC_v0.1.md').read_bytes()).hexdigest()}
    for name,data in [('summary.json',summary),('config.json',config),('manifest.json',manifest)]:
        (a.out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    for name,rows in [('trajectory.jsonl',trace),('sensor-frames.jsonl',frames),('events.jsonl',events)]:
        with (a.out/name).open('x') as f:
            for row in rows:
                f.write(json.dumps(row,allow_nan=False)+'\n')
    replay=(source/'replay.html').read_text()
    data=json.dumps({'config':config,'summary':summary,'trace':trace},allow_nan=False).replace('<','\\u003c')
    (a.out/'replay.html').write_text(replay.replace('/*REPLAY_DATA*/null',data))
    files=sorted(f for f in a.out.iterdir() if f.is_file())
    (a.out/'checksums.sha256').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in files))
    print(json.dumps(summary,indent=2))
    print('Replay:',a.out/'replay.html')
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
