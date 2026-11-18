$ErrorActionPreference = 'Continue'
$repo = 'C:\UE5_P\5.4\UEMCP'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$log = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-S3-precheck-20261118.log'
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('RUN cc433d95 pre-S3 (5.7) recheck per supervisor 14:47 item3 ' + $stamp)
[void]$sb.AppendLine('')
[void]$sb.AppendLine('===== baselines recompute (expect diff=0 missing=0 both) =====')
foreach ($list in @('bridgefix2-hash-after.txt', 'tsfix2-hash-after.txt')) {
  $p = Join-Path $repo ('feedback-review\logs\' + $list)
  $entries = @(Get-Content -LiteralPath $p | Where-Object { $_ -match '^[0-9A-Fa-f]{64}\s' })
  $same = 0; $changed = 0; $missing = 0
  foreach ($e in $entries) {
    $parts = $e -split '\s+', 2
    $want = $parts[0].ToUpper()
    $rel = $parts[1].Trim()
    $fp = Join-Path $repo $rel
    if (-not (Test-Path -LiteralPath $fp)) { $missing++; [void]$sb.AppendLine('MISSING: ' + $rel); continue }
    $got = (Get-FileHash -LiteralPath $fp -Algorithm SHA256).Hash.ToUpper()
    if ($got -eq $want) { $same++ } else { $changed++; [void]$sb.AppendLine('CHANGED: ' + $rel) }
  }
  [void]$sb.AppendLine('SUMMARY ' + $list + ' files=' + $entries.Count + ' same=' + $same + ' changed=' + $changed + ' missing=' + $missing + ' diff=' + ($changed + $missing))
}
[void]$sb.AppendLine('')
[void]$sb.AppendLine('===== state recheck =====')
$status = @(git -C $repo status --porcelain)
$del = @($status | Where-Object { $_.Length -ge 3 -and $_.Substring(0, 2) -match 'D' })
[void]$sb.AppendLine('git status-lines=' + $status.Count + ' deletion-lines=' + $del.Count)
$procs = @(Get-Process -Name 'UnrealEditor', 'UE4Editor' -ErrorAction SilentlyContinue)
[void]$sb.AppendLine('P-3 editor-processes count=' + $procs.Count)
$freePorts = @(); $busyPorts = @()
foreach ($port in 18778..18788) {
  $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $port)
  try { $l.Start(); $freePorts += $port } catch { $busyPorts += $port } finally { try { $l.Stop() } catch { } }
}
[void]$sb.AppendLine('P-4 ports free=[' + ($freePorts -join ',') + '] busy=[' + ($busyPorts -join ',') + ']')
$bcount = @(Get-ChildItem "$env:USERPROFILE\.uemcp\bridges" -Filter *.json -ErrorAction SilentlyContinue).Count
[void]$sb.AppendLine('bridges-dir-json count=' + $bcount)
[void]$sb.AppendLine('')
[void]$sb.AppendLine('===== 5.7 engine + SmokeBlank project integrity (supervisor item3) =====')
$exe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
[void]$sb.AppendLine('5.7 exe=' + (Test-Path $exe) + ' mtime=' + (Get-Item $exe -ErrorAction SilentlyContinue).LastWriteTime)
$bv = (Get-Content 'C:\Program Files\Epic Games\UE_5.7\Engine\Build.version' -Raw | ConvertFrom-Json)
$bvStr = '' + $bv.MajorName + '.' + $bv.MinorName + '.' + $bv.PatchName + '-' + $bv.Changelist
[void]$sb.AppendLine('5.7 Build.version=' + $bvStr)
$proj = "$env:USERPROFILE\Documents\Unreal Projects\UEMCP_Smoke_Blank"
$upj = Join-Path $proj 'UEMCP_Smoke_Blank.uproject'
[void]$sb.AppendLine('uproject exists=' + (Test-Path $upj) + ' sha256=' + (Get-FileHash $upj -Algorithm SHA256).Hash)
$j = (Get-Content -Raw $upj) | ConvertFrom-Json
[void]$sb.AppendLine('EngineAssociation=' + $j.EngineAssociation + ' plugins-declared=' + (@($j.Plugins).Count))
$all = @(Get-ChildItem $proj -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\(Saved|Intermediate|Binaries)\\' })
[void]$sb.AppendLine('project files (excl Saved/Intermediate/Binaries)=' + $all.Count)
$cfg = @(Get-ChildItem (Join-Path $proj 'Config') -File -ErrorAction SilentlyContinue).Count
[void]$sb.AppendLine('Config files=' + $cfg)
$plugDir = Join-Path $proj 'Plugins'
$plugNow = @(Get-ChildItem $plugDir -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
[void]$sb.AppendLine('Plugins/ dirs NOW=' + $(if ($plugNow.Count) { ($plugNow -join ',') } else { 'none' }))
$de = Join-Path $proj 'Config\DefaultEngine.ini'
[void]$sb.AppendLine('DefaultEngine.ini exists=' + (Test-Path $de) + ' sha256=' + (Get-FileHash $de -Algorithm SHA256).Hash + ' (O-PS baseline read-only)')
$upl = Get-Content -LiteralPath (Join-Path $repo 'UEMCPBridge\UEMCPBridge.uplugin') -Raw
[void]$sb.AppendLine('source uplugin 0.1.5 match=' + ($upl -match '"VersionName":\s*"0\.1\.5"'))
$sb.ToString() | Out-File -LiteralPath $log -Encoding UTF8
Write-Output ('LOG=' + $log)
Get-Content $log
