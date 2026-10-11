import hashlib,json,pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path('results/v46/confirmation');raw=(R/'analysis.json').read_bytes();a=json.loads(raw)
plt.rcParams.update({'font.size':10,'svg.hashsalt':'tiee-v46-fixed'})
colors=['#2674ad','#e49422','#24956e'];conditions=['normal','shift','burst']
def save(fig,name):
 fig.savefig(R/(name+'.png'),dpi=180,metadata={'Software':'TiEE v4.6; Matplotlib '+matplotlib.__version__})
 fig.savefig(R/(name+'.pdf'),metadata={'Creator':'TiEE v4.6','CreationDate':None,'ModDate':None})
 fig.savefig(R/(name+'.svg'),metadata={'Date':None})
 plt.close(fig)
fig,ax=plt.subplots(figsize=(10,5));labels=[]
for index,control in enumerate(('A1','A4','A0')):
 c=a['contrasts'][control];points=c['raw_points'];assert len(points)==60
 y=2-index
 for k,condition in enumerate(conditions):
  xs=points[k*20:(k+1)*20];ys=[y+(j%5-2)*.035 for j in range(20)];ax.scatter(xs,ys,s=17,alpha=.65,color=colors[k],label=condition if index==0 else None)
 low,high=c['ci_adjusted'];ax.plot([low,high],[y+.22,y+.22],color='#182c4b',lw=3);ax.scatter([c['paired_difference']],[y+.22],marker='D',s=35,color='#182c4b',zorder=4)
 ax.text(.99,y+.36,format(c['paired_difference'],'.3f')+' ['+format(low,'.3f')+', '+format(high,'.3f')+']',transform=ax.get_yaxis_transform(),ha='right',fontsize=9)
ax.axvline(0,color='#777',ls='--',lw=1);ax.set_yticks([0,1,2],['A3 - A0: fixed filter / FIFO','A3 - A4: conventional exact rule','A3 - A1: fixed filter / deadline'])
ax.set_ylim(-.4,2.7);ax.set_xlabel('Paired difference in net utility / measured engine CPU second');ax.set_title('TiEE v4.6: exploratory paired efficiency differences',loc='left',fontweight='bold');ax.legend(loc='lower right',ncol=3,frameon=False)
ax.spines[['top','right']].set_visible(False);fig.text(.02,.025,'Points: 60 paired trace blocks. Bars: planned Bonferroni 98.333% intervals. Performance acceptance is not established.',fontsize=9)
fig.tight_layout(rect=(0,.07,1,1));save(fig,'efficiency')
fig,ax=plt.subplots(figsize=(8,4.4))
for i,c in enumerate(conditions):
 g=a['guardrails'][c];rate=100*g['rate'];upper=100*g['upper95'];ax.plot([i,i],[rate,upper],color=colors[i],lw=3);ax.scatter([i],[rate],s=65,color=colors[i]);ax.plot([i-.08,i+.08],[upper,upper],color=colors[i],lw=2);ax.text(i,upper+.25,format(rate,'.2f')+'% / upper '+format(upper,'.2f')+'%',ha='center',fontsize=9)
ax.axhline(1,color='#b32929',ls='--',label='Required upper bound: 1%');ax.set_xlim(-.6,2.6);ax.set_xticks(range(3),conditions);ax.set_ylabel('Valid submitted events rejected (%)');ax.set_ylim(bottom=0);ax.set_title('A3 valid-rejection gate',loc='left',fontweight='bold');ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False,loc='upper right');fig.text(.02,.02,'Dots: observed rates. Caps: one-sided 95% trace-bootstrap upper bounds. Original recorder failure remains separately recorded.',fontsize=8);fig.tight_layout(rect=(0,.06,1,1));save(fig,'valid_rejection')
(R/'figure_metadata.json').write_text(json.dumps(dict(matplotlib_version=matplotlib.__version__,analysis_sha256=hashlib.sha256(raw).hexdigest(),figures=['efficiency','valid_rejection'],formats=['png','pdf','svg'],performance_claim='NOT ESTABLISHED'),indent=2)+chr(10));print('FIGURES_SAVED')
