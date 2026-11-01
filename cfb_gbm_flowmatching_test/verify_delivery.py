"""Actual baseline-only CLI execution against the selected formal checkpoint."""
from fm.common import *
import subprocess,sys

def main():
    pid=read(ROOT/'data/effective_splits.json')['test'][0]
    r=next(x for x in read(ROOT/'data/manifest.json') if x['patient_id']==pid)
    out=ROOT/'results/cli_verification'/pid
    cmd=[sys.executable,'infer.py','--baseline',r['source'],'--weeks',str(r['weeks']),'--checkpoint',str(ROOT/'weights/direct_roi/best.pt'),'--out',str(out),'--seed',str(7391+int(pid)*10000)]
    if r.get('baseline_gtv'):cmd+=['--mask',r['baseline_gtv']]
    subprocess.run(cmd,cwd=ROOT,check=True)
    same=np.array_equal(np.load(out/'model_grid.npy'),np.load(ROOT/'results/direct_roi'/pid/'model_grid.npy'))
    assert same
    summaries={k:read(ROOT/'logs'/f'{k}.json') for k in KINDS}
    assert len({s['sample_sequence_sha256'] for s in summaries.values()})==1
    split=read(ROOT/'data/effective_splits.json')
    for v in summaries.values():assert set(v['exposure'])<=set(split['train'])
    write(ROOT/'reports/cli_verification.json',dict(patient=pid,actual_subprocess_cli=True,baseline_only_arguments=True,full_ode_matches_evaluation_bitwise=same,matched_training_patient_slice_sequences=True,no_val_or_test_training_exposure=True,command=cmd))
if __name__=='__main__':main()
