# rel016-qa-livecapture.ps1 — 活体会话内双版本捕获（/health pluginVersion + MCP serverInfo.version，同会话带时间戳）
param([Parameter(Mandatory)][string]$WindowDir)
$ErrorActionPreference = 'Continue'
Set-Location 'C:\UE5_P\5.4\UEMCP'
$disc = Get-Content (Join-Path $WindowDir 'discovery.json') -Raw | ConvertFrom-Json
$port = [int]$disc.Record.port
$url = [string]$disc.Record.url
if (-not $url -or -not $port) {
    if ($port) { $url = 'http://127.0.0.1:' + $port } else { $url = 'http://127.0.0.1:18778' }
}
Write-Output ('SESSION-WINDOW: ' + $WindowDir)
Write-Output ('BRIDGE-URL: ' + $url)

Write-Output ('' )
Write-Output ('===== [1] bridge /health direct GET  ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz') + ' =====')
Write-Output 'COMMAND: Invoke-WebRequest <url>/health'
try {
    $h = Invoke-WebRequest -Uri ($url + '/health') -UseBasicParsing -TimeoutSec 15
    Write-Output ('HTTP ' + $h.StatusCode + '  at ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
    Write-Output ('RAW_HEALTH: ' + $h.Content)
    $hj = $h.Content | ConvertFrom-Json
    Write-Output ('pluginVersion=' + $hj.pluginVersion + '  ueVersion=' + $hj.ueVersion + '  buildHash=' + $hj.buildHash.Substring(0,12) + '  pid=' + $hj.pid)
    Write-Output ('HEALTH_RESULT ' + $(if ($hj.pluginVersion -eq '0.1.6') { 'PASS pluginVersion=0.1.6 (bridge side, live session)' } else { 'FAIL ' + $hj.pluginVersion }))
} catch {
    Write-Output ('HEALTH-ERROR: ' + $_.Exception.Message)
}

Write-Output ''
Write-Output ('===== [2] MCP server stdio initialize + live roundtrip  ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz') + ' =====')
Write-Output 'COMMAND: node feedback-review\qa-tools\rel016-qa-probe.mjs uemcp\packages\server\dist\index.js'
node 'feedback-review\qa-tools\rel016-qa-probe.mjs' 'C:\UE5_P\5.4\UEMCP\uemcp\packages\server\dist\index.js' 2>&1 | Where-Object { $_ -notmatch '"tools":\[' } | ForEach-Object { Write-Output ('PROBE| ' + $_) }
Write-Output ('PROBE_EXIT=' + $LASTEXITCODE + '  at ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
Write-Output ('CAPTURE-END: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
