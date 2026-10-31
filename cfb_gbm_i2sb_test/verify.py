"""Numerical bridge, real-slice gradient, checkpoint and inference independence checks."""
import argparse, tempfile, time
import numpy as np
import torch
from cfb.common import ROOT,dump,read,seed_all,sha
from cfb.bridge import Bridge
from cfb.model import SmallUNet
from cfb.training import build,predict_stack,tensor

def numerical():
    seed_all(101);device='cuda' if torch.cuda.is_available() else 'cpu';br=Bridge();results={}
    n=60000;x0=torch.full((n,1,1,1),-.3,device=device);x1=torch.full_like(x0,.6)
    for tvalue in [0.,1/64,.5,63/64,1.]:
        t=torch.full((n,),tvalue,device=device);xt=br.q(x0,x1,t,torch.randn_like(x0));a=float(br.variance(torch.tensor(tvalue)));b=.5-a
        mu=(b*(-.3)+a*.6)/.5;var=a*b/.5
        assert torch.isfinite(xt).all()
        if tvalue in [0.,1.]:assert torch.equal(xt,x0 if tvalue==0 else x1)
        assert abs(float(xt.mean())-mu)<.005 and abs(float(xt.var())-var)<.004
        if tvalue>0:
            label=br.label(xt,x0,t);assert torch.isfinite(label).all()
            assert float((br.x0_from_eps(xt,label,t)-x0).abs().max())<1e-6
        results[str(tvalue)]=dict(observed_mean=float(xt.mean()),expected_mean=mu,observed_variance=float(xt.var()),expected_variance=var)
    try:br.label(x0,x0,torch.zeros(n,device=device));raise AssertionError('t=0 must be rejected')
    except ValueError:pass
    v=br.variance(torch.linspace(0,1,4097,device=device));assert (torch.diff(v)>0).all()
    # Oracle reverse chain must reproduce Eq11 marginal, not only endpoints.
    xt=x1.clone()
    for i in range(64,32,-1):xt=br.posterior(xt,x0,(i-1)/64,i/64,torch.randn_like(xt))
    assert abs(float(xt.mean())-.15)<.005 and abs(float(xt.var())-.125)<.004
    end=br.posterior(xt,x0,0,.5,torch.randn_like(xt));assert torch.equal(end,x0)
    results['oracle_reverse_midpoint']=dict(mean=float(xt.mean()),variance=float(xt.var()),expected_mean=.15,expected_variance=.125)
    d=np.load(ROOT/'cache/003.npz');base=tensor(d['baseline'][60:62,None].astype('float32')*2-1,device);target=tensor(d['target'][60:62,None].astype('float32')*2-1,device)
    net=SmallUNet().to(device);t=torch.tensor([1/64,1.],device=device);weeks=torch.tensor([22.,22.],device=device)
    xt=br.q(target,base,t,torch.randn_like(base));loss=(net(xt,base,t,weeks)-br.label(xt,target,t)).square().mean();loss.backward()
    grads=[p.grad for p in net.parameters() if p.grad is not None];assert all(torch.isfinite(g).all() for g in grads);assert sum(float(g.abs().sum()) for g in grads)>0
    sample=br.sample(net,base,weeks,16,9);assert torch.isfinite(sample).all()
    dest=ROOT/'weights/numerical_test.pt';dest.parent.mkdir(exist_ok=True);torch.save(net.state_dict(),dest)
    net2=SmallUNet().to(device);net2.load_state_dict(torch.load(dest,weights_only=True,map_location=device));assert torch.equal(sample,br.sample(net2,base,weeks,16,9))
    results.update(real_pair_loss=float(loss.detach()),forward_backward_finite=True,save_reload_bitwise_equal=True,
                   exact_q_endpoints=True,endpoint_zero_label_rejected=True,oracle_reverse_endpoint_exact=True,
                   parameter_count=sum(p.numel() for p in net.parameters()),device=device)
    dump(ROOT/'reports/numerical_verification.json',results);print(results,flush=True)

def overfit(steps=600):
    seed_all(765);device='cuda' if torch.cuda.is_available() else 'cpu';pid=read(ROOT/'data/splits.json')['train'][0]
    row=next(r for r in read(ROOT/'data/manifest.json') if r['patient_id']==pid)
    d=np.load(ROOT/f'cache/{pid}.npz');n=len(d['baseline']);zs=[n//2,n//2+1]
    b=tensor(d['baseline'][zs,None].astype('float32')*2-1,device);target=tensor(d['target'][zs,None].astype('float32')*2-1,device)
    weeks=torch.full((2,),row['weeks'],device=device);cfg=read(ROOT/'configs/short.json');cfg.update(kind='i2sb',week_mean=float(np.log1p(row['weeks'])),week_std=1.)
    net,br=build(cfg,'i2sb',device);opt=torch.optim.AdamW(net.parameters(),lr=.001)
    # Fixed evaluation bridge states independent of stochastic training states.
    rng=torch.Generator(device=device).manual_seed(499);ts=torch.tensor([.25,.75],device=device)
    xtest=br.q(target,b,ts,torch.randn(b.shape,device=device,generator=rng));label=br.label(xtest,target,ts)
    @torch.no_grad()
    def evaluate():
        net.eval();l=float((net(xtest,b,ts,weeks)-label).square().mean())
        pred=br.sample(net,b,weeks,16,9021)
        m=tensor(d['mask'][zs,None].astype('float32'),device)>.5
        return dict(held_noise_bridge_mse=l,sample_brain_mae=float((pred[m]-target[m]).abs().mean()/2),identity_brain_mae=float((b[m]-target[m]).abs().mean()/2))
    before=evaluate();started=time.time();logs=[]
    for step in range(1,steps+1):
        net.train();t=torch.randint(1,65,(2,),device=device).float()/64;xt=br.q(target,b,t,torch.randn_like(b));lab=br.label(xt,target,t)
        opt.zero_grad();loss=(net(xt,b,t,weeks)-lab).square().mean();loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),1.);opt.step()
        if step%100==0:
            metrics=evaluate();logs.append(dict(step=step,loss=float(loss.detach()),**metrics));print('overfit',logs[-1],flush=True)
    after=evaluate();out=ROOT/'weights/overfit';out.mkdir(exist_ok=True)
    torch.save(dict(model=net.state_dict(),config=cfg,step=steps),out/'last.pt')
    report=dict(patient=pid,split='train only',slices=zs,steps=steps,before=before,after=after,history=logs,
                held_noise_loss_ratio=after['held_noise_bridge_mse']/before['held_noise_bridge_mse'],seconds=time.time()-started,
                passed=after['held_noise_bridge_mse']<before['held_noise_bridge_mse']*.5,
                meaning='capacity/optimization check only; not independent generalization; weights never reused for main training')
    dump(ROOT/'reports/overfit.json',report)
    with torch.no_grad():p=((br.sample(net,b,weeks,16,9021)[:,0]+1)/2).cpu().numpy()
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(2,4,figsize=(12,6))
    for i,z in enumerate(zs):
        for ax,im,title in zip(axs[i],[d['baseline'][z],d['target'][z],p[i],np.abs(p[i]-d['target'][z])],['Baseline','Real follow-up','Overfit prediction','Absolute error']):
            ax.imshow(im.T,origin='lower',cmap='gray' if title!='Absolute error' else 'magma',vmin=0,vmax=1 if title!='Absolute error' else .4);ax.set_title(title);ax.axis('off')
    fig.tight_layout();fig.savefig(ROOT/'reports/overfit.png',dpi=140);plt.close(fig)
    print(report,flush=True)
    if not report['passed']:raise RuntimeError('Overfit check failed; inspect report before main claims')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--overfit',action='store_true');p.add_argument('--steps',type=int,default=600);a=p.parse_args()
    if a.overfit:overfit(a.steps)
    else:numerical()
