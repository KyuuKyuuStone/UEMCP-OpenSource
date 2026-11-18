# rel016-qa-hashcheck.ps1 — 独立复验：8 个版本点文件 SHA256+字节数 vs 发版侧记录值
# 记录值来源（只读引用）：feedback-review/logs/rel016-bridge-hash.txt AFTER 段
#                            feedback-review/logs/rel016-ts-hash.txt AFTER 段
#                            feedback-review/logs/rel016-ts-manifest.txt tgz 行
# 用法: pwsh -File rel016-qa-hashcheck.ps1 [-Tag PRE|POST]  → 输出可重定向至 rel016-qa-hash.txt
param([string]$Tag = 'PRE')
$ErrorActionPreference = 'Stop'
$root = 'C:\UE5_P\5.4\UEMCP'
Set-Location $root
$expected = @(
    @{ rel='UEMCPBridge\UEMCPBridge.uplugin';                        sha='8f997ad3807b79487b68465a63816c40ea4137c681d9e162e34119bcdea36379'; bytes=523   ; src='rel016-bridge-hash.txt' }
    @{ rel='UEMCPBridge\Content\Python\uemcp_bridge\settings.py';    sha='9934703ba227faf9c8e5a2dc1e33902d6ef50f7645f3242e827081cde33fac02'; bytes=8879  ; src='rel016-bridge-hash.txt' }
    @{ rel='UEMCPBridge\README.md';                                  sha='9ecc3cf9f6a6350ec7023fea5b8daf4b6d19e6d56339f6ae4356b58ad0c948de'; bytes=21510 ; src='rel016-bridge-hash.txt' }
    @{ rel='README.md';                                              sha='6fbe5db680fec18bbc152e5910074d887e8b50abf020a3e98d32439c56c0604f'; bytes=45741 ; src='rel016-ts-hash.txt' }
    @{ rel='CHANGELOG.md';                                           sha='34556b01cdb8237c2d27dc5ccbfaa96263cf1ecf990b726f6e079ebfa013fec3'; bytes=13031 ; src='rel016-ts-hash.txt' }
    @{ rel='uemcp\packages\server\package.json';                     sha='d9c0e97221d2b2bfa31a307e35bc93a43e28834ffd6260882226f5389d96527b'; bytes=922   ; src='rel016-ts-hash.txt' }
    @{ rel='uemcp\packages\server\src\mcp\buildServer.ts';           sha='a84f711758d778a22ffda5f3396c5dd589bb3205de20fe2719a147f7f456a631'; bytes=1720  ; src='rel016-ts-hash.txt' }
    @{ rel='dist-release\uemcp-server-0.1.6.tgz';                    sha='f652f2c3ff8b4659c030d865369363f708a9104b8ebfad1bebf979eaddc47bf5'; bytes=712856; src='rel016-ts-manifest.txt' }
)
Write-Output ("rel016-qa hashcheck [$Tag] generated: " + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))
Write-Output ("repo HEAD: " + (git rev-parse HEAD))
$match = 0; $mismatch = 0
foreach ($e in $expected) {
    $item = Get-Item -LiteralPath $e.rel
    $actual = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $sizeOk = ($item.Length -eq $e.bytes)
    $shaOk = ($actual -eq $e.sha)
    if ($shaOk -and $sizeOk) { $match++; $verdict = 'MATCH' } else { $mismatch++; $verdict = 'MISMATCH' }
    Write-Output ("{0}  {1}  bytes={2} (expected {3}, size_ok={4})  recorded={5}  actual={6}  src={7}" -f $verdict, $e.rel, $item.Length, $e.bytes, $sizeOk, $e.sha, $actual, $e.src)
}
Write-Output ("SUMMARY[" + $Tag + "] match=" + $match + " mismatch=" + $mismatch)
