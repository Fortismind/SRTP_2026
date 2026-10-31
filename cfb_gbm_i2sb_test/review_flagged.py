"""Diagnostic only: inspect excluded actual pairs without admitting them automatically."""
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cfb.common import ROOT,read,dump
from cfb.preprocess import prepare_baseline,load_canonical,to_stack,normalize
from nibabel.processing import resample_from_to

records=[]
for r in read(ROOT/'data/manifest.json'):
    if r['status']=='accepted' or not (r['source'] and r['target']):continue
    try:
        b,m,plan,img,_=prepare_baseline(r['source']);target=load_canonical(r['target'])
        if target.shape!=img.shape or not np.allclose(target.affine,img.affine,atol=1e-3):target=resample_from_to(target,(img.shape,img.affine))
        raw=target.get_fdata(dtype=np.float32);t=to_stack(normalize(raw,plan),plan)
        fig,axs=plt.subplots(3,3,figsize=(9,9));zs=np.linspace(len(b)*.25,len(b)*.75,3).astype(int)
        for i,z in enumerate(zs):
            for ax,a,title in zip(axs[i],[b[z],t[z],np.abs(t[z]-b[z])],['Baseline','Follow-up baseline scale','Difference']):
                ax.imshow(a.T,origin='lower',cmap='gray',vmin=0,vmax=1);ax.set_title(f'{title} z={z}');ax.axis('off')
        fig.suptitle(f'Flagged patient {r["patient_id"]}: '+str(r['reasons']),fontsize=8);fig.tight_layout()
        out=ROOT/f'reports/flagged_{r["patient_id"]}.png';fig.savefig(out,dpi=120);plt.close(fig)
        records.append(dict(patient=r['patient_id'],reason=r['reasons'],target_finite=bool(np.isfinite(raw).all()),target_positive_percentiles=np.percentile(raw[raw>0],[.5,50,99.5]).tolist(),baseline_scale=[plan['intensity_low'],plan['intensity_high']],figure=str(out)))
    except Exception as e:records.append(dict(patient=r['patient_id'],error=str(e)))
dump(ROOT/'reports/flagged_pairs.json',records);print(records,flush=True)
