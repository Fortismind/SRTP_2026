"""Evaluate immutable completed runs while remaining training runs proceed."""
import torch
from cfb.common import ROOT,read,seed_all
from cfb.training import Cache
from phase2_run import install_test_guard
from phase2_evaluate import full_eval

install_test_guard();seed_all(20261031);device='cuda' if torch.cuda.is_available() else 'cpu'
plan=read(ROOT/'reports/phase2_2026-10-31/plan.json');ids=read(ROOT/'data/splits.json')['val']
manifest={r['patient_id']:r for r in read(ROOT/'data/manifest.json')};cache=Cache()
for kind in ['i2sb','regression']:
    full_eval(kind+'_original',ROOT/f'weights/{kind}_short/best.pt',ids,manifest,cache,device,[])
for r in plan['runs']:
    if (ROOT/f'logs/{r["name"]}/summary.json').exists():
        full_eval(r['name'],ROOT/f'weights/{r["name"]}/best.pt',ids,manifest,cache,device,ids[:3])
