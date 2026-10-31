"""Real target-denied inference, deterministic resume and image-space tests."""
import sys,json
from pathlib import Path
import numpy as np
import torch
from cfb.common import ROOT,read,dump,seed_all
from cfb.training import train,build,predict_stack
from infer import generate

def resume_check():
    cfg=read(ROOT/'configs/short.json');cfg.update(steps=4,validate_every=2,val_patients=1,val_slices=2,batch_size=2,max_minutes=3)
    folder=ROOT/'configs/verification';folder.mkdir(exist_ok=True)
    dump(folder/'four.json',cfg);train(folder/'four.json','i2sb','resume_full')
    cfg['steps']=2;dump(folder/'two.json',cfg);train(folder/'two.json','i2sb','resume_split')
    train(folder/'four.json','i2sb','resume_split',ROOT/'weights/resume_split/last.pt')
    a=torch.load(ROOT/'weights/resume_full/last.pt',map_location='cpu',weights_only=False)
    b=torch.load(ROOT/'weights/resume_split/last.pt',map_location='cpu',weights_only=False)
    equal=all(torch.equal(a['model'][k],b['model'][k]) for k in a['model'])
    assert equal,'resumed parameters differ'
    return dict(continuous_updates=4,split_updates='2 + resume to 4',model_bitwise_equal=equal)

def inference_check():
    split=read(ROOT/'data/splits.json');pid=split['test'][0]
    row=next(r for r in read(ROOT/'data/manifest.json') if r['patient_id']==pid)
    checkpoint=ROOT/'weights/i2sb_short/best.pt';guard={'active':False};reads=[]
    def audit(event,args):
        if not guard['active'] or event!='open' or not isinstance(args[0],(str,bytes)):return
        path=str(args[0]);low=path.lower().replace('\\','/')
        if low.endswith('.npz') or '_t1_t1gd.nii' in low or '_t2_' in low or '_gtv.nii' in low:
            raise RuntimeError('Forbidden future/cache/mask read during inference: '+path)
        if '.nii' in low:reads.append(path)
    sys.addaudithook(audit);guard['active']=True
    # Demonstrate that the guard really blocks a future read.
    blocked=False
    try:open(row['target'],'rb')
    except RuntimeError:blocked=True
    guard['active']=False
    assert blocked
    guard['active']=True
    try:pred,b,m,plan=generate(row['source'],row['weeks'],checkpoint,ROOT/'results/inference_guard_check',patient_id=int(pid))
    finally:guard['active']=False
    device='cuda' if torch.cuda.is_available() else 'cpu';ck=torch.load(checkpoint,map_location=device,weights_only=False);cfg=ck['config'];net,br=build(cfg,'i2sb',device);net.load_state_dict(ck['model']);net.eval()
    z=len(b)//2;batch=b[z:z+2]
    p1=predict_stack(net,br,batch,row['weeks'],cfg,device,int(pid));p2=predict_stack(net,br,batch,row['weeks'],cfg,device,int(pid));assert np.array_equal(p1,p2)
    cfg2=cfg.copy();cfg2['sampling_seed']+=1;p3=predict_stack(net,br,batch,row['weeks'],cfg2,device,int(pid))
    p4=predict_stack(net,br,batch,row['weeks']+5,cfg,device,int(pid))
    record=dict(patient=pid,split='test; checkpoint already selected',future_read_guard_proven_active=blocked,
                target_cache_and_gtv_reads_during_generation=0,nifti_file_accesses=sorted(set(reads)),
                same_seed_bitwise_equal=bool(np.array_equal(p1,p2)),different_seed_mae=float(np.abs(p1-p3).mean()),
                interval_plus5weeks_prediction_mae_difference=float(np.abs(p1-p4).mean()),
                warning='time sensitivity is a wiring check, not evidence of correct biological response')
    return record

if __name__=='__main__':
    report=dict(resume=resume_check(),inference=inference_check());dump(ROOT/'reports/integration_verification.json',report);print(report,flush=True)
