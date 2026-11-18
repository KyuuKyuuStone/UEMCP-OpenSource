param([string]$CaseFile = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-S4\s4-cases.json')
$ErrorActionPreference = 'Continue'
$Q = 'C:\UE5_P\5.4\UEMCP\feedback-review\qa-tools\qa-exec-bridge.mjs'
$OUT = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-S4'
$PF = Join-Path $OUT 'params'
New-Item -ItemType Directory -Force -Path $PF | Out-Null
'{}' | Set-Content (Join-Path $PF 'ping-empty.json') -Encoding UTF8
'{"limit":1}' | Set-Content (Join-Path $PF 'oq-query.json') -Encoding UTF8
$cf = Get-Content $CaseFile -Raw | ConvertFrom-Json

function Invoke-Rpc {
  param([string]$Slug, [string]$Method, $ParamsObj, [int]$TimeoutMs = 90000)
  $p = Join-Path $PF ($Slug + '.json')
  ($ParamsObj | ConvertTo-Json -Depth 10 -Compress) | Set-Content -Path $p -Encoding UTF8
  $resp = Join-Path $OUT ('resp-' + $Slug + '.json')
  $t0 = Get-Date
  $line = & node $Q rpc $Method --params-file $p --out $resp --timeout $TimeoutMs 2>&1 | Out-String
  $code = $LASTEXITCODE
  $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss.fff')
  Write-Output ('CASE ' + $Slug + ' EXIT=' + $code + ' AT=' + $ts)
  Write-Output ('  ' + $line.Trim())
  return $line
}
function Get-JsonPaths {
  param([string]$File, [string]$Pattern)
  if (-not (Test-Path $File)) { return @() }
  $raw = Get-Content $File -Raw
  return @([regex]::Matches($raw, $Pattern) | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
}

Write-Output ('S4-START ' + (Get-Date).ToString('s'))
# 0. health via QA subcommand: gates-full policies echo
$hl = & node $Q health 2>&1 | Out-String
Write-Output ('HEALTH ' + $hl.Trim())
# 1. actor.edit chain
Invoke-Rpc -Slug 'w-actor-spawn' -Method $cf.chain.spawn.method -ParamsObj $cf.chain.spawn.params | Out-Null
$paths = Get-JsonPaths (Join-Path $OUT 'resp-w-actor-spawn.json') '"actorPath"\s*:\s*"([^"]+)"'
if ($paths.Count -eq 0) { $paths = Get-JsonPaths (Join-Path $OUT 'resp-w-actor-spawn.json') '"path"\s*:\s*"([^"]+)"' }
$actorPath = if ($paths.Count -gt 0) { $paths[0] } else { '' }
Write-Output ('CHAIN-SPAWN-PATH [' + $actorPath + ']')
if ($actorPath -ne '') {
  $st = $cf.chain.setTransform.params; $st.operations[0].selector.value = $actorPath
  Invoke-Rpc -Slug 'w-actor-set-transform' -Method $cf.chain.setTransform.method -ParamsObj $st | Out-Null
  $sp = $cf.chain.setProps.params; $sp.operations[0].selector.value = $actorPath
  Invoke-Rpc -Slug 'w-actor-set-props' -Method $cf.chain.setProps.method -ParamsObj $sp | Out-Null
  $du = $cf.chain.duplicate.params; $du.operations[0].selector.value = $actorPath
  Invoke-Rpc -Slug 'w-actor-duplicate' -Method $cf.chain.duplicate.method -ParamsObj $du | Out-Null
} else {
  Write-Output 'CHAIN-SKIP set/dup: no actorPath extracted'
}
Invoke-Rpc -Slug 'w-actor-dryrun' -Method $cf.chain.dryRun.method -ParamsObj $cf.chain.dryRun.params | Out-Null
# 2. find all smoke actors (also proves dryRun created nothing)
Invoke-Rpc -Slug 'w-actor-find' -Method $cf.chain.findQuery.method -ParamsObj $cf.chain.findQuery.params | Out-Null
$all = Get-JsonPaths (Join-Path $OUT 'resp-w-actor-find.json') '"actorPath"\s*:\s*"([^"]+)"'
Write-Output ('FIND-COUNT ' + $all.Count)
$dryLeak = @($all | Where-Object { $_ -match 'DryRun' })
Write-Output ('DRYRUN-LEAK ' + $dryLeak.Count)
# 3. generic write batch
foreach ($c in $cf.generic) { Invoke-Rpc -Slug $c.slug -Method $c.method -ParamsObj $c.params | Out-Null }
# 4. PIE V2
Invoke-Rpc -Slug 'v2-pie-start' -Method $cf.pie.start.method -ParamsObj $cf.pie.start.params -TimeoutMs 130000 | Out-Null
Invoke-Rpc -Slug 'v2-pie-status' -Method $cf.pie.status.method -ParamsObj $cf.pie.status.params | Out-Null
Invoke-Rpc -Slug 'v2-pie-stop' -Method $cf.pie.stop.method -ParamsObj $cf.pie.stop.params -TimeoutMs 60000 | Out-Null
# 5. O-HOL: capture (detached process, redirected stdio) while pinging synchronously
$capP = Join-Path $PF 'w-actor-spawn.json'  # placeholder to be replaced below
'{"target":"editor","width":640,"height":360}' | Set-Content (Join-Path $PF 'ohol-capture.json') -Encoding UTF8
$capArgs = $Q + ' rpc viewport.capture --params-file "' + (Join-Path $PF 'ohol-capture.json') + '" --out "' + (Join-Path $OUT 'resp-ohol-capture.json') + '" --timeout 90000'
$capProc = Start-Process -FilePath 'node' -ArgumentList $capArgs -NoNewWindow -PassThru `
  -RedirectStandardOutput (Join-Path $OUT 'ohol-capture.stdout.txt') -RedirectStandardError (Join-Path $OUT 'ohol-capture.stderr.txt')
Start-Sleep -Milliseconds 400
for ($i = 1; $i -le 10; $i++) {
  $pl = & node $Q rpc bridge.ping --params-file (Join-Path $PF 'ping-empty.json') --out (Join-Path $OUT ('resp-ohol-ping-' + $i + '.json')) --timeout 15000 2>&1 | Out-String
  Write-Output ('PING ' + $i + ' ' + $pl.Trim())
  Start-Sleep -Milliseconds 350
}
$capProc.WaitForExit(90000) | Out-Null
Write-Output ('CAPTURE-EXITCODE ' + $capProc.ExitCode)
Write-Output ('CAPTURE-STDOUT ' + (Get-Content (Join-Path $OUT 'ohol-capture.stdout.txt') -Raw).Trim())
# 6. O-QUEUE: 16 concurrent actor.query
$procs = 1..16 | ForEach-Object {
  $i = $_
  $a = $Q + ' rpc actor.query --params-file "' + (Join-Path $PF 'oq-query.json') + '" --out "' + (Join-Path $OUT ('resp-oq-' + $i + '.json')) + '" --timeout 30000'
  Start-Process -FilePath 'node' -ArgumentList $a -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $OUT ('oq-' + $i + '.stdout.txt')) -RedirectStandardError (Join-Path $OUT ('oq-' + $i + '.stderr.txt'))
}
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline -and @($procs | Where-Object { -not $_.HasExited }).Count -gt 0) { Start-Sleep -Milliseconds 500 }
$posQ = 0; $maxQ = 0; $okQ = 0; $rl = 0
foreach ($f in Get-ChildItem $OUT -Filter 'resp-oq-*.json') {
  try { $j = Get-Content $f.FullName -Raw | ConvertFrom-Json } catch { continue }
  $res = $j.result
  if ($res.ok) { $okQ++ } elseif ($res.error -and $res.error.data -and $res.error.data.errorCode -eq 'RATE_LIMITED') { $rl++ }
  $qm = $res.meta.queuedMs
  if ($null -ne $qm -and $qm -gt 0) { $posQ++; if ($qm -gt $maxQ) { $maxQ = $qm } }
}
Write-Output ('O-QUEUE ok=' + $okQ + ' rateLimited=' + $rl + ' posQueuedMs=' + $posQ + ' maxQueuedMs=' + $maxQ + ' files=' + @(Get-ChildItem $OUT -Filter 'resp-oq-*.json').Count + '/16')
# 7. cleanup: delete every QASmokeW1 actor found
$find2 = $cf.chain.findQuery
Invoke-Rpc -Slug 'w-actor-find2' -Method $find2.method -ParamsObj $find2.params | Out-Null
$all2 = Get-JsonPaths (Join-Path $OUT 'resp-w-actor-find2.json') '"actorPath"\s*:\s*"([^"]+)"'
Write-Output ('CLEANUP-TARGETS ' + $all2.Count)
$n = 0
foreach ($p2 in $all2) {
  $n++
  $d = $cf.chain.delete.params
  $d.operations = @($d.operations[0])
  $d.operations[0].selector.value = $p2
  Invoke-Rpc -Slug ('x-actor-delete-' + $n) -Method $cf.chain.delete.method -ParamsObj $d | Out-Null
}
# verify empty
Invoke-Rpc -Slug 'w-actor-find3' -Method $find2.method -ParamsObj $find2.params | Out-Null
$all3 = Get-JsonPaths (Join-Path $OUT 'resp-w-actor-find3.json') '"actorPath"\s*:\s*"([^"]+)"'
Write-Output ('CLEANUP-REMAIN ' + $all3.Count)
Write-Output ('S4-END ' + (Get-Date).ToString('s'))
