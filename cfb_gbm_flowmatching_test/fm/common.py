import json,hashlib,random
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('D:/ai/cfb_gbm_i2sb_test')
KINDS=['direct','direct_mask','direct_roi','noise_roi','regression']
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for a in iter(lambda:f.read(1024*1024),b''):h.update(a)
    return h.hexdigest()
def seed(s):
    random.seed(s);np.random.seed(s);torch.manual_seed(s);torch.cuda.manual_seed_all(s)
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
def slices(brain,n=8):
    idx=np.where(brain.sum((1,2))>=10)[0]
    return idx[np.unique(np.linspace(0,len(idx)-1,min(n,len(idx))).round().astype(int))]
def load_patient(pid):
    with np.load(ROOT/'cache'/f'{pid}.npz') as a:return {k:a[k] for k in a.files}
def tensors(a,idx,device='cuda'):
    arr=[torch.tensor(a[k][idx,None].astype(np.float32),device=device) for k in ['b','y','brain','gtv','roi']]
    n=len(idx)
    return (*arr,torch.full((n,),float(a['available']),device=device),torch.full((n,),float(a['weeks']),device=device))
