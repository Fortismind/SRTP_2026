import math
import torch
from torch import nn
import torch.nn.functional as F

class Block(nn.Module):
    def __init__(self, cin, cout, emb):
        super().__init__()
        self.c1=nn.Conv2d(cin,cout,3,padding=1); self.n1=nn.GroupNorm(4,cout)
        self.c2=nn.Conv2d(cout,cout,3,padding=1); self.n2=nn.GroupNorm(4,cout)
        self.time=nn.Linear(emb,cout); self.skip=nn.Conv2d(cin,cout,1) if cin!=cout else nn.Identity()
    def forward(self,x,e):
        h=F.silu(self.n1(self.c1(x)))+self.time(e)[:,:,None,None]
        return F.silu(self.n2(self.c2(h))+self.skip(x))

class SmallUNet(nn.Module):
    def __init__(self, channels=16, kind='i2sb', week_mean=0., week_std=1.):
        super().__init__(); self.kind=kind; self.week_mean=week_mean; self.week_std=week_std
        c=channels; e=c*4
        self.embed=nn.Sequential(nn.Linear(33,e),nn.SiLU(),nn.Linear(e,e))
        self.d1=Block(2,c,e); self.d2=Block(c,c*2,e); self.mid=Block(c*2,c*4,e)
        self.u2=Block(c*6,c*2,e); self.u1=Block(c*3,c,e); self.out=nn.Conv2d(c,1,3,padding=1)
        nn.init.zeros_(self.out.weight); nn.init.zeros_(self.out.bias)
    def forward(self,xt,baseline,t,weeks):
        freq=torch.exp(torch.arange(16,device=t.device)*(-math.log(10000)/15))
        arg=t[:,None]*1000*freq[None,:]
        w=((torch.log1p(weeks)-self.week_mean)/max(self.week_std,1e-6))[:,None]
        e=self.embed(torch.cat([arg.sin(),arg.cos(),w],1))
        a=self.d1(torch.cat([xt,baseline],1),e); b=self.d2(F.avg_pool2d(a,2),e)
        h=self.mid(F.avg_pool2d(b,2),e)
        h=self.u2(torch.cat([F.interpolate(h,size=b.shape[-2:],mode='nearest'),b],1),e)
        h=self.u1(torch.cat([F.interpolate(h,size=a.shape[-2:],mode='nearest'),a],1),e)
        y=self.out(h)
        return baseline+y if self.kind=='regression' else y
