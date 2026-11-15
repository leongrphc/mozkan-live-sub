param(
    [Parameter(Mandatory=$true)][string]$SourceInstallation
)
$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path -LiteralPath $SourceInstallation).Path
$destinationRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
if ($sourceRoot.TrimEnd('\') -eq $destinationRoot.TrimEnd('\')) { throw 'Kaynak ve hedef farklı olmalı.' }
$copies = @(
    @('python', 'python'),
    @('app\models', 'models'),
    @('app\game_profiles', 'game_profiles'),
    @('app\samsung', 'samsung')
)
foreach ($copy in $copies) {
    $sourceFolder = Join-Path $sourceRoot $copy[0]
    $destinationFolder = Join-Path $destinationRoot $copy[1]
    if (-not (Test-Path -LiteralPath $sourceFolder -PathType Container)) { throw "Kaynak klasör yok: $sourceFolder" }
    & robocopy $sourceFolder $destinationFolder /E /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -ge 8) { throw "Kopyalama başarısız: $sourceFolder (kod $LASTEXITCODE)" }
}
Write-Output 'Yerel runtime, modeller, oyun profilleri ve Samsung yardımcıları hazır.'
