# QA 复算驱动脚本：只读运行 CMD 组 collect.py，UTF-8 字节级捕获输出
# 由测试工程师编写；不改动反馈原件目录任何文件
$ErrorActionPreference = "Stop"
$collect = 'C:\Users\Administrator\Desktop\UEMCP遇到的问题\CMD构建发布组_UEMCP反馈\raw\collect.py'
$logs    = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs'
$raw     = Join-Path $logs 'qa-collect-rawstdout-20261117.bin'
$rec     = Join-Path $logs 'qa-collect-recompute-20261117.log'

$env:PYTHONIOENCODING = 'utf-8'
$exit = -1
& cmd.exe /c "`"C:\Python314\python.exe`" `"$collect`" > `"$raw`" 2>&1"
$exit = $LASTEXITCODE

$scriptHash = (Get-FileHash $collect -Algorithm SHA256).Hash.ToLower()
$bytes = [System.IO.File]::ReadAllBytes($raw)
$head = @(
  '# RECOMPUTE RUN 2026-11-17 by QA (测试工程师)',
  "# HOST: $env:COMPUTERNAME USER: $env:USERNAME",
  '# COMMAND: cmd /c "C:\Python314\python.exe <collect.py>" > qa-collect-rawstdout-20261117.bin 2>&1  (PYTHONIOENCODING=utf-8)',
  "# SCRIPT_SHA256: $scriptHash",
  '# NOTE: 首次复算经 PowerShell 管道出现 GBK 重编码乱码，故改为字节级重定向；正文与 raw/collect.log 逐行比对见 qa-collect-diff-20261117.log',
  '# ===== output start ====='
)
$text = (($head -join "`r`n") + "`r`n") + [System.Text.Encoding]::UTF8.GetString($bytes) + "`r`n# ===== output end =====`r`nEXIT|$exit`r`n"
[System.IO.File]::WriteAllText($rec, $text, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "EXIT=$exit rec=$rec"
