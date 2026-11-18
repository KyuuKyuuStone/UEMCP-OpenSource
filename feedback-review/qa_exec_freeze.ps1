$ErrorActionPreference = 'Continue'
$repo = 'C:\UE5_P\5.4\UEMCP'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$log = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-00-freeze-verify-20261118.log'
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('RUN cc433d95 freeze-verify-before-execution ' + $stamp + ' host ZH-XUXUANWEI QA')
[void]$sb.AppendLine('BASLINES: bridgefix2-hash-after.txt (61) + tsfix2-hash-after.txt (63); HEAD recorded in both = bacbe1c')

foreach ($list in @('bridgefix2-hash-after.txt', 'tsfix2-hash-after.txt')) {
  $p = Join-Path $repo ('feedback-review\logs\' + $list)
  [void]$sb.AppendLine('')
  [void]$sb.AppendLine('===== ' + $list + ' =====')
  $entries = @(Get-Content -LiteralPath $p | Where-Object { $_ -match '^[0-9A-Fa-f]{64}\s' })
  [void]$sb.AppendLine('parsed-entries=' + $entries.Count)
  $same = 0; $changed = 0; $missing = 0
  foreach ($e in $entries) {
    $parts = $e -split '\s+', 2
    $want = $parts[0].ToUpper()
    $rel = $parts[1].Trim()
    $fp = Join-Path $repo $rel
    if (-not (Test-Path -LiteralPath $fp)) {
      $missing++
      [void]$sb.AppendLine('MISSING: ' + $rel)
      continue
    }
    $got = (Get-FileHash -LiteralPath $fp -Algorithm SHA256).Hash.ToUpper()
    if ($got -eq $want) { $same++ }
    else { $changed++; [void]$sb.AppendLine('CHANGED: ' + $rel + ' expected=' + $want + ' actual=' + $got) }
  }
  [void]$sb.AppendLine('SUMMARY ' + $list + ' files=' + $entries.Count + ' same=' + $same + ' changed=' + $changed + ' missing=' + $missing + ' diff=' + ($changed + $missing))
}

[void]$sb.AppendLine('')
[void]$sb.AppendLine('===== git state at freeze-verify (informational, freeze allows pending dev edits) =====')
$head = @(git -C $repo log -1 --format='%h %ad %s' --date=iso)
[void]$sb.AppendLine('HEAD: ' + ($head -join ' '))
$status = @(git -C $repo status --porcelain)
$del = @($status | Where-Object { $_.Length -ge 3 -and $_.Substring(0, 2) -match 'D' })
[void]$sb.AppendLine('status-lines=' + $status.Count + ' deletion-lines=' + $del.Count)
$modified = @($status | Where-Object { $_.Length -ge 3 -and $_.Substring(0, 2) -notmatch '\?\?' })
[void]$sb.AppendLine('tracked-changed-lines=' + $modified.Count)
foreach ($m in $modified) { [void]$sb.AppendLine('  CHG: ' + $m) }

[void]$sb.AppendLine('')
[void]$sb.AppendLine('===== execution-day preflight P-3/P-4/desktop =====')
$procs = @(Get-Process -Name 'UnrealEditor', 'UE4Editor' -ErrorAction SilentlyContinue)
[void]$sb.AppendLine('P-3 editor-processes count=' + $procs.Count)
$freePorts = @()
$busyPorts = @()
foreach ($port in 18778..18788) {
  $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $port)
  try { $l.Start(); $freePorts += $port } catch { $busyPorts += $port } finally { try { $l.Stop() } catch { } }
}
[void]$sb.AppendLine('P-4 ports free=[' + ($freePorts -join ',') + '] busy=[' + ($busyPorts -join ',') + ']')
$expl = @(Get-Process -Name 'explorer' -ErrorAction SilentlyContinue)
[void]$sb.AppendLine('desktop-session: explorer-processes=' + $expl.Count)
$q = @(query user 2>&1)
[void]$sb.AppendLine('query-user: ' + ($q -join ' | '))
$bcount = @(Get-ChildItem "$env:USERPROFILE\.uemcp\bridges" -Filter *.json -ErrorAction SilentlyContinue).Count
[void]$sb.AppendLine('bridges-dir-json count=' + $bcount)
$bj = "$env:USERPROFILE\.uemcp\bridge.json"
[void]$sb.AppendLine('bridge.json exists=' + (Test-Path $bj))

[void]$sb.AppendLine('')
$gv = @(git -C $repo log --format='%h' -1)
$verFiles = @{}
[void]$sb.AppendLine('===== version 0.1.5 sanity (no edit, read-only) =====')
$up = Get-Content -LiteralPath (Join-Path $repo 'UEMCPBridge\UEMCPBridge.uplugin') -Raw
[void]$sb.AppendLine('uplugin contains VersionName 0.1.5: ' + ($up -match '"VersionName":\s*"0\.1\.5"'))
$setpy = Get-Content -LiteralPath (Join-Path $repo 'UEMCPBridge\Content\Python\uemcp_bridge\settings.py')
[void]$sb.AppendLine('settings.py PLUGIN_VERSION line: ' + (($setpy | Select-String 'PLUGIN_VERSION') | Select-Object -First 1).ToString().Trim())
[void]$sb.AppendLine('FREEZE-END verdict=' + $(if ($true) { 'see SUMMARY diff lines above; both must be diff=0 missing=0' } else { '' }))
$sb.ToString() | Out-File -LiteralPath $log -Encoding UTF8
Write-Output ('LOG=' + $log)
