import unittest
import torch
from cfb.common import ROOT,read,dump
from cfb.training import train
from test_contracts import Contracts

class ResumeProtocol(unittest.TestCase):
    def test_fork_recomputes_best_when_validation_changes(self):
        cfg=read(ROOT/'configs/short.json');cfg.update(steps=2,validate_every=2,val_patients=1,val_slices=2,batch_size=2,max_minutes=2)
        folder=ROOT/'configs/phase2_verification';folder.mkdir(exist_ok=True)
        dump(folder/'initial.json',cfg);train(folder/'initial.json','i2sb','phase2_verify_initial')
        ck=torch.load(ROOT/'weights/phase2_verify_initial/last.pt',map_location='cpu',weights_only=False)
        ck['best']=-1.;sentinel=folder/'sentinel.pt';torch.save(ck,sentinel)
        cfg.update(steps=3,val_patients=2,val_slices=3,validation_min_region_pixels=10)
        dump(folder/'fork.json',cfg);train(folder/'fork.json','i2sb','phase2_verify_fork',sentinel)
        record=read(ROOT/'logs/phase2_verify_fork/resume_rebaseline.json')
        best=torch.load(ROOT/'weights/phase2_verify_fork/best.pt',map_location='cpu',weights_only=False)
        self.assertEqual(len(record['new_selection']['ids']),2)
        self.assertGreater(best['best'],0);self.assertEqual(best['config']['val_slices'],3)
        self.assertEqual(best['config']['validation_min_region_pixels'],10)

if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Contracts),unittest.defaultTestLoader.loadTestsFromTestCase(ResumeProtocol)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    dump(ROOT/'reports/phase2_2026-10-31/tests.json',dict(tests=result.testsRun,passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
