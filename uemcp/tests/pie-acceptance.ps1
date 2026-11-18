#Requires -Version 5.1
<#
.SYNOPSIS
    PIE tool acceptance cases (prepared in advance; run after the PIE tool ships).

.DESCRIPTION
    Validates the planned PIE lifecycle RPCs against a REAL editor + bridge:
        status (not running) -> start -> status (running, world non-empty)
        -> restart -> stop -> status (not running)
    Plus two negative cases:
        - start with bridge allowWrite=false -> PERMISSION_DENIED gate=bridge.allowWrite
        - invalid action value -> INVALID_ARGUMENT
    Assumes the PIE tool exposes one RPC method (default "pie.control") with
    {action: "status"|"start"|"restart"|"stop"} params.  If the shipped method
    name differs, pass -PieMethod.

.NOTES
    Lifecycle assumes the editor was launched with the bridge plugin enabled
    (harness -SkipLaunch -KeepPrepared or equivalent).  This script does NOT
    launch the editor; point -ProjectDir at a prepared project.
    Expected pre-ship result: every case fails with -32601 METHOD_NOT_FOUND.
#>
param(
    [Parameter(Mandatory = $true)] [string]$ProjectDir,
    [string]$PieMethod = 'pie.control',
    [string]$EvidenceDir = '',
    [int]$TimeoutSeconds = 180,
    [switch]$SkipEditorCheck
)
$ErrorActionPreference = 'Stop'
$repo = 'C:\UE5_P\5.4\UEMCP-OpenSource'
. (Join-Path $repo 'UEMCPBridge\Tests\ue_common.ps1')

$projectDir = (Get-Item $ProjectDir).FullName
if (-not $EvidenceDir) {
    $EvidenceDir = Join-Path $repo ("UEMCPBridge\Tests\smoke-runs\pie-acceptance-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
if (-not $SkipEditorCheck) {
    # Only assert when this script is expected to manage the editor lifecycle.
    # With -SkipEditorCheck the caller launches/manages the editor externally
    # (the attached bridge legitimately holds 18778-18788).
    Assert-NoEditorProcess
    Assert-PortsFree
}

# attach to the running bridge (editor must already be up with the plugin)
$session = $null
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    $entry = Get-BridgeDiscoveryRecord -ProjectDir $projectDir
    if ($entry) {
        $h = Get-BridgeHealth -BaseUrl ('http://127.0.0.1:{0}' -f $entry.Record.port)
        if ($h -and $h.Status -eq 200) { $session = $entry; break }
    }
    Start-Sleep -Seconds 2
}
if (-not $session) { throw "bridge not ready for $projectDir" }
$url = 'http://127.0.0.1:{0}' -f $session.Record.port
$token = [string]$session.Record.token
Write-Host ("attached: {0}" -f $url)

$script:id = 0
$cases = New-Object System.Collections.Generic.List[object]
function Invoke-PieCase {
    param([string]$Name, [object]$Params, [scriptblock]$Expect, [string]$Note = '')
    $script:id++
    $r = Invoke-UemcpRpc -BaseUrl $url -Token $token -Method $PieMethod -Params $Params -TimeoutSeconds 60 -Id $script:id
    $errCode = $null; $gate = $null
    $sc = $null
    if ($r.Json.error) {
        $errCode = $r.Json.error.data.errorCode
    } elseif ($r.Json.result -ne $null -and $r.Json.result.isError -eq $true) {
        $sc = $r.Json.result.structuredContent
        if ($sc -ne $null -and $sc.error -ne $null) {
            $errCode = $sc.error.code
            if ($sc.error.details -ne $null) { $gate = $sc.error.details.gate }
        }
    }
    $ok = & $Expect $r
    $cases.Add([ordered]@{
        name = $Name; request = $Params; httpStatus = $r.Status; durationMs = $r.DurationMs
        errorCode = $errCode; gate = $gate; expectation = $Note; pass = [bool]$ok; response = $r.Json
    })
    Write-Host ("[{0}] {1} -> {2}" -f (Get-Date -Format 'HH:mm:ss'), $Name, $(if ($ok) { 'PASS' } else { 'FAIL' }))
}

$okOk = { param($r) ($r.Status -eq 200) -and ($r.Json.result.ok -eq $true) }
$okDenied = { param($r) ($r.Status -eq 200 -or $r.Status -eq 403) -and ($r.Json.result.structuredContent.error.code -eq 'PERMISSION_DENIED') -and ($r.Json.result.structuredContent.error.details.gate -eq 'bridge.allowWrite') }
$okInvalid = { param($r) ($r.Json.result.isError -eq $true) -and ($r.Json.result.structuredContent.error.code -eq 'INVALID_ARGUMENT') }
$okMethodMissing = { param($r) ($r.Json.error.code -eq -32601) }

# ---- positive lifecycle ----
Invoke-PieCase -Name '01-status-before-start' -Params @{ action = 'status' } -Expect $okOk -Note 'ok=true, data.world empty/none'
Invoke-PieCase -Name '02-start' -Params @{ action = 'start' } -Expect $okOk -Note 'ok=true, PIE session begins'
Invoke-PieCase -Name '03-status-running' -Params @{ action = 'status' } -Expect $okOk -Note 'ok=true, world non-empty (isPieRunning=true)'
Invoke-PieCase -Name '04-restart' -Params @{ action = 'restart' } -Expect $okOk -Note 'ok=true'
Invoke-PieCase -Name '05-status-after-restart' -Params @{ action = 'status' } -Expect $okOk -Note 'ok=true, world non-empty'
Invoke-PieCase -Name '06-stop' -Params @{ action = 'stop' } -Expect $okOk -Note 'ok=true'
Invoke-PieCase -Name '07-status-after-stop' -Params @{ action = 'status' } -Expect $okOk -Note 'ok=true, world empty/none'

# ---- negative: write gate (requires bridge-settings allowWrite=false BEFORE the editor starts) ----
Invoke-PieCase -Name '08-start-denied-when-allowWrite-false' -Params @{ action = 'start' } -Expect $okDenied -Note 'PERMISSION_DENIED gate=bridge.allowWrite'
Invoke-PieCase -Name '09-invalid-action' -Params @{ action = 'explode' } -Expect $okInvalid -Note 'INVALID_ARGUMENT'

Write-JsonFile -Path (Join-Path $EvidenceDir 'pie-cases.json') -Object $cases
$pass = @($cases | Where-Object { $_.pass }).Count
Write-Host ("PIE_ACCEPTANCE_RESULT {0}/{1} passed (pre-ship runs expect 0/{1} with -32601 METHOD_NOT_FOUND)" -f $pass, $cases.Count)
Write-Host ("EVIDENCE: {0}" -f $EvidenceDir)
