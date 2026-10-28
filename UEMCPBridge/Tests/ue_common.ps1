# Shared helpers for the UEMCPBridge real-engine run scripts.
# Dot-source from ue_smoke_run.ps1 / ue_probe_run.ps1:
#   . (Join-Path $PSScriptRoot 'ue_common.ps1')
#
# ASCII only on purpose: works identically in Windows PowerShell 5.1 and pwsh 7
# without depending on code-page/BOM handling.

$script:TestsDir = $PSScriptRoot
$script:PluginRoot = Split-Path -Parent $script:TestsDir
$script:RepoRoot = Split-Path -Parent $script:PluginRoot
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Step {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message)
}

function Write-JsonFile {
    param([string]$Path, $Object, [int]$Depth = 12)
    $json = $Object | ConvertTo-Json -Depth $Depth
    [System.IO.File]::WriteAllText($Path, $json, $script:Utf8NoBom)
}

function Get-FileSha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return '' }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-ProjectHash {
    param([string]$ProjectDir)
    $normalized = ([System.IO.Path]::GetFullPath($ProjectDir) -replace '\\', '/').TrimEnd('/')
    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
        $hex = ([System.BitConverter]::ToString($sha1.ComputeHash($bytes)) -replace '-', '').ToLowerInvariant()
        return $hex.Substring(0, 16)
    } finally {
        $sha1.Dispose()
    }
}

function Get-UprojectPath {
    param([string]$ProjectDir)
    $files = @(Get-ChildItem -LiteralPath $ProjectDir -Filter *.uproject -File -ErrorAction SilentlyContinue)
    if ($files.Count -eq 0) { return $null }
    return $files[0].FullName
}

function Read-JsonFile {
    param([string]$Path)
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Test-PortAvailable {
    param([int]$Port)
    $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
    try {
        $listener.Server.ExclusiveAddressUse = $true
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        try { $listener.Stop() } catch { }
    }
}

function Get-UemcpPorts { return @(18778..18788) }

function Assert-PortsFree {
    param([int[]]$Ports = (Get-UemcpPorts))
    $busy = @()
    foreach ($port in $Ports) {
        if (-not (Test-PortAvailable -Port $port)) { $busy += $port }
    }
    if ($busy.Count -gt 0) {
        throw "Ports are in use: $($busy -join ', '). Close the other editor/bridge first."
    }
}

function Wait-PortsFree {
    param([int[]]$Ports = (Get-UemcpPorts), [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $busy = @()
        foreach ($port in $Ports) {
            if (-not (Test-PortAvailable -Port $port)) { $busy += $port }
        }
        if ($busy.Count -eq 0) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Assert-NoEditorProcess {
    $names = @('UnrealEditor', 'UnrealEditor-Cmd', 'UE4Editor', 'UE4Editor-Cmd')
    $running = @(Get-Process -Name $names -ErrorAction SilentlyContinue)
    if ($running.Count -gt 0) {
        $detail = ($running | ForEach-Object { "$($_.ProcessName)#$($_.Id)" }) -join ', '
        throw "An Unreal editor instance is already running ($detail). Close it before running this script."
    }
}

function Copy-Tree {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExcludeDirNames = @(),
        [string[]]$ExcludePatterns = @()
    )
    $sourceFull = [System.IO.Path]::GetFullPath($Source)
    $destFull = [System.IO.Path]::GetFullPath($Destination)
    if (-not (Test-Path -LiteralPath $sourceFull)) { throw "Copy source not found: $sourceFull" }
    New-Item -ItemType Directory -Path $destFull -Force | Out-Null
    $files = Get-ChildItem -LiteralPath $sourceFull -Recurse -File -Force
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($sourceFull.Length).TrimStart('\', '/')
        $parts = $relative -split '[\\/]'
        $skip = $false
        foreach ($part in $parts) {
            if ($ExcludeDirNames -contains $part) { $skip = $true; break }
        }
        if ($skip) { continue }
        foreach ($pattern in $ExcludePatterns) {
            if ($file.Name -like $pattern) { $skip = $true; break }
        }
        if ($skip) { continue }
        $target = Join-Path $destFull $relative
        $parent = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}

function Enable-UprojectPlugins {
    param([string]$UprojectPath, [string[]]$PluginNames)
    $descriptor = Read-JsonFile -Path $UprojectPath
    $plugins = @()
    if ($null -ne $descriptor.Plugins) { $plugins = @($descriptor.Plugins) }
    foreach ($name in $PluginNames) {
        $existing = $plugins | Where-Object { $_.Name -eq $name } | Select-Object -First 1
        if ($null -ne $existing) {
            $existing.Enabled = $true
        } else {
            $plugins += [pscustomobject]@{ Name = $name; Enabled = $true }
        }
    }
    $descriptor | Add-Member -NotePropertyName Plugins -NotePropertyValue $plugins -Force
    Write-JsonFile -Path $UprojectPath -Object $descriptor
}

function Install-PluginCopy {
    param([string]$PluginSource, [string]$ProjectDir)
    $target = Join-Path $ProjectDir 'Plugins\UEMCPBridge'
    Copy-Tree -Source $PluginSource -Destination $target `
        -ExcludeDirNames @('__pycache__', 'smoke-runs') `
        -ExcludePatterns @('*.pyc')
    return $target
}

function Remove-InstalledPlugin {
    param([string]$ProjectDir)
    $target = Join-Path $ProjectDir 'Plugins\UEMCPBridge'
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    $pluginsDir = Join-Path $ProjectDir 'Plugins'
    if ((Test-Path -LiteralPath $pluginsDir) -and
        (Get-ChildItem -LiteralPath $pluginsDir -Force | Measure-Object).Count -eq 0) {
        Remove-Item -LiteralPath $pluginsDir -Force
    }
}

function Get-BridgeDiscoveryRecord {
    param([string]$ProjectDir)
    $bridgesDir = Join-Path $env:USERPROFILE '.uemcp\bridges'
    if (-not (Test-Path -LiteralPath $bridgesDir)) { return $null }
    $target = ([System.IO.Path]::GetFullPath($ProjectDir) -replace '\\', '/').TrimEnd('/')
    $hashPath = Join-Path $bridgesDir ("{0}.json" -f (Get-ProjectHash -ProjectDir $ProjectDir))
    $candidates = @()
    if (Test-Path -LiteralPath $hashPath) { $candidates += $hashPath }
    foreach ($file in Get-ChildItem -LiteralPath $bridgesDir -Filter *.json -File -ErrorAction SilentlyContinue) {
        if ($candidates -notcontains $file.FullName) { $candidates += $file.FullName }
    }
    foreach ($candidate in $candidates) {
        try { $record = Read-JsonFile -Path $candidate } catch { continue }
        if ($null -eq $record) { continue }
        $recordDir = [string]$record.projectDir
        if (-not $recordDir) { continue }
        $recordDir = ($recordDir -replace '\\', '/').TrimEnd('/')
        if ($recordDir -ieq $target) {
            return [pscustomobject]@{ Path = $candidate; Record = $record }
        }
    }
    return $null
}

function Get-BridgeHealth {
    param([string]$BaseUrl, [int]$TimeoutSeconds = 3)
    try {
        $response = Invoke-WebRequest -Uri ($BaseUrl + '/health') -TimeoutSec $TimeoutSeconds -UseBasicParsing
        return [pscustomobject]@{ Status = [int]$response.StatusCode; Body = [string]$response.Content }
    } catch {
        return $null
    }
}

function Invoke-UemcpRpc {
    param(
        [string]$BaseUrl,
        [string]$Token,
        [string]$Method,
        $Params = @{},
        [int]$TimeoutSeconds = 60,
        [int]$Id = 1
    )
    if ($null -eq $Params) { $Params = @{} }
    $payload = @{ jsonrpc = '2.0'; id = $Id; method = $Method; params = $Params } |
        ConvertTo-Json -Depth 12 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $request = [System.Net.HttpWebRequest]::Create($BaseUrl + '/rpc')
    $request.Method = 'POST'
    $request.ContentType = 'application/json'
    $request.Headers.Add('X-UEMCP-Token', $Token)
    $request.Timeout = $TimeoutSeconds * 1000
    $request.ReadWriteTimeout = $TimeoutSeconds * 1000
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $status = 0
    $body = ''
    try {
        $stream = $request.GetRequestStream()
        try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Close() }
        $response = $request.GetResponse()
        try {
            $status = [int]$response.StatusCode
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream(), [System.Text.Encoding]::UTF8)
            try { $body = $reader.ReadToEnd() } finally { $reader.Close() }
        } finally { $response.Close() }
    } catch [System.Net.WebException] {
        $webResponse = $_.Exception.Response
        if ($null -ne $webResponse) {
            $status = [int]$webResponse.StatusCode
            $reader = New-Object System.IO.StreamReader($webResponse.GetResponseStream(), [System.Text.Encoding]::UTF8)
            try { $body = $reader.ReadToEnd() } finally { $reader.Close() }
            $webResponse.Close()
        } else {
            throw
        }
    } finally {
        $stopwatch.Stop()
    }
    $parsed = $null
    try { $parsed = $body | ConvertFrom-Json } catch { $parsed = $null }
    return [pscustomobject]@{
        Status     = $status
        Body       = $body
        Json       = $parsed
        DurationMs = [int]$stopwatch.ElapsedMilliseconds
    }
}

function Get-NewestEditorLog {
    param([string]$ProjectDir)
    $logDir = Join-Path $ProjectDir 'Saved\Logs'
    if (-not (Test-Path -LiteralPath $logDir)) { return $null }
    $log = Get-ChildItem -LiteralPath $logDir -Filter *.log -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $log) { return $null }
    return $log.FullName
}

function Stop-EditorProcess {
    param([System.Diagnostics.Process]$Process, [int]$GracefulSeconds = 90)
    $result = [pscustomobject]@{ Graceful = $false; Forced = $false; ExitCode = $null }
    if ($null -eq $Process) { return $result }
    if ($Process.HasExited) {
        $result.Graceful = $true
        $result.ExitCode = $Process.ExitCode
        return $result
    }
    # WM_CLOSE -> editor runs its normal shutdown path (python shutdown callback
    # fires, bridge.stop() removes discovery files and releases the socket).
    $signalled = $false
    try { $signalled = $Process.CloseMainWindow() } catch { $signalled = $false }
    if ($signalled) {
        if ($Process.WaitForExit($GracefulSeconds * 1000)) {
            $result.Graceful = $true
            $result.ExitCode = $Process.ExitCode
            return $result
        }
    }
    # Fall back to hard termination; the caller records this in the evidence and
    # then cleans up the orphaned discovery file explicitly.
    try {
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
            $Process.WaitForExit(30000) | Out-Null
            $result.Forced = $true
        }
    } catch { }
    try { $result.ExitCode = $Process.ExitCode } catch { }
    return $result
}

function Remove-OrphanedDiscovery {
    param([string]$ProjectDir, [int]$EditorPid)
    $entry = Get-BridgeDiscoveryRecord -ProjectDir $ProjectDir
    if ($null -eq $entry) { return $false }
    if ([int]$entry.Record.pid -ne $EditorPid) { return $false }
    Remove-Item -LiteralPath $entry.Path -Force -ErrorAction SilentlyContinue
    $latest = Join-Path $env:USERPROFILE '.uemcp\bridge.json'
    if (Test-Path -LiteralPath $latest) {
        try {
            $record = Read-JsonFile -Path $latest
            if (($record.pid -eq $entry.Record.pid) -and ($record.token -eq $entry.Record.token)) {
                Remove-Item -LiteralPath $latest -Force -ErrorAction SilentlyContinue
            }
        } catch { }
    }
    return $true
}

function New-RunDirectory {
    param([string]$EngineVersion, [string]$Kind = 'smoke')
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dir = Join-Path $script:TestsDir ("smoke-runs\{0}-{1}-{2}" -f $Kind, $EngineVersion, $stamp)
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    return $dir
}

function Write-Lines {
    param([string]$Path, [string[]]$Lines)
    [System.IO.File]::WriteAllLines($Path, $Lines, $script:Utf8NoBom)
}
