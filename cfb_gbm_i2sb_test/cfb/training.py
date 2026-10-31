import time, random, copy
from collections import OrderedDict
from pathlib import Path
import numpy as np
import torch
from .common import ROOT,dump,read,seed_all,sha
from .model import SmallUNet
from .bridge import Bridge

class Cache:
    def __init__(self,maxsize=8):self.data=OrderedDict();self.maxsize=maxsize
    def get(self,pid):
        if pid not in self.data:
            with np.load(ROOT/f'cache/{pid}.npz') as f:self.data[pid]={k:f[k].astype(np.float32) for k in f.files}
            if len(self.data)>self.maxsize:self.data.popitem(last=False)
        self.data.move_to_end(pid);return self.data[pid]

def tensor(a,device):return torch.from_numpy(a.copy()).float().to(device)

def build(cfg,kind,device):
    net=SmallUNet(cfg['channels'],kind,cfg['week_mean'],cfg['week_std']).to(device)
    bridge=Bridge(cfg['bridge_steps'],cfg['total_variance'])
    return net,bridge

@torch.no_grad()
def predict_stack(net,bridge,baseline,weeks,cfg,device,pid=0,batch_size=8):
    net.eval();out=[]
    for start in range(0,len(baseline),batch_size):
        b=tensor(baseline[start:start+batch_size,None]*2-1,device)
        w=torch.full((len(b),),float(weeks),device=device)
        if cfg['kind']=='i2sb':p=bridge.sample(net,b,w,cfg['nfe'],cfg['sampling_seed']+int(pid)*10000+start)
        else:p=net(b,b,torch.zeros(len(b),device=device),w).clamp(-1,1)
        out.append(((p[:,0]+1)/2).clamp(0,1).cpu().numpy())
    return np.concatenate(out)

@torch.no_grad()
def validate(net,bridge,cfg,ids,manifest,cache,device):
    scores=[];identity=[]
    for pid in ids:
        d=cache.get(pid);z=np.unique(np.linspace(0,len(d['baseline'])-1,cfg['val_slices']).round().astype(int))
        p=predict_stack(net,bridge,d['baseline'][z],manifest[pid]['weeks'],cfg,device,int(pid))
        per=[];ident=[]
        for a,b,t,m in zip(p,d['baseline'][z],d['target'][z],d['mask'][z]>.5):
            if m.sum()>=cfg.get('validation_min_region_pixels',1):per.append(float(np.abs(a[m]-t[m]).mean()));ident.append(float(np.abs(b[m]-t[m]).mean()))
        scores.append(float(np.mean(per)));identity.append(float(np.mean(ident)))
    return dict(mae=float(np.mean(scores)),identity_mae=float(np.mean(identity)),patient_mae=dict(zip(ids,scores)),patients=ids)

def train(config,kind='i2sb',run='i2sb_short',resume=None):
    cfg=read(config);seed_all(cfg['seed']);device='cuda' if torch.cuda.is_available() else 'cpu'
    splits=read(ROOT/'data/splits.json');manifest={r['patient_id']:r for r in read(ROOT/'data/manifest.json')}
    w=np.log1p([manifest[p]['weeks'] for p in splits['train']])
    cfg.update(kind=kind,week_mean=float(w.mean()),week_std=float(w.std()),device=device,
               training_interval_range=[min(manifest[p]['weeks'] for p in splits['train']),max(manifest[p]['weeks'] for p in splits['train'])],
               splits_sha256=sha(ROOT/'data/splits.json'),manifest_sha256=sha(ROOT/'data/manifest.json'))
    out=ROOT/'weights'/run
    if (out/'last.pt').exists() and not resume:raise FileExistsError('Existing run: use a new --run name or --resume')
    out.mkdir(parents=True,exist_ok=True);logs=ROOT/'logs'/run;logs.mkdir(parents=True,exist_ok=True)
    dump(out/'config.json',cfg);net,bridge=build(cfg,kind,device);optimizer=torch.optim.AdamW(net.parameters(),lr=cfg['lr'],weight_decay=1e-4)
    rng=np.random.default_rng(cfg['seed']);cache=Cache();best=float('inf');start_step=0
    val_ids=splits['val'][:cfg['val_patients']]
    selection=dict(ids=val_ids,slices=cfg['val_slices'],nfe=cfg['nfe'],sampling_seed=cfg['sampling_seed'],minimum_pixels=cfg.get('validation_min_region_pixels',1))
    if resume:
        ck=torch.load(resume,map_location=device,weights_only=False)
        # Changing the patient split, preprocessing or model is not a valid continuation.
        for key in ['kind','channels','size','bridge_steps','total_variance','splits_sha256','manifest_sha256','week_mean','week_std']:
            if ck['config'][key]!=cfg[key]:raise ValueError('Resume configuration mismatch: '+key)
        if ck['config']['seed']!=cfg['seed']:raise ValueError('Cannot change seed during exact resume; use a fresh run')
        net.load_state_dict(ck['model']);optimizer.load_state_dict(ck['optimizer']);best=ck['best'];start_step=ck['step']
        rng.bit_generator.state=ck['numpy_rng'];torch.set_rng_state(ck['torch_rng'].cpu())
        if device=='cuda':torch.cuda.set_rng_state_all([s.cpu() for s in ck['cuda_rng']])
        random.setstate(ck['python_rng'])
        old=ck['config']
        old_selection=dict(ids=splits['val'][:old['val_patients']],slices=old['val_slices'],nfe=old['nfe'],sampling_seed=old['sampling_seed'],minimum_pixels=old.get('validation_min_region_pixels',1))
        if old_selection!=selection or not (out/'best.pt').exists():
            initial=validate(net,bridge,cfg,val_ids,manifest,cache,device)
            best=initial['mae']
            initial_ck=dict(ck,config=cfg,best=best,selection_protocol=selection)
            torch.save(initial_ck,out/'best.pt')
            dump(logs/'resume_rebaseline.json',dict(parent=str(resume),step=start_step,old_selection=old_selection,new_selection=selection,validation=initial,reason='New selection protocol or fork: parent current state evaluated anew; old best score not carried over'))
    if start_step>=cfg['steps']:raise ValueError('Total steps must exceed resumed step')
    dump(logs/'selection_protocol.json',dict(validation_ids=val_ids,criterion='minimum equal-patient baseline brain-support MAE on fixed baseline evenly spaced slices',sampling_seed=cfg['sampling_seed'],test_not_used=True))
    started=time.time();history=[]
    for step in range(start_step+1,cfg['steps']+1):
        net.train();pid=str(rng.choice(splits['train']));d=cache.get(pid)
        z=rng.integers(0,len(d['baseline']),size=cfg['batch_size'])
        b=tensor(d['baseline'][z,None]*2-1,device);target=tensor(d['target'][z,None]*2-1,device)
        weeks=torch.full((len(b),),float(manifest[pid]['weeks']),device=device)
        optimizer.zero_grad(set_to_none=True)
        if kind=='i2sb':
            t=torch.randint(1,bridge.steps+1,(len(b),),device=device).float()/bridge.steps
            xt=bridge.q(target,b,t,torch.randn_like(b));label=bridge.label(xt,target,t)
            loss=torch.nn.functional.mse_loss(net(xt,b,t,weeks),label)
        else:
            pred=net(b,b,torch.zeros(len(b),device=device),weeks)
            loss=torch.nn.functional.mse_loss(pred,target)
        if not torch.isfinite(loss):raise FloatingPointError('nonfinite training loss')
        loss.backward();grad=float(torch.nn.utils.clip_grad_norm_(net.parameters(),1.))
        if not np.isfinite(grad):raise FloatingPointError('nonfinite gradient')
        optimizer.step()
        row=dict(step=step,loss=float(loss.detach()),grad_norm=grad,patient=pid,elapsed_seconds=time.time()-started)
        timed_out=time.time()-started>cfg['max_minutes']*60
        if step%cfg['validate_every']==0 or step==cfg['steps'] or timed_out:
            val=validate(net,bridge,cfg,val_ids,manifest,cache,device);row['validation']=val
            improved=val['mae']<best
            if improved:best=val['mae']
            ck=dict(model=net.state_dict(),optimizer=optimizer.state_dict(),step=step,best=best,config=cfg,selection_protocol=selection,
                    numpy_rng=rng.bit_generator.state,torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all() if device=='cuda' else [],python_rng=random.getstate())
            torch.save(ck,out/'last.pt')
            if improved:torch.save(ck,out/'best.pt')
            print(f'{run} step={step} loss={float(loss.detach()):.5f} val_MAE={val["mae"]:.5f} best={best:.5f} seconds={time.time()-started:.1f}',flush=True)
        elif step%25==0:print(f'{run} step={step} loss={float(loss.detach()):.5f} seconds={time.time()-started:.1f}',flush=True)
        with (logs/'train.jsonl').open('a',encoding='utf-8') as f:
            import json;f.write(json.dumps(row)+'\n')
        history.append(row)
        if timed_out:break
    dump(logs/'summary.json',dict(run=run,kind=kind,start_step=start_step,last_step=step,best_val_mae=best,
         elapsed_seconds=time.time()-started,parameters=sum(p.numel() for p in net.parameters()),
         gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device=='cuda' else 0,validation_ids=val_ids))
    return out
