import csv,gzip,json,pathlib,statistics,datetime
R=pathlib.Path('results/v46')
def rows(name):return [json.loads(x) for x in (R/name).read_text().splitlines()]
def q(xs,p):
 xs=sorted(float(x) for x in xs if x is not None);return xs[min(len(xs)-1,int((len(xs)-1)*p))] if xs else None
def main():
 plan=json.loads((R/'confirmation/plan.json').read_text());runs=rows('confirmation/runs.jsonl');assert len(runs)==len(plan['jobs'])
 analysis=json.loads((R/'confirmation/analysis.json').read_text());out=[];stage=[];resources=[]
 for arm in ('A0','A1','A2','A3','A4'):
  rs=[x for x in runs if x['arm']==arm];ledger=[x for r in rs for x in r['ledger']]
  item=dict(execution_cpu_mean=statistics.mean(x['execution_cpu_seconds'] for x in rs),probe_cpu_mean=statistics.mean(x['probe_cpu_seconds'] for x in rs),arm=arm,runs=len(rs),net_utility_per_cpu_mean=statistics.mean(x['net_utility_per_cpu'] for x in rs),net_utility_mean=statistics.mean(x['net_total_utility'] for x in rs),useful_throughput_mean=statistics.mean(x['useful_throughput'] for x in rs),cpu_mean=statistics.mean(x['service_cpu_seconds'] for x in rs),working_set_sample_peak_mib=max(sum(v['working_set_bytes'] for v in s['services'].values())/1048576 for r in rs for s in r['resource_samples']),queue_peak=max(x['sql_pending_peak'] for x in rs),sql_growth_mean=statistics.mean(x['table_growth_bytes'] for x in rs),wal_growth_mean=statistics.mean(x['wal_growth_bytes'] for x in rs),aof_growth_mean=statistics.mean(x['aof_growth_bytes'] for x in rs),drain_failures=sum(not x['drain_pass'] for x in rs),http_errors=sum(x['http_errors'] for x in rs),poll_errors=sum(x['poll_errors'] for x in rs))
  for field in ('offered_terminal_ms','dispatch_terminal_ms','queue_seconds','db_latency_seconds','execution_cpu'):
   for p in (.5,.95,.99):item[field+'_'+str(p)]=q([x.get(field) for x in ledger],p)
  for p in (.5,.95,.99):item['ack_run_quantile_mean_'+str(p)]=statistics.mean(x['ack_latency_ms'][str(p)] for x in rs)
  out.append(item)
 for r in runs:
  for x in r['ledger']:
   d=x.get('decision') or {};stage.append(dict(condition=r['condition'],block=r['block'],arm=r['arm'],id=x['id'],state=x['state'],decision_seconds=d.get('decision_seconds'),execution_cpu_seconds=x.get('execution_cpu'),queue_seconds=x.get('queue_seconds'),db_latency_seconds=x.get('db_latency_seconds'),offered_terminal_ms=x.get('offered_terminal_ms'),dispatch_terminal_ms=x.get('dispatch_terminal_ms')))
  for s in r['resource_samples']:
   for cid,v in s['services'].items():resources.append(dict(condition=r['condition'],block=r['block'],arm=r['arm'],sample_monotonic=s['at'],container_id=cid,**v))
 for name,data in [('metrics_by_arm.csv',out),('stage_metrics.csv',stage),('resource_samples.csv',resources)]:
  with (R/'confirmation'/name).open('w') as f:w=csv.DictWriter(f,list(data[0]));w.writeheader();w.writerows(data)
 (R/'confirmation/metrics_by_arm.json').write_text(json.dumps(out,indent=2)+chr(10))
 faults=rows('tests/v46_faults.jsonl');supp=rows('tests/supplementary.jsonl');legacy=rows('tests/legacy_pool0/integration.jsonl')+rows('tests/legacy_pool8/integration.jsonl');assert all(x['status']=='PASSED' for x in faults+supp+legacy)
 gates=dict(confirmation_complete='PASSED' if analysis['confirmation_complete'] else 'FAILED',power='PASSED' if analysis['power_budget_sufficient'] else 'FAILED',valid_rejection={c:'PASSED' if x['upper95']<=.01 else 'FAILED' for c,x in analysis['guardrails'].items()},calibration={c:'PASSED' if x['brier_ci95'][1]<0 else 'FAILED' for c,x in analysis['guardrails'].items()},A3_drain='PASSED' if all(x['drain_failures']==0 for x in analysis['guardrails'].values()) else 'FAILED',all_arm_http='PASSED' if all(x['http_errors']==0 for x in out) else 'FAILED',performance_acceptance='NOT ESTABLISHED')
 (R/'confirmation/acceptance_gates.json').write_text(json.dumps(gates,indent=2)+chr(10))
 lines=pathlib.Path('V4_6_REPORT_CONTEXT.md').read_text().splitlines()
 lines+=['','## Performance gate status','',json.dumps(gates,indent=2),'','Performance acceptance is distinct from the final correctness suites. HTTP/overload failures and HELD backlog remain in raw accounting.']
 lines+=['','## Final measured results','',f'Confirmation completed: {len(runs)} runs, {analysis["block_count"]} paired blocks.','', '| Arm | Useful/s | Net utility/CPU s | CPU s/run | Sampled peak MiB | Queue peak | Drain failures | HTTP errors |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for x in out:lines.append('| '+' | '.join([x['arm']]+[f'{x[k]:.3f}' for k in ('useful_throughput_mean','net_utility_per_cpu_mean','cpu_mean','working_set_sample_peak_mib')]+[str(x[k]) for k in ('queue_peak','drain_failures','http_errors')])+' |')
 lines+=['','Throughput and CPU columns are means across runs; memory and queue columns are maxima. Useful throughput counts completed valuable events. All metrics are in metrics_by_arm.json/CSV; stage and resource timing exports accompany them.','', '| Arm | Offered p50/p95/p99 ms | Dispatch p50/p95/p99 ms | ACK mean-run p50/p95/p99 ms | SQL/WAL/AOF mean growth KiB |','|---|---|---|---|---|']
 for x in out:
  cells=[x['arm']]
  for field in ('offered_terminal_ms','dispatch_terminal_ms','ack_run_quantile_mean'):cells.append(' / '.join(f'{x[field+"_"+str(p)]:.3f}' for p in (.5,.95,.99)))
  cells.append(' / '.join(f'{x[k]/1024:.3f}' for k in ('sql_growth_mean','wal_growth_mean','aof_growth_mean')));lines.append('| '+' | '.join(cells)+' |')
 lines+=['','Offered/dispatch percentiles pool observed terminal events; unresolved events remain failures with no invented latency. ACK entries are means of run percentiles.','',f'Training required {plan["training_power_required_blocks"]} blocks/condition for the frozen 10% minimum effect; only {plan["blocks_per_condition"]} were budgeted. Power gate FAILED.','', '| Contrast | Utility/CPU difference | Adjusted interval | Total utility difference/run |','|---|---:|---|---:|']
 for arm,x in analysis['contrasts'].items():lines.append(f'| A3 - {arm} | {x["paired_difference"]:.3f} | [{x["ci_adjusted"][0]:.3f}, {x["ci_adjusted"][1]:.3f}] | {x["total_utility_difference"]:.3f} |')
 lines+=['', '| Condition | Valid rejection rate / upper 95% | Brier difference / 95% interval | A3 drain failures |','|---|---|---|---:|']
 for c,x in analysis['guardrails'].items():lines.append(f'| {c} | {100*x["rate"]:.2f}% / {100*x["upper95"]:.2f}% | {x["brier_difference"]:.4f} / [{x["brier_ci95"][0]:.4f}, {x["brier_ci95"][1]:.4f}] | {x["drain_failures"]} |')
 lines+=['','## Measured crash recovery','', '| Pool | Service | Seconds |','|---|---|---:|']
 for row in faults:
  for service,seconds in row.get('detail',{}).get('recovery_seconds',{}).items():lines.append(f'| {row["pool"]} | {service} | {seconds:.3f} |')
 lines+=['','Recovery duration includes test restart and terminal-result verification, not a production SLA.','', 'Performance superiority and a distinct TiEE advantage remain NOT ESTABLISHED. Complete raw accounting and multiplicity-adjusted paired intervals are in analysis.json and efficiency.svg.','']
 pathlib.Path('V4_6_ENGINEERING_REPORT.md').write_text(chr(10).join(lines))
 for p in R.glob('*/runs.jsonl'):
  with p.open('rb') as src,gzip.GzipFile(filename=str(p)+'.gz',mode='wb',mtime=0) as dst:dst.write(src.read())
 print('REPORT',len(runs),'runs')
if __name__=='__main__':main()
