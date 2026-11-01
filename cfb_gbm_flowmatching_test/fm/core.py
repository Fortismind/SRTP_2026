"""Independent paired endpoint Flow Matching, tau=1 source -> tau=0 followup."""
import math
import torch
from torch import nn
from torch.nn import functional as F

class Block(nn.Module):
    def __init__(self, ci, co, e):
        super().__init__()
        self.a=nn.Conv2d(ci,co,3,padding=1); self.b=nn.Conv2d(co,co,3,padding=1)
        self.n=nn.GroupNorm(4,co); self.m=nn.GroupNorm(4,co)
        self.mod=nn.Linear(e,2*co); self.skip=nn.Conv2d(ci,co,1) if ci!=co else nn.Identity()
    def forward(self,x,e):
        scale,shift=self.mod(e).chunk(2,1)
        h=self.n(self.a(x))*(1+scale[:,:,None,None])+shift[:,:,None,None]
        return F.silu(self.m(self.b(F.silu(h)))+self.skip(x))

class UNet(nn.Module):
    def __init__(self, mean=0., std=1., channels=16):
        super().__init__(); self.mean=mean; self.std=std; c=channels; e=c*4
        self.time=nn.Sequential(nn.Linear(32,e),nn.SiLU(),nn.Linear(e,e))
        self.weeks=nn.Sequential(nn.Linear(1,e),nn.SiLU(),nn.Linear(e,e))
        self.a=Block(4,c,e); self.b=Block(c,2*c,e); self.mid=Block(2*c,4*c,e)
        self.up=Block(6*c,2*c,e); self.end=Block(3*c,c,e); self.out=nn.Conv2d(c,1,3,padding=1)
        nn.init.zeros_(self.out.weight); nn.init.zeros_(self.out.bias)
    def forward(self,z,b,m,available,t,w):
        freq=torch.exp(torch.arange(16,device=t.device)*(-math.log(10000)/15))
        arg=t[:,None]*1000*freq
        e=self.time(torch.cat([arg.sin(),arg.cos()],1))+self.weeks(((torch.log1p(w)-self.mean)/max(self.std,1e-6))[:,None])
        h=self.a(torch.cat([z,b,m,available[:,None,None,None].expand_as(b)],1),e)
        j=self.b(F.avg_pool2d(h,2),e); k=self.mid(F.avg_pool2d(j,2),e)
        k=self.up(torch.cat([F.interpolate(k,size=j.shape[-2:],mode='nearest'),j],1),e)
        return self.out(self.end(torch.cat([F.interpolate(k,size=h.shape[-2:],mode='nearest'),h],1),e))

def path(y,source,t):
    tt=t[:,None,None,None]
    return (1-tt)*y+tt*source,source-y

def region_mean(error,mask):
    area=mask.sum((1,2,3)); valid=area>0
    values=(error*mask).sum((1,2,3))/area.clamp_min(1)
    return values[valid].mean() if valid.any() else error.sum()*0

def objective(net,b,y,brain,m,roi,available,w,kind,lam=.1,endpoint_fraction=.125):
    if kind=='direct': m=torch.zeros_like(m); available=torch.zeros_like(available)
    t=torch.rand(b.shape[0],device=b.device)
    t[:max(1,round(b.shape[0]*endpoint_fraction))]=1
    source=torch.randn_like(b) if kind=='noise_roi' else b
    z,u=path(y,source,t)
    if kind=='regression':
        pred=b+net(b,b,m,available,torch.ones_like(t),w)
        main=region_mean((pred-y)**2,brain)
    else:
        v=net(z,b,m,available,t,w); main=region_mean((v-u)**2,brain)
        pred=z-t[:,None,None,None]*v
    local=region_mean((pred-y).abs(),roi)
    weight=lam if kind in ('direct_roi','noise_roi','regression') else 0
    return main+weight*local,dict(fm_or_mse=float(main.detach()),roi=float(local.detach()),roi_fraction=float((roi.sum((1,2,3))>0).float().mean()))

@torch.no_grad()
def solve(net,b,m,available,w,kind,steps=16,solver='euler',seed=7391):
    if kind=='identity':return b.clone(),0
    if kind=='direct':m=torch.zeros_like(m);available=torch.zeros_like(available)
    t=torch.ones(b.shape[0],device=b.device)
    if kind=='regression':return b+net(b,b,m,available,t,w),1
    gen=torch.Generator(device=b.device).manual_seed(seed)
    z=torch.randn(b.shape,device=b.device,generator=gen) if kind=='noise_roi' else b.clone()
    nfe=0;h=1/steps
    for k in range(steps):
        t.fill_(1-k*h);v=net(z,b,m,available,t,w);nfe+=1
        next_z=z-h*v
        if solver=='heun':
            t.fill_(1-(k+1)*h);v2=net(next_z,b,m,available,t,w);nfe+=1
            next_z=z-h*(v+v2)/2
        z=next_z
        if not torch.isfinite(z).all():raise FloatingPointError('nonfinite ODE state')
    return z,nfe
