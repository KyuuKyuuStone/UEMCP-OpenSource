$ErrorActionPreference = 'Continue'
$log = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-run-S3.log'
function EnvOrUnset($name) {
  $v = [Environment]::GetEnvironmentVariable($name, 'Process')
  if ($null -eq $v) { return '<unset>' }
  return $v
}
$hdr = @()
$hdr += ('START ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
$hdr += 'S3: 5.7 UEMCP_Smoke_Blank, gates factory-default-off (no env set), bridge-direct readonly tier per plan S3'
$hdr += 'COMMAND: & UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.7 -KeepPrepared -TimeoutSeconds 600'
foreach ($n in @('UEMCP_BRIDGE_ALLOW_WRITE', 'UEMCP_BRIDGE_ALLOW_EXEC', 'UEMCP_BRIDGE_ALLOW_CONSOLE')) {
  $hdr += ('ENV-CHECK ' + $n + '=' + (EnvOrUnset $n))
}
$hdr | Out-File -LiteralPath $log -Encoding UTF8
& 'C:\UE5_P\5.4\UEMCP\UEMCPBridge\Tests\ue_smoke_run.ps1' -EngineVersion 5.7 -KeepPrepared -TimeoutSeconds 600 *>&1 | Add-Content -LiteralPath $log -Encoding UTF8
('EXIT=' + $LASTEXITCODE) | Add-Content -LiteralPath $log -Encoding UTF8
('END ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) | Add-Content -LiteralPath $log -Encoding UTF8
Write-Output ('S3 EXIT=' + $LASTEXITCODE)
