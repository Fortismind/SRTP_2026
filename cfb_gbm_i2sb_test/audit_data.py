import csv, argparse, re, time
from pathlib import Path
from collections import Counter
import numpy as np
import nibabel as nib
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cfb.common import ROOT,dump,seed_all
from cfb.preprocess import geometry,valid_image,prepare_pair

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f,delimiter='\t'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',default=r'E:\srtp项目\ADNI-T1-PET(AV45 FDG)等4个文件\CFB-GBM');ap.add_argument('--size',type=int,default=128);args=ap.parse_args()
    seed_all(20261025);data=Path(args.data);cache=ROOT/'cache';cache.mkdir(exist_ok=True)
    files=list(data.rglob('*.nii.gz')); lookup={};duplicates=[]
    for f in files:
        m=re.fullmatch(r'(\d+)_(t\d+)_(\w+)\.nii\.gz',f.name)
        if m:
            key=(int(m[1]),m[2],m[3])
            if key in lookup: duplicates.append(dict(key=key,paths=[str(lookup[key]),str(f)]))
            lookup[key]=f
    if duplicates: dump(ROOT/'data/duplicates.json',duplicates);raise ValueError('Ambiguous files; resolve duplicates first')
    metadata=rows(next(data.glob('*mri_availability*.tsv')));clean=[];summary_rows=[]
    for row in metadata:
        try: pid=int(row['id_patient'])
        except (ValueError,TypeError): summary_rows.append(row);continue
        clean.append((pid,row))
    meta={};duplicates_meta=[]
    for pid,row in clean:
        key=(pid,row['temporality'])
        if key in meta: duplicates_meta.append(key)
        meta[key]=row
    if duplicates_meta:raise ValueError('Duplicate metadata patient/visit rows')
    treatments={int(r['id_patient']):r for r in rows(next(data.glob('*treatment_data*.tsv'))) if r.get('id_patient','').isdigit()}
    ids=sorted(set(k[0] for k in lookup)|set(p for p,_ in clean));manifest=[];missing=[]
    for (pid,visit),row in meta.items():
        for mod in ['t1gd','flair','adc','t1eg','t1tse','t2star','t2tse']:
            if row.get(mod)=='1' and (pid,visit,mod) not in lookup:missing.append(dict(patient=pid,visit=visit,modality=mod))
    start=time.time();accepted=[];figures=[]
    for pid in ids:
        source=lookup.get((pid,'t0','t1gd'));target=lookup.get((pid,'t1','t1gd'));gtv=lookup.get((pid,'t0','gtv'))
        row=dict(patient_id=f'{pid:03d}',source=str(source) if source else None,target=str(target) if target else None,
                 baseline_gtv=str(gtv) if gtv else None,optional_treatment=treatments.get(pid,{}),status='excluded',reasons=[],qc={})
        if not source:row['reasons'].append('missing_actual_t0_t1gd')
        if not target:row['reasons'].append('missing_actual_t1_t1gd')
        try:
            weeks=float(meta[(pid,'t1')]['time_diff_t0 (weeks)'])-float(meta[(pid,'t0')]['time_diff_t0 (weeks)'])
            if not np.isfinite(weeks) or weeks<=0:raise ValueError()
            row['weeks']=weeks
        except (KeyError,ValueError,TypeError):row['weeks']=None;row['reasons'].append('missing_or_invalid_clinical_interval')
        if not row['reasons']:
            try:
                for key,path in [('baseline',source),('target',target)]:
                    im=nib.load(str(path));valid_image(im);row['qc'][key]=geometry(im)
                x1,x0,mask,gm,plan=prepare_pair(source,target,gtv,args.size)
                np.savez_compressed(cache/f'{pid:03d}.npz',baseline=x1.astype('float16'),target=x0.astype('float16'),mask=mask,gtv=gm)
                dump(cache/f'{pid:03d}.json',plan)
                row['qc'].update({k:plan[k] for k in ['spatial_action','alignment_r','support_dice','gtv_status']})
                row['status']='accepted';accepted.append(f'{pid:03d}')
                z=int(np.flatnonzero(mask.sum((1,2))>0)[len(np.flatnonzero(mask.sum((1,2))>0))//2])
                figures.append((f'{pid:03d}',x1[z].copy(),x0[z].copy(),plan['alignment_r']))
            except Exception as e:
                row['reasons'].append(type(e).__name__+': '+str(e))
        manifest.append(row)
        dump(ROOT/'data/manifest.json',manifest)
        if len(manifest)%10==0:print(f'patients={len(manifest)}/{len(ids)} accepted={len(accepted)} seconds={time.time()-start:.1f}',flush=True)
    shuffled=np.random.default_rng(20261025).permutation(accepted).tolist();n=len(shuffled);nv=max(1,round(.15*n));nt=max(1,round(.15*n))
    splits=dict(seed=20261025,train=sorted(shuffled[nv+nt:]),val=sorted(shuffled[:nv]),test=sorted(shuffled[nv:nv+nt]))
    dump(ROOT/'data/splits.json',splits)
    with (ROOT/'data/manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['patient_id','source','target','weeks','status','reasons','baseline_gtv','optional_treatment','qc']);w.writeheader();w.writerows(manifest)
    summary=dict(actual_nifti_files=len(files),patients=len(ids),actual_t0_t1_pairs=sum(bool(r['source'] and r['target']) for r in manifest),accepted=len(accepted),
                 split_sizes={k:len(splits[k]) for k in ['train','val','test']},excluded_reasons=dict(Counter(reason for r in manifest for reason in r['reasons'])),
                 ignored_no_patient_id_rows=summary_rows,metadata_expected_missing=missing,seconds=time.time()-start,
                 alignment_qc='world geometry + baseline/target Pearson r >= .35 and foreground support dice >= .65; not proof of anatomical registration',
                 gtv_status_counts=dict(Counter(r['qc'].get('gtv_status') for r in manifest if r['status']=='accepted')))
    dump(ROOT/'reports/data_audit.json',summary)
    # All accepted patients, deterministic baseline median slice. No cherry-picking.
    for startidx in range(0,len(figures),24):
        group=figures[startidx:startidx+24];fig,axes=plt.subplots(6,8,figsize=(16,12))
        for ax in axes.flat:ax.axis('off')
        for i,(pid,b,t,r) in enumerate(group):
            ax=axes.flat[i*2];ax.imshow(b.T,origin='lower',cmap='gray',vmin=0,vmax=1);ax.set_title(f'{pid} t0',fontsize=8)
            ax=axes.flat[i*2+1];ax.imshow(t.T,origin='lower',cmap='gray',vmin=0,vmax=1);ax.set_title(f't1 r={r:.2f}',fontsize=8)
        fig.tight_layout();fig.savefig(ROOT/f'reports/qc_contact_{startidx//24:02d}.png',dpi=110);plt.close(fig)
    print(summary,flush=True)

if __name__=='__main__':main()
