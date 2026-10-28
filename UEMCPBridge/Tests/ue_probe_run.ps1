#Requires -Version 5.1
<#
.SYNOPSIS
    Run Tests/probe_ue57.py against UE 5.4 and/or UE 5.7 and build a 5.4-vs-5.7
    per-API comparison report.

.DESCRIPTION
    Each engine is run with UnrealEditor-Cmd.exe -run=pythonscript (no GUI, one
    instance at a time).  Reports are collected under
    UEMCPBridge/Tests/smoke-runs/probe-<stamp>/ together with the raw commandlet
    logs and a compare.md table.

    The probe itself is read-only (no --live-actors / --capture / --console),
    so no editor state is created beyond the project's Saved directory.

.PARAMETER EngineVersion
    both (default), 5.4 or 5.7.

.PARAMETER ProjectDir54 / ProjectDir57
    Project to run the probe in. Defaults: the in-repo ue54_text sample and
    <%USERPROFILE%>/Documents/Unreal Projects/UEMCP_Smoke_Blank (created from
    the TP_BlankBP template when missing).

.PARAMETER TimeoutSeconds
    Per-engine commandlet timeout (default 900).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_probe_run.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_probe_run.ps1 -EngineVersion 5.7
#>
[CmdletBinding()]
param(
    [ValidateSet('5.4', '5.7', 'both')]
    [string]$EngineVersion = 'both',

    [string]$ProjectDir54 = '',
    [string]$ProjectDir57 = '',

    [int]$TimeoutSeconds = 900,

    [string]$EngineRoot54 = 'C:\Program Files\Epic Games\UE_5.4',
    [string]$EngineRoot57 = 'C:\Program Files\Epic Games\UE_5.7'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ue_common.ps1')

$runDir = New-RunDirectory -EngineVersion $EngineVersion -Kind 'probe'
$probeScript = Join-Path $script:TestsDir 'probe_ue57.py'
if (-not (Test-Path -LiteralPath $probeScript)) { throw "probe script not found: $probeScript" }

if (-not $ProjectDir54) {
    $ProjectDir54 = Join-Path $script:RepoRoot 'ue_p_text\ue54_text'
}
if (-not $ProjectDir57) {
    $ProjectDir57 = Join-Path $env:USERPROFILE 'Documents\Unreal Projects\UEMCP_Smoke_Blank'
}

$engines = @()
if ($EngineVersion -eq 'both') { $engines = @('5.4', '5.7') } else { $engines = @($EngineVersion) }

function Resolve-EngineInputs {
    param([string]$Version)
    if ($Version -eq '5.4') {
        return [pscustomobject]@{
            Version = '5.4'; Root = $EngineRoot54
            Project = [System.IO.Path]::GetFullPath($ProjectDir54).TrimEnd('\')
        }
    }
    return [pscustomobject]@{
        Version = '5.7'; Root = $EngineRoot57
        Project = [System.IO.Path]::GetFullPath($ProjectDir57).TrimEnd('\')
    }
}

function Ensure-ProbeProject {
    param($Inputs)
    $projectDir = $Inputs.Project
    if (Test-Path -LiteralPath $projectDir) {
        if (-not (Get-UprojectPath -ProjectDir $projectDir)) {
            throw "Project directory exists but has no .uproject: $projectDir"
        }
        return
    }
    if ($Inputs.Version -ne '5.7') {
        throw "UE 5.4 sample project not found: $projectDir"
    }
    $template = Join-Path $Inputs.Root 'Templates\TP_BlankBP'
    if (-not (Test-Path -LiteralPath $template)) {
        throw "TP_BlankBP template not found: $template"
    }
    New-Item -ItemType Directory -Path $projectDir -Force | Out-Null
    Copy-Tree -Source $template -Destination $projectDir
    $templateUproject = Join-Path $projectDir 'TP_BlankBP.uproject'
    $newName = (Split-Path -Leaf $projectDir) + '.uproject'
    Rename-Item -LiteralPath $templateUproject -NewName $newName
    $uproject = Join-Path $projectDir $newName
    $descriptor = Read-JsonFile -Path $uproject
    $descriptor | Add-Member -NotePropertyName EngineAssociation -NotePropertyValue '5.7' -Force
    if ($null -eq $descriptor.Modules) {
        $descriptor | Add-Member -NotePropertyName Modules -NotePropertyValue @() -Force
    }
    Write-JsonFile -Path $uproject -Object $descriptor
    Write-Step "probe: created UE 5.7 blank project at $projectDir"
}

function Invoke-ProbeForEngine {
    param($Inputs)
    $result = [ordered]@{
        version     = $Inputs.Version
        engineRoot  = $Inputs.Root
        project     = $Inputs.Project
        exitCode    = $null
        timedOut    = $false
        reportPath  = ''
        reportFound = $false
        requiredFailed = 0
        checksTotal = 0
        engine      = $null
        error       = $null
    }

    $editorCmd = Join-Path $Inputs.Root 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
    if (-not (Test-Path -LiteralPath $editorCmd)) {
        $result.error = "UnrealEditor-Cmd.exe not found: $editorCmd"
        return $result
    }

    Ensure-ProbeProject -Inputs $Inputs
    $uproject = Get-UprojectPath -ProjectDir $Inputs.Project
    if (-not $uproject) { throw "No .uproject in $($Inputs.Project)" }

    $outPath = Join-Path $runDir ("probe-{0}.json" -f $Inputs.Version)
    $stdoutPath = Join-Path $runDir ("probe-{0}.stdout.log" -f $Inputs.Version)
    $stderrPath = Join-Path $runDir ("probe-{0}.stderr.log" -f $Inputs.Version)
    $cmdLine = '"{0}" -run=pythonscript "-script={1}" -unattended -nop4 -nosplash -nullrhi "--out={2}"' -f
        $uproject, $probeScript, $outPath

    Write-Step ("probe {0}: {1}" -f $Inputs.Version, $cmdLine)
    Assert-NoEditorProcess
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    # System.Diagnostics.Process (not Start-Process) so ExitCode is reliable and
    # the redirected pipes are drained asynchronously (no deadlock on long logs).
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $editorCmd
    $startInfo.Arguments = $cmdLine
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $process.Start() | Out-Null
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while (-not $process.HasExited -and (Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
    }
    if (-not $process.HasExited) {
        $result.timedOut = $true
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    $process.WaitForExit()
    $stopwatch.Stop()
    try { $result.exitCode = $process.ExitCode } catch { }
    try {
        [System.IO.File]::WriteAllText($stdoutPath, $stdoutTask.GetAwaiter().GetResult(), $script:Utf8NoBom)
        [System.IO.File]::WriteAllText($stderrPath, $stderrTask.GetAwaiter().GetResult(), $script:Utf8NoBom)
    } catch { }
    $process.Dispose()
    Write-Step ("probe {0}: finished in {1}s exit={2}" -f $Inputs.Version,
        [math]::Round($stopwatch.Elapsed.TotalSeconds, 1), $result.exitCode)

    if (-not (Test-Path -LiteralPath $outPath)) {
        # Fallback: probe defaults to <Project>/Saved/UEMCP/probe_ue57.json
        $fallback = Join-Path $Inputs.Project 'Saved\UEMCP\probe_ue57.json'
        if (Test-Path -LiteralPath $fallback) {
            Copy-Item -LiteralPath $fallback -Destination $outPath -Force
            Write-Step "probe: used default report location $fallback"
        }
    }

    if (Test-Path -LiteralPath $outPath) {
        $result.reportFound = $true
        $result.reportPath = $outPath
        try {
            $report = Read-JsonFile -Path $outPath
            $result.engine = $report.engine
            $checks = @($report.checks)
            $result.checksTotal = $checks.Count
            $result.requiredFailed = @($checks | Where-Object { $_.required -and -not $_.ok }).Count
        } catch {
            $result.error = "cannot parse probe report: $($_.Exception.Message)"
        }
    } else {
        $result.error = "probe report not produced (exit=$($result.exitCode), timeout=$($result.timedOut))"
    }
    return $result
}

function Format-ProbeValue {
    param($Entry)
    if ($null -eq $Entry) { return '(missing)' }
    if (-not $Entry.ok) { return 'FAIL: ' + [string]$Entry.error }
    $value = $Entry.value
    if ($null -eq $value) { return 'ok' }
    if ($value -is [string] -or $value -is [bool] -or $value -is [int] -or $value -is [double]) {
        return ('ok: ' + [string]$value)
    }
    try {
        $text = $value | ConvertTo-Json -Compress -Depth 4
    } catch {
        $text = [string]$value
    }
    if ($text.Length -gt 140) { $text = $text.Substring(0, 137) + '...' }
    return ('ok: ' + ($text -replace '\|', '\|'))
}

$results = @()
foreach ($engine in $engines) {
    try {
        $inputs = Resolve-EngineInputs -Version $engine
        $results += Invoke-ProbeForEngine -Inputs $inputs
    } catch {
        $results += [pscustomobject]@{
            version = $engine; engineRoot = ''; project = ''; exitCode = $null
            timedOut = $false; reportPath = ''; reportFound = $false
            requiredFailed = 0; checksTotal = 0; engine = $null
            error = $_.Exception.Message
        }
    }
}

foreach ($item in $results) {
    Write-JsonFile -Path (Join-Path $runDir ("result-{0}.json" -f $item.version)) -Object $item
}

# --- comparison table -------------------------------------------------------
$reports = @{}
foreach ($item in $results) {
    if ($item.reportFound) {
        $reports[$item.version] = Read-JsonFile -Path $item.reportPath
    }
}

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# UE 5.4 vs 5.7 probe comparison')
$lines.Add('')
$lines.Add(('- generated: {0}' -f (Get-Date).ToString('o')))
$lines.Add(('- probe: `Tests/probe_ue57.py` (read-only; no --live-actors/--capture/--console)'))
$lines.Add(('- evidence: `{0}`' -f $runDir))
$lines.Add('')
$lines.Add('| engine | engine version | python | report | required failures | exit |')
$lines.Add('| --- | --- | --- | --- | --- | --- |')
foreach ($item in $results) {
    $engineInfo = $item.engine
    $versionText = if ($engineInfo) { [string]$engineInfo.version } else { '(none)' }
    $pythonText = if ($reports.ContainsKey($item.version)) { [string]$reports[$item.version].python } else { '(none)' }
    $pythonText = ($pythonText -split ' ')[0]
    $lines.Add(('| {0} | {1} | {2} | {3} | {4} | {5} |' -f $item.version, $versionText, $pythonText,
            $(if ($item.reportFound) { 'yes' } else { 'NO' }), $item.requiredFailed, $item.exitCode))
}
$lines.Add('')

$checkNames = New-Object System.Collections.Generic.List[string]
foreach ($item in $results) {
    if (-not $reports.ContainsKey($item.version)) { continue }
    foreach ($check in $reports[$item.version].checks) {
        if (-not $checkNames.Contains([string]$check.name)) { $checkNames.Add([string]$check.name) }
    }
}

$lines.Add('| check | 5.4 | 5.7 |')
$lines.Add('| --- | --- | --- |')
foreach ($name in $checkNames) {
    $cells = @()
    foreach ($version in @('5.4', '5.7')) {
        if (-not $reports.ContainsKey($version)) {
            $cells += '(not run)'
            continue
        }
        $entry = $reports[$version].checks | Where-Object { $_.name -eq $name } | Select-Object -First 1
        $cells += (Format-ProbeValue -Entry $entry)
    }
    $lines.Add(('| `{0}` | {1} | {2} |' -f $name, $cells[0], $cells[1]))
}
$lines.Add('')

$failLines = @()
foreach ($item in $results) {
    if ($item.error) { $failLines += ("{0}: {1}" -f $item.version, $item.error) }
    if ($item.reportFound -and $item.requiredFailed -gt 0) {
        $failed = @($reports[$item.version].checks | Where-Object { $_.required -and -not $_.ok } |
            ForEach-Object { "$($_.name) ($($_.error))" })
        $failLines += ("{0}: required checks failed -> {1}" -f $item.version, ($failed -join '; '))
    }
}

if ($failLines.Count -eq 0) {
    $lines.Add('RESULT: PASS - every required probe check passed on: ' + (($results | ForEach-Object { $_.version }) -join ', '))
} else {
    $lines.Add('RESULT: FAIL')
    foreach ($line in $failLines) { $lines.Add('- ' + $line) }
}
$lines.Add('')
$lines.Add('Notes:')
$lines.Add('- `editor` is the value of `unreal.is_editor()`; commandlet runs report `true` on both engines.')
$lines.Add('- `projectDir` may be relative under `-run=pythonscript`; the bridge abspaths it before hashing discovery files.')
$lines.Add('- `worldPartitionProperty` is expected to be "unavailable (Exception)" on both versions: `UWorld::world_partition` is not a UPROPERTY (see README, Known limitations).')

Write-Lines -Path (Join-Path $runDir 'compare.md') -Lines $lines.ToArray()
Write-Lines -Path (Join-Path $runDir 'summary.txt') -Lines $lines.ToArray()
$lines | ForEach-Object { Write-Host $_ }

$failed = @($results | Where-Object { (-not $_.reportFound) -or ($_.requiredFailed -gt 0) -or $_.timedOut -or $_.error })
Write-Host ("EVIDENCE: {0}" -f $runDir)
if ($failed.Count -gt 0) {
    Write-Host ("PROBE_RESULT FAIL: {0} engine(s) incomplete" -f $failed.Count) -ForegroundColor Red
    exit 1
}
Write-Host 'PROBE_RESULT PASS' -ForegroundColor Green
exit 0
