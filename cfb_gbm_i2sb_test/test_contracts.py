import unittest,tempfile
from pathlib import Path
import numpy as np
import nibabel as nib
from cfb.preprocess import prepare_baseline,restore_stack,to_stack
from cfb.metrics import patient_metrics
from cfb.common import ROOT,read,dump

class Contracts(unittest.TestCase):
    def test_native_space_restore_and_explicit_coverage(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            folder=Path(tmp);shape=(32,36,28);coords=np.indices(shape)
            support=((coords[0]-16)**2/11**2+(coords[1]-18)**2/13**2+(coords[2]-14)**2/10**2)<1
            data=np.where(support,100+coords[0]+coords[1]*2+coords[2]*3,0).astype('float32')
            affine=np.diag([-2.,-3.,4.,1.]);affine[:3,3]=[42.,53.,-24.]
            image=nib.Nifti1Image(data,affine);image.set_qform(affine,1);image.set_sform(affine,1)
            source=folder/'baseline.nii.gz';nib.save(image,source)
            stack,mask,plan,_,native_mask=prepare_baseline(source,32)
            self.assertTrue(mask.any());self.assertEqual(mask.dtype,np.bool_)
            restore_stack(stack,plan,source,folder/'out',native_mask)
            pred=nib.load(folder/'out/prediction_normalized.nii.gz');coverage=nib.load(folder/'out/coverage.nii.gz').get_fdata()>0
            a=pred.get_fdata();self.assertEqual(pred.shape,shape);np.testing.assert_allclose(pred.affine,affine)
            self.assertTrue(np.isfinite(a[coverage]).all());self.assertTrue(np.isnan(a[~coverage]).all())
            expected=np.clip((data-plan['intensity_low'])/(plan['intensity_high']-plan['intensity_low']),0,1)
            # Native axis sign and origin must be restored, not only volume shape.
            self.assertLess(float(np.mean(np.abs(a[coverage]-expected[coverage]))),.08)
            self.assertEqual(set(np.unique(to_stack(native_mask,plan,True)).tolist()),{False,True})

    def test_patient_metric_aggregation_and_background(self):
        n=2;shape=(n,32,32);mask=np.zeros(shape,dtype=bool);mask[:,6:26,6:26]=True
        b=np.zeros(shape,dtype=np.float32);b[mask]=.5;target=b.copy();pred=b.copy();pred[0][mask[0]]+=.1;pred[1][mask[1]]+=.3
        pred[:,0:3]=1 # Outside support must not enter MAE.
        scores=patient_metrics(pred,target,mask,b)['brain_support']
        self.assertAlmostEqual(scores['mae'],.2,places=5)
        self.assertAlmostEqual(scores['psnr'],(-10*np.log10(.01)-10*np.log10(.09))/2,places=4)
        identical=patient_metrics(b,b,mask,b)['brain_support'];self.assertEqual(identical['mae'],0.)
        self.assertAlmostEqual(identical['ssim'],1.,places=5)

    def test_patient_split_has_no_overlap_and_covers_accepted(self):
        split=read(ROOT/'data/splits.json');sets=[set(split[k]) for k in ['train','val','test']]
        self.assertFalse(sets[0]&sets[1]);self.assertFalse(sets[0]&sets[2]);self.assertFalse(sets[1]&sets[2])
        accepted={r['patient_id'] for r in read(ROOT/'data/manifest.json') if r['status']=='accepted'}
        self.assertEqual(set.union(*sets),accepted)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    dump(ROOT/'reports/contracts.json',dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful()))
    raise SystemExit(0 if result.wasSuccessful() else 1)
