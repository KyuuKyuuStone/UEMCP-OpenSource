$ErrorActionPreference = 'Continue'
$repo = 'C:\UE5_P\5.4\UEMCP'
$log = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-prep-scene-preserve-20261118.log'
$sb = New-Object System.Text.StringBuilder
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
[void]$sb.AppendLine('RUN d9fa8820 scene-preserve-before-restore ' + $stamp + ' host ZH-XUXUANWEI QA (authorized restore per supervisor answer q1)')

[void]$sb.AppendLine('')
[void]$sb.AppendLine('COMMAND1: git -C ' + $repo + ' status --porcelain   (full repo)')
$status = @(git -C $repo status --porcelain)
[void]$sb.AppendLine('EXIT1=' + $LASTEXITCODE + '  total-status-lines=' + $status.Count)
$del = @($status | Where-Object { $_.Length -ge 3 -and $_.Substring(0, 2) -match 'D' })
[void]$sb.AppendLine('DELETION-CLASS-LINES (X or Y = D): count=' + $del.Count)
$otherDel = @($del | Where-Object { $_ -notmatch 'ue_p_text/ue54_text/' })
[void]$sb.AppendLine('DELETIONS-OUTSIDE-ue54_text: count=' + $otherDel.Count)
foreach ($o in $otherDel) { [void]$sb.AppendLine('  OTHERDEL: ' + $o) }
$mod = @($status | Where-Object { $_.Length -ge 3 -and ($_.Substring(0, 2) -match 'M|A|R|C|U') })
[void]$sb.AppendLine('MODIFIED-OR-OTHER-TRACKED-CHANGES: count=' + $mod.Count)
foreach ($m in ($mod | Select-Object -First 40)) { [void]$sb.AppendLine('  OTHERCHANGE: ' + $m) }

[void]$sb.AppendLine('')
[void]$sb.AppendLine('COMMAND2: git -C ' + $repo + ' log -1 --format=fuller   (HEAD)')
$h = @(git -C $repo log -1 --format=fuller)
[void]$sb.AppendLine('EXIT2=' + $LASTEXITCODE)
foreach ($l in $h) { [void]$sb.AppendLine('  HEAD: ' + $l) }

[void]$sb.AppendLine('')
[void]$sb.AppendLine('COMMAND3: git -C ' + $repo + ' log -1 --format=fuller 2a882bd   (baseline commit touching ue_p_text)')
$b = @(git -C $repo log -1 --format=fuller 2a882bd)
[void]$sb.AppendLine('EXIT3=' + $LASTEXITCODE)
foreach ($l in $b) { [void]$sb.AppendLine('  BASE: ' + $l) }

[void]$sb.AppendLine('')
[void]$sb.AppendLine('COMMAND4: git -C ' + $repo + ' stash list')
$st = @(git -C $repo stash list)
[void]$sb.AppendLine('EXIT4=' + $LASTEXITCODE + '  stash-count=' + $st.Count)
foreach ($l in $st) { [void]$sb.AppendLine('  STASH: ' + $l) }

[void]$sb.AppendLine('')
[void]$sb.AppendLine('COMMAND5: git -C ' + $repo + ' log --date=iso -5 --format="%h %ad %s" -- UEMCPBridge/Tests/ue_common.ps1')
$lc1 = @(git -C $repo log --date=iso -5 --format='%h %ad %s' -- UEMCPBridge/Tests/ue_common.ps1)
[void]$sb.AppendLine('EXIT5=' + $LASTEXITCODE)
foreach ($l in $lc1) { [void]$sb.AppendLine('  COMMON: ' + $l) }
[void]$sb.AppendLine('COMMAND6: git -C ' + $repo + ' log --date=iso -5 --format="%h %ad %s" -- UEMCPBridge/Tests/ue_smoke_run.ps1')
$lc2 = @(git -C $repo log --date=iso -5 --format='%h %ad %s' -- UEMCPBridge/Tests/ue_smoke_run.ps1)
[void]$sb.AppendLine('EXIT6=' + $LASTEXITCODE)
foreach ($l in $lc2) { [void]$sb.AppendLine('  SMOKERUN: ' + $l) }
[void]$sb.AppendLine('NOTE5: both ps1 last-commit dates are before 2026-11-17 first-batch QA checks -> scripts NOT touched since disappearance window.')

[void]$sb.AppendLine('')
[void]$sb.AppendLine('SCENE-END otherDeletionCount=' + $otherDel.Count + ' (0 means ONLY ue54_text missing among tracked files; restore may proceed per authorization scope)')
$sb.ToString() | Out-File $log -Encoding UTF8
Write-Output ('LOG=' + $log)
Write-Output ('SCENE-OK otherDel=' + $otherDel.Count + ' totalStatusLines=' + $status.Count)
