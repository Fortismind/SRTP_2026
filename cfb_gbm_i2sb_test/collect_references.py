from pathlib import Path
import urllib.request, json, hashlib
from pypdf import PdfReader
from cfb.common import ROOT, dump, environment

out=ROOT/'references'; out.mkdir(exist_ok=True)
p=Path(r'C:\Users\trigg\Desktop\IISB.pdf')
r=PdfReader(p); text='\n\n'.join(f'PAGE {i+1}\n'+page.extract_text() for i,page in enumerate(r.pages))
(out/'local_paper_text.txt').write_text(text,encoding='utf-8')
dump(out/'paper_check.json',dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pages=len(r.pages),first_page=text[:2500],title_confirmed='I2SB: Image-to-Image Schrodinger Bridge',method_pages=[4,5]))
print(text[:800].encode('ascii','replace').decode())
base='https://raw.githubusercontent.com/NVlabs/I2SB/master/'
provenance=[]
for f in ['LICENSE','i2sb/diffusion.py','i2sb/runner.py','README.md']:
    data=urllib.request.urlopen(base+f,timeout=60).read()
    dest=out/'official'/f;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    provenance.append(dict(url=base+f,sha256=hashlib.sha256(data).hexdigest()))
try:
    commit=json.loads(urllib.request.urlopen('https://api.github.com/repos/NVlabs/I2SB/commits/master',timeout=30).read())['sha']
except Exception as e: commit=str(e)
dump(out/'provenance.json',dict(commit=commit,files=provenance))
dump(ROOT/'reports/environment.json',environment())
