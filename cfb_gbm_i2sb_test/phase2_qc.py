"""Train/validation cache diagnostics only; never reads test image caches."""
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cfb.common import ROOT,read,dump

OUT=ROOT/'reports/phase2_2026-10-31'
def run():
    OUT.mkdir(exist_ok=True,parents=True);splits=read(ROOT/'data/splits.json');rows=[]
    manifest={r['patient_id']:r for r in read(ROOT/'data/manifest.json')}
    for split in ['train','val']:
        for pid in splits[split]:
            with np.load(ROOT/f'cache/{pid}.npz') as d:
                b=d['baseline'].astype('float32');t=d['target'].astype('float32');m=d['mask']
                assert np.isfinite(b).all() and np.isfinite(t).all() and m.any()
                rows.append(dict(patient=pid,split=split,slices=len(b),brain_fraction=float(m.mean()),baseline_high_saturation=float((b[m]>=.999).mean()),
                    target_high_saturation=float((t[m]>=.999).mean()),target_low_saturation=float((t[m]<=.001).mean()),
                    baseline_median=float(np.median(b[m])),target_median=float(np.median(t[m])),
                    alignment_r=manifest[pid]['qc']['alignment_r'],support_dice=manifest[pid]['qc']['support_dice']))
    selected=[]
    for split in ['train','val']:
        ss=[r for r in rows if r['split']==split]
        selected += [r['patient'] for r in sorted(ss,key=lambda r:(-r['target_high_saturation'],r['patient']))[:3]]
        selected += [r['patient'] for r in sorted(ss,key=lambda r:(r['alignment_r'],r['patient']))[:3]]
    selected=list(dict.fromkeys(selected));fig,axs=plt.subplots(len(selected),3,figsize=(9,3*len(selected)))
    for axes,pid in zip(axs,selected):
        with np.load(ROOT/f'cache/{pid}.npz') as d:
            z=len(d['baseline'])//2
            for ax,key in zip(axes,['baseline','target','mask']):
                ax.imshow(d[key][z].T,origin='lower',cmap='gray',vmin=0,vmax=1);ax.set_title(f'{pid} {key}');ax.axis('off')
    fig.tight_layout();fig.savefig(OUT/'qc_selected.png',dpi=90);plt.close(fig)
    report=dict(patients=rows,selected_for_diagnostic_review=selected,test_image_caches_read=False,
        note='Clipping fractions measured on cached model grid, not raw-volume saturation; target-based selection for QC only, never inference cropping',
        summary={s:dict(patients=sum(r['split']==s for r in rows),target_high_saturation_mean=float(np.mean([r['target_high_saturation'] for r in rows if r['split']==s])),
            over_5percent_high_saturation=[r['patient'] for r in rows if r['split']==s and r['target_high_saturation']>.05]) for s in ['train','val']})
    dump(OUT/'cache_qc.json',report);print(report['summary'],flush=True);return report

if __name__=='__main__':run()
