import json, random, hashlib, platform, sys, subprocess
from pathlib import Path
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]

def dump(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def seed_all(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def environment():
    import importlib.metadata as md
    packages = {p: md.version(p) for p in ['torch','numpy','scipy','nibabel','scikit-image','matplotlib','pypdf']}
    return dict(platform=platform.platform(), python=sys.version, executable=sys.executable,
                packages=packages, torch_actual=torch.__version__, cuda=torch.version.cuda,
                cuda_available=torch.cuda.is_available(), gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                gpu_memory_bytes=torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else 0,
                nvidia_smi=subprocess.run(['nvidia-smi'],capture_output=True,text=True).stdout)
