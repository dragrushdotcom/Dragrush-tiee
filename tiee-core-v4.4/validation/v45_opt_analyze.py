"""Paired analysis of conventional connection reuse."""
import csv,json,pathlib,statistics
from v45_analyze import interval,memory
import matplotlib.pyplot as plt
OUT=pathlib.Path('results/v45/optimization')
def main():
    rows=json.loads((OUT/'randomized-benchmark.json').read_text());assert len(rows)==12 and all(r['integrity_pass'] for r in rows)
    for r in rows:r['error_count']=sum(n for status,n in r['http_statuses'].items() if int(status)>=400)
    fields=['error_count','index','stage','pair_id','seed','arm','pool_size','accepted','noise','n','rounds','useful_completion_rps','completion_p50_ms','completion_p95_ms','completion_p99_ms','total_service_cpu_seconds','sql_pending_peak','stream_depth_peak','sql_table_growth_bytes','wal_growth_bytes','redis_aof_disk_growth_bytes','resident_memory_before_bytes','resident_memory_after_bytes','workload_hash','integrity_pass']
    with (OUT/'trials.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator=chr(10));w.writeheader();w.writerows(rows)
    summaries=[]
    for stage in ['training','held_out']:
        group=[r for r in rows if r['stage']==stage];pairs=[]
        for pid in sorted({r['pair_id'] for r in group}):
            p={r['arm']:r for r in group if r['pair_id']==pid};assert p['baseline']['workload_hash']==p['pooled']['workload_hash'];pairs.append(p)
        out={'stage':stage,'pairs':len(pairs)}
        for m in ['useful_completion_rps','completion_p95_ms','total_service_cpu_seconds']:
            estimate,low,high=interval([p['pooled'][m]/p['baseline'][m] for p in pairs]);out[m+'_ratio']={'estimate':estimate,'ci95':[low,high]}
        for arm in ['baseline','pooled']:
            rs=[r for r in group if r['arm']==arm];out[arm]={m:statistics.mean(r[m] for r in rs) for m in ['useful_completion_rps','completion_p95_ms','total_service_cpu_seconds','sql_pending_peak']}
        summaries.append(out)
    (OUT/'summary.json').write_text(json.dumps(summaries,indent=2))
    fig,axs=plt.subplots(1,2,figsize=(10,4.8))
    for j,metric in enumerate(['useful_completion_rps','total_service_cpu_seconds']):
        for i,stage in enumerate(['training','held_out']):
            for arm,offset,color in [('baseline',-.16,'#4263eb'),('pooled',.16,'#0b8f76')]:
                values=[r[metric] for r in rows if r['stage']==stage and r['arm']==arm]
                axs[j].bar(i+offset,statistics.mean(values),width=.3,color=color,label=arm if i==0 else None,alpha=.75)
                axs[j].scatter([i+offset]*len(values),values,color='black',s=14,zorder=3)
        axs[j].set_xticks([0,1],['training: 50% noise','held out: 25% noise']);axs[j].set_ylabel('Useful completions / second' if j==0 else 'Total service CPU seconds');axs[j].legend();axs[j].grid(axis='y',alpha=.2)
    fig.suptitle('Conventional PostgreSQL connection reuse: randomized paired trials\nIdentical baseline policy; bars are means, dots are individual runs')
    fig.tight_layout();fig.savefig(OUT/'connection-reuse.png',dpi=170);plt.close(fig)
    print(json.dumps(summaries,indent=2))
if __name__=='__main__':main()
