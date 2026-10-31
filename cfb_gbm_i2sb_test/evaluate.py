"""Generate before opening target; evaluation is the only target-reading stage."""
import argparse,csv,time
from pathlib import Path
import numpy as np
import nibabel as nib
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cfb.common import ROOT,read,dump,sha
from cfb.metrics import patient_metrics
from infer import generate

def plot_example(pid,weeks,b,t,p,m,output):
    z=int(np.flatnonzero(m.sum((1,2))>0)[len(np.flatnonzero(m.sum((1,2))>0))//2])
    fig,axs=plt.subplots(2,4,figsize=(14,7),facecolor='#f7f8fa')
    ims=[b[z],t[z],p[z],np.abs(p[z]-t[z]),t[z]-b[z],p[z]-b[z],m[z],np.abs(b[z]-t[z])]
    titles=['Baseline MRI','Real follow-up MRI','Generated follow-up MRI','Generation absolute error','True change: t1 - t0','Predicted change: generated - t0','Baseline brain-support region','Identity absolute error']
    for i,(ax,im,title) in enumerate(zip(axs.flat,ims,titles)):
        kwargs=dict(cmap='coolwarm',vmin=-.4,vmax=.4) if i in [4,5] else dict(cmap='magma',vmin=0,vmax=.4) if i in [3,7] else dict(cmap='gray',vmin=0,vmax=1)
        art=ax.imshow(im.T,origin='lower',**kwargs);ax.set_title(title,fontsize=10);ax.axis('off')
        if i in [3,4,5,7]:fig.colorbar(art,ax=ax,shrink=.7)
    fig.suptitle(f'Patient {pid} | interval {weeks:g} weeks | baseline median support slice {z} | single fixed seed',fontsize=12)
    fig.tight_layout();fig.savefig(output,dpi=150);plt.close(fig)

def evaluate(checkpoint,run,limit=None):
    splits=read(ROOT/'data/splits.json');ids=splits['test'];ids=ids[:limit] if limit else ids
    ck=__import__('torch').load(checkpoint,map_location='cpu',weights_only=False)
    if ck['config']['splits_sha256']!=sha(ROOT/'data/splits.json'):raise ValueError('Split changed since training')
    manifest={r['patient_id']:r for r in read(ROOT/'data/manifest.json')};output=ROOT/'results'/run;output.mkdir(parents=True,exist_ok=True)
    dump(output/'evaluation_protocol.json',dict(patients=ids,examples=splits['test'][:3],selection='first 3 numeric test IDs, median baseline support slice',
         checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),normalization='baseline .5/99.5 percentile clipped [0,1] shared by pair',
         data_range=1,minimum_region_pixels_per_slice=10,metrics='slice first then patient; SSIM win7 with centers at 3-pixel eroded baseline support; no tumor Dice',sampling='single predefined seed; no target-based sample selection'))
    results=[];started=time.time()
    for pid in ids:
        row=manifest[pid];dest=output/pid
        # This function independently opens baseline only and writes reconstructed NIfTI.
        pred,b,m,plan=generate(row['source'],row['weeks'],checkpoint,dest,patient_id=int(pid))
        # Future target is opened for evaluation only, AFTER generation has returned.
        with np.load(ROOT/f'cache/{pid}.npz') as d:
            target=d['target'].astype('float32');gtv=d['gtv']
            assert np.allclose(b,d['baseline'].astype('float32'),atol=.00025), 'preprocess differs from cache'
        # Identity uses exactly the same (float16 cache precision) target and brain region.
        score=patient_metrics(pred,target,m,b,gtv);identity=patient_metrics(b,target,m,b,gtv)
        record=dict(patient_id=pid,weeks=row['weeks'],model=score,identity=identity,
                    delta_brain_mae=score['brain_support']['mae']-identity['brain_support']['mae'])
        results.append(record);dump(dest/'metrics.json',record)
        # All test patients get figures; displayed examples still chosen before seeing results.
        plot_example(pid,row['weeks'],b,target,pred,m,dest/'comparison.png')
        generated=nib.load(str(dest/'prediction_normalized.nii.gz'));source=nib.load(row['source']);coverage=nib.load(str(dest/'coverage.nii.gz')).get_fdata()>0
        values=generated.get_fdata(dtype=np.float32)
        assert generated.shape==source.shape and np.allclose(generated.affine,source.affine,atol=1e-5)
        assert np.isfinite(values[coverage]).all() and np.isnan(values[~coverage]).all()
        dump(dest/'nifti_verification.json',dict(native_shape=list(generated.shape),affine_matches_baseline=True,finite_inside_coverage=True,nan_outside_coverage=True,covered_voxels=int(coverage.sum())))
        dump(output/'per_patient.json',results)
        print(f'{run} patient={pid} MAE={score["brain_support"]["mae"]:.5f} identity={identity["brain_support"]["mae"]:.5f} seconds={time.time()-started:.1f}',flush=True)
    summary=dict(patients=len(results),checkpoint_step=ck['step'],seconds=time.time()-started,
                 improved_mae_patients=sum(r['delta_brain_mae']<0 for r in results),normalization_data_range=1.,
                 aggregation='equal-weight slice means within patient, then equal-weight patients')
    for method in ['model','identity']:
        summary[method]={}
        for region in ['brain_support','baseline_planning_GTV']:
            rr=[r[method][region] for r in results if r[method].get(region)]
            if rr:
                means={}
                for k in rr[0]:
                    if k=='slices':continue
                    values=[r[k] for r in rr if r[k] is not None]
                    means[k]=float(np.mean(values)) if values else None
                summary[method][region]={**means,'patients':len(rr)}
    dump(output/'summary.json',summary)
    with (output/'per_patient.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['patient_id','weeks','model_mae','identity_mae','delta_mae','model_psnr','identity_psnr','model_ssim','identity_ssim'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in results:
            a=r['model']['brain_support'];b=r['identity']['brain_support'];w.writerow(dict(patient_id=r['patient_id'],weeks=r['weeks'],model_mae=a['mae'],identity_mae=b['mae'],delta_mae=r['delta_brain_mae'],model_psnr=a['psnr'],identity_psnr=b['psnr'],model_ssim=a['ssim'],identity_ssim=b['ssim']))
    print(summary,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--run',required=True);p.add_argument('--limit',type=int);a=p.parse_args();evaluate(a.checkpoint,a.run,a.limit)
