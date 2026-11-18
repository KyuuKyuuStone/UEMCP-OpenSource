param([ValidateSet('s4b','s5')][string]$Which = 's4b')
$ErrorActionPreference = 'Continue'
$M = 'C:\UE5_P\5.4\UEMCP\feedback-review\qa-tools\qa-exec-mcp.mjs'
$AUDIT = "$env:USERPROFILE\.uemcp\audit\2026-11-18.jsonl"
$L = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs'
$DIR = Join-Path $L ('qasmoke-exec-' + $Which.ToUpper())
New-Item -ItemType Directory -Force -Path $DIR | Out-Null
$before = @(Get-Content $AUDIT -Encoding UTF8 -ErrorAction SilentlyContinue).Count
Write-Output ('AUDIT-BEFORE-LINES ' + $before + ' AT ' + (Get-Date).ToString('s'))
if ($Which -eq 's4b') {
  $out = Join-Path $DIR 'transcript-s4b-standard.jsonl'
  & node $M --policy standard --out $out (Join-Path $L 'qasmoke-exec-S4b\s4b-cases.json') 2>&1
} else {
  $out = Join-Path $DIR 'transcript-s5-full.jsonl'
  & node $M --policy full --allow-gates --out $out (Join-Path $L 'qasmoke-exec-S5\s5-cases.json') 2>&1
}
Write-Output ('MCP-EXIT ' + $LASTEXITCODE)
$afterLines = @(Get-Content $AUDIT -Encoding UTF8)
Write-Output ('AUDIT-AFTER-LINES ' + $afterLines.Count)
$slice = @($afterLines | Select-Object -Skip $before)
$slicePath = Join-Path $DIR ('audit-delta-' + $Which + '.jsonl')
Set-Content -Path $slicePath -Value $slice -Encoding UTF8
Write-Output ('AUDIT-DELTA-ROWS ' + $slice.Count + ' saved=' + $slicePath)
foreach ($l in $slice) {
  if (-not ('' + $l).Trim()) { continue }
  $j = $l | ConvertFrom-Json
  Write-Output ('AUDIT ' + $j.tool + ' ok=' + $j.ok + ' decision=' + $j.decision + ' confirmationMode=' + ('' + $j.confirmationMode) + ' errorCode=' + ('' + $j.errorCode) + ' confirmationDenied=' + ('' + $j.confirmationDenied) + ' origin=' + ('' + $j.origin) + ' stage=' + ('' + $j.stage) + ' reqId=' + ('' + $j.requestId).Substring(0,[Math]::Min(13,('' + $j.requestId).Length)) + ' durationMs=' + $j.durationMs + ' transport=' + $j.transport + ' client=' + ($j.client.name))
}
