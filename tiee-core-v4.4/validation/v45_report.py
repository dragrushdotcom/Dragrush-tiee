"""Generate report only after all final verification artifacts exist and pass."""
import json,pathlib,statistics,datetime
ROOT=pathlib.Path('.');OUT=ROOT/'results/v45'
def read(name):return json.loads((OUT/name).read_text())
def checks(name):
    rows=[]
    for line in (OUT/name).read_text().splitlines():
        if line.startswith('{'):
            try:r=json.loads(line)
            except ValueError:continue
            if 'test' in r: rows.append(r)
    assert rows and all(r['pass_'] for r in rows),(name,rows)
    return {r['test']:r for r in rows}
def main():
    a=read('randomized-benchmark.json');b=read('optimization/randomized-benchmark.json')
    assert len(a)==30 and len(b)==12 and all(r['integrity_pass'] for r in a+b)
    default={}
    for f in ['integration-fixed.log','extended.log','regression-final-default.log']:default.update(checks(f))
    pooled={}
    for f in ['pool-integration.log','pool-extended.log','pool-regression.log']:pooled.update(checks(f))
    assert len(default)==20 and default.keys()==pooled.keys()
    assert 'Ran 10 tests' in (OUT/'unit-tests-final.log').read_text() and (OUT/'unit-tests-final.log').read_text().rstrip().endswith('OK')
    (OUT/'final-test-matrix.json').write_text(json.dumps({'default':default,'pool_size_8':pooled,'source_tests':10,'unexecuted':['physical power loss','simultaneous PostgreSQL and Redis durable-volume loss','prolonged production load','real AI/GPU workloads','non-neutral EV scheduling']},indent=2)+'\n')
    summaries=read('summary.json');optimization=read('optimization/summary.json');preserve=read('preservation.json')
    rec=[r['detail']['recovery_seconds'] for r in list(default.values())+list(pooled.values()) if 'recovery_seconds' in r.get('detail',{})]
    cpu={s:sum(r['resources_after'][s]['cpu_seconds']-r['resources_before'][s]['cpu_seconds'] for r in a) for s in a[0]['resources_before']}
    pgshare=100*cpu['postgres']/sum(cpu.values())
    lines=['# TiEE Core v4.5 — real infrastructure, recovery and performance evidence','',
        'Status: Experimental pilot verified on the existing scaling potato Codespace. No production deployment. Report generated '+datetime.datetime.now(datetime.timezone.utc).isoformat()+'.','',
        '## Findings','',
        f'- All 20 named real-service gates passed across the default and bounded-connection-reuse profiles; 40 final gate outcomes. Ten source contract tests also passed.',
        f'- All 30 neutral-policy comparison runs and all 12 connection-reuse experiment runs passed independent digest and event accounting checks. These measured runs submitted {sum(r["n"] for r in a+b):,} source events, excluding warmups.',
        '- No distinct TiEE performance advantage is established. Baseline and TiEE apply the same deterministic bot filter and asynchronous pipeline; TiEE eligibility is a neutral implementation, with no operational EV scoring or value scheduling.',
        f'- PostgreSQL consumed {pgshare:.1f}% of measured service CPU in the original comparison. Repeated connection establishment was selected as a conventional optimization target; the separate paired experiment below evaluates bounded connection reuse.',
        f'- Recorded target-event recovery durations across final gates ranged from {min(rec):.3f} to {max(rec):.3f} seconds, including container startup/readiness and coarse observation overhead. See raw logs for each fault and timer boundary.','',
        '## Preservation and source changes','',
        'Verified base commit: '+preserve['verified_commit']+'. Development branch: tiee-core-v45-validation. The original robotics-v01 worktree status was checked against its fresh preservation snapshot and remained unchanged. All 404 original regular files outside .git were also byte-identical to the fresh archive.',
        'Original backup: '+preserve['original_backup']+'. Fresh complete repository archive and staged/unstaged patches: '+preserve['fresh_backup']+'. Archive readability and SHA-256 hashes are recorded in results/v45/preservation.json. Existing robotics archives and prior reports were retained.','',
        'Changes serialize concurrent schema DDL with a PostgreSQL transaction advisory lock, recreate a lost Redis consumer group without restarting the worker, retry transient group recreation failures, lock event rows before result/audit commit, and prevent broker replays from executing SQL-rejected events. Optional PG_POOL_SIZE=8 enables bounded connection reuse; the default 0 retains the original connection mode for reproduction. The pool dependency is pinned.',
        'Singularity Gateway performs durable SQL admission; Quantum EV Logic Engine is the neutral eligible function in app/common.py; Grand Gallery is Redis Streams with AOF appendfsync=always; King’s Chamber stores event, result and audit tables in PostgreSQL. Relay reconciliation retries unresolved accepted rows. Acknowledgment to Redis follows successful result transaction commit. There is no external actuator or irreversible side effect in this workload.','',
        '## Final real-service test matrix','',
        '| Gate | Default | Pool size 8 |','|---|---|---|']
    for name in default:lines.append(f'| {name} | PASS | PASS |')
    lines += ['',
        'Crash gates use real SIGKILL on pilot containers. Pending reclaim explicitly delivers a target event to a dead Redis consumer with relay stopped, then exercises the 3,000 ms Redis pending-delivery lease through XAUTOCLAIM. The implementation has no separate SQL worker-lease subsystem. Stream/group loss deletes only the pilot stream; the deterministic regression removes an initialized group and verifies completion without worker restart. Backpressure fills a 32-event bound, checks 503 plus absence from SQL, permits duplicate retry, drains, and safely retries the same ID.',
        'Transaction triggers force relay SQL rollback after observed XADD and result-insert rollback before acknowledgment. The concurrent idempotence regression publishes 40 duplicates, uses two worker processes and delays a selected result insert; exactly one result and one DONE audit survive. Rejected-event identity conflicts and broker replay rejection are verified. The schema regression performs 32 concurrent schema calls on a fresh SQL database.','',
        '## Failed and initially unexecuted checks','',
        '- Initial real startup failed: Gateway and worker exited with a PostgreSQL pg_type uniqueness error during concurrent CREATE TABLE. Traces are retained in startup-failure.log; the advisory-lock fix and fresh-database concurrency regression address it.',
        '- The first harness run failed eight gate invocations before their substantive assertions because an output directory lacked parents. This was corrected; integration-initial.log preserves those harness failures.',
        '- The first cold-schema regression failed before exercising DDL because the helper lacked /srv on its Python import path. The corrected final-default and pooled runs passed. regression.log retains the initial failure.',
        '- The first pooled profile failed subsequent admission after PostgreSQL restart because stale sessions were handed out. Connection checkout checks and two-second acquisition/connect limits were added; pool-integration-before-check.log retains the failed attempt. The final pooled suite below is the acceptance gate.',
        '- The inherited pre-fix recovery suite passed eight checks. Its stream-loss timing was insufficient to establish the suspected missing-group behavior; the stronger final regression is the relevant evidence.',
        '- No unresolved failures remain among the final executed gates. Physical power-loss durability, simultaneous loss of PostgreSQL and Redis durable volumes, prolonged production load, real AI/GPU workloads, and non-neutral EV scheduling were not executed. These results do not validate those cases.','',
        '## Matched randomized comparison','',
        'Training: 400 events, 2,000 SHA-256 rounds, noise 0%, 50%, 90%. Held out: 600 events/8,000 rounds/25% noise and 450 events/4,000 rounds/75% noise. Three paired repetitions per workload; workload and arm order randomized with saved seed 451011. Seeds for held-out workloads differ from training. Each trial uses a fresh database and 30-event warmup. Input hashes excluding run-specific IDs and independent expected output sets match within pairs.',
        'Both arms use one worker process, eight publisher threads, identical rejection criteria, schema, admission capacity, relay retry settings, Redis AOF and PostgreSQL durability, container image and shared Codespace resources. The probe container holds HTTP generation, commit observation and digest verification; it is excluded from service CPU/RAM totals.','',
        '| Workload | Arm | Useful/s mean | Completion p50 ms | p95 ms | p99 ms |',
        '|---|---|---:|---:|---:|---:|']
    for s in summaries:
        for arm in ['baseline','tiee']:
            r=s[arm];lines.append(f'| {s["stage"]}, {s["noise"]:.0%} noise | {arm} | {r["useful_completion_rps"]:.2f} | {r["completion_p50_ms"]:.1f} | {r["completion_p95_ms"]:.1f} | {r["completion_p99_ms"]:.1f} |')
    lines += ['','| Workload | TiEE/baseline useful-throughput ratio | Descriptive 95% interval |','|---|---:|---|']
    for s in summaries:
        r=s['useful_completion_rps_ratio'];lines.append(f'| {s["stage"]}, {s["noise"]:.0%} noise | {r["estimate"]:.3f} | [{r["ci95"][0]:.3f}, {r["ci95"][1]:.3f}] |')
    lines += ['','Geometric paired bootstrap uses 10,000 resamples and seed 451012. Only three pairs per workload make these intervals descriptive and sensitive to environmental noise; no multiplicity correction or production inference is claimed. Small observed differences between behaviorally identical arms do not establish a TiEE-specific causal gain.','',
        '## CPU, RAM, queues and storage','',
        '| Workload | Arm | Service CPU s | Sampled working-set MiB | SQL pending peak | Stream peak | SQL tables KiB growth | WAL KiB growth | AOF KiB growth |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        for arm in ['baseline','tiee']:
            r=s[arm];lines.append(f'| {s["stage"]}, {s["noise"]:.0%} | {arm} | {r["total_service_cpu_seconds"]:.2f} | {r["sampled_working_set_peak_bytes"]/2**20:.1f} | {r["sql_pending_peak"]:.1f} | {r["stream_depth_peak"]:.1f} | {r["sql_table_growth_bytes"]/1024:.1f} | {r["wal_growth_bytes"]/1024:.1f} | {r["redis_aof_disk_growth_bytes"]/1024:.1f} |')
    lines += ['','All values above are means of per-run measurements. Cgroup memory endpoints are separate raw fields, not the Docker working-set metric. Sampled peaks are lower bounds on unobserved peaks. SQL size includes indexes; WAL and AOF deltas share persistent pilot storage and include background maintenance/allocation effects. CPU counter windows extend through client verification and metric collection, so background service work during that tail is included. Raw CSV/JSON includes HTTP errors/status counts, admission p50/p95/p99, all completion observations, queue and Docker stats samples, per-service CPU, and storage snapshots.','',
        '## Conventional connection-reuse experiment','',
        'The baseline policy is held constant. Three randomized pairs compare pool size 0 versus maximum 8 connections per application process on a training 400-event/2,000-round/50%-noise workload and a held-out 600-event/8,000-round/25%-noise workload. Randomization seed 451013; new input seeds. Worker resources and durability match. The recovery suite was rerun with pooling before measuring this candidate.','',
        '| Workload | Original useful/s | Pooled useful/s | Pooled/original ratio [95% descriptive CI] | CPU ratio | P95 ratio |','|---|---:|---:|---|---:|---:|']
    for s in optimization:
        r=s['useful_completion_rps_ratio'];lines.append(f'| {s["stage"]} | {s["baseline"]["useful_completion_rps"]:.2f} | {s["pooled"]["useful_completion_rps"]:.2f} | {r["estimate"]:.3f} [{r["ci95"][0]:.3f}, {r["ci95"][1]:.3f}] | {s["total_service_cpu_seconds_ratio"]["estimate"]:.3f} | {s["completion_p95_ms_ratio"]["estimate"]:.3f} |')
    lines += ['',f'The training queue peak increased from {optimization[0]["baseline"]["sql_pending_peak"]:.1f} to {optimization[0]["pooled"]["sql_pending_peak"]:.1f} events, while mean p95 increased from {optimization[0]["baseline"]["completion_p95_ms"]:.1f} to {optimization[0]["pooled"]["completion_p95_ms"]:.1f} ms. Held-out mean p95 decreased from {optimization[1]["baseline"]["completion_p95_ms"]:.1f} to {optimization[1]["pooled"]["completion_p95_ms"]:.1f} ms, while queue peak increased from {optimization[1]["baseline"]["sql_pending_peak"]:.1f} to {optimization[1]["pooled"]["sql_pending_peak"]:.1f}. Faster admission can increase backlog even when useful throughput improves.','',
    'Connection reuse is a conventional database optimization available equally to TiEE and the control. It provides no evidence for toroidal, quantum or EV-specific superiority. Additional candidates include shorter publication transactions and batched worker connections, but they were not implemented or credited as measured improvements here.','',
        '## Next engineering gate','',
        'Compare a calibrated, non-neutral EV policy against an equally optimized conventional filter and scheduler on a real target workload. Match output obligations and measure false rejection, scheduling cost, and end-to-end utility before crediting a TiEE-specific gain.',
        '', '## Reproduction and evidence','',
        'See REPRODUCE_V4_5.md for credential generation, isolated Compose commands, all suites, randomized runs and figure generation. Exact plotting dependencies are recorded in results/v45/chart-requirements.txt. Environment, base commit, archive hashes, image digests and limits are recorded in JSON. The Codespace advertised two cores/eight GB; resources are shared, with no per-service CPU reservation.',
        '[Reproduction commands](REPRODUCE_V4_5.md), [comparison CSV](results/v45/trials.csv), [comparison raw JSON](results/v45/randomized-benchmark.json), [optimization CSV](results/v45/optimization/trials.csv), [optimization raw JSON](results/v45/optimization/randomized-benchmark.json), and [artifact hashes](results/v45/artifact-sha256.json). Archived SQL trial databases and Docker volumes are retained. No secrets are included in committed artifacts.','', '![Matched throughput and latency](results/v45/throughput-latency.png)','', '![Paired statistical uncertainty](results/v45/paired-uncertainty.png)','', '![Conventional connection reuse](results/v45/optimization/connection-reuse.png)','']
    (ROOT/'V4_5_ENGINEERING_REPORT.md').write_text('\n'.join(lines))
    print('REPORT_VERIFIED',len(default),len(pooled),len(a),len(b))
if __name__=='__main__':main()
