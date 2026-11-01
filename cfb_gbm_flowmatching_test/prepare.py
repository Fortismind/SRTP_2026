"""Read-only source audit. All new caches live here; never reuse target caches in inference."""
from fm.common import *
from fm.preprocess import *
import shutil,collections,platform,sys,importlib.metadata,time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def baseline_mask(path,img,plan,support):
    gm=np.zeros(support.shape,bool); status='missing';available=False; roi=gm.copy()
    if path and Path(path).is_file():
        gi=load_canonical(path)
        if gi.shape==img.shape and np.allclose(gi.affine,img.affine,atol=1e-3):
            raw=gi.get_fdata(dtype=np.float32)
            if np.isfinite(raw).all():
                gm=raw>0;available=True;status='valid_nonempty' if gm.any() else 'valid_empty'
                # Dilate in native physical mm before downsampling; handles anisotropic spacing.
                if gm.any():
                    spacing=np.array(img.header.get_zooms()[:3]);margin=np.ceil(5/spacing).astype(int)+1
                    coords=np.array(np.where(gm));lo=np.maximum(0,coords.min(1)-margin);hi=np.minimum(gm.shape,coords.max(1)+margin+1)
                    box=tuple(slice(l,h) for l,h in zip(lo,hi));roi=np.zeros_like(gm)
                    roi[box]=ndi.distance_transform_edt(~gm[box],sampling=spacing)<=5.
                else:roi=gm.copy()
        else:status='different_world_grid_not_used'
    return to_stack(gm,plan,True),to_stack(roi,plan,True),available,status

def main():
    seed(20261101);start=time.time()
    for d in ['data','reports','cache','weights','logs','results','configs']: (ROOT/d).mkdir(exist_ok=True)
    rows=read(OLD/'data/manifest.json');splits=read(OLD/'data/splits.json')
    write(ROOT/'reports/original_artifact_hashes.json',{str(p):sha(p) for p in [OLD/'README.md',OLD/'THIRD_PARTY.md',OLD/'reports/实验报告.md',OLD/'reports/data_audit.json',OLD/'data/manifest.csv',OLD/'data/splits.json',OLD/'cfb/preprocess.py',OLD/'cfb/metrics.py']})
    for name in ['manifest.csv','manifest.json','splits.json']:shutil.copyfile(OLD/'data'/name,ROOT/'data'/name)
    ids=sum([splits[k] for k in ['train','val','test']],[]); assert len(ids)==len(set(ids))
    byid={r['patient_id']:r for r in rows}; audits=[];exclusions=[]
    signatures={a['patient_id']:a['images'] for a in read(OLD/'reports/header_forms_and_source_signatures.json')}
    for i,pid in enumerate(ids):
        r=byid[pid]
        try:
            # Reuse paired intensities ONLY after current file signatures, physical grids,
            # preprocessing source and recorded baseline plan are verified.
            plan=read(OLD/'cache'/f'{pid}.json');sig=signatures[pid]
            verified=plan['version']==VERSION and plan['size']==128
            for key,geomkey in [('source','native_geometry'),('target','target_geometry')]:
                file=Path(r[key]);st=file.stat();current=geometry(nib.load(str(file)))
                verified=verified and st.st_size==sig[key]['bytes'] and st.st_mtime_ns==sig[key]['mtime_ns'] and current==plan[geomkey]
            old_pre=(OLD/'cfb/preprocess.py').read_text(encoding='utf-8').split('def restore_stack')[0]
            new_pre=(ROOT/'fm/preprocess.py').read_text(encoding='utf-8').split('def restore_stack')[0]
            verified=verified and old_pre==new_pre
            if verified:
                with np.load(OLD/'cache'/f'{pid}.npz') as cached:
                    b=cached['baseline'].astype('float32');y=cached['target'].astype('float32');brain=cached['mask'].astype(bool)
                if (ROOT/'cache'/f'{pid}.npz').exists():
                    with np.load(ROOT/'cache'/f'{pid}.npz') as fresh:
                        assert np.array_equal(b,fresh['b']) and np.array_equal(y,fresh['y']) and np.array_equal(brain,fresh['brain'])
                plan['cache_reuse']='verified old paired intensity cache; new GTV/ROI cache rebuilt'
                plan['source_cache_sha256']=sha(OLD/'cache'/f'{pid}.npz')
            else:
                b,y,brain,_,plan=prepare_pair(r['source'],r['target'],None)
                plan['cache_reuse']='full raw recomputation because signature or protocol changed'
            img=load_canonical(r['source']);support=np.zeros(img.shape,bool)
            gtv,roi,available,status=baseline_mask(r.get('baseline_gtv'),img,plan,support)
            p=ROOT/'cache'/f'{pid}.npz'
            np.savez_compressed(p,b=b.astype('float16'),y=y.astype('float16'),brain=brain,gtv=gtv,roi=roi,available=np.array(available),weeks=np.array(r['weeks'],dtype='float32'))
            plan.update(mask_status=status,roi_dilation_mm=5.,source=r['source'],target=r['target'])
            write(ROOT/'cache'/f'{pid}.json',plan)
            saturation=float(np.mean((y[brain]>=1)|(y[brain]<=0)))
            audits.append(dict(patient=pid,mask_status=status,available=available,gtv_voxels=int(gtv.sum()),gtv_support_fraction=float((gtv&brain).sum()/max(gtv.sum(),1)),spatial_action=plan['spatial_action'],alignment_r=plan['alignment_r'],support_dice=plan['support_dice'],target_saturation=saturation,source_signature=[Path(r['source']).stat().st_size,Path(r['source']).stat().st_mtime_ns]))
            if available and gtv.any():
                z=int(gtv.sum((1,2)).argmax());fig,ax=plt.subplots(figsize=(3,3));ax.imshow(b[z],cmap='gray',vmin=0,vmax=1);ax.contour(gtv[z],levels=[.5],colors='r',linewidths=.6);ax.contour(roi[z],levels=[.5],colors='y',linewidths=.4);ax.set_title(pid+' baseline planning GTV');ax.axis('off');fig.savefig(ROOT/'reports'/f'gtv_{pid}.png');plt.close(fig)
        except PermissionError:raise
        except Exception as e:
            exclusions.append(dict(patient=pid,error=repr(e)))
            write(ROOT/'reports/preparation_exclusions.json',exclusions)
        print('prepare',i+1,len(ids),pid,flush=True)
    effective={k:[p for p in splits[k] if p not in {e['patient'] for e in exclusions}] for k in ['train','val','test']}
    assert all(effective.values()), 'No usable patients: abort instead of writing empty splits'
    write(ROOT/'data/effective_splits.json',effective)
    weeks=np.log1p([float(byid[p]['weeks']) for p in effective['train']])
    write(ROOT/'data/week_stats.json',dict(mean=float(weeks.mean()),std=float(weeks.std())))
    # Audit baseline treatment fields but do not introduce them into any condition.
    clinical={k:sum(not str(byid[p].get('optional_treatment',{}).get(k,'')).strip() for p in ids) for k in ['dose (Gy)','fractions_number','delay_t0_to_radiotherapy (weeks)']}
    data_root=Path(rows[0]['source']).parents[4]
    write(ROOT/'reports/data_audit.json',dict(audited_original_manifest_rows=len(rows),rechecked_fixed_split_patients=len(ids),effective_sizes={k:len(v) for k,v in effective.items()},exclusions=exclusions,mask_status_counts=dict(collections.Counter(a['mask_status'] for a in audits)),patients=audits,clinical_missing_counts=clinical,clinical_decision='weeks only; dose/fractions timing not verified, omitted in all arms; no survival inputs',followup_segmentation='not established; baseline planning GTV only',seconds=time.time()-start))
    write(ROOT/'reports/environment.json',dict(python=sys.version,platform=platform.platform(),torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),memory_GiB=torch.cuda.get_device_properties(0).total_memory/2**30,packages={k:importlib.metadata.version(k) for k in ['numpy','scipy','nibabel','scikit-image','matplotlib']}))
if __name__=='__main__':main()
