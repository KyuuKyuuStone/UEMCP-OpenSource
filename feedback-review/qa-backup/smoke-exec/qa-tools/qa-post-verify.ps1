$ErrorActionPreference = 'Continue'
$repo = 'C:\UE5_P\5.4\UEMCP'
$proj = "$env:USERPROFILE\Documents\Unreal Projects\UEMCP_Smoke_Blank"
Write-Output ('POST-VERIFY-START ' + (Get-Date).ToString('s'))

Write-Output '== 1. git status (baseline 63 lines / 0 deletions) =='
$gs = @(git -C $repo status --porcelain)
Write-Output ('git-status-lines=' + $gs.Count)
$del = @($gs | Where-Object { $_ -match '^ ?D' })
Write-Output ('git-deletions=' + $del.Count)
$untracked = @($gs | Where-Object { $_ -match '^\?\?' })
Write-Output ('git-untracked=' + $untracked.Count)
$mod = @($gs | Where-Object { $_ -match '^\s?M' })
Write-Output ('git-modified=' + $mod.Count)

Write-Output '== 2. frozen baselines recompute =='
foreach ($bl in @('feedback-review\logs\bridgefix2-hash-after.txt', 'feedback-review\logs\tsfix2-hash-after.txt')) {
  $lines = @(Get-Content (Join-Path $repo $bl) -Encoding UTF8 | Where-Object { $_ -match '^[0-9a-fA-F]{64}' })
  $mismatch = 0; $missing = 0
  foreach ($l in $lines) {
    $parts = $l -split '\s+', 2
    $sha = $parts[0]; $path = $parts[1].TrimStart('*').Trim()
    $full = if ([System.IO.Path]::IsPathRooted($path)) { $path } else { Join-Path $repo $path }
    if (-not (Test-Path $full)) { $missing++; Write-Output ('MISSING ' + $full); continue }
    $now = (Get-FileHash -Path $full -Algorithm SHA256).Hash.ToLower()
    if ($now -ne $sha.ToLower()) { $mismatch++; Write-Output ('MISMATCH ' + $full) }
  }
  Write-Output ('BASELINE ' + $bl + ' files=' + $lines.Count + ' mismatch=' + $mismatch + ' missing=' + $missing)
}

Write-Output '== 3. processes and ports =='
Write-Output ('editor-processes=' + @(Get-Process UnrealEditor, UE4Editor -ErrorAction SilentlyContinue).Count)
$busy = @()
foreach ($port in 18778..18788) {
  $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($c) { $busy += $port }
}
Write-Output ('busy-ports=' + $(if ($busy.Count) { $busy -join ',' } else { 'NONE' }))

Write-Output '== 4. project restoration =='
$upSha = (Get-FileHash -Path (Join-Path $proj 'UEMCP_Smoke_Blank.uproject') -Algorithm SHA256).Hash
Write-Output ('uproject-sha=' + $upSha + ' expect=91344BCB7A15D46BD4EB07BAD168E4E59D912DB3B2DAE2C5303CB64488D6E777 match=' + ($upSha -eq '91344BCB7A15D46BD4EB07BAD168E4E59D912DB3B2DAE2C5303CB64488D6E777'))
$ini = Join-Path $proj 'Config\DefaultEngine.ini'
$iniSha = (Get-FileHash -Path $ini -Algorithm SHA256).Hash
Write-Output ('DefaultEngine.ini-sha=' + $iniSha + ' expect=225B2BA989B78AB74C968DB809203E759A8365295A64E7648D315C54FB6CE1B2 match=' + ($iniSha -eq '225B2BA989B78AB74C968DB809203E759A8365295A64E7648D315C54FB6CE1B2'))
Write-Output ('plugin-dir-exists=' + (Test-Path (Join-Path $proj 'Plugins\UEMCPBridge')))
Write-Output ('bridges-json=' + @(Get-ChildItem "$env:USERPROFILE\.uemcp\bridges" -Filter *.json -ErrorAction SilentlyContinue).Count + ' bridge.json=' + (Test-Path "$env:USERPROFILE\.uemcp\bridge.json"))

Write-Output '== 5. SmokeBlank Content touch scan (>= 2026-11-18 06:00Z) =='
$cutoff = (Get-Date '2026-11-18T14:00:00')
$touched = @(Get-ChildItem (Join-Path $proj 'Content') -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $cutoff })
Write-Output ('content-touched-files=' + $touched.Count)
foreach ($t in $touched) { Write-Output ('  TOUCHED ' + $t.FullName + ' ' + $t.LastWriteTime.ToString('s')) }

Write-Output '== 6. engine dir still present (rule 5: any disappearance -> stop) =='
Write-Output ('UE_5.7-exe=' + (Test-Path 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'))
Write-Output ('UE_5.4-dir=' + (Test-Path 'C:\Program Files\Epic Games\UE_5.4'))
Write-Output ('POST-VERIFY-END ' + (Get-Date).ToString('s'))
