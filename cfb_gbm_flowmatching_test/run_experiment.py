"""Bounded sequential experiment runner; writes progress and preserves failures."""
from fm.common import *
import subprocess,sys,time

def main():
    while not (ROOT/'reports/environment.json').exists():time.sleep(5)
    assert all(read(ROOT/'data/effective_splits.json').values())
    jobs=[('checks.py',[]),('verify_mask_contract.py',[]),('train.py',['--kind','all']),('evaluate.py',[]),('verify_delivery.py',[]),('finalize.py',[])]
    for script,args in jobs:
        write(ROOT/'reports/pipeline_status.json',dict(stage=script,status='running'))
        with open(ROOT/f'logs_{script[:-3]}.txt','w',encoding='utf-8') as f:
            result=subprocess.run([sys.executable,'-u',script]+args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        if result.returncode:
            write(ROOT/'reports/pipeline_status.json',dict(stage=script,status='failed',returncode=result.returncode));raise RuntimeError(script+' failed, see log')
    write(ROOT/'reports/pipeline_status.json',dict(status='complete'))
if __name__=='__main__':main()
