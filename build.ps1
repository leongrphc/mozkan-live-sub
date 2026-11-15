$ErrorActionPreference = 'Stop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Windows .NET Framework C# derleyicisi bulunamadı.' }
& $compiler /nologo /target:winexe /reference:System.Windows.Forms.dll "/out:$PSScriptRoot\AltyaziAtolyesi.exe" "$PSScriptRoot\launcher.cs"
if ($LASTEXITCODE -ne 0) { throw 'Başlatıcı derlenemedi.' }
