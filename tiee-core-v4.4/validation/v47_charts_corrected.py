import datetime,hashlib,json,pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path('results/v47/corrected');a=json.loads((R/'analysis.json').read_text());plt.rcParams.update({'font.size':10,'svg.hashsalt':'v47-report-fixed'})
def save(fig,name):
 fig.tight_layout();fig.savefig(R/(name+'.png'),dpi=180);fig.savefig(R/(name+'.pdf'),metadata={'CreationDate':None,'ModDate':None});fig.savefig(R/(name+'.svg'),metadata={'Date':None});plt.close(fig)
conditions=['normal','shift','burst'];fig,ax=plt.subplots(figsize=(8,4.8))
for i,c in enumerate(conditions):
 g=a['guardrails'][c];rate=100*g['loss_rate'];upper=100*g['loss_upper95'];ax.plot([i,i],[rate,upper],lw=3,color='#2674ad');ax.scatter([i],[rate],s=65,color='#2674ad');ax.plot([i-.08,i+.08],[upper,upper],lw=2,color='#2674ad');ax.text(i,upper+.08,format(rate,'.2f')+'% / upper '+format(upper,'.2f')+'%',ha='center',fontsize=9)
ax.axhline(1,color='#b32929',ls='--');ax.set_xticks(range(3),conditions);ax.set_xlim(-.6,2.6);ax.set_ylim(0,max(1.4,max(100*g['loss_upper95'] for g in a['guardrails'].values())*1.2));ax.set_ylabel('Valid offered events not DONE (%)');ax.set_title('A3 useful-work loss: corrected Gateway regression',loc='left',fontweight='bold');ax.text(.98,.95,'Dashed line: 1% IID screening limit',transform=ax.transAxes,ha='right',va='top',fontsize=9);ax.spines[['top','right']].set_visible(False);fig.text(.02,.015,'Exact one-sided 95% binomial bounds assume synthetic IID validity. Three trace blocks/condition do not certify production risk.',fontsize=8);fig.subplots_adjust(bottom=.17);save(fig,'useful_loss')
fig,ax=plt.subplots(figsize=(8,4.5));arms=['A1','A3','A4'];categories=['postgres','gateway','relay','worker','redis','network_anchor'];bottom=[0.]*3
for category in categories:
 values=[100*a['component_profiles'][arm].get(category,{}).get('fraction',0) for arm in arms];ax.bar(arms,values,bottom=bottom,label=category);bottom=[x+y for x,y in zip(bottom,values)]
ax.set_ylabel('Measured engine CPU (%)');ax.set_title('Per-service CPU share during corrected runs',loc='left',fontweight='bold');ax.legend(bbox_to_anchor=(1.02,1),loc='upper left',frameon=False);ax.spines[['top','right']].set_visible(False);save(fig,'component_cpu')
fig,ax=plt.subplots(figsize=(8,4.2));colors=['#2674ad','#24956e','#e49422'];x=range(3);values=[a['metrics'][arm]['useful_throughput_mean'] for arm in arms];ax.bar(arms,values,color=colors);ax.set_ylabel('Useful completed events / observed wall second');ax.set_title('Corrected Gateway: matched-workload useful throughput',loc='left',fontweight='bold')
for i,v in enumerate(values):ax.text(i,v,format(v,'.2f'),ha='center',va='bottom')
ax.set_ylim(0,max(values)*1.16);ax.spines[['top','right']].set_visible(False);save(fig,'useful_throughput')
