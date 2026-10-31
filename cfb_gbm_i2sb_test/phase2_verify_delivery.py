"""Final follow-up checks: no old artifact overwrite, no test exposure, all budgets complete."""
from pathlib import Path
import json,py_compile
import torch
from cfb.common import ROOT,read,dump,sha

out=ROOT/'reports/phase2_2026-10-31';plan=read(out/'plan.json');comparison=read(out/'comparison.json');split=read(ROOT/'data/splits.json')
assert (out/'evaluation_completed.json').exists() and read(out/'tests.json')['passed']
assert read(out/'guard_verification.json')['test_image_bytes_read']==0
checks={}
for r in plan['runs']:
    cfg=read(ROOT/f'weights/{r["name"]}/config.json');history=[json.loads(s) for s in (ROOT/f'logs/{r["name"]}/train.jsonl').read_text().splitlines()]
    summary=read(ROOT/f'logs/{r["name"]}/summary.json')
    assert summary['last_step']==5000 and len(summary['validation_ids'])==24
    assert {x['patient'] for x in history}<=set(split['train'])
    assert all(x['loss']>=0 for x in history)
    best=torch.load(ROOT/f'weights/{r["name"]}/best.pt',map_location='cpu',weights_only=False)
    last=torch.load(ROOT/f'weights/{r["name"]}/last.pt',map_location='cpu',weights_only=False)
    assert last['step']==5000 and best['step']<=5000
    assert all(torch.isfinite(t).all() for t in best['model'].values())
    assert cfg['splits_sha256']==sha(ROOT/'data/splits.json')==plan['splits_sha256']
    assert cfg['manifest_sha256']==sha(ROOT/'data/manifest.json')==plan['manifest_sha256']
    checks[r['name']]=dict(last_step=5000,best_step=best['step'],new_steps=len(history),training_patients_seen=len({x['patient'] for x in history}),
        best_sha256=sha(ROOT/f'weights/{r["name"]}/best.pt'),last_sha256=sha(ROOT/f'weights/{r["name"]}/last.pt'),seconds=summary['elapsed_seconds'])
    if r['resume']:assert sha(r['resume'])==plan['parent_sha256'][r['name']]
old_hashes=read(ROOT/'reports/artifact_checksums.json')
for kind in ['i2sb','regression']:
    rel=Path('weights')/(kind+'_short')/'best.pt';assert sha(ROOT/rel)==old_hashes[str(rel)]
for name in comparison['results']:
    cases=read(ROOT/f'results/phase2_2026-10-31/{name}/per_patient.json')
    assert {x['patient_id'] for x in cases}==set(split['val'])
for kind,name in comparison['chosen'].items():
    folder=ROOT/f'results/phase2_2026-10-31/{name}/{split["val"][0]}/native'
    record=read(folder/'spatial_verification.json');assert record['shape_matches'] and record['affine_matches'] and record['finite_inside_coverage'] and record['nan_outside_coverage']
    for file in ['prediction_normalized.nii.gz','prediction_baseline_intensity.nii.gz','coverage.nii.gz','inference.json']:assert (folder/file).stat().st_size>0
for p in list(ROOT.glob('phase2*.py'))+[ROOT/'test_phase2.py',ROOT/'cfb/training.py']:py_compile.compile(str(p),doraise=True)
assert (out/'第二轮训练报告.md').stat().st_size>0
dump(out/'delivery_verification.json',dict(runs=checks,all_completed=True,old_main_weights_unchanged=True,manifest_and_splits_unchanged=True,
    test_image_exposure=False,validation_patients=24,validation_not_independent_test=True,new_optim_updates=sum(c['new_steps'] for c in checks.values()),
    original_space_nifti_verified_for_selected_models=True))
print('PHASE2 VERIFIED',checks,flush=True)
