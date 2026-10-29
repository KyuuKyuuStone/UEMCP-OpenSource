#Requires -Version 5.1
<#
.SYNOPSIS
    End-to-end real-editor smoke run for UEMCPBridge (UE 5.4 / 5.7).

.DESCRIPTION
    One run = preflight -> (create 5.7 blank project) -> install plugin copy ->
    launch UnrealEditor -> wait for bridge -> collect 8 RPC transcripts ->
    graceful shutdown -> restore project -> verify cleanup.

    Evidence is written to UEMCPBridge/Tests/smoke-runs/smoke-<engine>-<stamp>/.

    The repository sample project (ue_p_text/ue54_text) is always restored:
    the .uproject bytes are compared by SHA-256 before/after and the plugin copy
    is deleted, so the working tree is left untouched.

.PARAMETER EngineVersion
    5.4 or 5.7. Selects the editor binary and the default project.

.PARAMETER ProjectDir
    Target UE project directory. Defaults: 5.4 -> <repo>/ue_p_text/ue54_text,
    5.7 -> <%USERPROFILE%>/Documents/Unreal Projects/UEMCP_Smoke_Blank (created
    from the TP_BlankBP template on first run).

.PARAMETER PluginSource
    Plugin folder to install. Defaults to <repo>/UEMCPBridge.

.PARAMETER SkipLaunch
    Do everything except launching the editor (preflight, project creation,
    plugin install, .uproject edit), then clean up and exit 0. Combine with
    -KeepPrepared to leave the project ready for a manual launch.

.PARAMETER KeepPrepared
    With -SkipLaunch: do not clean up. The prepared project stays on disk.

.PARAMETER NoFocusAssist
    Disable the focus assist: do not bring the editor window to the foreground
    and do not retry viewport.capture once after a CAPTURE_TIMEOUT.  Useful for
    reproducing the background-throttling limitation (README "Known limitations").
    By default the harness focuses the editor and retries the capture once.

.PARAMETER TimeoutSeconds
    How long to wait for the bridge to answer /health (default 420).

.PARAMETER EngineRoot
    Override the engine install root (default C:\Program Files\Epic Games\UE_<ver>).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.4

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.7 -SkipLaunch

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.7 -NoFocusAssist
#>
[CmdletBinding()]
param(
    [ValidateSet('5.4', '5.7')]
    [string]$EngineVersion = '5.4',

    [string]$ProjectDir = '',

    [string]$PluginSource = '',

    [switch]$SkipLaunch,

    [switch]$KeepPrepared,

    [switch]$NoFocusAssist,

    [int]$TimeoutSeconds = 420,

    [string]$EngineRoot = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ue_common.ps1')

$runDir = New-RunDirectory -EngineVersion $EngineVersion -Kind 'smoke'
$startedAt = Get-Date
$repro = 'powershell -ExecutionPolicy Bypass -File "{0}" -EngineVersion {1}' -f $PSCommandPath, $EngineVersion
if ($ProjectDir) { $repro += ' -ProjectDir "{0}"' -f $ProjectDir }
if ($SkipLaunch) { $repro += ' -SkipLaunch' }
if ($NoFocusAssist) { $repro += ' -NoFocusAssist' }

if (-not $EngineRoot) { $EngineRoot = "C:\Program Files\Epic Games\UE_$EngineVersion" }
$editorExe = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$templateDir = Join-Path $EngineRoot 'Templates\TP_BlankBP'

if (-not $PluginSource) { $PluginSource = $script:PluginRoot }
$PluginSource = [System.IO.Path]::GetFullPath($PluginSource)

if (-not $ProjectDir) {
    if ($EngineVersion -eq '5.4') {
        $ProjectDir = Join-Path $script:RepoRoot 'ue_p_text\ue54_text'
    } else {
        $ProjectDir = Join-Path $env:USERPROFILE 'Documents\Unreal Projects\UEMCP_Smoke_Blank'
    }
}
$ProjectDir = [System.IO.Path]::GetFullPath($ProjectDir).TrimEnd('\')
$repoSampleDir = [System.IO.Path]::GetFullPath((Join-Path $script:RepoRoot 'ue_p_text\ue54_text')).TrimEnd('\')
$isRepoProject = ($ProjectDir -ieq $repoSampleDir)

$state = [ordered]@{
    engineVersion     = $EngineVersion
    engineRoot        = $EngineRoot
    editorExe         = $editorExe
    projectDir        = $ProjectDir
    projectCreated    = $false
    pluginSource      = $PluginSource
    pluginTarget      = ''
    isRepoProject     = $isRepoProject
    skipLaunch        = [bool]$SkipLaunch
    keepPrepared      = [bool]$KeepPrepared
    uprojectPath      = ''
    uprojectShaBefore = ''
    uprojectShaAfter  = ''
    bridgeUrl         = ''
    bridgePort        = 0
    bridgePid         = 0
    editorPid         = 0
    startedAt         = $startedAt.ToString('o')
    readyInSeconds    = $null
    focusAssist       = $null
    rpc               = @()
    cleanup           = $null
    ok                = $false
}

$editorProcess = $null
$uprojectBaselineBytes = $null
$prepared = $false
$dryRunCleanup = $false
$skipCleanup = $false
$step = 'preflight'
$failure = $null
$failureCode = 1

function Save-Failure {
    param([string]$Step, [string]$Message, [int]$Code)
    $payload = [ordered]@{
        ok      = $false
        step    = $Step
        message = $Message
        repro   = $repro
        runDir  = $runDir
        state   = $state
    }
    Write-JsonFile -Path (Join-Path $runDir 'failure.json') -Object $payload
    Write-Host ''
    Write-Host "FAILED at step '$Step': $Message" -ForegroundColor Red
    Write-Host "REPRO: $repro" -ForegroundColor Yellow
    Write-Host "EVIDENCE: $runDir" -ForegroundColor Yellow
}

try {
    # ---------------------------------------------------------------- preflight
    $step = 'preflight'
    Write-Step "preflight: engine $EngineVersion at $EngineRoot"
    if (-not (Test-Path -LiteralPath $editorExe)) {
        throw "UnrealEditor.exe not found: $editorExe"
    }
    if (-not (Test-Path -LiteralPath $PluginSource)) {
        throw "PluginSource not found: $PluginSource"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $PluginSource 'UEMCPBridge.uplugin'))) {
        throw "PluginSource is not a UEMCPBridge folder (UEMCPBridge.uplugin missing): $PluginSource"
    }

    Assert-NoEditorProcess
    Write-Step 'preflight: no UnrealEditor process'

    if ($ProjectDir -eq $repoSampleDir -and $EngineVersion -ne '5.4') {
        throw "The in-repo sample project is a UE 5.4 project; use it with -EngineVersion 5.4 only."
    }

    $projectExisted = Test-Path -LiteralPath $ProjectDir
    if (-not $projectExisted) {
        if ($EngineVersion -ne '5.7') {
            throw "Project not found: $ProjectDir"
        }
        if (-not (Test-Path -LiteralPath $templateDir)) {
            throw "Template not found: $templateDir"
        }
        Write-Step "preflight: creating UE 5.7 blank project from TP_BlankBP -> $ProjectDir"
        New-Item -ItemType Directory -Path $ProjectDir -Force | Out-Null
        Copy-Tree -Source $templateDir -Destination $ProjectDir
        $templateUproject = Join-Path $ProjectDir 'TP_BlankBP.uproject'
        if (-not (Test-Path -LiteralPath $templateUproject)) {
            throw "Template copy does not contain TP_BlankBP.uproject"
        }
        $newName = (Split-Path -Leaf $ProjectDir) + '.uproject'
        Rename-Item -LiteralPath $templateUproject -NewName $newName
        $state.projectCreated = $true
        Write-Step "preflight: project created ($newName)"
    }

    $uprojectPath = Get-UprojectPath -ProjectDir $ProjectDir
    if (-not $uprojectPath) { throw "No .uproject found in $ProjectDir" }
    $state.uprojectPath = $uprojectPath
    $null = Read-JsonFile -Path $uprojectPath   # parse check

    Assert-PortsFree
    Write-Step 'preflight: ports 18778-18788 are free'

    # The blank template ships EngineAssociation=""; pin it before we take the
    # baseline so a failed/aborted run still leaves a usable 5.7 project.
    if ($state.projectCreated) {
        $descriptor = Read-JsonFile -Path $uprojectPath
        $descriptor | Add-Member -NotePropertyName EngineAssociation -NotePropertyValue $EngineVersion -Force
        if ($null -eq $descriptor.Modules) {
            $descriptor | Add-Member -NotePropertyName Modules -NotePropertyValue @() -Force
        }
        Write-JsonFile -Path $uprojectPath -Object $descriptor
    }

    $uprojectBaselineBytes = [System.IO.File]::ReadAllBytes($uprojectPath)
    [System.IO.File]::WriteAllBytes((Join-Path $runDir 'uproject.before.json'), $uprojectBaselineBytes)
    $state.uprojectShaBefore = (Get-FileSha256 -Path $uprojectPath)
    Write-Step ("preflight: .uproject parsed, sha256={0}" -f $state.uprojectShaBefore.Substring(0, 12))

    # ---------------------------------------------------------------- prepare
    $step = 'prepare'
    Write-Step 'prepare: enabling UEMCPBridge / PythonScriptPlugin / EditorScriptingUtilities'
    Enable-UprojectPlugins -UprojectPath $uprojectPath -PluginNames @(
        'UEMCPBridge', 'PythonScriptPlugin', 'EditorScriptingUtilities'
    )

    $pluginTarget = Join-Path $ProjectDir 'Plugins\UEMCPBridge'
    if (Test-Path -LiteralPath $pluginTarget) {
        $backup = $pluginTarget + '.bak-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
        Move-Item -LiteralPath $pluginTarget -Destination $backup
        $state.pluginTargetBackup = $backup
        Write-Step "prepare: existing plugin copy backed up to $backup"
    }
    $state.pluginTarget = Install-PluginCopy -PluginSource $PluginSource -ProjectDir $ProjectDir
    $installedFiles = @(Get-ChildItem -LiteralPath $state.pluginTarget -Recurse -File).Count
    Write-Step "prepare: plugin installed ($installedFiles files) -> $($state.pluginTarget)"

    $plan = [ordered]@{
        engineVersion = $EngineVersion
        projectDir    = $ProjectDir
        uproject      = $uprojectPath
        pluginSource  = $PluginSource
        pluginTarget  = $state.pluginTarget
        launch        = ('"{0}" "{1}" -log -nop4 -nosplash' -f $editorExe, $uprojectPath)
        repro         = $repro
    }
    Write-JsonFile -Path (Join-Path $runDir 'plan.json') -Object $plan

    if ($SkipLaunch) {
        $step = 'cleanup'
        Write-Step 'skip-launch: preparing only, no editor started'
        if ($KeepPrepared) {
            $state.ok = $true
            $skipCleanup = $true
            Write-JsonFile -Path (Join-Path $runDir 'run.json') -Object $state
            Write-Host 'PREPARED (left in place). Launch with:' -ForegroundColor Green
            Write-Host ('  "{0}" "{1}" -log -nop4 -nosplash' -f $editorExe, $uprojectPath)
            exit 0
        }
        $dryRunCleanup = $true
        throw [System.OperationCanceledException]::new('__cleanup_only__')
    }

    # ----------------------------------------------------------------- launch
    $step = 'launch'
    Write-Step "launch: $editorExe"
    $arguments = '"{0}" -log -nop4 -nosplash' -f $uprojectPath
    $editorProcess = Start-Process -FilePath $editorExe -ArgumentList $arguments -PassThru
    $state.editorPid = $editorProcess.Id
    Write-Step "launch: editor pid=$($editorProcess.Id); waiting up to ${TimeoutSeconds}s for /health"

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $entry = $null
    $health = $null
    while ((Get-Date) -lt $deadline) {
        if ($editorProcess.HasExited) {
            break
        }
        $entry = Get-BridgeDiscoveryRecord -ProjectDir $ProjectDir
        if ($null -ne $entry) {
            $url = 'http://127.0.0.1:{0}' -f $entry.Record.port
            $health = Get-BridgeHealth -BaseUrl $url
            if ($null -ne $health -and $health.Status -eq 200) { break }
        }
        Start-Sleep -Seconds 2
    }

    if ($null -eq $entry -or $null -eq $health -or $health.Status -ne 200) {
        $logPath = Get-NewestEditorLog -ProjectDir $ProjectDir -ProjectName (Split-Path -Leaf $ProjectDir)
        $tail = @()
        if ($logPath) {
            $tail = @(Get-Content -LiteralPath $logPath -Tail 40 -ErrorAction SilentlyContinue)
            Write-Lines -Path (Join-Path $runDir 'editor-log-tail.txt') -Lines $tail
        }
        if ($editorProcess.HasExited) {
            throw ("Editor exited before the bridge became ready (exit code {0}). Log tail: {1}`n{2}" -f
                $editorProcess.ExitCode, $logPath, ($tail -join "`n"))
        }
        throw "Bridge did not answer /health within ${TimeoutSeconds}s. Log tail: $logPath`n$($tail -join "`n")"
    }

    $state.readyInSeconds = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
    $state.bridgeUrl = $url
    $state.bridgePort = [int]$entry.Record.port
    $state.bridgePid = [int]$entry.Record.pid
    $token = [string]$entry.Record.token
    if (-not $token) { throw 'Discovery record has no token' }
    Write-Step ("launch: bridge ready in {0}s at {1} (pid {2})" -f $state.readyInSeconds, $url, $state.bridgePid)

    # UE throttles ticks when the window is not foreground (measured ~3.1 fps),
    # which can starve viewport.capture.  Focus the editor and allow one retry
    # unless -NoFocusAssist was passed (ZIP-1).
    $focusAssist = [ordered]@{ enabled = (-not $NoFocusAssist); foreground = $null; captureRetries = 0 }
    if ($focusAssist.enabled) {
        $focusAssist.foreground = [bool](Set-EditorForeground -Process $editorProcess)
        Write-Step ("launch: focus assist foreground={0}" -f $focusAssist.foreground)
        Start-Sleep -Milliseconds 500
    } else {
        Write-Step 'launch: focus assist disabled (-NoFocusAssist)'
    }
    $state.focusAssist = $focusAssist

    # ---------------------------------------------------------------- collect
    $step = 'collect'
    [System.IO.File]::WriteAllText((Join-Path $runDir 'health.json'), $health.Body, $script:Utf8NoBom)
    Copy-Item -LiteralPath $entry.Path -Destination (Join-Path $runDir 'discovery.json') -Force

    $logPath = Get-NewestEditorLog -ProjectDir $ProjectDir -ProjectName (Split-Path -Leaf $ProjectDir)
    if ($logPath) {
        Write-Lines -Path (Join-Path $runDir 'editor-log-path.txt') -Lines @($logPath)
        $uemcpLines = @(Select-String -LiteralPath $logPath -Pattern '\[UEMCP\]' -ErrorAction SilentlyContinue |
            ForEach-Object { $_.Line.Trim() })
        Write-Lines -Path (Join-Path $runDir 'editor-log-uemcp.txt') -Lines $uemcpLines
        $started = @($uemcpLines | Where-Object { $_ -match 'bridge_started' })
        if ($started.Count -eq 0) {
            throw "Editor log has no '[UEMCP] bridge_started' line: $logPath"
        }
        Write-Step ("collect: editor log {0} contains bridge_started" -f (Split-Path -Leaf $logPath))
    } else {
        throw "No editor log found under $ProjectDir\Saved\Logs"
    }

    $rpcCases = @(
        @{ Slug = '01-bridge-ping'; Method = 'bridge.ping'; Params = @{} },
        @{ Slug = '02-bridge-capabilities'; Method = 'bridge.capabilities'; Params = @{} },
        @{ Slug = '03-editor-status'; Method = 'editor.status'; Params = @{
                sections = @('editor', 'level', 'selection', 'capabilities', 'policies') } },
        @{ Slug = '04-actor-query'; Method = 'actor.query'; Params = @{ limit = 5; fields = @('identity', 'transform') } },
        @{ Slug = '05-asset-search'; Method = 'asset.search'; Params = @{ path = '/Game'; limit = 5 } },
        @{ Slug = '06-level-get-current'; Method = 'level.control'; Params = @{ action = 'get_current' } },
        @{ Slug = '07-material-list'; Method = 'material.params'; Params = @{
                action = 'list'; materialPath = '/Engine/BasicShapes/BasicShapeMaterial' } },
        @{ Slug = '08-viewport-capture'; Method = 'viewport.capture'; Params = @{
                target = 'level_viewport'; width = 640; height = 360; format = 'png'
                returnMode = 'file'; timeoutMs = 20000 } }
    )

    $index = 0
    foreach ($case in $rpcCases) {
        $index++
        # One retry for viewport.capture only: a background-throttled editor can
        # miss the frame deadline once, and a second attempt usually succeeds.
        $maxAttempts = 1
        if ($focusAssist.enabled -and $case.Method -eq 'viewport.capture') { $maxAttempts = 2 }
        $attempt = 0
        do {
            $attempt++
            $response = Invoke-UemcpRpc -BaseUrl $url -Token $token -Method $case.Method `
                -Params $case.Params -TimeoutSeconds 90 -Id $index
            $record = [ordered]@{
                index      = $index
                method     = $case.Method
                request    = @{ jsonrpc = '2.0'; id = $index; method = $case.Method; params = $case.Params }
                httpStatus = $response.Status
                durationMs = $response.DurationMs
                response   = $response.Json
                ok         = $false
                error      = $null
            }

            $resultOk = ($null -ne $response.Json) -and ($response.Json.result.ok -eq $true) -and
                        ($null -eq $response.Json.error)
            if (-not $resultOk) {
                $reason = 'unexpected response'
                if ($null -ne $response.Json.error) {
                    $reason = '{0}: {1}' -f $response.Json.error.data.errorCode, $response.Json.error.message
                } elseif ($response.Status -ne 200) {
                    $reason = "HTTP $($response.Status)"
                }
                $record.error = $reason
            } else {
                $record.ok = $true
            }

            $captureTimeout = (-not $record.ok) -and ($null -ne $response.Json) -and
                              ($null -ne $response.Json.error) -and
                              ($response.Json.error.data.errorCode -eq 'CAPTURE_TIMEOUT')
            if ($attempt -lt $maxAttempts -and $captureTimeout) {
                $focusAssist.captureRetries++
                Write-Step ("collect: viewport.capture hit CAPTURE_TIMEOUT; retrying in 2s (attempt {0}/{1})" -f
                    $attempt, $maxAttempts)
                Start-Sleep -Seconds 2
                continue
            }
            break
        } while ($true)
        $record.attempt = $attempt

        if ($case.Method -eq 'viewport.capture' -and $record.ok) {
            $capturePath = [string]$response.Json.result.data.path
            if ($capturePath -and (Test-Path -LiteralPath $capturePath)) {
                $info = Get-Item -LiteralPath $capturePath
                $bytes = [System.IO.File]::ReadAllBytes($capturePath)
                $isPng = ($bytes.Length -ge 8) -and ($bytes[0] -eq 0x89) -and ($bytes[1] -eq 0x50) -and
                         ($bytes[2] -eq 0x4E) -and ($bytes[3] -eq 0x47)
                $record.capture = [ordered]@{
                    path = $capturePath; bytes = $info.Length; isPng = $isPng
                    format = [string]$response.Json.result.data.format
                }
                if (-not $isPng) {
                    $record.ok = $false
                    $record.error = 'capture output is not a PNG file'
                }
                if ($info.Length -lt 1024) {
                    $record.ok = $false
                    $record.error = "capture file is suspiciously small ($($info.Length) bytes)"
                }
                if ($isPng -and $info.Length -lt 20MB) {
                    Copy-Item -LiteralPath $capturePath -Destination (Join-Path $runDir 'viewport-capture.png') -Force
                }
            } else {
                $record.ok = $false
                $record.error = "capture file missing: $capturePath"
            }
        }

        Write-JsonFile -Path (Join-Path $runDir ("rpc-{0}.json" -f $case.Slug)) -Object $record
        $state.rpc += $record
        $statusText = if ($record.ok) { 'PASS' } else { "FAIL ($($record.error))" }
        Write-Step ("collect: {0} -> {1} [{2} ms]" -f $case.Method, $statusText, $response.DurationMs)
    }

    $failedRpc = @($state.rpc | Where-Object { -not $_.ok })
    if ($failedRpc.Count -gt 0) {
        throw ("{0} of {1} RPC calls failed: {2}" -f $failedRpc.Count, $state.rpc.Count,
            (($failedRpc | ForEach-Object { "$($_.method) -> $($_.error)" }) -join '; '))
    }

    $state.ok = $true
} catch {
    if ($_.Exception.Message -eq '__cleanup_only__') {
        # -SkipLaunch requested cleanup; not a failure.
    } else {
        $failure = $_.Exception.Message
        switch ($step) {
            'preflight' { $failureCode = 1 }
            'prepare'   { $failureCode = 1 }
            'launch'    { $failureCode = 2 }
            'collect'   { $failureCode = 3 }
            default     { $failureCode = 3 }
        }
    }
} finally {
    # ----------------------------------------------------------------- cleanup
    $cleanup = [ordered]@{
        editorStopped = $false
        forced        = $false
        portsFree     = $true
        pluginRemoved = $false
        uprojectShaAfter = ''
        uprojectRestored = $false
        orphanDiscoveryRemoved = $false
        errors        = @()
    }
    if ($skipCleanup) {
        Write-Host 'Cleanup skipped (-KeepPrepared).' -ForegroundColor Yellow
    } else {
    try {
        if ($null -ne $editorProcess) {
            $stop = Stop-EditorProcess -Process $editorProcess -GracefulSeconds 90
            $cleanup.editorStopped = $true
            $cleanup.forced = [bool]$stop.Forced
            if ($stop.Forced) {
                $cleanup.orphanDiscoveryRemoved = Remove-OrphanedDiscovery -ProjectDir $ProjectDir -EditorPid $editorProcess.Id
            }
        }
        if ($null -ne $editorProcess) {
            $cleanup.portsFree = Wait-PortsFree -TimeoutSeconds 60
            if (-not $cleanup.portsFree) {
                $cleanup.errors += 'ports 18778-18788 still busy after shutdown'
            }
        }

        $projectUproject = Get-UprojectPath -ProjectDir $ProjectDir
        if ($projectUproject -and $state.pluginTarget -and (Test-Path -LiteralPath $state.pluginTarget)) {
            Remove-InstalledPlugin -ProjectDir $ProjectDir
            $cleanup.pluginRemoved = -not (Test-Path -LiteralPath $state.pluginTarget)
            if ($state.Contains('pluginTargetBackup') -and (Test-Path -LiteralPath $state.pluginTargetBackup)) {
                Move-Item -LiteralPath $state.pluginTargetBackup -Destination $state.pluginTarget
                $cleanup.errors += 'restored pre-existing plugin copy from backup'
            }
        }

        if ($projectUproject -and $null -ne $uprojectBaselineBytes) {
            [System.IO.File]::WriteAllBytes($projectUproject, $uprojectBaselineBytes)
            $cleanup.uprojectShaAfter = Get-FileSha256 -Path $projectUproject
            $cleanup.uprojectRestored = ($cleanup.uprojectShaAfter -eq $state.uprojectShaBefore)
            if (-not $cleanup.uprojectRestored) {
                $cleanup.errors += '.uproject bytes differ from the baseline after restore'
            }
        }
    } catch {
        $cleanup.errors += $_.Exception.Message
    }
    }

    $state.cleanup = $cleanup
    $state.ok = [bool]$state.ok -and ($cleanup.errors.Count -eq 0)
    $state.finishedAt = (Get-Date).ToString('o')
    Write-JsonFile -Path (Join-Path $runDir 'cleanup.json') -Object $cleanup
    Write-JsonFile -Path (Join-Path $runDir 'run.json') -Object $state

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add(("UEMCP smoke run: engine {0}, project {1}" -f $EngineVersion, $ProjectDir))
    $lines.Add(("started {0}, finished {1}" -f $state.startedAt, $state.finishedAt))
    $lines.Add(("bridge: {0} (port {1}, pid {2}) ready in {3}s" -f $state.bridgeUrl, $state.bridgePort, $state.bridgePid, $state.readyInSeconds))
    foreach ($item in $state.rpc) {
        $lines.Add(("RPC {0,-26} {1} http={2} {3}ms" -f $item.method,
                $(if ($item.ok) { 'PASS' } else { 'FAIL' }), $item.httpStatus, $item.durationMs))
        if (-not $item.ok) { $lines.Add(("    error: " + $item.error)) }
    }
    $lines.Add(("cleanup: pluginRemoved={0} uprojectRestored={1} portsFree={2} forced={3}" -f
            $cleanup.pluginRemoved, $cleanup.uprojectRestored, $cleanup.portsFree, $cleanup.forced))
    foreach ($cleanupError in $cleanup.errors) { $lines.Add(("cleanup warning: " + $cleanupError)) }
    if ($failure) {
        $lines.Add(("RESULT: FAIL ({0})" -f $failure))
    } elseif ($SkipLaunch -and -not $KeepPrepared) {
        $lines.Add('RESULT: PASS (dry run, no editor launched)')
    } else {
        $lines.Add('RESULT: PASS')
    }
    Write-Lines -Path (Join-Path $runDir 'summary.txt') -Lines $lines.ToArray()

    if ($isRepoProject) {
        Write-Host ''
        Write-Host 'Repo sample project cleanup:' -ForegroundColor Green
        Write-Host ("  plugin copy removed : {0}" -f $cleanup.pluginRemoved)
        Write-Host ("  .uproject restored  : {0} (sha256 {1})" -f $cleanup.uprojectRestored,
            $cleanup.uprojectShaAfter.Substring(0, [Math]::Min(12, $cleanup.uprojectShaAfter.Length)))
        Write-Host ("  ports released      : {0}" -f $cleanup.portsFree)
    }
    Write-Host ("EVIDENCE: {0}" -f $runDir)
}

if ($failure) {
    Save-Failure -Step $step -Message $failure -Code $failureCode
    exit $failureCode
}

if ($dryRunCleanup) {
    if ($state.cleanup.errors.Count -gt 0) {
        Save-Failure -Step 'cleanup' -Message ("dry-run cleanup incomplete: {0}" -f ($state.cleanup.errors -join '; ')) -Code 4
        exit 4
    }
    Write-Host ("SMOKE_RESULT PASS (dry run: prepared then cleaned, no editor launched) {0}" -f $runDir) -ForegroundColor Green
    exit 0
}

if ((-not $state.ok) -or ($state.cleanup.errors.Count -gt 0)) {
    $cleanupProblem = ($state.cleanup.errors -join '; ')
    if (-not $cleanupProblem) { $cleanupProblem = 'run did not reach PASS state' }
    Save-Failure -Step 'cleanup' -Message ("cleanup incomplete: {0}" -f $cleanupProblem) -Code 4
    exit 4
}

Write-Host ("SMOKE_RESULT PASS ({0})" -f $runDir) -ForegroundColor Green
exit 0
