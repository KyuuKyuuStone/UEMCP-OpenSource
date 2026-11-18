# QA exec window (task cc433d95): prepare project via frozen ue_common functions, launch editor,
# wait bridge /health. Bridge STAYS ONLINE after this script exits (detached Start-Process).
# Gates: -Gates full sets UEMCP_BRIDGE_ALLOW_*='true' for THIS process, inherited by editor child.
param(
    [ValidateSet('off', 'full')][string]$Gates = 'off',
    [string]$EngineVersion = '5.7',
    [string]$ProjectDir = '',
    [int]$LaunchTimeoutSeconds = 480,
    [string]$ExtraArgs = ''
)
$ErrorActionPreference = 'Continue'
$repo = 'C:\UE5_P\5.4\UEMCP'
. (Join-Path $repo 'UEMCPBridge\Tests\ue_common.ps1')
if (-not $ProjectDir) {
    if ($EngineVersion -eq '5.4') { $ProjectDir = Join-Path $repo 'ue_p_text\ue54_text' }
    else { $ProjectDir = Join-Path $env:USERPROFILE 'Documents\Unreal Projects\UEMCP_Smoke_Blank' }
}
$ProjectDir = [System.IO.Path]::GetFullPath($ProjectDir).TrimEnd('\')
$engineRoot = "C:\Program Files\Epic Games\UE_$EngineVersion"
$editorExe = Join-Path $engineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$winDir = Join-Path $repo ('feedback-review\logs\qasmoke-window\' + $stamp)
New-Item -ItemType Directory -Path $winDir -Force | Out-Null
Write-Output ('WINDOW-DIR ' + $winDir)

# preflight equivalents
$procs = @(Get-Process -Name 'UnrealEditor', 'UE4Editor' -ErrorAction SilentlyContinue)
if ($procs.Count -gt 0) { Write-Output 'FATAL editor process already running'; exit 1 }
$busy = @()
foreach ($port in 18778..18788) { if (-not (Test-PortAvailable -Port $port)) { $busy += $port } }
if ($busy.Count -gt 0) { Write-Output ('FATAL busy ports: ' + ($busy -join ',')); exit 1 }
Write-Output 'PREFLIGHT ok no-editor ports-free'

# backup uproject BEFORE enabling plugins
$up = Get-UprojectPath -ProjectDir $ProjectDir
if (-not $up) { Write-Output 'FATAL no uproject'; exit 1 }
$backup = Join-Path $winDir 'uproject.before.bak'
Copy-Item -LiteralPath $up -Destination $backup
[void](Get-FileSha256 -Path $backup) | Out-Null
'{"projectDir":"' + ($ProjectDir -replace '\\', '\\') + '","uproject":"' + ($up -replace '\\', '\\') + '","engineVersion":"' + $EngineVersion + '","backup":"' + ($backup -replace '\\', '\\') + '"}' | Out-File (Join-Path $winDir 'window.json') -Encoding UTF8
Write-Output ('UPROJECT-BACKUP sha=' + (Get-FileSha256 -Path $up))

# prepare equivalents (same as smoke script: plugin copy + enable 3 plugins)
Install-PluginCopy -PluginSource (Join-Path $repo 'UEMCPBridge') -ProjectDir $ProjectDir
Enable-UprojectPlugins -UprojectPath $up -PluginNames @('UEMCPBridge', 'PythonScriptPlugin', 'EditorScriptingUtilities')
Write-Output 'PREPARED plugin-copied+3-plugins-enabled'

if ($Gates -eq 'full') {
    [Environment]::SetEnvironmentVariable('UEMCP_BRIDGE_ALLOW_WRITE', 'true', 'Process')
    [Environment]::SetEnvironmentVariable('UEMCP_BRIDGE_ALLOW_EXEC', 'true', 'Process')
    [Environment]::SetEnvironmentVariable('UEMCP_BRIDGE_ALLOW_CONSOLE', 'true', 'Process')
    Write-Output 'GATES env set: ALLOW_WRITE/EXEC/CONSOLE=true'
} else {
    foreach ($n in @('UEMCP_BRIDGE_ALLOW_WRITE', 'UEMCP_BRIDGE_ALLOW_EXEC', 'UEMCP_BRIDGE_ALLOW_CONSOLE')) {
        Remove-Item -LiteralPath ('Env:' + $n) -ErrorAction SilentlyContinue
    }
    Write-Output 'GATES env removed entirely (factory-off, envOverrides must be empty)'
}

# launch (same args as smoke script plan.json)
$extra = ''
if ($ExtraArgs) { $extra = ' ' + $ExtraArgs }
$ep = Start-Process -FilePath $editorExe -ArgumentList ('"' + $up + '" -log -nop4 -nosplash' + $extra) -PassThru
Write-Output ('EDITOR-STARTED pid=' + $ep.Id)
$deadline = (Get-Date).AddSeconds($LaunchTimeoutSeconds)
$rec = $null
$healthOk = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 4
    if ($ep.HasExited) { Write-Output ('FATAL editor exited code=' + $ep.ExitCode); exit 2 }
    $rec = Get-BridgeDiscoveryRecord -ProjectDir $ProjectDir
    if ($null -ne $rec) {
        $h = Get-BridgeHealth -BaseUrl ([string]$rec.Record.url) -TimeoutSeconds 3
        if ($null -ne $h -and $h.Status -eq 200) { $healthOk = $true; break }
    }
}
if (-not $healthOk) { Write-Output 'FATAL bridge /health not ready in window'; exit 2 }
$rec.Record | ConvertTo-Json -Depth 6 | Out-File (Join-Path $winDir 'discovery.json') -Encoding UTF8
$h.Body | Out-File (Join-Path $winDir 'health.json') -Encoding UTF8
Write-Output ('BRIDGE-READY url=' + $rec.Record.url + ' pid=' + $rec.Record.pid + ' token-len=' + ([string]$rec.Record.token).Length)
Write-Output ('UEVERSION ' + $rec.Record.ueVersion + ' PLUGINVERSION ' + $rec.Record.pluginVersion)
Write-Output ('WINDOW-OPEN ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
