"""Deployment entry point: no followup/paired cache access or target argument."""
import argparse,time
import nibabel as nib
from fm.common import ROOT,read,write,seed
from fm.core import UNet,solve
from fm.preprocess import prepare_baseline,restore_stack
from prepare import baseline_mask
import numpy as np
import torch

def predict(baseline,weeks,checkpoint,out,mask=None,steps=16,solver='euler',sampling_seed=7391):
    if not np.isfinite(weeks) or weeks<0:raise ValueError('weeks must be finite and >=0')
    if steps<1:raise ValueError('steps must be positive')
    seed(20261101);ck=torch.load(checkpoint,map_location='cuda',weights_only=False);net=UNet(**ck['stats'],channels=ck['config']['channels']).cuda();net.load_state_dict(ck['model']);net.eval()
    b,brain,plan,img,support=prepare_baseline(baseline)
    m,roi,av,status=baseline_mask(mask,img,plan,support)
    predictions=[];raw_min=float('inf');raw_max=-float('inf');nfe=None;start=time.perf_counter()
    for z in range(0,len(b),8):
        x=torch.tensor(b[z:z+8,None],device='cuda');n=len(x)
        y,nfe=solve(net,x,torch.tensor(m[z:z+8,None].astype('float32'),device='cuda'),torch.full((n,),float(av),device='cuda'),torch.full((n,),float(weeks),device='cuda'),ck['kind'],steps,solver,sampling_seed+z)
        raw_min=min(raw_min,float(y.min()));raw_max=max(raw_max,float(y.max()));predictions.append(y[:,0].clamp(0,1).cpu().numpy())
    pred=np.concatenate(predictions);restore_stack(pred,plan,baseline,out,support)
    # preserve raw model-grid output separately for reproducibility of evaluation.
    np.save(str(out)+'/model_grid.npy',pred)
    write(str(out)+'/inference.json',dict(baseline=str(baseline),weeks=weeks,mask=str(mask),mask_status=status,kind=ck['kind'],nfe_per_slice=nfe,total_batch_network_calls=nfe*len(predictions),solver=solver,steps=steps,sampling_seed=sampling_seed,seconds=time.perf_counter()-start,raw_range=[raw_min,raw_max],postprocessing='clamp once at final output [0,1], no intermediate state clipping',coverage='baseline support only; NaN elsewhere; 2D slices may be discontinuous'))
    return pred

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--weeks',required=True,type=float);p.add_argument('--mask');p.add_argument('--checkpoint',required=True);p.add_argument('--out',required=True);p.add_argument('--steps',type=int,default=16);p.add_argument('--solver',choices=['euler','heun'],default='euler');p.add_argument('--seed',type=int,default=7391);a=p.parse_args()
    predict(a.baseline,a.weeks,a.checkpoint,a.out,a.mask,a.steps,a.solver,a.seed)
