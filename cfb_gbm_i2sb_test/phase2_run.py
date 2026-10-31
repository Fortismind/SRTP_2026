"""Frozen bounded follow-up experiment, train/val only. No test image access."""
import sys,time,shutil
import numpy as np
from cfb.common import ROOT,read,dump,sha,environment
from cfb.training import train

OUT=ROOT/'reports/phase2_2026-10-31'
def install_test_guard():
    blocked={str(int(p)) for p in read(ROOT/'data/splits.json')['test']}
    def guard(event,args):
        if event!='open' or not isinstance(args[0],(str,bytes)):return
        from pathlib import Path
        name=Path(str(args[0])).name
        if name.endswith('.npz') and name[:-4].isdigit() and str(int(name[:-4])) in blocked:
            raise RuntimeError('Phase2 forbids test cache access: '+name)
        if name.endswith('.nii.gz') and name.split('_')[0].isdigit() and str(int(name.split('_')[0])) in blocked:
            raise RuntimeError('Phase2 forbids test raw image access: '+name)
    sys.addaudithook(guard)

def main():
    install_test_guard();OUT.mkdir(exist_ok=True,parents=True)
    if (OUT/'plan.json').exists():raise FileExistsError('Frozen phase2 plan already exists; do not silently rerun')
    probe=read(ROOT/'data/splits.json')['test'][0];blocked=False
    try:
        with open(ROOT/f'cache/{probe}.npz','rb'):pass
    except RuntimeError:blocked=True
    assert blocked,'Test image guard must reject access before reading'
    dump(OUT/'guard_verification.json',dict(guard_proven_active=True,deliberate_test_open_blocked_before_read=True,test_image_bytes_read=0))
    tests=read(OUT/'tests.json');assert tests['passed']
    qc=read(OUT/'cache_qc.json')
    runs=[]
    for seed in [20261025,20261031]:
        for kind in ['i2sb','regression']:
            cfg=read(ROOT/'configs/short.json');cfg.update(seed=seed,steps=5000,validate_every=500,val_patients=24,val_slices=16,validation_min_region_pixels=10,max_minutes=8)
            name=f'{kind}_phase2_s{seed}';path=ROOT/f'configs/{name}.json';dump(path,cfg)
            parent=ROOT/f'weights/{kind}_short/last.pt' if seed==20261025 else None
            runs.append(dict(name=name,kind=kind,seed=seed,config=str(path),resume=str(parent) if parent else None))
    plan=dict(date='2026-10-31',runs=runs,validation='all 24 val patients; 16 evenly spaced baseline slices; >=10 region pixels; equal patient MAE',
        selection='fixed single sampling seed 7391 and NFE16; lowest validation MAE; ties retain earlier checkpoint; never select by test or sample target match',
        post_selection='all baseline-covered val slices; report MAE PSNR SSIM and predefined time-condition and sampling-seed diagnostics',
        test='previously inspected test no longer pristine; image access blocked; no new test evaluation this round',
        preprocessing='unchanged baseline-only v1; diagnostic clipping fractions do not trigger a hidden target-based intensity remapping',
        max_training_minutes=32,additional_steps_limit=18800,manifest_sha256=sha(ROOT/'data/manifest.json'),splits_sha256=sha(ROOT/'data/splits.json'),
        parent_sha256={r['name']:sha(r['resume']) for r in runs if r['resume']},environment=environment())
    dump(OUT/'plan.json',plan)
    for p in list((ROOT/'cfb').glob('*.py'))+[ROOT/'phase2_run.py',ROOT/'train.py']:
        dest=OUT/'source_snapshot'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    start=time.time()
    for r in runs:
        print('START',r['name'],flush=True)
        train(r['config'],r['kind'],r['name'],r['resume'])
        completed=[x for x in runs if (ROOT/f'logs/{x["name"]}/summary.json').exists()]
        dump(OUT/'progress.json',dict(completed=[x['name'] for x in completed],elapsed_seconds=time.time()-start))
    dump(OUT/'training_completed.json',dict(runs=[r['name'] for r in runs],seconds=time.time()-start))

if __name__=='__main__':main()
