"""Export an explicit source allowlist to a NEW folder; never copy experiment data."""
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def source_files():
    files = [ROOT / '.gitignore', ROOT / 'requirements.lock.txt']
    for pattern in ('*.py', '*.md'):
        files.extend(ROOT.glob(pattern))
    files.extend((ROOT / 'fm').glob('*.py'))
    files.extend((ROOT / 'configs').glob('*.json'))
    files.extend(ROOT / name for name in (
        'data/splits.json', 'references/provenance.json', 'references/official/LICENSE'))
    return sorted({p for p in files if p.is_file()}, key=lambda p: p.relative_to(ROOT).as_posix())

def main():
    parser = argparse.ArgumentParser(description='Export code, configuration, anonymous splits and attribution only')
    parser.add_argument('--output', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError('Output must be a new directory')
    if '.git' in output.parts:
        raise ValueError('Cannot export into Git metadata')
    files = source_files()
    if not args.dry_run:
        output.mkdir(parents=True)
        for source in files:
            target = output / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print(json.dumps(dict(output=str(output), dry_run=args.dry_run,
                         files=[p.relative_to(ROOT).as_posix() for p in files],
                         total_bytes=sum(p.stat().st_size for p in files)), indent=2))

if __name__ == '__main__':
    main()
