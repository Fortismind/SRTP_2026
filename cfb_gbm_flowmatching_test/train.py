from fm.common import *
from fm.core import UNet,objective,solve
import argparse,time,csv

@torch.no_grad()
def validate(net,patients,kind,cfg):
    net.eval();values=[]
    for pid,a in patients.items():
        idx=slices(a['brain'],cfg['validation_slices']);b,y,brain,m,roi,av,w=tensors(a,idx)
        pred,nfe=solve(net,b,m,av,w,kind,cfg['ode_steps'],cfg['solver'],7391+int(pid)*10000)
        error=((pred.clamp(0,1)-y).abs()*brain).sum((1,2,3))/brain.sum((1,2,3)).clamp_min(1)
        values.append(float(error.mean()))
    net.train();return float(np.mean(values))

def run(kind,run_name,cfg,resume=None):
    seed(cfg['seed']);out=ROOT/'weights'/run_name;out.mkdir(parents=True,exist_ok=True)
    if (out/'last.pt').exists() and not resume:raise FileExistsError('Use a new --run or --resume')
    stats=read(ROOT/'data/week_stats.json');net=UNet(**stats,channels=cfg['channels']).cuda()
    protocol_hashes={name:sha(ROOT/name) for name in ['data/effective_splits.json','data/manifest.json','data/week_stats.json']}
    opt=torch.optim.AdamW(net.parameters(),lr=cfg['lr']);rng=np.random.default_rng(cfg['seed'])
    split=read(ROOT/'data/effective_splits.json');patients={p:load_patient(p) for p in split['train']};val={p:load_patient(p) for p in split['val']}
    first=0;best=float('inf');elapsed=0;history=[];exposure={};sequence=hashlib.sha256();total_roi=0.
    if resume:
        ck=torch.load(resume,map_location='cuda',weights_only=False)
        assert ck['kind']==kind and ck['stats']==stats
        assert ck['protocol_hashes']==protocol_hashes, 'Data protocol changed; start a new run'
        for key in ['seed','batch','channels','lambda_roi','endpoint_fraction','validation_slices','ode_steps','solver','lr']:
            assert ck['config'][key]==cfg[key], 'Resume mismatch: '+key
        net.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);first=ck['step'];best=ck['best'];elapsed=ck['elapsed'];history=ck['history'];exposure=ck['exposure']
        rng.bit_generator.state=ck['numpy_rng'];torch.set_rng_state(ck['torch_rng'].cpu());torch.cuda.set_rng_state(ck['cuda_rng'].cpu())
        if not (out/'best.pt').exists():
            best=validate(net,val,kind,cfg)
            torch.save({**ck,'best':best,'config':cfg},out/'best.pt')
    write(ROOT/'configs'/f'{run_name}.json',cfg)
    torch.cuda.reset_peak_memory_stats();start=time.perf_counter();updates=[]
    for step in range(first+1,cfg['steps']+1):
        ts=time.perf_counter();pids=rng.choice(split['train'],cfg['batch']);items=[]
        for pid in pids:
            a=patients[pid];valid=np.where(a['brain'].sum((1,2))>=10)[0];z=int(rng.choice(valid));items.append(tensors(a,[z]));exposure[pid]=exposure.get(pid,0)+1;sequence.update(f'{pid}:{z};'.encode())
        batch=[torch.cat([v[j] for v in items]) for j in range(7)]
        # Paired flips share the same transform for images, support, GTV and ROI.
        if rng.random()<.5:batch[:5]=[a.flip(-1) for a in batch[:5]]
        loss,parts=objective(net,*batch,kind,cfg['lambda_roi'],cfg['endpoint_fraction'])
        if not torch.isfinite(loss):raise FloatingPointError('nonfinite training loss')
        opt.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),1.)
        if not torch.isfinite(norm):raise FloatingPointError('nonfinite gradients')
        opt.step();torch.cuda.synchronize();updates.append(time.perf_counter()-ts);total_roi+=parts['roi_fraction']
        if step%100==0:print(kind,step,float(loss),round(time.perf_counter()-start,1),flush=True)
        stop=(elapsed+time.perf_counter()-start)>=cfg['max_seconds']
        if step%cfg['validate_every']==0 or step==cfg['steps'] or stop:
            v=validate(net,val,kind,cfg);history.append(dict(step=step,loss=float(loss),validation_mae=v,**parts))
            ck=dict(model=net.state_dict(),optimizer=opt.state_dict(),step=step,kind=kind,stats=stats,config=cfg,protocol_hashes=protocol_hashes,best=min(best,v),elapsed=elapsed+time.perf_counter()-start,history=history,exposure=exposure,numpy_rng=rng.bit_generator.state,torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state())
            torch.save(ck,out/'last.pt')
            if v<best:best=v;torch.save(ck,out/'best.pt')
            print('validation',kind,step,v,flush=True)
        if stop:break
    summary=dict(kind=kind,updates=step,best_validation_mae=best,seconds=elapsed+time.perf_counter()-start,update_seconds_mean=float(np.mean(updates)),parameters=sum(p.numel() for p in net.parameters()),peak_MiB=torch.cuda.max_memory_allocated()/2**20,training_patients_seen=len(exposure),exposure=exposure,sample_sequence_sha256=sequence.hexdigest(),roi_sample_fraction=total_roi/max(step-first,1),history=history,checkpoint_selection=cfg['selection'])
    write(ROOT/'logs'/f'{run_name}.json',summary)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=KINDS+['all'],default='all');p.add_argument('--run');p.add_argument('--config',default='configs/bounded.json');p.add_argument('--resume');args=p.parse_args()
    cfg=read(args.config)
    for kind in KINDS if args.kind=='all' else [args.kind]:run(kind,args.run or kind,cfg,args.resume)
