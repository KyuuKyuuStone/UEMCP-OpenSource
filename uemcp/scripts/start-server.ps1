# UEMCP Server 启动脚本（分离进程，不随调用方终端/会话退出）
# 用法：powershell -File scripts\start-server.ps1 [-Port 18777] [-Policy read-only] [-ExtraArgs "--allow-destructive"]
# 日志：<uemcp>/logs/server-YYYY-MM-DD.log（应用日志）+ server-stdout/stderr-<date>.log（进程输出）
# PID 文件：<uemcp>/logs/server.pid
param(
  [int]$Port = 18777,
  [string]$Policy = "read-only",
  [string]$ExtraArgs = ""
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot   # <uemcp>/
$serverJs = Join-Path $root "packages\server\dist\index.js"
if (-not (Test-Path $serverJs)) {
  Write-Output "ERROR: $serverJs not found. Run 'pnpm build' first."
  exit 1
}
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# 已有实例在跑则不重复启动
$pidFile = Join-Path $logs "server.pid"
if (Test-Path $pidFile) {
  $old = Get-Content $pidFile -ErrorAction SilentlyContinue
  if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
    Write-Output "Already running: pid=$old (delete $pidFile or run stop-server.ps1 first)"
    exit 1
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$stamp = Get-Date -Format "yyyy-MM-dd"
$stdout = Join-Path $logs "server-stdout-$stamp.log"
$stderr = Join-Path $logs "server-stderr-$stamp.log"

$argList = @($serverJs, "--transport", "http", "--port", "$Port", "--policy", $Policy)
if ($ExtraArgs -and $ExtraArgs.Trim() -ne "") {
  $argList += $ExtraArgs.Split(" ") | Where-Object { $_ -ne "" }
}

$p = Start-Process -FilePath "node" -ArgumentList $argList `
  -WindowStyle Hidden `
  -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
  -PassThru

Set-Content -Path $pidFile -Value $p.Id -Encoding ascii
Write-Output "Started uemcp server pid=$($p.Id) port=$Port policy=$Policy"
Write-Output "App log: $logs\server-$stamp.log"
Write-Output "PID file: $pidFile"
