<#
.SYNOPSIS
    Package the UEMCPBridge plugin into distributable zips for one or more engine versions.

.DESCRIPTION
    Builds dist-release/UEMCPBridge-<major.minor>.zip (one per requested version) from the
    current plugin sources. No product logic is modified; the source .uplugin is never touched.

    Package layout (identical file manifest across all versions built in one run; the ONLY
    content difference is the injected EngineVersion / Description version tag in .uplugin):

        UEMCPBridge/
            UEMCPBridge.uplugin   (EngineVersion + Description injected per version)
            README.md             (copied as-is from UEMCPBridge/)
            COMPAT-UE57.md        (5.7 compatibility table, shipped with the package)
            LICENSE               (full MIT text copied from the repository root - NOT a pointer)
            Content/...           (copied recursively; __pycache__ / *.py[cod] pruned)
            Tests/                (self-check scripts + SMOKE-REAL-ENGINE.md; *.ps1 executors,
                                   smoke-runs/ run artifacts, __pycache__, *.py[cod] are
                                   excluded - maintainer-only material stays out)

    Tools/ is never packaged (source-repository only; the README shipped in the package
    states this).

    Both/all versions are built from ONE staging snapshot, so the packages are guaranteed
    to share an identical file manifest (verified in-script before exit). A
    dist-release/SHA256SUMS.txt ("<sha256>  <filename>", lowercase hex, two spaces) is
    regenerated over every UEMCPBridge-*.zip currently in dist-release after each run.

    Injection rules for the PACKAGED .uplugin (the source descriptor is version-agnostic):
        EngineVersion  -> replaced if the field exists, inserted if it does not.
        Description    -> the "Unreal Engine x.y[.z]" fragment is rewritten to the requested
                          version; the script fails if the fragment is absent.

    The script is idempotent (staging and target zips are wiped and rebuilt) and exits
    non-zero on any failure (bad input, missing sources, injection mismatch, or a failed
    self-verification that mirrors the release gates: forward-slash entry names, no
    maintainer/junk entries, LICENSE full-text hash match, JSON validity, metadata checks).

    EngineVersion input normalization:
        "5.4"        -> EngineVersion "5.4.0", archive UEMCPBridge-5.4.zip
        "5.7"        -> EngineVersion "5.7.0", archive UEMCPBridge-5.7.zip
        "5.4.4"      -> EngineVersion "5.4.4", archive UEMCPBridge-5.4.zip (name = major.minor)
        "5.4","5.7"  (or -EngineVersion 5.4,5.7) -> both archives from one snapshot

.USAGE
    ./scripts/pack-bridge.ps1 -EngineVersion 5.4,5.7     # release build: both, one snapshot
    ./scripts/pack-bridge.ps1 -EngineVersion 5.4
    ./scripts/pack-bridge.ps1 5.4                        # positional form
    pwsh -NoProfile -File scripts/pack-bridge.ps1 -EngineVersion 5.4,5.7

    Works under Windows PowerShell 5.1 and PowerShell 7+. Run from any working directory;
    paths are resolved relative to the repository root (the parent of the scripts/ folder
    this file lives in).

.NOTES
    Output dist-release/ is git-ignored. This script only stages copies; it never edits
    the plugin sources in UEMCPBridge/.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string[]]$EngineVersion
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-NormalizedVersion([string]$Value) {
    if ($Value -notmatch '^\d+\.\d+(\.\d+)?$') {
        throw "Invalid engine version '$Value': expected 'major.minor' (e.g. 5.4) or 'major.minor.patch' (e.g. 5.4.4)."
    }
    $parts = $Value.Split('.')
    $short = $parts[0] + '.' + $parts[1]
    $full  = if ($parts.Count -ge 3) { $Value } else { $Value + '.0' }
    [pscustomobject]@{ Input = $Value; Short = $short; Full = $full }
}

function Build-Zip([string]$StagedRoot, [string]$ZipPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $dirs = Get-ChildItem $StagedRoot -Recurse -Directory -Force |
        Sort-Object FullName |
        ForEach-Object { $_.FullName.Substring($StagedRoot.Length + 1).Replace('\', '/') + '/' }
    $files = Get-ChildItem $StagedRoot -Recurse -File -Force | Sort-Object FullName

    $archive = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($d in $dirs) { $archive.CreateEntry($d) | Out-Null }
        foreach ($f in $files) {
            $entryName = $f.FullName.Substring($StagedRoot.Length + 1).Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive, $f.FullName, $entryName,
                [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    }
    finally { $archive.Dispose() }
}

function Read-ZipEntryText($Archive, [string]$EntryName) {
    $entry = $Archive.Entries | Where-Object { $_.FullName -eq $EntryName }
    if (-not $entry) { throw "Expected zip entry missing: $EntryName" }
    $reader = New-Object System.IO.StreamReader($entry.Open())
    try { $reader.ReadToEnd() } finally { $reader.Dispose() }
}

function Verify-Package([string]$ZipPath, $VersionInfo, [string]$LicenseHash) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $names = @($archive.Entries | ForEach-Object { $_.FullName })
        $v = $VersionInfo.Short

        if (@($names | Where-Object { $_ -match '\\' }).Count -gt 0) {
            throw 'verification failed: zip entries contain backslashes'
        }
        $banned = @($names | Where-Object { $_ -match '__pycache__|\.pyc$|\.pyo$|node_modules/|(^|/)\.git/|(^|/)logs/|\.test-run|smoke-runs|(^|/)Tools/' })
        if ($banned.Count -gt 0) { throw "verification failed: junk/maintainer entries present: $($banned -join ', ')" }
        $ps1 = @($names | Where-Object { $_ -match '^UEMCPBridge/Tests/.*\.ps1$' })
        if ($ps1.Count -gt 0) { throw "verification failed: .ps1 executors under Tests/: $($ps1 -join ', ')" }
        foreach ($must in @('UEMCPBridge/UEMCPBridge.uplugin',
                            'UEMCPBridge/README.md',
                            'UEMCPBridge/COMPAT-UE57.md',
                            'UEMCPBridge/LICENSE',
                            'UEMCPBridge/Content/Python/uemcp_bridge/server.py',
                            'UEMCPBridge/Content/Python/init_unreal.py')) {
            if ($names -notcontains $must) { throw "verification failed: required entry missing: $must" }
        }
        if (@($names | Where-Object { $_ -like 'UEMCPBridge/Tests/*' }).Count -lt 1) {
            throw 'verification failed: no self-check files under UEMCPBridge/Tests/'
        }
        if ($names -notcontains 'UEMCPBridge/Tests/SMOKE-REAL-ENGINE.md') {
            throw 'verification failed: required entry missing: UEMCPBridge/Tests/SMOKE-REAL-ENGINE.md'
        }

        # every .md referenced by the packaged README must ship in the package (anti dead-link)
        $readmeText = Read-ZipEntryText $Archive 'UEMCPBridge/README.md'
        $mdRefs = [regex]::Matches($readmeText, '[A-Za-z0-9_.\-]+\.md') |
            ForEach-Object { $_.Value } | Sort-Object -Unique
        foreach ($md in $mdRefs) {
            $hit = @($names | Where-Object { $_ -eq "UEMCPBridge/$md" -or $_ -like "*/$md" })
            if ($hit.Count -eq 0) {
                throw "verification failed: README references '$md' which is not in the package (dead link)"
            }
        }

        # LICENSE must be the full MIT text, byte-identical to the repository root LICENSE
        $zippedLicenseHash = $null
        $licEntry = $archive.Entries | Where-Object { $_.FullName -eq 'UEMCPBridge/LICENSE' }
        $stream = $licEntry.Open()
        try {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try   { $zippedLicenseHash = ([System.BitConverter]::ToString($sha.ComputeHash($stream)) -replace '-', '').ToLower() }
            finally { $sha.Dispose() }
        }
        finally { $stream.Dispose() }
        if ($zippedLicenseHash -ne $LicenseHash) {
            throw "verification failed: packaged LICENSE is not identical to the repository-root MIT full text"
        }

        # .uplugin metadata
        $up = Read-ZipEntryText $Archive 'UEMCPBridge/UEMCPBridge.uplugin' | ConvertFrom-Json
        if ("$($up.EngineVersion)" -notlike "$v*") {
            throw "verification failed: EngineVersion='$($up.EngineVersion)' does not match $v"
        }
        if ("$($up.Type)" -ne 'Editor') { throw "verification failed: Type='$($up.Type)' is not Editor" }
        if (@($up.Modules).Count -ne 0) { throw 'verification failed: Modules is not empty' }
        $depNames = @($up.Plugins | ForEach-Object { $_.Name })
        foreach ($dep in @('PythonScriptPlugin', 'EditorScriptingUtilities')) {
            if ($depNames -notcontains $dep) { throw "verification failed: dependency missing: $dep" }
        }
        $desc = "$($up.Description)"
        if ([string]::IsNullOrWhiteSpace($desc)) { throw 'verification failed: Description is empty' }
        if ($desc -notmatch [regex]::Escape("Unreal Engine $v")) {
            throw "verification failed: Description does not mention 'Unreal Engine $v'"
        }
        $other = if ($v -eq '5.4') { '5.7' } else { '5.4' }
        if ($desc -match [regex]::Escape($other)) {
            throw "verification failed: Description claims the wrong engine version ($other)"
        }

        return ,@($names | Sort-Object)
    }
    finally { $archive.Dispose() }
}

try {
    # ---------------------------------------------------------------- resolve paths
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $pluginDir    = Join-Path $repoRoot 'UEMCPBridge'
    $upluginSrc   = Join-Path $pluginDir 'UEMCPBridge.uplugin'
    $pluginReadme = Join-Path $pluginDir 'README.md'
    $compatDoc    = Join-Path $pluginDir 'COMPAT-UE57.md'
    $contentDir   = Join-Path $pluginDir 'Content'
    $testsDir     = Join-Path $pluginDir 'Tests'
    $repoLicense  = Join-Path $repoRoot 'LICENSE'
    $releaseDir   = Join-Path $repoRoot 'dist-release'
    $stagingRoot  = Join-Path $releaseDir '.staging'

    # ---------------------------------------------------------------- normalize input
    $versions = @()
    foreach ($raw in $EngineVersion) {
        foreach ($piece in ($raw -split ',')) {
            $t = $piece.Trim()
            if ($t) { $versions += Get-NormalizedVersion $t }
        }
    }
    if ($versions.Count -eq 0) { throw 'No engine version requested.' }
    $dup = $versions | Group-Object Short | Where-Object { $_.Count -gt 1 }
    if ($dup) { throw "Duplicate engine version requested: $(($dup | ForEach-Object { $_.Name }) -join ', ')" }

    Write-Host ("pack-bridge: versions = " + (($versions | ForEach-Object { "$($_.Input) (EngineVersion=$($_.Full))" }) -join ', '))

    # ---------------------------------------------------------------- fail fast on missing sources
    foreach ($required in @($pluginDir, $upluginSrc, $pluginReadme, $compatDoc, $contentDir, $testsDir, $repoLicense)) {
        if (-not (Test-Path $required)) { throw "Required source not found: $required" }
    }
    if (-not (Test-Path (Join-Path $contentDir 'Python'))) { throw "Required source not found: $(Join-Path $contentDir 'Python')" }

    # read the version-agnostic descriptor ONCE; every version re-parses this same text
    $upluginRaw = Get-Content $upluginSrc -Raw

    # ---------------------------------------------------------------- idempotent reset
    if (Test-Path $stagingRoot) { Remove-Item -Recurse -Force $stagingRoot }
    foreach ($vi in $versions) {
        $zipPath = Join-Path $releaseDir ("UEMCPBridge-{0}.zip" -f $vi.Short)
        if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
    }
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

    # ---------------------------------------------------------------- stage the shared snapshot (once)
    $commonPlugin = Join-Path $stagingRoot 'common\UEMCPBridge'
    New-Item -ItemType Directory -Path $commonPlugin -Force | Out-Null

    Copy-Item $pluginReadme (Join-Path $commonPlugin 'README.md')
    Copy-Item $compatDoc    (Join-Path $commonPlugin 'COMPAT-UE57.md')
    Copy-Item $repoLicense  (Join-Path $commonPlugin 'LICENSE')   # full MIT text, not a pointer
    Copy-Item $contentDir (Join-Path $commonPlugin 'Content') -Recurse
    Copy-Item $testsDir   (Join-Path $commonPlugin 'Tests')   -Recurse

    # prune junk everywhere in the snapshot
    Get-ChildItem $stagingRoot -Recurse -Directory -Force -Filter '__pycache__' | Remove-Item -Recurse -Force
    Get-ChildItem $stagingRoot -Recurse -File -Force -Include '*.pyc', '*.pyo'  | Remove-Item -Force

    # prune maintainer-only material from Tests/: .ps1 executors and run artifacts
    # (Tests/*.md docs - e.g. SMOKE-REAL-ENGINE.md - DO ship with the package)
    Get-ChildItem (Join-Path $commonPlugin 'Tests') -Recurse -File -Force -Filter '*.ps1' | Remove-Item -Force
    $testsStaged = Join-Path $commonPlugin 'Tests'
    Get-ChildItem $testsStaged -Recurse -Directory -Force | Where-Object { $_.Name -eq 'smoke-runs' } | Remove-Item -Recurse -Force
    Write-Host 'pack-bridge: staged common snapshot (README, COMPAT-UE57.md, full MIT LICENSE, Content/, Tests/ minus ps1 & smoke-runs)'

    $repoLicenseHash = (Get-FileHash $repoLicense -Algorithm SHA256).Hash.ToLower()

    # ---------------------------------------------------------------- build one package per version
    $manifests = @{}
    foreach ($vi in $versions) {
        $vStaging  = Join-Path $stagingRoot ("v-" + $vi.Short)
        $vPlugin   = Join-Path $vStaging 'UEMCPBridge'
        New-Item -ItemType Directory -Path $vStaging -Force | Out-Null
        Copy-Item $commonPlugin $vStaging -Recurse

        # inject EngineVersion + Description into the staged COPY
        $j = $upluginRaw | ConvertFrom-Json
        $descPattern = '(Unreal Engine )\d+(\.\d+)*'
        if ([regex]::Matches("$($j.Description)", $descPattern).Count -lt 1) {
            throw "Description engine tag ('Unreal Engine x.y[.z]') not found in $upluginSrc (Description='$($j.Description)')"
        }
        $j.Description = [regex]::Replace("$($j.Description)", $descPattern, ('${1}' + $vi.Short))
        if ($j.PSObject.Properties['EngineVersion']) { $j.EngineVersion = $vi.Full }
        else { $j | Add-Member -NotePropertyName 'EngineVersion' -NotePropertyValue $vi.Full }
        $upluginText = $j | ConvertTo-Json -Depth 10
        $check = $upluginText | ConvertFrom-Json
        if ($check.EngineVersion -ne $vi.Full) { throw "Injection failed for $($vi.Short): EngineVersion='$($check.EngineVersion)'" }
        Set-Content -Path (Join-Path $vPlugin 'UEMCPBridge.uplugin') -Value $upluginText -Encoding UTF8

        $zipPath = Join-Path $releaseDir ("UEMCPBridge-{0}.zip" -f $vi.Short)
        Build-Zip $vStaging $zipPath
        $manifests[$vi.Short] = Verify-Package $zipPath $vi $repoLicenseHash

        $zipSize  = (Get-Item $zipPath).Length
        $zipHash  = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()
        Write-Host ("pack-bridge: OK {0} -> {1:N0} bytes, {2} entries, sha256={3}" -f $zipPath, $zipSize, $manifests[$vi.Short].Count, $zipHash)
    }

    # ---------------------------------------------------------------- cross-version manifest equality
    if ($versions.Count -ge 2) {
        $first = $manifests[$versions[0].Short]
        foreach ($vi in $versions | Select-Object -Skip 1) {
            $other = $manifests[$vi.Short]
            $diff = Compare-Object -ReferenceObject $first -DifferenceObject $other
            if ($diff) {
                throw ("manifest mismatch between {0} and {1}: {2}" -f $versions[0].Short, $vi.Short, (($diff | Select-Object -First 10 | ForEach-Object { $_.InputObject }) -join ', '))
            }
        }
        Write-Host 'pack-bridge: cross-version manifest check passed (identical file lists)'
    }

    # ---------------------------------------------------------------- SHA256SUMS.txt over all zips present
    $zips = Get-ChildItem $releaseDir -Filter 'UEMCPBridge-*.zip' -File | Sort-Object Name
    if ($zips.Count -eq 0) { throw 'No packages found for checksum generation.' }
    $sums = $zips | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name }
    Set-Content -Path (Join-Path $releaseDir 'SHA256SUMS.txt') -Value $sums -Encoding ASCII
    Write-Host ("pack-bridge: SHA256SUMS.txt regenerated ({0} zip(s))" -f $zips.Count)

    # ---------------------------------------------------------------- cleanup staging
    Remove-Item -Recurse -Force $stagingRoot
    Write-Host 'pack-bridge: DONE'
    exit 0
}
catch {
    if (Get-Variable stagingRoot -ErrorAction SilentlyContinue) {
        if (Test-Path $stagingRoot) { Remove-Item -Recurse -Force $stagingRoot }
    }
    Write-Error ("pack-bridge failed: {0}" -f $_.Exception.Message)
    exit 1
}
