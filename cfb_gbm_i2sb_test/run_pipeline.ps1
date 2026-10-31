param([switch]$SkipAudit)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$env:PYTHONUTF8='1'
function Run-Python([string[]]$Arguments) {
    & .\.venv\Scripts\python.exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Step failed: $Arguments" }
}
if (-not $SkipAudit) { Run-Python -Arguments @('audit_data.py') }
Run-Python -Arguments @('post_audit.py')
Run-Python -Arguments @('review_flagged.py')
Run-Python -Arguments @('gtv_overlay.py')
Run-Python -Arguments @('test_contracts.py')
Run-Python -Arguments @('illustrate_bridge.py')
Run-Python -Arguments @('verify.py')
Run-Python -Arguments @('verify.py','--overfit','--steps','600')
Run-Python -Arguments @('train.py','--kind','i2sb','--run','i2sb_short')
Run-Python -Arguments @('train.py','--kind','regression','--run','regression_short')
Run-Python -Arguments @('integration_checks.py')
Run-Python -Arguments @('evaluate.py','--checkpoint','weights/i2sb_short/best.pt','--run','i2sb_short')
Run-Python -Arguments @('evaluate.py','--checkpoint','weights/regression_short/best.pt','--run','regression_short')
Run-Python -Arguments @('make_report.py')
