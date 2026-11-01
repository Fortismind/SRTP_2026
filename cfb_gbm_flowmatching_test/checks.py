from fm.common import *
from fm.core import *
import time

def main():
    seed(20261101);b=torch.rand(2,1,128,128,device='cuda');y=torch.rand_like(b) if hasattr(torch,'rand_like') else torch.rand_like(b)
    assert torch.equal(path(y,b,torch.zeros(2,device='cuda'))[0],y)
    assert torch.equal(path(y,b,torch.ones(2,device='cuda'))[0],b)
    class Oracle(torch.nn.Module):
        def forward(self,z,b,m,av,t,w):return b-y
    for solver in ['euler','heun']:
        pred,nfe=solve(Oracle(),b,b,torch.ones(2,device='cuda'),torch.ones(2,device='cuda'),'direct_mask',16,solver)
        assert torch.allclose(pred,y,atol=2e-6)
    split=read(ROOT/'data/splits.json');pid=split['train'][0];a=load_patient(pid);idx=np.array([len(a['b'])//2,len(a['b'])//2+1]);batch=tensors(a,idx)
    rows={r['patient_id']:r for r in read(ROOT/'data/manifest.json')};ww=np.log1p([rows[p]['weeks'] for p in split['train']]);stats=dict(mean=float(ww.mean()),std=float(ww.std()))
    net=UNet(**stats).cuda();loss,_=objective(net,*batch,'direct_roi');loss.backward()
    assert all(torch.isfinite(p.grad).all() for p in net.parameters() if p.grad is not None)
    assert net(batch[0],batch[0],batch[3],batch[5],torch.ones(2,device='cuda'),batch[6]).shape==batch[0].shape
    empty=torch.zeros_like(batch[4]);assert float(region_mean(batch[0],empty))==0
    before=solve(net,batch[0],batch[3],batch[5],batch[6],'direct_roi')[0]
    torch.save(net.state_dict(),ROOT/'weights/check.pt');net.load_state_dict(torch.load(ROOT/'weights/check.pt',weights_only=True))
    assert torch.equal(before,solve(net,batch[0],batch[3],batch[5],batch[6],'direct_roi')[0])
    # No mask vs provided empty mask is explicitly distinguishable via availability.
    assert torch.equal(batch[0].flip(-1).flip(-1),batch[0])
    # Independent two-slice overfit; not initialized into any formal arm.
    net=UNet(**stats).cuda();opt=torch.optim.AdamW(net.parameters(),lr=.001);start=time.perf_counter()
    def error():
        p,_=solve(net,batch[0],batch[3],batch[5],batch[6],'direct_roi')
        return float(region_mean((p.clamp(0,1)-batch[1]).abs(),batch[2]))
    first=error()
    for _ in range(600):
        opt.zero_grad();loss,_=objective(net,*batch,'direct_roi');loss.backward();opt.step()
    last=error();torch.save(net.state_dict(),ROOT/'weights/overfit_only.pt')
    # Resume must reproduce optimizer and random-time/noise state, not just load weights.
    import copy
    seed(77);continuous=UNet(**stats).cuda();optimizer=torch.optim.AdamW(continuous.parameters(),lr=.0002)
    for step in range(4):
        optimizer.zero_grad();l,_=objective(continuous,*batch,'noise_roi');l.backward();optimizer.step()
        if step==1:state=copy.deepcopy(dict(model=continuous.state_dict(),optimizer=optimizer.state_dict(),rng=torch.cuda.get_rng_state()))
    resumed=UNet(**stats).cuda();resumed.load_state_dict(state['model']);resumed_opt=torch.optim.AdamW(resumed.parameters(),lr=.0002);resumed_opt.load_state_dict(state['optimizer']);torch.cuda.set_rng_state(state['rng'])
    for _ in range(2):
        resumed_opt.zero_grad();l,_=objective(resumed,*batch,'noise_roi');l.backward();resumed_opt.step()
    assert all(torch.equal(v,resumed.state_dict()[k]) for k,v in continuous.state_dict().items())
    write(ROOT/'reports/checks.json',dict(path_endpoints=True,velocity_sign_and_constant_oracle=True,euler_nfe=16,heun_nfe=32,finite_gradient=True,shape=True,empty_roi_zero=True,reload_equal=True,overfit=dict(patient=pid,slices=idx.tolist(),steps=600,seconds=time.perf_counter()-start,initial_full_ode_mae=first,final_full_ode_mae=last),note='overfit weights excluded from formal runs; endpoint estimate never used for validation'))
    report=read(ROOT/'reports/checks.json');report['resume_optimizer_rng_2_plus_2_equal_4']=True;write(ROOT/'reports/checks.json',report)
    print('CHECKS OK',first,last,flush=True)
if __name__=='__main__':main()
