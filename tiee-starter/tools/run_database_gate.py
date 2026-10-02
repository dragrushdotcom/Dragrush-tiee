"""Launch only a new isolated test project; retain DB volume and evidence."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new evidence directory')
    args = parser.parse_args()
    if not shutil.which('docker'):
        parser.error('Docker is unavailable; no database tests were run')
    subprocess.run(['docker','compose','version'], check=True, capture_output=True)
    subprocess.run(['docker','info'], check=True, capture_output=True)
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    project = 'tieecheck_' + uuid.uuid4().hex[:12]
    env = dict(os.environ)
    env.update(TIEE_ADMIN_PASSWORD=secrets.token_hex(24), TIEE_APP_PASSWORD=secrets.token_hex(24),
               TIEE_EVIDENCE_DIR=str(output), TIEE_TEST_UID=str(getattr(os, 'getuid', lambda:10001)()),
               TIEE_TEST_GID=str(getattr(os, 'getgid', lambda:10001)()))
    command = ['docker','compose','-f',str(root/'compose.integration.yaml'),'-p',project]
    steps = []
    code = 1
    try:
        # Do not log compose config: it contains generated disposable credentials.
        for suffix in (['build','tests'], ['up','-d','--wait','--wait-timeout','90','db'],
                       ['run','--rm','-T','tests']):
            result = subprocess.run(command+suffix, env=env, cwd=root, capture_output=True, text=True)
            label = suffix[0]
            # Image installation/build output is safe; remove generated passwords defensively.
            text = result.stdout + result.stderr
            for key in ('TIEE_ADMIN_PASSWORD','TIEE_APP_PASSWORD'):
                text = text.replace(env[key], '[redacted]')
            (output/f'{label}.log').write_text(text)
            steps.append({'step':label, 'exit_code':result.returncode})
            if result.returncode:
                break
        else:
            report = json.loads((output/'database-gate.json').read_text())
            code = 0 if report['status'] == 'PASS' else 1
        images = subprocess.run(command+['images','--format','json'], env=env, cwd=root, capture_output=True, text=True)
        (output/'images.json').write_text(images.stdout)
    finally:
        # Stop only this generated project; no volumes, containers, or data deleted here.
        stopped = subprocess.run(command+['stop'], env=env, cwd=root, capture_output=True, text=True)
        (output/'launcher.json').write_text(json.dumps({'project': project, 'steps': steps,
            'gate_exit_code': code, 'stop_exit_code': stopped.returncode,
            'volume_retained': True, 'credentials_persisted': False}, indent=2))
        print(f'Evidence: {output}; project: {project}; gate exit: {code}')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
