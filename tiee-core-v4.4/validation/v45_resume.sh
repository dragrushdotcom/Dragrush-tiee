#!/usr/bin/env bash
set -eu
cd /workspaces/Dragrush-tiee-v45/tiee-core-v4.4
set -a
. ./.env.v45
set +a
export COMPOSE_PROJECT_NAME=tiee45pilot PG_POOL_SIZE=8
python validation/v45_extended.py >results/v45/pool-extended.log 2>&1
python validation/v45_regression.py >results/v45/pool-regression.log 2>&1
echo POOL_RECOVERY_ALL_PASS
unset PG_POOL_SIZE
python validation/v45_optimize.py >results/v45/optimization-run.log 2>&1
/tmp/tiee45-analysis/bin/python validation/v45_opt_analyze.py >results/v45/optimization-analysis.log 2>&1
echo OPTIMIZATION_AND_ANALYSIS_PASS
