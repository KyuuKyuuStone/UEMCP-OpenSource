# QA consolidation: re-extract key values from RAW resp files (never from memory).
$ErrorActionPreference = 'Continue'
$W4 = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-W4'
$S4 = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-S4'
$S4B = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-S4B'
$S5 = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-S5'
Write-Output ('CONSOLIDATE-AT ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))

Write-Output '== W4b O-QUEUE redo: slow exec + pings (values re-extracted from resp files; console of redo not tee-d, raw files are authority) =='
$sl = Get-Content (Join-Path $W4 'resp-oslow2.json') -Raw | ConvertFrom-Json
Write-Output ('SLOW python.exec ok=' + $sl.response.result.ok + ' envelopeDurationMs=' + $sl.durationMs + ' ts=' + $sl.ts)
foreach ($f in Get-ChildItem $W4 -Filter 'resp-w4-ping-*.json' | Sort-Object Name) {
  $j = Get-Content $f.FullName -Raw | ConvertFrom-Json
  Write-Output ('PING ' + $f.Name + ' http=' + $j.httpStatus + ' ok=' + $j.response.result.ok + ' meta.queuedMs=' + [string]$j.response.result.meta.queuedMs + ' envelopeDurationMs=' + $j.durationMs + ' ts=' + $j.ts)
}

Write-Output '== W4b O-STAGE raw payload key fields (from resp envelopes) =='
foreach ($slug in 'ostage-a-nameerror','ostage-b-missing-param','ostage-b2-missing-asset') {
  $j = Get-Content (Join-Path $W4 ('resp-' + $slug + '.json')) -Raw | ConvertFrom-Json
  if ($j.response.error) {
    $d = $j.response.error.data
    Write-Output ($slug + ' rpcCode=' + $j.response.error.code + ' http=' + $j.httpStatus + ' errorCode=' + $d.errorCode + ' origin=' + [string]$d.details.origin + ' stage=' + [string]$d.details.stage)
  } else {
    Write-Output ($slug + ' OK-PATH result=' + ($j.response.result | ConvertTo-Json -Compress -Depth 4))
  }
}

Write-Output '== W4 gates15 / A-4 (from summary files) =='
$g = Get-Content (Join-Path $W4 'transcript-w4-gates15.jsonl.summary.json') -Raw | ConvertFrom-Json
$tlo = @($g.results | Where-Object { $_.call -eq 'tools/list' })
Write-Output ('FULL+GATES tools/list count=' + $tlo[0].count)
$a = Get-Content (Join-Path $W4 'transcript-w4-a4.jsonl.summary.json') -Raw | ConvertFrom-Json
$i = 0
foreach ($r in @($a.results | Where-Object { $_.call -eq 'tools/call' })) {
  $i++
  Write-Output ('A4-' + $i + ' ' + $r.name + ' isError=' + $r.isError + ' elicitations=' + @($r.serverElicitations).Count + ' text=' + ([string]$r.contentText).Substring(0, [Math]::Min(200, ([string]$r.contentText).Length)))
}
$fj = Get-Content (Join-Path $W4 'resp-find-final.json') -Raw | ConvertFrom-Json
Write-Output ('W4-CLEANUP data.total=' + $fj.response.result.data.total + ' returned=' + $fj.response.result.data.returned)

Write-Output '== S4 windowed capture timeouts (raw) =='
foreach ($n in 'w-capture-timeout-1','w-capture-timeout-2','ohol-capture2') {
  $p = Join-Path $S4 ('resp-' + $n + '.json')
  if (-not (Test-Path $p)) { $p = Join-Path $S4B ('resp-' + $n + '.json') }
  if (Test-Path $p) {
    $j = Get-Content $p -Raw | ConvertFrom-Json
    Write-Output ($n + ' http=' + $j.httpStatus + ' code=' + [string]$j.response.error.code + ' msg=' + [string]$j.response.error.message + ' dur=' + $j.durationMs)
  }
}
Write-Output '== S4 rollback -32024 (raw) =='
foreach ($n in 'w-actor-set-transform','w-actor-duplicate','r3-del') {
  $p = Join-Path $S4 ('resp-' + $n + '.json')
  if (Test-Path $p) {
    $j = Get-Content $p -Raw | ConvertFrom-Json
    if ($j.response.error) { Write-Output ($n + ' code=' + $j.response.error.code + ' msg=' + $j.response.error.message) } else { Write-Output ($n + ' ok=' + $j.response.result.ok) }
  }
}
Write-Output '== S5 elicitation scan across ALL transcripts == total'
$allT = @(Get-ChildItem $S4B,$S5,$W4 -Filter 'transcript-*.jsonl' -ErrorAction SilentlyContinue)
foreach ($t in $allT) {
  $n = @(Select-String -Path $t.FullName -Pattern 'elicitation/create').Count
  Write-Output ('TRANSCRIPT ' + $t.Name + ' elicitation/create=' + $n)
}
Write-Output '== S4b level.control audit gap (from audit-delta-s4b.jsonl) =='
if (Test-Path (Join-Path $S4B 'audit-delta-s4b.jsonl')) {
  Get-Content (Join-Path $S4B 'audit-delta-s4b.jsonl') | ForEach-Object {
    $o = $_ | ConvertFrom-Json
    Write-Output ('AUDIT ' + [string]$o.tool + ' | dec=' + [string]$o.decision + ' | conf=' + [string]$o.confirmationMode + ' | err=' + [string]$o.errorCode)
  }
}
Write-Output '== bridge audit window2 tally (115 lines) =='
$ba = Join-Path $S5 'bridge-audit-window2.jsonl'
if (Test-Path $ba) {
  $lines = @(Get-Content $ba)
  Write-Output ('BRIDGE-AUDIT-LINES ' + $lines.Count)
  $lines | ForEach-Object { $_ | ConvertFrom-Json } | Group-Object method | Sort-Object Count -Descending | ForEach-Object { Write-Output ('  METHOD ' + $_.Name + ' = ' + $_.Count) }
  $reqStr = @($lines | ForEach-Object { ($_ | ConvertFrom-Json).PSObject.Properties['requestId'] } | Where-Object { $_ -and ($_.Value -is [string]) }).Count
  Write-Output ('  requestId-strings = ' + $reqStr)
  $q = @($lines | ForEach-Object { ($_ | ConvertFrom-Json).queuedMs } | Where-Object { $_ -gt 0 }).Count
  $qm = @($lines | ForEach-Object { ($_ | ConvertFrom-Json).queuedMs } | Measure-Object -Maximum).Maximum
  Write-Output ('  queuedMs-positive = ' + $q + ' max = ' + $qm)
}
Write-Output 'CONSOLIDATE-END'
