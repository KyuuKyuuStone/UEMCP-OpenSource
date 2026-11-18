$ErrorActionPreference = 'Continue'
$Q = 'C:\UE5_P\5.4\UEMCP\feedback-review\qa-tools\qa-exec-bridge.mjs'
$OUT = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-S4'
$PF = Join-Path $OUT 'params'
Write-Output '== FIX-1: re-parse existing O-QUEUE files (correct envelope path response.result) =='
$posQ = 0; $maxQ = 0; $okQ = 0; $rl = 0; $nullQ = 0
foreach ($f in Get-ChildItem $OUT -Filter 'resp-oq-*.json') {
  $j = Get-Content $f.FullName -Raw | ConvertFrom-Json
  $res = $j.response.result
  if ($null -ne $res.error) { if ($res.error.data.errorCode -eq 'RATE_LIMITED') { $rl++ }; continue }
  if ($res.ok) { $okQ++ }
  $qm = $res.meta.queuedMs
  if ($null -eq $qm) { $nullQ++ } elseif ($qm -gt 0) { $posQ++; if ($qm -gt $maxQ) { $maxQ = $qm } }
}
Write-Output ('O-QUEUE-PARSED ok=' + $okQ + ' rateLimited=' + $rl + ' queuedMsNull=' + $nullQ + ' queuedMsPositive=' + $posQ + ' maxQueuedMs=' + $maxQ)

Write-Output '== FIX-2: redo actor chain with correct array handling =='
function Invoke-Rpc {
  param([string]$Slug, [string]$Method, [string]$ParamsJson, [int]$TimeoutMs = 90000)
  $p = Join-Path $PF ($Slug + '.json')
  Set-Content -Path $p -Value $ParamsJson -Encoding UTF8
  $resp = Join-Path $OUT ('resp-' + $Slug + '.json')
  $line = & node $Q rpc $Method --params-file $p --out $resp --timeout $TimeoutMs 2>&1 | Out-String
  Write-Output ('CASE ' + $Slug + ' EXIT=' + $LASTEXITCODE + ' AT=' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss.fff'))
  Write-Output ('  ' + $line.Trim())
}
function Extract-ActorPaths { param([string]$File)
  $raw = Get-Content $File -Raw
  $ms = [regex]::Matches($raw, '"actorPath"\s*:\s*"([^"]+)"')
  $out = @(); foreach ($m in $ms) { $out += $m.Groups[1].Value }
  return @($out | Select-Object -Unique)
}
Invoke-Rpc -Slug 'r2-spawn' -Method 'actor.edit' -ParamsJson '{"operations":[{"op":"spawn","class":"StaticMeshActor","label":"QASmokeW2","location":{"x":200.0,"y":0.0,"z":0.0}}]}'
$paths = @(Extract-ActorPaths (Join-Path $OUT 'resp-r2-spawn.json'))
$actorPath = ''
if ($paths.Count -gt 0) { $actorPath = [string]$paths[0] }
Write-Output ('R2-SPAWN-PATH [' + $actorPath + '] count=' + $paths.Count)
if ($actorPath.Length -gt 5) {
  $sel = '{"kind":"actorPath","value":"' + $actorPath + '"}'
  Invoke-Rpc -Slug 'r2-set-transform' -Method 'actor.edit' -ParamsJson ('{"operations":[{"op":"set_transform","selector":' + $sel + ',"location":{"x":500.0,"y":100.0,"z":50.0},"snapToGrid":false}]}')
  Invoke-Rpc -Slug 'r2-set-props' -Method 'actor.edit' -ParamsJson ('{"operations":[{"op":"set_properties","selector":' + $sel + ',"properties":{"mobility":"movable","tags":{"qa":"s4"}}}]}')
  Invoke-Rpc -Slug 'r2-duplicate' -Method 'actor.edit' -ParamsJson ('{"operations":[{"op":"duplicate","selector":' + $sel + ',"count":2,"offset":{"x":0.0,"y":200.0,"z":0.0},"labelSuffix":"_qadup"}]}')
  Invoke-Rpc -Slug 'r2-select' -Method 'actor.edit' -ParamsJson ('{"operations":[{"op":"select","selector":' + $sel + ',"mode":"replace"}]}')
  Invoke-Rpc -Slug 'r2-dryrun' -Method 'actor.edit' -ParamsJson '{"operations":[{"op":"spawn","class":"StaticMeshActor","label":"QASmokeDryRun2"}],"dryRun":true}'
  # verify transform actually applied + dryRun leak check + dup count
  Invoke-Rpc -Slug 'r2-find' -Method 'actor.query' -ParamsJson '{"filter":{"labelContains":"QASmokeW2"},"fields":["identity","transform"],"limit":20}'
}
Write-Output '== FIX-3: redo O-HOL with real capture (level_viewport file mode, ~2s) =='
'{"target":"level_viewport","width":640,"height":360,"format":"png","returnMode":"file","timeoutMs":20000}' | Set-Content (Join-Path $PF 'ohol-capture2.json') -Encoding UTF8
$capArgs = '"' + $Q + '" rpc viewport.capture --params-file "' + (Join-Path $PF 'ohol-capture2.json') + '" --out "' + (Join-Path $OUT 'resp-ohol-capture2.json') + '" --timeout 60000'
$capProc = Start-Process -FilePath 'node' -ArgumentList $capArgs -NoNewWindow -PassThru `
  -RedirectStandardOutput (Join-Path $OUT 'ohol2-capture.stdout.txt') -RedirectStandardError (Join-Path $OUT 'ohol2-capture.stderr.txt')
Start-Sleep -Milliseconds 400
for ($i = 1; $i -le 10; $i++) {
  $pl = & node $Q rpc bridge.ping --params-file (Join-Path $PF 'ping-empty.json') --out (Join-Path $OUT ('resp-ohol2-ping-' + $i + '.json')) --timeout 15000 2>&1 | Out-String
  Write-Output ('PING2 ' + $i + ' ' + $pl.Trim())
  Start-Sleep -Milliseconds 300
}
$capProc.WaitForExit(90000) | Out-Null
Write-Output ('CAPTURE2-EXITCODE ' + $capProc.ExitCode)
Write-Output ('CAPTURE2-STDOUT ' + ((Get-Content (Join-Path $OUT 'ohol2-capture.stdout.txt') -Raw).Trim()))

Write-Output '== FIX-4: delete all QASmokeW2* actors =='
$left = @(Extract-ActorPaths (Join-Path $OUT 'resp-r2-find.json'))
Write-Output ('W2-FOUND ' + $left.Count)
$n = 0
foreach ($p2 in $left) {
  $n++
  $dj = '{"operations":[{"op":"delete","selector":{"kind":"actorPath","value":"' + [string]$p2 + '"},"confirm":true}],"atomic":false}'
  Invoke-Rpc -Slug ('r2-delete-' + $n) -Method 'actor.edit' -ParamsJson $dj
}
Invoke-Rpc -Slug 'r2-find-final' -Method 'actor.query' -ParamsJson '{"filter":{"labelContains":"QASmokeW"},"fields":["identity"],"limit":50}'
Write-Output 'S4-FIXEND'
