# Reproduce v4.8 relay polling experiment

Use the existing scaling potato Codespace, never create another. Work in a separate development worktree from the published tiee-core-v48-db-profile branch, preserving the original robotics branch and pending changes. Do not deploy or publish ports. Existing private test .env.v47 has mode 0600; never commit or print credentials. For an independent isolated replay, provision private test credentials as in REPRODUCE_V4_7.md and preserve all existing volumes/evidence.

Published results must first be moved to a preserved output directory in the replay worktree; do not overwrite results/v48/plan.json or raw attempts. Run from tiee-core-v4.4. The source/runtime hashes in plan.json are authoritative. The CPU/latency targets and analysis implementation were frozen before collection. Two stages use fresh distinct seeds and randomized paired order; the candidate stays fixed at 20ms.

Build one identical application image for all services/variants:

    DOCKER_BUILDKIT=0 docker build -t tiee47pilot-gateway .
    docker tag tiee47pilot-gateway tiee47pilot-relay
    docker tag tiee47pilot-gateway tiee47pilot-worker
    docker tag tiee47pilot-gateway tiee47pilot-probe
    docker tag tiee47pilot-gateway tiee47pilot-network_anchor
    mkdir -p results/v48
    python -u validation/v48_profile.py
    PYTHONPATH=. python validation/v48_poll_config.py
    python -u validation/v48_tests.py
    python validation/v48_round.py freeze
    python -u validation/v48_round.py collect
    python validation/v48_analyze_postcollection.py
python validation/v48_secondary.py
    /workspaces/tiee-v46-report-venv/bin/python validation/v48_report.py
python validation/v48_write_report.py

The existing report virtual environment supplies matplotlib; exact version is saved in figure_metadata.json. Polling bounds/default validation is recorded in poll_config.json; rerun with app.v48_relay.poll_seconds for accepted values 0.005, 0.02, 0.1 and rejected values 0, -1, 0.004, 0.101, nan, inf, -inf and invalid, and verify unset default equals 0.005.

v48_profile imports the v47 private harness and adds compose.v48.profile.yml, which starts PostgreSQL with pg_stat_statements and I/O timing and assigns service application names. Its wait observer operates only during the diagnostic profile. v48_tests adds compose.v48.yml and uses actual 20ms relay cadence. v48_round uses the same compose files, image, workers, pooling and durability for both variants; only RELAY_POLL_SECONDS differs. No wait observer runs during performance collection. Every run gets a fresh database and 24-event warmup. All failed attempts, HTTP errors, rejection/expiry and drain results remain in evidence.

The profile export is matched to the installed PostgreSQL 17 column names shared_blk_read_time/shared_blk_write_time. Normalized query counters aggregate identical query shapes, including advisory locks with different constants. Statement profiles include warmup and immediate postmeasurement reads; cumulative statement execution time is wall time, not CPU. Wait samples are diagnostic occupancy observations and add overhead. Engine CPU and resource endpoints come from the matched recorder, which excludes probe CPU but cannot remove shared-host contention.

After collection, stop only the private project (volumes retained):

    python -c "import sys; sys.path.insert(0,'validation'); import v48_round as r; r.h.dc('stop','-t','5')"

Use validation/v48_manifest.py after final files are written to byte-check original work, scan private credential values and hash artifacts. Verify lossless decompression of runs.jsonl.gz against the raw recorder output, stage only intended source/results/report files, run git diff --cached --check and commit to a separate development branch. Do not change the frozen source or tune the candidate from held-out results. Physical host/power/disk failures and distinct TiEE superiority remain unexecuted in this experiment.


Post-collection analysis correction: the frozen v48_analyze.py is retained byte-for-byte as the preregistered source, but its poll_errors aggregation expected a number where each run stores a list. Use v48_analyze_postcollection.py for analysis; it changes only the aggregation to sum list lengths. The correction and both SHA256 values are in validation/ANALYZER_CORRECTION.md. Frozen adoption thresholds and benchmark inputs are unchanged.
