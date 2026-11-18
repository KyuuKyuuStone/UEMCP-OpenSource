$ErrorActionPreference = 'Continue'
$repo = 'C:\UE5_P\5.4\UEMCP'
$tool = Join-Path $repo 'feedback-review\qa-tools\qa-exec-bridge.mjs'
$outDir = Join-Path $repo 'feedback-review\logs\qasmoke-exec-S3-matrix'
$driveLog = Join-Path $outDir 'driver.log'
$cases = Get-Content (Join-Path $outDir 's3-cases.json') -Raw | ConvertFrom-Json
('DRIVER START ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  S3 KeepPrepared window, 5.7 UEMCP_Smoke_Blank gates-OFF matrix supplement') | Out-File $driveLog -Encoding UTF8
foreach ($c in $cases) {
  $pf = Join-Path $outDir ('params-' + $c.slug + '.json')
  ($c.params | ConvertTo-Json -Depth 10 -Compress) | Out-File $pf -Encoding UTF8 -NoNewline
  $resp = Join-Path $outDir ('resp-' + $c.slug + '.json')
  $line = (& node $tool rpc $c.method --params-file $pf --out $resp 2>&1) -join ' '
  ('CASE ' + $c.slug + ' exit=' + $LASTEXITCODE + ' :: ' + $line) | Add-Content $driveLog -Encoding UTF8
}
'--- health (18 keys contract) ---' | Add-Content $driveLog -Encoding UTF8
$hp = & node $tool health 2>&1
($hp -join ' ') | Add-Content $driveLog -Encoding UTF8
$hp | Out-File (Join-Path $outDir 'resp-health.json') -Encoding UTF8
'--- asset.search paging (nextOffset null passthrough) ---' | Add-Content $driveLog -Encoding UTF8
$pg1 = '{"path":"/Engine/BasicShapes","limit":2,"offset":0}'
$pg1 | Out-File (Join-Path $outDir 'params-paging-page1.json') -Encoding UTF8 -NoNewline
$l1 = (& node $tool rpc 'asset.search' --params-file (Join-Path $outDir 'params-paging-page1.json') --out (Join-Path $outDir 'resp-paging-page1.json') 2>&1) -join ' '
('CASE paging-page1 :: ' + $l1) | Add-Content $driveLog -Encoding UTF8
$pg2 = '{"path":"/Engine/BasicShapes","limit":500,"offset":0}'
$pg2 | Out-File (Join-Path $outDir 'params-paging-singlepage.json') -Encoding UTF8 -NoNewline
$l2 = (& node $tool rpc 'asset.search' --params-file (Join-Path $outDir 'params-paging-singlepage.json') --out (Join-Path $outDir 'resp-paging-singlepage.json') 2>&1) -join ' '
('CASE paging-singlepage(limit500) :: ' + $l2) | Add-Content $driveLog -Encoding UTF8
'--- BFS truncated warning (>50 seeds, includeDependencies) ---' | Add-Content $driveLog -Encoding UTF8
$pg3 = '{"path":"/Engine","limit":500,"includeDependencies":true}'
$pg3 | Out-File (Join-Path $outDir 'params-bfs-truncated.json') -Encoding UTF8 -NoNewline
$l3 = (& node $tool rpc 'asset.search' --params-file (Join-Path $outDir 'params-bfs-truncated.json') --out (Join-Path $outDir 'resp-bfs-truncated.json') --timeout 120000 2>&1) -join ' '
('CASE bfs-truncated :: ' + $l3) | Add-Content $driveLog -Encoding UTF8
'DRIVER END ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Add-Content $driveLog -Encoding UTF8
Write-Output 'MATRIX DONE'
Get-Content $driveLog
