"""I2SB Eq.11/12 and Gaussian reverse posterior, implemented from equations.

Reference: Liu et al. ICML 2023; NVlabs/I2SB i2sb/diffusion.py, runner.py.
Exact continuous integrals and explicit endpoints replace inclusive discrete sums.
No official source is copied in this implementation. See THIRD_PARTY.md.
"""
import math
import torch

class Bridge:
    def __init__(self, steps=64, total_variance=0.5):
        assert steps >= 2 and total_variance > 0
        self.steps, self.total_variance = steps, total_variance

    def variance(self, t):
        # beta(t) proportional to .05 + .95 sin(pi*t)^2; integral over [0,1]=.525.
        t = torch.as_tensor(t)
        if ((t<0)|(t>1)).any(): raise ValueError('diffusion time outside [0,1]')
        v=self.total_variance * (.05*t + .95*(t/2-torch.sin(2*math.pi*t)/(4*math.pi))) / .525
        return torch.where(t==0,torch.zeros_like(v),torch.where(t==1,torch.full_like(v,self.total_variance),v))

    def v(self, t, x):
        return self.variance(torch.as_tensor(t,device=x.device,dtype=x.dtype)).reshape(-1,1,1,1)

    def q(self, x0, x1, t, noise):
        a = self.v(t,x0); b = (self.total_variance-a).clamp_min(0)
        return b/self.total_variance*x0 + a/self.total_variance*x1 + (a*b/self.total_variance).sqrt()*noise

    def label(self, xt, x0, t):
        a = self.v(t,xt)
        if (a <= 0).any(): raise ValueError('Eq12 undefined at t=0; train t in {1/N,...,1}')
        return (xt-x0)/a.sqrt()

    def x0_from_eps(self, xt, eps, t):
        return xt-self.v(t,xt).sqrt()*eps

    def posterior(self, xt, x0hat, s, t, noise):
        a, c = self.v(t,xt), self.v(s,xt)
        if (a <= 0).any() or (c > a).any(): raise ValueError('Require 0 <= s < t <= 1')
        ratio = c/a
        return (1-ratio)*x0hat + ratio*xt + (c*(1-ratio)).clamp_min(0).sqrt()*noise

    @torch.no_grad()
    def sample(self, net, baseline, weeks, nfe=16, seed=0):
        if not 1 <= nfe <= self.steps: raise ValueError('nfe outside supported range')
        rng = torch.Generator(device=baseline.device).manual_seed(seed)
        xt = baseline.clone()
        grid = torch.linspace(0,self.steps,nfe+1,device=xt.device).round()/self.steps
        for i in range(nfe,0,-1):
            t=grid[i].expand(len(xt)); s=grid[i-1].expand(len(xt))
            eps=net(xt,baseline,t,weeks)
            x0hat=self.x0_from_eps(xt,eps,t).clamp(-1,1)
            noise=torch.randn(xt.shape,device=xt.device,generator=rng)
            xt=self.posterior(xt,x0hat,s,t,noise)
        return xt
