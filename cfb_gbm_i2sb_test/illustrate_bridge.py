import numpy as np
import torch
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cfb.common import ROOT,seed_all,read
from cfb.bridge import Bridge

seed_all(99);pid=read(ROOT/'data/splits.json')['train'][0]
data=np.load(ROOT/f'cache/{pid}.npz');z=len(data['baseline'])//2
x0=torch.from_numpy(data['target'][z:z+1,None].astype('float32')*2-1)
x1=torch.from_numpy(data['baseline'][z:z+1,None].astype('float32')*2-1);br=Bridge()
fig,axs=plt.subplots(2,5,figsize=(14,6))
for ax,t in zip(axs[0],[0.,.25,.5,.75,1.]):
    q=br.q(x0,x1,torch.tensor([t]),torch.randn_like(x0));ax.imshow(((q[0,0]+1)/2).numpy().T,origin='lower',cmap='gray',vmin=0,vmax=1)
    ax.set_title(f'Bridge tau={t:g}'+(' (future)' if t==0 else ' (baseline)' if t==1 else ''));ax.axis('off')
t=torch.linspace(0,1,256);v=br.variance(t);a=.5-v
for ax in axs[1]:ax.axis('off')
ax=axs[1,0];ax.axis('on');ax.plot(t,v/.5,label='baseline weight');ax.plot(t,a/.5,label='future weight');ax.set_title('Endpoint mean weights');ax.legend(fontsize=7)
ax=axs[1,1];ax.axis('on');ax.plot(t,v*a/.5);ax.set_title('Bridge variance');ax.set_xlabel('diffusion tau')
ax=axs[1,2];ax.axis('on');ax.plot(t,v);ax.set_title('Integrated noise B(tau)');ax.set_xlabel('diffusion tau')
axs[1,3].text(0,1,'Clinical interval: weeks\nSeparate network input.\nNot a bridge step.\n\nInference: right -> left\nTarget used in training only.',va='top',fontsize=11)
fig.suptitle(f'I2SB training bridge | train patient {pid} | illustrative fixed seed (not inference)');fig.tight_layout()
fig.savefig(ROOT/'reports/bridge_explanation.png',dpi=140);plt.close(fig)
