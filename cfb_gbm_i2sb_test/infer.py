"""Standalone target-free CLI. Reads baseline, weeks and trusted local checkpoint only."""
import argparse
from pathlib import Path
import numpy as np
import torch
from cfb.common import dump,seed_all,sha
from cfb.preprocess import prepare_baseline,restore_stack
from cfb.training import build,predict_stack

def generate(baseline,weeks,checkpoint,output,seed=None,patient_id=0,device=None):
    if not np.isfinite(weeks) or weeks<=0:raise ValueError('weeks must be finite and > 0')
    seed_all(20261025);device=device or ('cuda' if torch.cuda.is_available() else 'cpu')
    ck=torch.load(checkpoint,map_location=device,weights_only=False);cfg=ck['config'].copy()
    if seed is not None:cfg['sampling_seed']=seed
    b,m,plan,_,support=prepare_baseline(baseline,cfg['size'])
    net,bridge=build(cfg,cfg['kind'],device);net.load_state_dict(ck['model']);net.eval()
    pred=predict_stack(net,bridge,b,float(weeks),cfg,device,int(patient_id))
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    restore_stack(pred,plan,baseline,output,support)
    np.save(output/'prediction_stack.npy',pred.astype('float32'))
    dump(output/'inference.json',dict(baseline=str(baseline),weeks=weeks,checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),checkpoint_step=ck['step'],
         model=cfg['kind'],sampling_seed=cfg['sampling_seed'],patient_seed_offset=int(patient_id)*10000,
         batch_size=8,batch_seed_rule='sampling_seed + patient_id*10000 + first_slice_index_of_batch',nfe=cfg['nfe'],
         future_inputs=[],plan=plan,training_interval_range=cfg.get('training_interval_range'),device=device))
    return pred,b,m,plan

if __name__=='__main__':
    p=argparse.ArgumentParser(description='基线增强T1 + 临床间隔(周) -> 随访MRI；只加载自己生成的可信权重')
    p.add_argument('--baseline',required=True);p.add_argument('--weeks',type=float,required=True);p.add_argument('--checkpoint',required=True);p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=7391);p.add_argument('--patient-id',type=int,default=0);p.add_argument('--device',choices=['cuda','cpu'])
    a=p.parse_args();generate(a.baseline,a.weeks,a.checkpoint,a.output,a.seed,a.patient_id,a.device)
