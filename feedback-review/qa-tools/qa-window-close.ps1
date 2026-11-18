# QA exec window close: equivalent cleanup per smoke-script semantics (frozen functions via dot-source).
# Restores uproject from window dir backup bytes, removes plugin copy, stops editor, waits ports free, prunes stale discovery.
param([Parameter(Mandatory = $true)][string]$WindowDir)
$ErrorActionPreference = 'Continue'
$repo = 'C:\UE5_P\5.4\UEMCP'
. (Join-Path $repo 'UEMCPBridge\Tests\ue_common.ps1')
$win = Read-JsonFile -Path (Join-Path $WindowDir 'window.json')
$ProjectDir = $win.projectDir
$up = $win.uproject
$backup = $win.backup
$beforeSha = (Get-FileSha256 -Path $backup)

$procs = @(Get-Process -Name 'UnrealEditor' -ErrorAction SilentlyContinue)
foreach ($p in $procs) {
    $cl = ''
    try { $cl = [string]$p.MainModule.FileName } catch { }
    if ($cl -notmatch 'UE_5\.[47]') { continue }
    $stop = Stop-EditorProcess -Process $p -GracefulSeconds 90
    Write-Output ('EDITOR-STOPPED pid=' + $p.Id + ' forced=' + [bool]$stop.Forced)
    if ($stop.Forced) { [void](Remove-OrphanedDiscovery -ProjectDir $ProjectDir -EditorPid $p.Id) }
}
$portsFree = Wait-PortsFree -TimeoutSeconds 60
Write-Output ('PORTS-FREE ' + $portsFree)
Remove-InstalledPlugin -ProjectDir $ProjectDir
$plugGone = -not (Test-Path (Join-Path $ProjectDir 'Plugins\UEMCPBridge'))
Write-Output ('PLUGIN-REMOVED ' + $plugGone)

$baseBytes = [System.IO.File]::ReadAllBytes($backup)
[System.IO.File]::WriteAllBytes($up, $baseBytes)
$afterSha = (Get-FileSha256 -Path $up)
Write-Output ('UPROJECT-RESTORED ' + ($afterSha -eq $beforeSha) + ' sha=' + $afterSha)
$stale = Get-BridgeDiscoveryRecord -ProjectDir $ProjectDir
if ($null -ne $stale) {
    $okProc = $false
    try { Get-Process -Id ([int]$stale.Record.pid) -ErrorAction Stop | Out-Null; $okProc = $true } catch { }
    if (-not $okProc) {
        Remove-Item -LiteralPath $stale.Path -Force
        Write-Output ('STALE-DISCOVERY-REMOVED ' + $stale.Path)
    } else { Write-Output ('STALE-DISCOVERY-BUT-PID-ALIVE ' + $stale.Record.pid) }
}
$bj = Join-Path $env:USERPROFILE '.uemcp\bridge.json'
if (Test-Path $bj) {
    $rj = $null
    try { $rj = Read-JsonFile -Path $bj } catch { }
    if ($null -ne $rj) {
        $alive = $false
        try { Get-Process -Id ([int]$rj.pid) -ErrorAction Stop | Out-Null; $alive = $true } catch { }
        if (-not $alive) { Remove-Item -LiteralPath $bj -Force; Write-Output 'LATEST-POINTER-REMOVED stale bridge.json' }
    }
}
Write-Output ('WINDOW-CLOSED ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))

