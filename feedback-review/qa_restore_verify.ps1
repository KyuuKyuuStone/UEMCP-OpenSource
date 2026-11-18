$ErrorActionPreference = 'Continue'
$repo = 'C:\UE5_P\5.4\UEMCP'
$log = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-prep-restore-verify-20261118.log'
$sb = New-Object System.Text.StringBuilder
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
[void]$sb.AppendLine('RUN d9fa8820 authorized-restore ue_p_text/ue54_text ' + $stamp + ' (supervisor authorization q1: write exemption limited to this restore only; scene preserved in qasmoke-prep-scene-preserve-20261118.log)')
$target = 'ue_p_text/ue54_text'
$disk = 'C:\UE5_P\5.4\UEMCP\ue_p_text\ue54_text'
[void]$sb.AppendLine('')
[void]$sb.AppendLine('PRE-CHECK: Test-Path ' + $disk + ' = ' + (Test-Path $disk))
[void]$sb.AppendLine('')
[void]$sb.AppendLine('COMMAND-R: git -C ' + $repo + ' checkout -- ' + $target)
git -C $repo checkout -- $target 2>&1 | ForEach-Object { [void]$sb.AppendLine('  OUT: ' + $_.ToString()) }
[void]$sb.AppendLine('EXIT-R=' + $LASTEXITCODE)
[void]$sb.AppendLine('')
[void]$sb.AppendLine('===== VERIFY =====')
$v1 = @(git -C $repo status --porcelain -- $target)
[void]$sb.AppendLine('V-1 git status --porcelain -- ' + $target + ' -> lines=' + $v1.Count + ' (expect 0) EXIT=' + $LASTEXITCODE)
foreach ($l in ($v1 | Select-Object -First 10)) { [void]$sb.AppendLine('  V1: ' + $l) }
$tree = @(git -C $repo ls-tree -r HEAD --name-only -- $target)
[void]$sb.AppendLine('V-2a git ls-tree -r HEAD count=' + $tree.Count + ' EXIT=' + $LASTEXITCODE)
$diskFiles = @(Get-ChildItem -LiteralPath $disk -Recurse -File -Force -ErrorAction SilentlyContinue)
[void]$sb.AppendLine('V-2b disk file count=' + $diskFiles.Count + ' (expect ' + $tree.Count + ')')
$d3 = @(git -C $repo diff --stat HEAD -- $target)
[void]$sb.AppendLine('V-3 git diff --stat HEAD -- ' + $target + ' -> lines=' + $d3.Count + ' (expect 0) EXIT=' + $LASTEXITCODE)
[void]$sb.AppendLine('V-4 Test-Path ' + $disk + ' = ' + (Test-Path $disk) + '  Test-Path uproject = ' + (Test-Path ($disk + '\ue54_text.uproject')))
$upRaw = Get-Content -Raw -LiteralPath ($disk + '\ue54_text.uproject')
$up = $null
try { $up = $upRaw | ConvertFrom-Json } catch { }
[void]$sb.AppendLine('V-5 uproject JSON parse=' + ($null -ne $up) + '  EngineAssociation=' + $up.EngineAssociation + '  Plugins=' + (($up.Plugins | ForEach-Object { $_.Name + ':' + $_.Enabled }) -join ','))
$blobRef = @($tree | Where-Object { $_ -match '\.uproject$' } | Select-Object -First 1)
$headUpro = @(git -C $repo show ("HEAD:" + $blobRef)) 
$norm1 = ($headUpro -join "`n") -replace "`r", ''
$norm2 = $upRaw -replace "`r", ''
[void]$sb.AppendLine('V-6 uproject worktree-vs-HEAD (LF-normalized string compare, blob=' + $blobRef + '): MATCH=' + ($norm1.TrimEnd() -eq $norm2.TrimEnd()))
$samples = @($tree | Where-Object { $_ -match '\.(ini|uproject)$' } | Select-Object -First 4)
foreach ($sp in $samples) {
  $diskPath = Join-Path $repo ($sp -replace '/', '\')
  $hb = @(git -C $repo show ("HEAD:" + $sp))
  $h1 = ($hb -join "`n") -replace "`r", ''
  if (Test-Path -LiteralPath $diskPath) {
    $h2raw = (Get-Content -Raw -LiteralPath $diskPath) -replace "`r", ''
    [void]$sb.AppendLine('V-7 sample MATCH=' + ($h1.TrimEnd() -eq $h2raw.TrimEnd()) + '  ' + $sp)
  } else { [void]$sb.AppendLine('V-7 sample MISSING ' + $sp) }
}
[void]$sb.AppendLine('')
[void]$sb.AppendLine('V-8 5.7-side tracked check: ls-tree HEAD ue_p_text non-ue54_text entries =')
$non54 = @($tree | Where-Object { $_ -notmatch '^ue_p_text/ue54_text/' })
$allTree = @(git -C $repo ls-tree -r HEAD --name-only -- ue_p_text)
$non54 = @($allTree | Where-Object { $_ -notmatch '^ue_p_text/ue54_text/' })
[void]$sb.AppendLine('  count=' + $non54.Count + ' (0 = HEAD tracks ONLY ue54_text under ue_p_text; 5.7 default project lives outside repo in Documents)')
$smoke = "$env:USERPROFILE\Documents\Unreal Projects\UEMCP_Smoke_Blank\UEMCP_Smoke_Blank.uproject"
$smokeParsed = $null
try { $smokeParsed = (Get-Content -Raw -LiteralPath $smoke) | ConvertFrom-Json } catch { }
[void]$sb.AppendLine('V-9 5.7 SmokeBlank uproject on disk: exists=' + (Test-Path -LiteralPath $smoke) + ' parse=' + ($null -ne $smokeParsed) + ' EngineAssociation=' + $smokeParsed.EngineAssociation)
$full2 = @(git -C $repo status --porcelain | Where-Object { $_.Length -ge 3 -and $_.Substring(0, 2) -match 'D' })
[void]$sb.AppendLine('V-10 POST-RESTORE full-repo deletion lines=' + $full2.Count + ' (expect 0)')
[void]$sb.AppendLine('')
[void]$sb.AppendLine('RESTORE-END deletionsAfter=' + $full2.Count + ' diskFiles=' + $diskFiles.Count + ' treeCount=' + $tree.Count + ' exitR=' + $(if ($LASTEXITCODE) { 'see-EXIT-R-line' } else { '0' }))
$sb.ToString() | Out-File $log -Encoding UTF8
Write-Output ('RESTORE LOG=' + $log)
Write-Output ('diskFiles=' + $diskFiles.Count + ' tree=' + $tree.Count + ' statusTargetLines=' + $v1.Count + ' delAfter=' + $full2.Count)
