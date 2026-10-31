"""Final artifact coverage and original-source modification-time checks (no retraining)."""
from pathlib import Path
import numpy as np
import torch
from cfb.common import ROOT,read,dump,sha

splits=read(ROOT/'data/splits.json');expected=set(splits['test']);report={}
for run in ['i2sb_short','regression_short']:
    out=ROOT/'results'/run;records=read(out/'per_patient.json')
    assert {r['patient_id'] for r in records}==expected
    summary=read(out/'summary.json');assert summary['patients']==len(expected)
    for pid in expected:
        folder=out/pid
        for f in ['comparison.png','prediction_normalized.nii.gz','prediction_baseline_intensity.nii.gz','coverage.nii.gz','inference.json','metrics.json','prediction_stack.npy','nifti_verification.json']:
            assert (folder/f).stat().st_size>0,(pid,f)
        spatial=read(folder/'nifti_verification.json');assert spatial['affine_matches_baseline'] and spatial['nan_outside_coverage'] and spatial['finite_inside_coverage']
        info=read(folder/'inference.json');assert info['future_inputs']==[]
        assert info['checkpoint_sha256']==sha(ROOT/f'weights/{run}/best.pt')
    last=torch.load(ROOT/f'weights/{run}/last.pt',map_location='cpu',weights_only=False)
    assert last['step']==600 and last['config']['splits_sha256']==sha(ROOT/'data/splits.json') and last['config']['manifest_sha256']==sha(ROOT/'data/manifest.json')
    report[run]=dict(test_patients=len(expected),nifti_outputs=3*len(expected),all_required_patient_artifacts_present=True,
                     all_spatial_checks_passed=True,clinical_future_inputs_during_generation=[],last_training_step=last['step'],selected_step=summary['checkpoint_step'])
for f in ['README.md','THIRD_PARTY.md','requirements.lock.txt','reports/实验报告.md','reports/contracts.json','reports/overfit.json','reports/integration_verification.json','reports/numerical_verification.json','reports/cli_verification.json']:
    assert (ROOT/f).is_file(),f
# Compare size and mtime to signatures collected after data audit, before experiments.
signatures=read(ROOT/'reports/header_forms_and_source_signatures.json');manifest={r['patient_id']:r for r in read(ROOT/'data/manifest.json')};changes=[];checked=0
for r in signatures:
    for key,sig in r['images'].items():
        p=Path(manifest[r['patient_id']][key]);stat=p.stat();checked+=1
        if stat.st_size!=sig['bytes'] or stat.st_mtime_ns!=sig['mtime_ns']:changes.append(str(p))
assert not changes,changes
report['original_sources']=dict(files_checked=checked,size_and_mtime_unchanged=True,scope='all actual pairs and available baseline GTV in header audit; not a cryptographic full-data hash')
report['project_size_bytes']=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file() and '.venv' not in p.parts)
dump(ROOT/'reports/delivery_verification.json',report);print(report,flush=True)
