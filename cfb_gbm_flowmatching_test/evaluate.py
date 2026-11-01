from fm.common import *
from fm.core import UNet,solve
from fm.metrics import patient_metrics
from fm.preprocess import restore_stack
from train import validate
from infer import predict
import nibabel as nib
import argparse,time,csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def metrics(p,a):
    r=patient_metrics(p,a['y'].astype('float32'),a['brain'],a['b'].astype('float32'),a['gtv'])
    extra=patient_metrics(p,a['y'].astype('float32'),a['brain'],a['b'].astype('float32'),a['roi'])
    r['baseline_ROI']=extra.get('baseline_planning_GTV')
    ring=a['roi']&~a['gtv']&a['brain']
    r['GTV_surrounding_5mm']=patient_metrics(p,a['y'].astype('float32'),a['brain'],a['b'].astype('float32'),ring).get('baseline_planning_GTV')
    mask=a['brain'];actual=(a['y'].astype('float32')-a['b'].astype('float32'))[mask];change=(p-a['b'].astype('float32'))[mask]
    valid=np.abs(actual)>.02
    r['change_direction_accuracy_gt_0.02']=float(np.mean(np.sign(actual[valid])==np.sign(change[valid]))) if valid.any() else None
    r['change_correlation']=float(np.corrcoef(actual,change)[0,1]) if min(np.std(actual),np.std(change))>1e-6 else None
    return r

def figures(pid,kind,p,a):
    z=int(slices(a['brain'],3)[1]);b=a['b'][z];y=a['y'][z]
    fig,axs=plt.subplots(1,7,figsize=(21,3))
    ims=[b,y,p[z],abs(p[z]-y),y-b,p[z]-b,b]
    for i,(ax,im,label) in enumerate(zip(axs,ims,['Baseline','Actual followup','Generated','Absolute error','Actual change','Predicted change','Baseline GTV / ROI'])):
        ax.imshow(im,cmap='coolwarm' if i in (4,5) else 'gray',vmin=-.5 if i in (4,5) else 0,vmax=.5 if i in (4,5) else 1)
        if i==6:
            if a['gtv'][z].any():ax.contour(a['gtv'][z],levels=[.5],colors='r',linewidths=.7)
            if a['roi'][z].any():ax.contour(a['roi'][z],levels=[.5],colors='y',linewidths=.5)
        ax.set_title(label);ax.axis('off')
    fig.suptitle(f'{pid} {kind}, baseline-selected z={z}');fig.tight_layout();fig.savefig(ROOT/'results'/kind/pid/'comparison.png',dpi=100);plt.close(fig)

def stability():
    cfg=read(ROOT/'configs/bounded.json');ids=read(ROOT/'data/effective_splits.json')['val'];patients={p:load_patient(p) for p in ids}
    results=[]
    for kind in ['direct_roi','noise_roi']:
        ck=torch.load(ROOT/'weights'/kind/'best.pt',map_location='cuda',weights_only=False);net=UNet(**ck['stats'],channels=cfg['channels']).cuda();net.load_state_dict(ck['model'])
        for solver,steps in [('euler',8),('euler',16),('euler',32),('heun',16)]:
            t=time.perf_counter();c={**cfg,'ode_steps':steps,'solver':solver};v=validate(net,patients,kind,c)
            results.append(dict(kind=kind,solver=solver,steps=steps,nfe=steps*(2 if solver=='heun' else 1),validation_mae=v,seconds=time.perf_counter()-t))
    write(ROOT/'reports/solver_stability.json',results)

def main():
    seed(20261101);split=read(ROOT/'data/effective_splits.json');byid={r['patient_id']:r for r in read(ROOT/'data/manifest.json')};all_results={};guard=[]
    stability() # validation only; test protocol remains fixed Euler 16.
    for kind in ['identity']+KINDS:
        patients={}
        for pid in split['test']:
            a=load_patient(pid);r=byid[pid];out=ROOT/'results'/kind/pid;out.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
            if kind=='identity':
                p=a['b'].astype('float32');timing=dict(seconds=0.,nfe_per_slice=0)
            else:
                # Actively block all NIfTI reads except baseline and optional baseline GTV.
                original_load=nib.load;original_numpy_load=np.load;accesses=[]
                allowed={str(Path(r['source']).resolve()),str(Path(r['baseline_gtv']).resolve())} if r.get('baseline_gtv') else {str(Path(r['source']).resolve())}
                def guarded(path,*args,**kwargs):
                    q=str(Path(path).resolve());assert q in allowed, 'Forbidden future NIfTI read: '+q
                    accesses.append(q);return original_load(path,*args,**kwargs)
                def no_cache(*args,**kwargs):raise AssertionError('Paired cache read during inference')
                rejected_future=False;rejected_cache=False
                try:guarded(r['target'])
                except AssertionError:rejected_future=True
                try:no_cache(ROOT/'cache'/f'{pid}.npz')
                except AssertionError:rejected_cache=True
                assert rejected_future and rejected_cache
                nib.load=guarded;np.load=no_cache
                try:p=predict(r['source'],float(r['weeks']),ROOT/'weights'/kind/'best.pt',out,r.get('baseline_gtv'),sampling_seed=7391+int(pid)*10000)
                finally:nib.load=original_load;np.load=original_numpy_load
                guard.append(dict(kind=kind,patient=pid,allowed_reads_only=True,cache_reads=0,guard_rejection_selftest=True,nifti_reads=sorted(set(accesses))))
                timing=read(out/'inference.json')
                # Native grid round-trip including qform/sform and coverage.
                src=nib.load(r['source']);dst=nib.load(out/'prediction_normalized.nii.gz');coverage=nib.load(out/'coverage.nii.gz').get_fdata()>0;raw=dst.get_fdata()
                assert src.shape==dst.shape and np.allclose(src.affine,dst.affine)
                for name in ['qform','sform']:
                    f0,c0=getattr(src,'get_'+name)(coded=True);f1,c1=getattr(dst,'get_'+name)(coded=True);assert c0==c1 and (f0 is None or np.allclose(f0,f1))
                assert np.isfinite(raw[coverage]).all() and np.isnan(raw[~coverage]).all()
                write(out/'spatial_verification.json',dict(shape_affine_qform_sform_match=True,coverage_finite_outside_nan=True))
            result=metrics(p,a);result.update(patient=pid,inference_seconds=timing['seconds'],nfe=timing['nfe_per_slice']);patients[pid]=result
            write(out/'metrics.json',result);figures(pid,kind,p,a);print('evaluate',kind,pid,round(time.perf_counter()-start,2),flush=True)
        write(ROOT/'results'/kind/'per_patient.json',patients)
        flat=[dict(patient=pid,**v['brain_support']) for pid,v in patients.items()]
        with open(ROOT/'results'/kind/'per_patient.csv','w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=flat[0].keys());writer.writeheader();writer.writerows(flat)
        summary={}
        for region in ['brain_support','baseline_planning_GTV','baseline_ROI','GTV_surrounding_5mm']:
            vals=[v[region] for v in patients.values() if v.get(region)]
            summary[region]={key:float(np.mean([v[key] for v in vals if v.get(key) is not None])) for key in ['mae','psnr','ssim','predicted_change_mae','actual_change_mae'] if any(v.get(key) is not None for v in vals)}
            summary[region]['patients']=len(vals)
        summary['runtime']=dict(mean_patient_inference_seconds=float(np.mean([v['inference_seconds'] for v in patients.values()])),nfe_per_slice=next(iter(patients.values()))['nfe'])
        write(ROOT/'results'/kind/'summary.json',summary);all_results[kind]=summary
    comparison={}
    main=read(ROOT/'results/direct_roi/per_patient.json')
    for kind in ['identity','direct','direct_mask','noise_roi','regression']:
        other=read(ROOT/'results'/kind/'per_patient.json');deltas={pid:main[pid]['brain_support']['mae']-other[pid]['brain_support']['mae'] for pid in main}
        regions={}
        for region in ['baseline_planning_GTV','baseline_ROI','GTV_surrounding_5mm']:
            rd={pid:main[pid][region]['mae']-other[pid][region]['mae'] for pid in main if main[pid].get(region) and other[pid].get(region)}
            regions[region]=dict(patient_differences=rd,mean_mae_difference=float(np.mean(list(rd.values()))) if rd else None,improved_patients=sum(d<0 for d in rd.values()))
        comparison[kind]=dict(mean_mae_difference=float(np.mean(list(deltas.values()))),improved_patients=sum(d<0 for d in deltas.values()),patient_differences=deltas,regional_comparisons=regions)
    write(ROOT/'reports/comparison.json',comparison);write(ROOT/'reports/test_summary.json',all_results);write(ROOT/'reports/inference_guard.json',guard)
if __name__=='__main__':main()
