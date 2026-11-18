# UEMCP Server 停止脚本：按 logs/server.pid 停止进程并清理 pid 文件
# 用法：powershell -File scripts\stop-server.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root "logs\server.pid"
if (-not (Test-Path $pidFile)) {
  Write-Output "No pid file at $pidFile (server not started via start-server.ps1?)"
  exit 1
}
$procId = Get-Content $pidFile -ErrorAction SilentlyContinue
if (-not $procId) {
  Write-Output "Pid file empty; removing."
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  exit 1
}
$proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
if ($proc) {
  Stop-Process -Id $procId -Force -ErrorAction Stop
  Write-Output "Stopped uemcp server pid=$procId"
} else {
  Write-Output "Process pid=$procId not running (stale pid file); cleaning."
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
