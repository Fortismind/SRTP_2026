import numpy as np
import nibabel as nib
from cfb.common import ROOT,read,dump

records=[]
for r in read(ROOT/'data/manifest.json'):
    if not (r['source'] and r['target']):continue
    record={'patient_id':r['patient_id'],'images':{}}
    for key in ['source','target','baseline_gtv']:
        if not r[key]:continue
        from pathlib import Path
        path=Path(r[key]);im=nib.load(str(path));q,qc=im.get_qform(coded=True);s,sc=im.get_sform(coded=True)
        record['images'][key]=dict(bytes=path.stat().st_size,mtime_ns=path.stat().st_mtime_ns,
            qform=q.tolist() if q is not None else None,sform=s.tolist() if s is not None else None,
            qform_sform_max_abs_diff=float(np.abs(q-s).max()) if q is not None and s is not None else None,
            qform_sform_consistent=bool(np.allclose(q,s,atol=1e-3)) if q is not None and s is not None else None)
    records.append(record)
dump(ROOT/'reports/header_forms_and_source_signatures.json',records)
print('pairs',len(records),'qform/sform inconsistent',[(r['patient_id'],k) for r in records for k,v in r['images'].items() if v['qform_sform_consistent'] is False],flush=True)
