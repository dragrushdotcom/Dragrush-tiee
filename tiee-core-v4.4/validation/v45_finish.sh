#!/usr/bin/env bash
set -eu
cd /workspaces/Dragrush-tiee-v45/tiee-core-v4.4
set -a
. ./.env.v45
set +a
export COMPOSE_PROJECT_NAME=tiee45pilot
while pgrep -f '^python validation/v45_benchmark.py$' >/dev/null; do sleep 2; done
python - <<'PY'
import json,pathlib
rows=json.loads(pathlib.Path('results/v45/randomized-benchmark.json').read_text())
assert len(rows)==30 and all(r['integrity_pass'] for r in rows)
PY
/tmp/tiee45-analysis/bin/python validation/v45_analyze.py >results/v45/analysis.log 2>&1
echo BASELINE_ANALYSIS_PASS
docker compose -p tiee45pilot -f docker-compose.yml -f compose.validation.yml up -d --build >results/v45/pool-build.log 2>&1
python validation/v45_regression.py >results/v45/regression-final-default.log 2>&1
echo DEFAULT_REGRESSION_PASS
export PG_POOL_SIZE=8
docker compose -p tiee45pilot -f docker-compose.yml -f compose.validation.yml up -d --force-recreate gateway relay worker >results/v45/pool-startup.log 2>&1
python validation/validate.py integration >results/v45/pool-integration.log 2>&1
python validation/v45_extended.py >results/v45/pool-extended.log 2>&1
python validation/v45_regression.py >results/v45/pool-regression.log 2>&1
echo POOL_RECOVERY_ALL_PASS
unset PG_POOL_SIZE
python validation/v45_optimize.py >results/v45/optimization-run.log 2>&1
/tmp/tiee45-analysis/bin/python validation/v45_opt_analyze.py >results/v45/optimization-analysis.log 2>&1
echo OPTIMIZATION_AND_ANALYSIS_PASS
