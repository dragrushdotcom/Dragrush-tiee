import csv,json,math,pathlib,random,statistics
from v46_data import trace
OUT=pathlib.Path('results/v46');rng=random.Random(460030)
def interval(v,alpha=.05):
    a=sorted(v);return [a[int(len(a)*alpha/2)],a[min(len(a)-1,int(len(a)*(1-alpha/2)))]]
def bootstrap(groups,stat,reps=20000,alpha=.05):
    out=[]
    for _ in range(reps):out.append(stat([rng.choice(g) for g in groups for _ in g]))
    return interval(out,alpha)
def main():
    plan=json.loads((OUT/'confirmation/plan.json').read_text());runs=[json.loads(x) for x in (OUT/'confirmation/runs.jsonl').read_text().splitlines()];groups={};contrasts={}
    for row in runs:groups.setdefault((row['condition'],row['block']),{})[row['arm']]=row
    complete={k:v for k,v in groups.items() if len(v)==5};assert len(complete)==len(groups),'incomplete paired blocks'
    for control in ('A1','A4','A0'):
        by_condition=[[p['A3']['net_utility_per_cpu']-p[control]['net_utility_per_cpu'] for (c,b),p in complete.items() if c==condition] for condition in ('normal','shift','burst')]
        values=[x for group in by_condition for x in group];contrasts[control]=dict(paired_difference=statistics.mean(values),ci95=bootstrap(by_condition,statistics.mean),ci_adjusted=bootstrap(by_condition,statistics.mean,alpha=.05/3),pairs=len(values),raw_points=values,total_utility_difference=statistics.mean(p['A3']['net_total_utility']-p[control]['net_total_utility'] for p in complete.values()))
    training=trace(460001,6000);prev=sum(x['valid'] for x in training)/len(training);cal=[];guard={};reliability=[]
    for condition in ('normal','shift','burst'):
        a=[p['A3'] for (c,b),p in complete.items() if c==condition];paired=[]
        for row in a:
            paired.append(statistics.mean((x['decision']['p_valid']-int(x['valid']))**2-(prev-int(x['valid']))**2 for x in row['ledger'] if x['decision']))
        cal+=paired;bounds=bootstrap([a],lambda samples:sum(x['valid_rejected'] for x in samples)/sum(x['valid_count'] for x in samples),alpha=.1);guard[condition]=dict(valid_rejected=sum(x['valid_rejected'] for x in a),valid_count=sum(x['valid_count'] for x in a),rate=sum(x['valid_rejected'] for x in a)/sum(x['valid_count'] for x in a),upper95=bounds[1],drain_failures=sum(not x['drain_pass'] for x in a),http_errors=sum(x['http_errors'] for x in a),brier_difference=statistics.mean(paired),brier_ci95=bootstrap([paired],statistics.mean))
    ledgers=[x for p in complete.values() for x in p['A3']['ledger'] if x['decision']]
    for lo in range(10):
        items=[x for x in ledgers if lo/10<=x['decision']['p_valid']<(lo+1)/10];reliability.append(dict(lower=lo/10,count=len(items),mean_prediction=statistics.mean(x['decision']['p_valid'] for x in items) if items else None,observed_validity=statistics.mean(int(x['valid']) for x in items) if items else None))
    summary=dict(run_count=len(runs),block_count=len(complete),contrasts=contrasts,guardrails=guard,reliability=reliability,calibration_brier_difference=statistics.mean(cal),calibration_ci95=bootstrap([cal],statistics.mean),power_budget_sufficient=plan['power_budget_sufficient'],performance_claim='NOT ESTABLISHED',distinct_TiEE_mechanism='ABSENT: A4 shares exact observable rule',confirmation_complete=len(runs)==len(plan['jobs']))
    (OUT/'confirmation/analysis.json').write_text(json.dumps(summary,indent=2));keys=['condition','block','arm','net_total_utility','net_utility_per_cpu','service_cpu_seconds','wall_seconds','useful_throughput','valid_count','valid_rejected','brier','log_loss','sql_pending_peak','table_growth_bytes','wal_growth_bytes','aof_growth_bytes','drain_pass','http_errors']
    with (OUT/'confirmation/runs.csv').open('w') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in runs)
    with (OUT/'confirmation/utility_ledger.csv').open('w') as f:
        keys=['condition','block','arm','id','valid','state','utility','execution_cpu','queue_seconds','db_latency_seconds','raw_offered_terminal_ms','raw_dispatch_terminal_ms'];w=csv.DictWriter(f,keys);w.writeheader()
        for r in runs:
            for x in r['ledger']:w.writerow({k:r[k] if k in r else x.get(k[4:]) if k.startswith('raw_') else x.get(k) for k in keys})
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560"><rect width="1000" height="560" fill="white"/><g font-family="sans-serif" fill="#172334"><text x="50" y="35" font-size="22">v4.6 paired efficiency differences: A3 minus controls</text><text x="50" y="60" font-size="14">Raw block points and multiplicity-adjusted intervals. Utility / engine CPU second.</text>']
    values=[x for c in contrasts.values() for x in c['raw_points']]+[x for c in contrasts.values() for x in c['ci_adjusted']]+[0];low=min(values);high=max(values);span=max(high-low,1);scale=lambda v:100+(v-low)*800/span
    svg.append(f'<line x1="{scale(0)}" y1="90" x2="{scale(0)}" y2="450" stroke="#777" stroke-dasharray="5,5"/>')
    for index,(name,c) in enumerate(contrasts.items()):
        y=140+index*130;svg.append(f'<text x="50" y="{y-40}" font-size="17">A3 − {name}: {c["paired_difference"]:.3f}</text>')
        for j,v in enumerate(c['raw_points']):svg.append(f'<circle cx="{scale(v)}" cy="{y+(j%7-3)*4}" r="3" fill="#497bc1" opacity="0.65"/>')
        a,b=c['ci_adjusted'];svg.append(f'<line x1="{scale(a)}" y1="{y+28}" x2="{scale(b)}" y2="{y+28}" stroke="#182c4b" stroke-width="4"/><text x="50" y="{y+55}" font-size="14">Adjusted interval [{a:.3f}, {b:.3f}]</text>')
    svg.append('<text x="50" y="530" font-size="16">Performance superiority and TiEE-specific advantage are not established.</text></g></svg>');(OUT/'confirmation/efficiency.svg').write_text(''.join(svg));print(json.dumps(summary,indent=2)[:6000])
if __name__=='__main__':main()
