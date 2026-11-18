# rel016-qa-gates.ps1 — 独立复验四门禁运行器（输出 rel016-qa-{build,typecheck,test,smoke}.log）
$ErrorActionPreference = 'Continue'
$root = 'C:\UE5_P\5.4\UEMCP'
$log  = "$root\feedback-review\logs"
$steps = @(
    @{ name = 'build';     cmd = 'pnpm --config.verifyDepsBeforeRun=false build' },
    @{ name = 'typecheck'; cmd = 'pnpm --config.verifyDepsBeforeRun=false typecheck' },
    @{ name = 'test';      cmd = 'pnpm --config.verifyDepsBeforeRun=false test' },
    @{ name = 'smoke';     cmd = 'pnpm --config.verifyDepsBeforeRun=false smoke' }
)
foreach ($s in $steps) {
    $out = "$log\rel016-qa-$($s.name).log"
    $head = @(
        "rel016-qa gate: $($s.name)",
        "COMMAND: $($s.cmd)",
        "CWD: $root\uemcp",
        "START: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
    ) -join "`r`n"
    $head | Set-Content $out -Encoding UTF8
    $body = & pwsh -NoProfile -Command "Set-Location '$root\uemcp'; $($s.cmd) 2>&1" | Out-String
    $ec = $LASTEXITCODE
    Add-Content $out ("`r`n" + $body)
    Add-Content $out ("EXIT_CODE: $ec`r`nEND: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
    Write-Host ("STEP {0} EXIT={1}" -f $s.name, $ec)
    if ($ec -ne 0) { Write-Host 'HALT: gate failed, stopping runner (failure scene preserved in the log)'; break }
}
