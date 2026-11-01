"""All inference transformations are determined by baseline alone."""
from pathlib import Path
import itertools
import numpy as np
import nibabel as nib
from nibabel.processing import resample_from_to
from scipy import ndimage as ndi
import torch
import torch.nn.functional as F

VERSION='baseline_bbox_pad128_v1'

def geometry(img):
    corners=nib.affines.apply_affine(img.affine,np.array(list(itertools.product(*[(0,n-1) for n in img.shape[:3]]))))
    return dict(shape=list(img.shape),spacing=list(map(float,img.header.get_zooms()[:3])),
                orientation=list(nib.aff2axcodes(img.affine)),affine=img.affine.tolist(),
                world_min=corners.min(0).tolist(),world_max=corners.max(0).tolist(),
                qform_code=int(img.header['qform_code']),sform_code=int(img.header['sform_code']),
                determinant=float(np.linalg.det(img.affine[:3,:3])))

def valid_image(img):
    if len(img.shape)!=3: raise ValueError('not_3D')
    if not np.isfinite(img.affine).all() or abs(np.linalg.det(img.affine[:3,:3]))<1e-8: raise ValueError('invalid_affine')
    if min(img.header.get_zooms()[:3])<=0: raise ValueError('invalid_spacing')
    if max(int(img.header['sform_code']),int(img.header['qform_code']))==0: raise ValueError('missing_world_coordinate_form')

def load_canonical(path):
    img=nib.load(str(path)); valid_image(img)
    return nib.as_closest_canonical(img)

def baseline_plan(path,size=128):
    img=load_canonical(path); a=img.get_fdata(dtype=np.float32)
    if not np.isfinite(a).all(): raise ValueError('nonfinite_baseline')
    positive=a[a>0]
    if positive.size<1000: raise ValueError('empty_baseline')
    lo,hi=np.percentile(positive,[.5,99.5])
    if hi-lo<1e-6: raise ValueError('constant_baseline')
    # Baseline foreground support. This is NOT a tumor mask or validated brain extraction.
    mask=a>max(float(lo),float(hi)*.02)
    labels,n=ndi.label(mask); counts=np.bincount(labels.ravel()); counts[0]=0
    mask=labels==counts.argmax()
    for z in range(mask.shape[2]): mask[:,:,z]=ndi.binary_fill_holes(mask[:,:,z])
    inds=np.array(np.where(mask)); lower=inds.min(1); upper=inds.max(1)+1
    lower[:2]=np.maximum(lower[:2]-4,0);upper[:2]=np.minimum(upper[:2]+4,a.shape[:2])
    box=[[int(l),int(u)] for l,u in zip(lower,upper)]
    xy=upper[:2]-lower[:2]; side=int(max(xy)); pad=[int((side-v)//2) for v in xy]
    plan=dict(version=VERSION,size=size,canonical_shape=list(a.shape),canonical_affine=img.affine.tolist(),
              native_geometry=geometry(nib.load(str(path))),box=box,side=side,pad=pad,
              intensity_low=float(lo),intensity_high=float(hi),
              mask_rule='baseline positive .5 percentile / .02*p99.5 threshold, largest 3D component, 2D hole fill',
              coverage='all baseline foreground axial slices; outside bbox/foreground is not model prediction')
    return img,a,mask,plan

def to_stack(a,plan,mask=False):
    box=tuple(slice(l,u) for l,u in plan['box']); crop=a[box].transpose(2,0,1)
    n,h,w=crop.shape; square=np.zeros((n,plan['side'],plan['side']),dtype=np.float32)
    p,q=plan['pad'];square[:,p:p+h,q:q+w]=crop
    t=torch.from_numpy(square[:,None])
    if mask: return (F.interpolate(t,size=(plan['size'],)*2,mode='nearest')[:,0].numpy()>.5)
    return F.interpolate(t,size=(plan['size'],)*2,mode='bilinear',align_corners=False)[:,0].numpy()

def normalize(a,plan):
    return np.clip((a-plan['intensity_low'])/(plan['intensity_high']-plan['intensity_low']),0,1)

def prepare_baseline(path,size=128):
    img,a,m,p=baseline_plan(path,size)
    return to_stack(normalize(a,p),p),to_stack(m,p,True),p,img,m

def prepare_pair(source,target,gtv=None,size=128):
    x1,mask,p,img,m=prepare_baseline(source,size)
    future=load_canonical(target)
    same=future.shape==img.shape and np.allclose(future.affine,img.affine,atol=1e-3)
    action='same world grid; no additional registration' if same else 'affine world resampling to baseline; not registration'
    if not same:
        # Require substantial physical overlap before resampling; registration not silently inferred.
        g0,g1=geometry(img),geometry(future)
        overlap=np.maximum(0,np.minimum(g0['world_max'],g1['world_max'])-np.maximum(g0['world_min'],g1['world_min']))
        ratio=np.prod(overlap)/max(np.prod(np.array(g0['world_max'])-g0['world_min']),1)
        if ratio<.9: raise ValueError('insufficient_world_overlap_need_registration')
        future=resample_from_to(future,(img.shape,img.affine),order=1)
    a=future.get_fdata(dtype=np.float32)
    if not np.isfinite(a).all(): raise ValueError('nonfinite_target')
    if np.count_nonzero(a>0)<1000 or np.ptp(a)<1e-6: raise ValueError('empty_or_constant_target')
    x0=to_stack(normalize(a,p),p)
    # Pair QC only, never used to choose crop, normalization, slices or inference postprocessing.
    r=float(np.corrcoef(x1[mask],x0[mask])[0,1])
    support=a>max(float(np.percentile(a[a>0],.5)),float(np.percentile(a[a>0],99.5))*.02)
    overlap_dice=float(2*np.count_nonzero(m & support)/max(np.count_nonzero(m)+np.count_nonzero(support),1))
    if not np.isfinite(r) or r<.35 or overlap_dice<.65: raise ValueError(f'poor_pair_alignment_proxy_r={r:.3f}_support_dice={overlap_dice:.3f}_manual_registration_needed')
    gm=np.zeros_like(mask);gtv_status='missing'
    if gtv:
        try:
            gi=load_canonical(gtv)
            if gi.shape!=img.shape or not np.allclose(gi.affine,img.affine,atol=1e-3):
                gtv_status='different_grid_not_used_without_verified_registration'
            else:
                raw=gi.get_fdata(dtype=np.float32)
                if not np.isfinite(raw).all(): raise ValueError('nonfinite_gtv')
                gm=to_stack(raw>0,p,True);gtv_status='same_world_grid_baseline_planning_GTV_not_followup_tumor'
        except Exception as e: gtv_status='unusable: '+str(e)
    p.update(target_geometry=geometry(nib.load(str(target))),spatial_action=action,alignment_r=r,support_dice=overlap_dice,gtv_status=gtv_status)
    return x1,x0,mask,gm,p

def restore_stack(stack,plan,baseline_path,outdir,canonical_support=None):
    """Restore baseline native grid. Outside baseline support = NaN, coverage = 0."""
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    baseline=nib.load(str(baseline_path));can=nib.as_closest_canonical(baseline)
    a=F.interpolate(torch.from_numpy(stack[:,None].astype(np.float32)),size=(plan['side'],)*2,mode='bilinear',align_corners=False)[:,0].numpy()
    box=plan['box'];h=box[0][1]-box[0][0];w=box[1][1]-box[1][0];p,q=plan['pad']
    vol=np.zeros(can.shape,dtype=np.float32);coverage=np.zeros(can.shape,dtype=np.uint8)
    sl=tuple(slice(l,u) for l,u in box);vol[sl]=a[:,p:p+h,q:q+w].transpose(1,2,0)
    if canonical_support is None:_,_,canonical_support,_=baseline_plan(baseline_path,plan['size'])
    coverage[sl]=1;coverage=coverage*(canonical_support.astype(np.uint8))
    # Orientation-only inverse to original voxel axes; no extra interpolation.
    transform=nib.orientations.ornt_transform(nib.orientations.io_orientation(can.affine),nib.orientations.io_orientation(baseline.affine))
    vol=nib.orientations.apply_orientation(vol,transform).copy()
    coverage=nib.orientations.apply_orientation(coverage,transform).copy()
    vol[coverage==0]=np.nan
    for name,data in [('prediction_normalized',vol),('prediction_baseline_intensity',vol*(plan['intensity_high']-plan['intensity_low'])+plan['intensity_low']),('coverage',coverage)]:
        hdr=baseline.header.copy();hdr.set_data_dtype(data.dtype)
        output=nib.Nifti1Image(data,baseline.affine,hdr)
        output.set_qform(*baseline.get_qform(coded=True))
        output.set_sform(*baseline.get_sform(coded=True))
        nib.save(output,str(outdir/(name+'.nii.gz')))
