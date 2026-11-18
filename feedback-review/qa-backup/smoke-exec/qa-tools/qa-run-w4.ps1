# QA window-4 completion run (task cc433d95): full+allow-gates tools/list, A-4 delete confirm:false probe,
# O-STAGE PYTHON_ERROR negatives (plan 4.3), O-QUEUE sleep variant. NO product code changes.
$ErrorActionPreference = 'Continue'
$Q = 'C:\UE5_P\5.4\UEMCP\feedback-review\qa-tools\qa-exec-bridge.mjs'
$M = 'C:\UE5_P\5.4\UEMCP\feedback-review\qa-tools\qa-exec-mcp.mjs'
$OUT = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-W4'
$PF = Join-Path $OUT 'params'
New-Item -ItemType Directory -Force -Path $PF | Out-Null
$AUD = Join-Path $env:USERPROFILE '.uemcp\audit\2026-11-18.jsonl'
Write-Output ('W4-START ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))

function Invoke-Rpc {
  param([string]$Slug, [string]$Method, [string]$ParamsJson, [int]$TimeoutMs = 90000)
  $p = Join-Path $PF ($Slug + '.json')
  Set-Content -Path $p -Value $ParamsJson -Encoding UTF8
  $resp = Join-Path $OUT ('resp-' + $Slug + '.json')
  $line = & node $Q rpc $Method --params-file $p --out $resp --timeout $TimeoutMs 2>&1 | Out-String
  Write-Output ('CASE ' + $Slug + ' EXIT=' + $LASTEXITCODE + ' AT=' + (Get-Date).ToString('HH:mm:ss.fff'))
  Write-Output ('  ' + $line.Trim())
  return (Join-Path $OUT ('resp-' + $Slug + '.json'))
}
function AuditCount { if (Test-Path $AUD) { @(Get-Content $AUD).Count } else { 0 } }

Write-Output '== W4-0 readiness: bridge ping direct =='
Invoke-Rpc -Slug 'ready-ping' -Method 'bridge.ping' -ParamsJson '{}' | Out-Null

Write-Output '== W4-1 MCP full + --allow-gates tools/list (expected 15) =='
$before1 = AuditCount
& node $M --policy full --allow-gates --out (Join-Path $OUT 'transcript-w4-gates15.jsonl') (Join-Path $OUT 'w4-gates15-cases.json') 2>&1 | ForEach-Object { Write-Output ('GATES15 ' + $_) }
$s = Get-Content (Join-Path $OUT 'transcript-w4-gates15.jsonl.summary.json') -Raw | ConvertFrom-Json
$tl = @($s.results | Where-Object { $_.call -eq 'tools/list' })[0]
Write-Output ('GATES15-COUNT ' + $tl.count)
Write-Output ('GATES15-NAMES ' + ($tl.names -join ','))

Write-Output '== W4-2 A-4 probe: MCP full(no destructive) delete confirm:false =='
$before2 = AuditCount
& node $M --policy full --out (Join-Path $OUT 'transcript-w4-a4.jsonl') (Join-Path $OUT 'w4-a4-cases.json') 2>&1 | ForEach-Object { Write-Output ('A4RUN ' + $_) }
$a4 = Get-Content (Join-Path $OUT 'transcript-w4-a4.jsonl.summary.json') -Raw | ConvertFrom-Json
$idx = 0
foreach ($r in $a4.results) {
  if ($r.call -eq 'tools/call') {
    $idx++
    $txt = if ($r.contentText) { $r.contentText } else { '' }
    $elicit = @(if ($r.serverElicitations) { $r.serverElicitations }).Count
    Write-Output ('A4-CASE ' + $idx + ' name=' + $r.name + ' isError=' + $r.isError + ' elicitations=' + $elicit + ' err=' + (($r.error | ConvertTo-Json -Compress -Depth 6)))
    Write-Output ('A4-TEXT ' + $txt.Substring(0, [Math]::Min(400, $txt.Length)))
  }
}

Write-Output '== W4-3 O-STAGE negatives (plan 4.3, direct bridge, full) =='
Invoke-Rpc -Slug 'ostage-a-nameerror' -Method 'python.exec' -ParamsJson '{"code":"raise NameError(\"qa_o_stage_caller_error\")\n"}' | Out-Null
Invoke-Rpc -Slug 'ostage-b-missing-param' -Method 'python.exec' -ParamsJson '{}' | Out-Null
Invoke-Rpc -Slug 'ostage-b2-missing-asset' -Method 'python.exec' -ParamsJson '{"code":"import unreal\nresult = unreal.EditorAssetLibrary.rename_asset(\"/Game/__QA_NoSuchAsset__.No\", \"/Game/__QA_NoSuchAsset2__.No2\")\nprint(result)\nresult + 1\n"}' | Out-Null
foreach ($slug in 'ostage-a-nameerror','ostage-b-missing-param','ostage-b2-missing-asset') {
  $j = Get-Content (Join-Path $OUT ('resp-' + $slug + '.json')) -Raw | ConvertFrom-Json
  $e = $j.response.error
  $d = if ($e) { $e.data } else { $null }
  Write-Output ('O-STAGE-PROBE ' + $slug + ' code=' + $(if ($e) { $e.code } else { 'ok' }) + ' errorCode=' + $(if ($d) { $d.errorCode } else { '-' }) + ' origin=' + $(if ($d) { [string]$d.origin } else { '-' }) + ' stage=' + $(if ($d) { [string]$d.stage } else { '-' }))
}

Write-Output '== W4-4 O-QUEUE variant: 1 slow python.sleep(5) + 5 parallel pings =='
$slowArgs = '"' + $Q + '" rpc python.exec --params-file "' + (Join-Path $PF 'osleep.json') + '" --out "' + (Join-Path $OUT 'resp-oslow.json') + '" --timeout 60000'
'{"code":"import time\nprint(\"qa-slow-start\")\ntime.sleep(5)\nprint(\"qa-slow-end\")\n7*6\n"}' | Set-Content (Join-Path $PF 'osleep.json') -Encoding UTF8
$capProc = Start-Process -FilePath 'node' -ArgumentList $slowArgs -NoNewWindow -PassThru `
  -RedirectStandardOutput (Join-Path $OUT 'oslow.stdout.txt') -RedirectStandardError (Join-Path $OUT 'oslow.stderr.txt')
Start-Sleep -Milliseconds 300
for ($i = 1; $i -le 5; $i++) {
  $pl = & node $Q rpc bridge.ping --params-file (Join-Path $PF 'ping-empty.json') --out (Join-Path $OUT ('resp-w4-ping-' + $i + '.json')) --timeout 15000 2>&1 | Out-String
  Write-Output ('W4-PING ' + $i + ' ' + $pl.Trim())
  Start-Sleep -Milliseconds 500
}
$capProc.WaitForExit(60000) | Out-Null
Write-Output ('W4-SLOW-EXITCODE ' + $capProc.ExitCode)
Write-Output ('W4-SLOW-STDOUT ' + ((Get-Content (Join-Path $OUT 'oslow.stdout.txt') -Raw).Trim()))
for ($i = 1; $i -le 5; $i++) {
  $j = Get-Content (Join-Path $OUT ('resp-w4-ping-' + $i + '.json')) -Raw | ConvertFrom-Json
  $qm = $j.response.result.meta.queuedMs
  $du = $j.response.result.durationMs
  Write-Output ('W4-PINGQ ' + $i + ' durMs=' + $du + ' queuedMs=' + $qm)
}

Write-Output '== W4-5 cleanup + audit delta =='
Invoke-Rpc -Slug 'cleanup-del-1' -Method 'actor.edit' -ParamsJson '{"operations":[{"op":"delete","selector":{"kind":"label","value":"QASmokeW4"},"confirm":true}],"atomic":false}' | Out-Null
Invoke-Rpc -Slug 'cleanup-find' -Method 'actor.query' -ParamsJson '{"filter":{"labelContains":"QASmokeW4"},"fields":["identity"],"limit":20}' | Out-Null
$cj = Get-Content (Join-Path $OUT 'resp-cleanup-find.json') -Raw | ConvertFrom-Json
Write-Output ('W4-CLEANUP-REMAINING total=' + $cj.response.result.meta.total + ' ok=' + $cj.response.result.ok)
$after = AuditCount
Write-Output ('W4-AUDIT before1=' + $before1 + ' before2=' + $before2 + ' after=' + $after)
if ($after -gt $before1) {
  Write-Output 'W4-AUDIT-DELTA-LINES (tool|decision|confirmationMode|errorCode):'
  Get-Content $AUD | Select-Object -Skip $before1 | ForEach-Object {
    $o = $_ | ConvertFrom-Json
    Write-Output ('  ' + [string]$o.tool + ' | ' + [string]$o.decision + ' | ' + [string]$o.confirmationMode + ' | ' + [string]$o.errorCode)
  }
}
Write-Output ('W4-END ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
