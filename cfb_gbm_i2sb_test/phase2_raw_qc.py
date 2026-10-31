"""Read-only raw QC for predefined high-clipping train/val patients, never test."""
import numpy as np
from cfb.common import ROOT,read,dump
from cfb.preprocess import baseline_plan,load_canonical

out=ROOT/'reports/phase2_2026-10-31';cache=read(out/'cache_qc.json');manifest={r['patient_id']:r for r in read(ROOT/'data/manifest.json')};rows=[]
for split in ['train','val']:
    selected=sorted([r for r in cache['patients'] if r['split']==split],key=lambda r:(-r['target_high_saturation'],r['patient']))[:3]
    for selected_row in selected:
        pid=selected_row['patient'];row=manifest[pid]
        b,a,mask,plan=baseline_plan(row['source']);target=load_canonical(row['target'])
        assert target.shape==b.shape and np.allclose(target.affine,b.affine,atol=1e-3)
        t=target.get_fdata(dtype=np.float32);lo=plan['intensity_low'];hi=plan['intensity_high']
        stat=dict(patient=pid,split=split,world_grid_matches=True,baseline_range=[lo,hi],
            raw_target_above_baseline_upper_fraction=float((t[mask]>hi).mean()),raw_target_below_baseline_lower_fraction=float((t[mask]<lo).mean()),
            baseline_brain_median=float(np.median(a[mask])),target_brain_median=float(np.median(t[mask])),
            caveat='Foreground mask not expert brain segmentation; geometry match not full anatomical registration validation')
        rows.append(stat);dump(out/'raw_qc.json',dict(rule='top3 clipping train and top3 clipping val from cache QC',test_images_read=False,patients=rows));print(stat,flush=True)
