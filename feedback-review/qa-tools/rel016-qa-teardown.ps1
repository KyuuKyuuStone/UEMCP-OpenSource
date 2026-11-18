# rel016-qa-teardown.ps1 — 受控拆除 -KeepPrepared 留下的已备窗口（复刻 ue_smoke_run.ps1 cleanup 语义，不修改任何既有脚本）
# 用法: pwsh -File rel016-qa-teardown.ps1 -RunDir <smoke run 目录>
param([Parameter(Mandatory)][string]$RunDir)
$ErrorActionPreference = 'Stop'
Write-Output ("rel016-qa teardown START: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
Write-Output ("RUNDIR: $RunDir")
$state = Get-Content (Join-Path $RunDir 'run.json') -Raw | ConvertFrom-Json
$uprojectPath = $state.uprojectPath
$projectDir   = $state.projectDir
$pluginTarget = $state.pluginTarget
$editorPid    = [int]$state.editorPid
Write-Output ("state: pid=$editorPid pluginTarget=$pluginTarget uproject=$uprojectPath shaBefore=$($state.uprojectShaBefore)")

# 1) graceful stop editor (复刻 Stop-EditorProcess: CloseMainWindow -> wait -> kill)
$proc = $null
if ($editorPid -gt 0) { $proc = Get-Process -Id $editorPid -ErrorAction SilentlyContinue }
$stopped = $false; $forced = $false
if ($null -ne $proc) {
    $null = $proc.CloseMainWindow()
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline -and -not $proc.HasExited) { Start-Sleep -Seconds 2 }
    if (-not $proc.HasExited) { $proc.Refresh(); }
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force; $forced = $true; $proc.WaitForExit(30000) | Out-Null }
    $stopped = $proc.HasExited
} else { $stopped = $true }
Write-Output ("editor stopped=$stopped forced=$forced")

# 2) ports free (复刻 Wait-PortsFree)
$deadline = (Get-Date).AddSeconds(60)
$portsFree = $false
while ((Get-Date) -lt $deadline) {
    $busy = @(18778..18788 | Where-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue })
    if ($busy.Count -eq 0) { $portsFree = $true; break }
    Start-Sleep -Seconds 2
}
Write-Output "ports 18778-18788 free=$portsFree"

# 3) remove installed plugin copy; restore pre-existing backup if recorded (复刻 cleanup 行 498-505)
$pluginRemoved = $null
if ((Test-Path $uprojectPath) -and $pluginTarget -and (Test-Path $pluginTarget)) {
    Remove-Item -LiteralPath $pluginTarget -Recurse -Force
    $pluginRemoved = -not (Test-Path $pluginTarget)
    if ($state.pluginTargetBackup -and (Test-Path $state.pluginTargetBackup)) {
        Move-Item -LiteralPath $state.pluginTargetBackup -Destination $pluginTarget
        Write-Output ("restored pre-existing plugin backup -> $pluginTarget")
        $pluginRemoved = $false
    }
} else { $pluginRemoved = -not ($pluginTarget -and (Test-Path $pluginTarget)) }
Write-Output "pluginRemoved=$pluginRemoved"

# 4) restore uproject bytes from runDir/uproject.before.json; verify sha (复刻 cleanup 行 507-514)
$shaAfter = ''
$restored = $false
if (Test-Path $uprojectPath) {
    $bytes = [System.IO.File]::ReadAllBytes((Join-Path $RunDir 'uproject.before.json'))
    [System.IO.File]::WriteAllBytes($uprojectPath, $bytes)
    $shaAfter = (Get-FileHash -Path $uprojectPath -Algorithm SHA256).Hash
    $restored = ($shaAfter -eq $state.uprojectShaBefore)
}
Write-Output ("uprojectShaAfter=$shaAfter uprojectRestored=$restored")

# 5) residual checks
$leftProcs = @(Get-Process UnrealEditor -ErrorAction SilentlyContinue).Count
$leftPlugin = Test-Path (Join-Path $projectDir 'Plugins\UEMCPBridge')
$ok = $stopped -and $portsFree -and $restored -and ($leftProcs -eq 0) -and (-not $leftPlugin)
Write-Output ("residual: editorProcs=$leftProcs pluginDirPresent=$leftPlugin")
Write-Output ("TEARDOWN_RESULT " + $(if ($ok) { 'PASS' } else { 'FAIL' }))
Write-Output ("rel016-qa teardown END: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
if (-not $ok) { exit 5 } else { exit 0 }
