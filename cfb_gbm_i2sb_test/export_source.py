"""Export source-only files to a NEW directory, without touching any Git history."""
import argparse,shutil,json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def source_files():
    files=[ROOT/'.gitignore',ROOT/'requirements.lock.txt']
    for pattern in ['*.py','*.ps1','*.md']:files.extend(ROOT.glob(pattern))
    files.extend((ROOT/'cfb').glob('*.py'))
    files.extend((ROOT/'configs').glob('*.json'))
    files.extend([ROOT/'data/splits.json',ROOT/'references/provenance.json',ROOT/'references/official/LICENSE'])
    return sorted({p for p in files if p.is_file()},key=lambda p:str(p.relative_to(ROOT)))

def main():
    p=argparse.ArgumentParser(description='导出源码、配置、固定划分和来源许可证；不包含 MRI、权重、日志或患者清单')
    p.add_argument('--output',required=True);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    destination=Path(a.output).resolve()
    if destination.exists():raise FileExistsError('Output must be a NEW directory; existing folders will not be overwritten')
    if '.git' in destination.parts:raise ValueError('Cannot export into Git metadata')
    files=source_files();size=sum(f.stat().st_size for f in files)
    if not a.dry_run:
        destination.mkdir(parents=True)
        for source in files:
            target=destination/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    print(json.dumps(dict(output=str(destination),dry_run=a.dry_run,files=[str(f.relative_to(ROOT)) for f in files],total_bytes=size),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
