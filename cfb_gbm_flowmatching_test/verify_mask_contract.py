"""Targeted missing/empty/physical-distance and paired transform contract."""
from fm.common import *
from fm.preprocess import to_stack
from prepare import baseline_mask
import nibabel as nib

def main():
    folder=ROOT/'reports/mask_contract';folder.mkdir(exist_ok=True)
    img=nib.Nifti1Image(np.zeros((16,16,8),np.float32),np.diag([2.,2.,3.,1.]));img.set_qform(img.affine,1);img.set_sform(img.affine,1)
    plan=dict(box=[[0,16],[0,16],[0,8]],side=16,pad=[0,0],size=128)
    missing=baseline_mask(None,img,plan,np.zeros(img.shape,bool));nib.save(img,folder/'empty.nii.gz')
    empty=baseline_mask(folder/'empty.nii.gz',img,plan,np.zeros(img.shape,bool))
    assert not missing[2] and empty[2] and not empty[0].any() and not empty[1].any()
    mask=np.zeros(img.shape,np.float32);mask[8,8,4]=1;nii=nib.Nifti1Image(mask,img.affine,img.header);nib.save(nii,folder/'point.nii.gz')
    gm,roi,av,status=baseline_mask(folder/'point.nii.gz',img,plan,np.zeros(img.shape,bool))
    xyz=np.indices(img.shape);dist=((xyz[0]-8)*2)**2+((xyz[1]-8)*2)**2+((xyz[2]-4)*3)**2
    expected=to_stack(dist<=25,plan,True)
    assert np.array_equal(roi,expected)
    b=np.arange(16*16*8,dtype=np.float32).reshape(img.shape);y=b+3
    bs=to_stack(b,plan);ys=to_stack(y,plan)
    assert np.allclose(ys[:,::-1,::-1]-bs[:,::-1,::-1],3,atol=1e-4)
    write(ROOT/'reports/mask_contract.json',dict(missing_available_false=True,provided_empty_available_true=True,empty_roi_zero=True,anisotropic_5mm_dilation_matches_world_distance=True,paired_transform_same_coordinates=True))
    print('MASK CONTRACT OK')
if __name__=='__main__':main()
