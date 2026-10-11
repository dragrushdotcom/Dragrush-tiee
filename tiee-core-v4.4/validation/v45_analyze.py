"""CSV, paired bootstrap uncertainty, and reproducible matplotlib figures."""
import csv,json,math,random,statistics,pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=pathlib.Path('results/v45')
def interval(values):
    rng=random.Random(451012);n=len(values)
    draws=sorted(math.exp(statistics.mean(math.log(rng.choice(values)) for _ in range(n))) for _ in range(10000))
    return math.exp(statistics.mean(map(math.log,values))),draws[249],draws[9749]
def memory(text):
    s=text.split('/')[0].strip()
    for unit,m in [('GiB',2**30),('MiB',2**20),('KiB',2**10),('GB',10**9),('MB',10**6),('kB',10**3),('B',1)]:
        if s.endswith(unit):return float(s[:-len(unit)])*m
    raise ValueError(text)
def main():
    rows=json.loads((OUT/'randomized-benchmark.json').read_text());assert len(rows)==30 and all(x['integrity_pass'] for x in rows)
    fields=['error_count','index','stage','pair_id','repetition','seed','arm','noise','n','rounds','accepted','rejected','drain_seconds','useful_completion_rps','ack_p50_ms','ack_p95_ms','ack_p99_ms','completion_p50_ms','completion_p95_ms','completion_p99_ms','total_service_cpu_seconds','sql_pending_peak','stream_depth_peak','resident_memory_before_bytes','resident_memory_after_bytes','sql_table_growth_bytes','wal_growth_bytes','redis_aof_disk_growth_bytes','sampled_working_set_peak_bytes','workload_hash','integrity_pass']
    for r in rows:
        r['error_count']=sum(n for status,n in r['http_statuses'].items() if int(status)>=400)
        samples=[sum(memory(x['MemUsage']) for x in sample['rows']) for sample in r['stats_samples']]
        r['sampled_working_set_peak_bytes']=max(samples,default=0)
    with (OUT/'trials.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator=chr(10));w.writeheader();w.writerows(rows)
    summaries=[]
    for stage,noise in [('training',0),('training',.5),('training',.9),('held_out',.25),('held_out',.75)]:
        group=[r for r in rows if r['stage']==stage and r['noise']==noise];pairs=[]
        for pid in sorted({r['pair_id'] for r in group}):
            pair={r['arm']:r for r in group if r['pair_id']==pid};assert pair['baseline']['workload_hash']==pair['tiee']['workload_hash']
            pairs.append(pair)
        summary=dict(stage=stage,noise=noise,paired_runs=len(pairs),ratio_ci_method='geometric paired bootstrap; 10000 resamples; seed 451012; descriptive with n=3')
        for metric in ['useful_completion_rps','completion_p95_ms','total_service_cpu_seconds']:
            ratio,low,high=interval([p['tiee'][metric]/p['baseline'][metric] for p in pairs])
            summary[metric+'_ratio']={'estimate':ratio,'ci95':[low,high]}
        for arm in ['baseline','tiee']:
            rs=[r for r in group if r['arm']==arm]
            summary[arm]={k:statistics.mean(r[k] for r in rs) for k in ['useful_completion_rps','completion_p50_ms','completion_p95_ms','completion_p99_ms','total_service_cpu_seconds','sql_pending_peak','stream_depth_peak','sampled_working_set_peak_bytes','sql_table_growth_bytes','wal_growth_bytes','redis_aof_disk_growth_bytes']}
            summary[arm]['service_cpu_seconds']={s:statistics.mean(r['resources_after'][s]['cpu_seconds']-r['resources_before'][s]['cpu_seconds'] for r in rs) for s in ['gateway','relay','worker','redis','postgres']}
        summaries.append(summary)
    (OUT/'summary.json').write_text(json.dumps(summaries,indent=2))
    labels=[f"{s['stage'].replace('_',' ')}\n{s['noise']:.0%} noise" for s in summaries]
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,2,figsize=(12,4.8))
    for j,metric in enumerate(['useful_completion_rps','completion_p95_ms']):
        for arm,color,offset in [('baseline','#4263eb',-.15),('tiee','#0b8f76',.15)]:
            xs=[i+offset for i in range(len(summaries))]
            axs[j].bar(xs,[s[arm][metric] for s in summaries],width=.28,label=arm,color=color,alpha=.75)
            for i,s in enumerate(summaries):
                raw=[r[metric] for r in rows if r['stage']==s['stage'] and r['noise']==s['noise'] and r['arm']==arm]
                axs[j].scatter([i+offset]*len(raw),raw,color='black',s=14,zorder=3)
        axs[j].set_xticks(range(5),labels);axs[j].set_ylabel('Useful completions / second' if j==0 else 'Observed completion p95 (ms)');axs[j].legend();axs[j].grid(axis='y',alpha=.2)
    fig.suptitle('TiEE v4.5: identical conventional filtering and async infrastructure\nBars: means; dots: individual runs; latency includes 20 ms polling resolution')
    fig.tight_layout();fig.savefig(OUT/'throughput-latency.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.8))
    for i,s in enumerate(summaries):
        r=s['useful_completion_rps_ratio'];e=r['estimate'];lo,hi=r['ci95']
        ax.errorbar(i,e,yerr=[[e-lo],[hi-e]],fmt='o',color='#0b8f76',capsize=6)
    ax.axhline(1,color='#666',linestyle='--');ax.set_xticks(range(5),labels);ax.set_ylabel('TiEE / baseline useful throughput');ax.set_title('Paired throughput ratio and descriptive 95% bootstrap interval\nOnly three pairs per workload; no distinct TiEE execution algorithm in these arms');ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'paired-uncertainty.png',dpi=170);plt.close(fig)
    print(json.dumps(summaries,indent=2))
if __name__=='__main__':main()
