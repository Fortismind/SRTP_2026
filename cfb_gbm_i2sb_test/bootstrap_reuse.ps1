param([string]$GpuPython = 'D:\ai\.venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath $GpuPython)) { throw "GPU Python missing: $GpuPython" }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $GpuPython -m venv --system-site-packages .venv
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
$gpuSite = & $GpuPython -c "import sysconfig; print(sysconfig.get_path('purelib'))"
Set-Content -LiteralPath '.venv\Lib\site-packages\reuse_gpu.pth' -Value "import sys; sys.path.insert(1, r'$gpuSite')"
& .\.venv\Scripts\python.exe -m pip install nibabel==5.4.2 scipy==1.15.3 scikit-image==0.25.2 pypdf==6.21.2 openpyxl==3.1.5
if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
& .\.venv\Scripts\python.exe -c "import torch,numpy,scipy;print(torch.__version__,torch.cuda.is_available(),numpy.__version__,scipy.__version__)"
