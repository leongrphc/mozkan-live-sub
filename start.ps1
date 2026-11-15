$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot 'python\python.exe'
$models = Join-Path $PSScriptRoot 'models'
if (-not (Test-Path -LiteralPath $runtime)) { throw 'Yerel Python ortamı bulunamadı. prepare-runtime.ps1 ile hazırlayın.' }
& $runtime -E -s -X utf8 "$PSScriptRoot\src\main.py" --models $models
exit $LASTEXITCODE
