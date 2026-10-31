"""Optional baseline planning GTV QC only; never controls slice selection in model."""
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cfb.common import ROOT,read,dump

ids=[r['patient_id'] for r in read(ROOT/'data/manifest.json') if r['status']=='accepted' and r['qc']['gtv_status'].startswith('same_world_grid')]
for start in range(0,len(ids),30):
    group=ids[start:start+30];fig,axs=plt.subplots(5,6,figsize=(14,12))
    for ax in axs.flat:ax.axis('off')
    for ax,pid in zip(axs.flat,group):
        with np.load(ROOT/f'cache/{pid}.npz') as d:
            z=int(d['gtv'].sum((1,2)).argmax());a=d['baseline'][z];mask=d['gtv'][z]
            ax.imshow(a.T,origin='lower',cmap='gray',vmin=0,vmax=1)
            if mask.any():ax.contour(mask.T.astype(float),levels=[.5],colors=['#ff7733'],linewidths=.7,origin='lower')
            ax.set_title(f'{pid} | baseline planning GTV | z={z}',fontsize=7)
    fig.tight_layout();fig.savefig(ROOT/f'reports/gtv_overlay_{start//30:02d}.png',dpi=100);plt.close(fig)
dump(ROOT/'reports/gtv_overlay_protocol.json',dict(patients=ids,rule='maximum baseline GTV area slice for optional mask QC only',used_for_training_or_prediction_slice_selection=False,meaning='baseline planning target; not followup segmentation'))
print('Baseline GTV contact sheets written:',len(ids),flush=True)
