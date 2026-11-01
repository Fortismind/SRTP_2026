import numpy as np
from scipy.ndimage import binary_erosion
from skimage.metrics import structural_similarity

def patient_metrics(pred,target,mask,baseline,gtv=None):
    """Slice means first, then equal-weight patient mean. All images in [0,1]."""
    def region(region_mask):
        values=[]
        for p,t,m,b,brain in zip(pred,target,region_mask,baseline,mask):
            if m.sum()<10:continue
            err=p[m]-t[m];mse=float(np.mean(err**2))
            _,ssmap=structural_similarity(p,t,data_range=1.,win_size=7,full=True)
            # Windows must lie completely inside the baseline brain-support mask.
            centers=m & binary_erosion(brain,iterations=3,border_value=0)
            values.append(dict(mae=float(np.mean(np.abs(err))),psnr=float(-10*np.log10(max(mse,1e-12))),
                               ssim=float(ssmap[centers].mean()) if centers.any() else None,
                               predicted_change_mae=float(np.abs(p[m]-b[m]).mean()),
                               actual_change_mae=float(np.abs(t[m]-b[m]).mean())))
        if not values:return None
        return {**{key:float(np.mean([v[key] for v in values if v[key] is not None])) if any(v[key] is not None for v in values) else None for key in values[0]},'slices':len(values)}
    out={'brain_support':region(mask)}
    if gtv is not None and gtv.any():out['baseline_planning_GTV']=region(gtv & mask)
    return out
