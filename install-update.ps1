param(
    [Parameter(Mandatory = $true)]
    [string]$TargetDirectory
)
$ErrorActionPreference = 'Stop'

# This script is run by the user after closing the old installation.
# It never stops an application and never touches LocalAppData settings.
$targetRoot = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $TargetDirectory).Path).TrimEnd('\')
$sourceRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
if ($targetRoot -eq $sourceRoot) { throw 'Güncellemeyi kurulumdan ayrı bir klasöre çıkarın.' }
$targetPrefix = $targetRoot + '\'
if ($sourceRoot.StartsWith($targetPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Güncelleme kaynak klasörü kurulumun dışında olmalı.'
}
foreach ($relative in @('python\pythonw.exe', 'models\opus-mt-tc-big-en-tr-ct2\model.bin', 'src\main.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $targetRoot $relative) -PathType Leaf)) {
        throw "Eksik kurulum dosyası: $relative"
    }
}
$mainText = [IO.File]::ReadAllText((Join-Path $targetRoot 'src\main.py'))
if ($mainText -notmatch "(?m)^APP_VERSION='0\.4\.0'\s*$") {
    throw 'Bu güncelleme yalnız 0.4.0 kurulumuna uygulanabilir. Yeni sürüm için tam paketi kullanın.'
}

function Assert-NoRunningInstallation {
    $running = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($targetPrefix, [StringComparison]::OrdinalIgnoreCase)) -or
        ($_.CommandLine -and $_.CommandLine.IndexOf($targetPrefix, [StringComparison]::OrdinalIgnoreCase) -ge 0)
    })
    if ($running.Count) { throw 'Bu kurulumdan çalışan işlem var. Uygulamayı kendiniz kapatıp yeniden deneyin.' }
}

function Assert-NoReparsePath([string]$path) {
    $cursor = $path
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $entry = Get-Item -LiteralPath $cursor -Force
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Bağlantılı dosya/klasör üzerinden güncelleme yapılmaz: $cursor"
            }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

Assert-NoRunningInstallation
Assert-NoReparsePath $targetRoot
$manifestPath = Join-Path $sourceRoot 'update-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.version -ne '0.4.1' -or @($manifest.from_versions).Count -ne 1 -or $manifest.from_versions[0] -ne '0.4.0') {
    throw 'Güncelleme manifesti geçersiz.'
}
$records = @($manifest.files)
if ($records.Count -lt 1 -or $records.Count -gt 1000) { throw 'Güncelleme dosya sayısı geçersiz.' }
$seen = @{}
$payloads = @()
foreach ($record in $records) {
    $relative = [string]$record.path
    if ($relative -notmatch '^[A-Za-z0-9_. /-]+$' -or $relative -match '(^|/)(\.|\.\.)(/|$)' -or
        [IO.Path]::IsPathRooted($relative) -or $relative.Contains('\')) {
        throw "Geçersiz güncelleme yolu: $relative"
    }
    if ($seen.ContainsKey($relative)) { throw "Tekrarlanan güncelleme yolu: $relative" }
    $seen[$relative] = $true
    # Only source, the new launcher and explicitly named product documents belong here.
    if ($relative -notmatch '^src/' -and $relative -notmatch '^UPDATE-[0-9.]+\.md$' -and
        $relative -notin @('MOZKANLiveSub.exe','start.ps1','README.md','TESLIM.md','TESLIM-MOZKAN.md',
                           'GUNCELLEME.md','install-update.ps1','REBRAND.md','requirements.txt')) {
        throw "Güncelleme kapsamı dışında dosya: $relative"
    }
    # Old delivery notes are immutable; leave them in the existing installation.
    if ($relative -eq 'TESLIM.md' -or ($relative -like 'UPDATE-*' -and $relative -ne 'UPDATE-0.4.1.md')) { continue }
    $source = [IO.Path]::GetFullPath((Join-Path $sourceRoot $relative))
    $destination = [IO.Path]::GetFullPath((Join-Path $targetRoot $relative))
    if (-not $destination.StartsWith($targetPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Hedef yolu kurulum dışına çıkıyor.' }
    Assert-NoReparsePath $source
    Assert-NoReparsePath $destination
    $bytes = [IO.File]::ReadAllBytes($source)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $hash = [BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
    if ($bytes.Length -ne $record.bytes -or $hash -ne $record.sha256) { throw "Dosya doğrulanamadı: $relative" }
    $payloads += [pscustomobject]@{ Relative=$relative; Destination=$destination; Bytes=$bytes; Hash=$hash }
}
foreach ($required in @('src/main.py','src/console_ui.py','src/presentation.py','src/tv_panel.py','src/hotkeys.py','src/glossary.py','src/history.py','src/audio/navigate.wav','MOZKANLiveSub.exe')) {
    if (-not $seen.ContainsKey($required)) { throw "Eksik güncelleme girdisi: $required" }
}
$backupRoot = Join-Path $targetRoot ('backups\before-0.4.1-' + [Guid]::NewGuid().ToString('N'))
Assert-NoReparsePath $backupRoot
Assert-NoRunningInstallation
[IO.Directory]::CreateDirectory($backupRoot) | Out-Null
$applied = @()
try {
    # All old files are backed up before the first replacement.
    foreach ($payload in $payloads) {
        if (Test-Path -LiteralPath $payload.Destination -PathType Leaf) {
            $backup = Join-Path $backupRoot $payload.Relative
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($backup)) | Out-Null
            [IO.File]::Copy($payload.Destination, $backup, $false)
        }
    }
    # Main version changes last. A partial update does not advertise the new version.
    foreach ($payload in ($payloads | Sort-Object @{Expression={ $_.Relative -eq 'src/main.py' }})) {
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($payload.Destination)) | Out-Null
        $temporary = $payload.Destination + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
        try {
            [IO.File]::WriteAllBytes($temporary, $payload.Bytes)
            if ([IO.File]::Exists($payload.Destination)) {
                [IO.File]::Replace($temporary, $payload.Destination, $null)
            } else {
                [IO.File]::Move($temporary, $payload.Destination)
            }
            $applied += $payload.Relative
        } finally {
            if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        }
    }
    foreach ($payload in $payloads) {
        if ((Get-FileHash -LiteralPath $payload.Destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $payload.Hash) {
            throw "Kurulu dosya doğrulanamadı: $($payload.Relative)"
        }
    }
    $receipt = [ordered]@{
        version = '0.4.1'
        from_version = '0.4.0'
        installed_utc = [DateTime]::UtcNow.ToString('o')
        backup = $backupRoot
        files = @($payloads | ForEach-Object { [ordered]@{ path=$_.Relative; sha256=$_.Hash } })
    }
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $targetRoot 'installed-update-0.4.1.json') -Encoding UTF8
} catch {
    # Backups and a precise list remain available if permissions or disk errors interrupt installation.
    $applied | Set-Content -LiteralPath (Join-Path $backupRoot 'applied-files.txt') -Encoding UTF8
    throw "Güncelleme tamamlanamadı. Uygulamayı açmayın; yedek: $backupRoot. Hata: $($_.Exception.Message)"
}
Write-Output "Güncellendi: $targetRoot\MOZKANLiveSub.exe"
Write-Output "Önceki dosyalar: $backupRoot"
Write-Output 'Ayarlar ve eski başlatıcı korundu. Uygulama otomatik açılmadı.'
