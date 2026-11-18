$OUT = 'C:\UE5_P\5.4\UEMCP\feedback-review\logs\qasmoke-exec-S4'
foreach ($f in (Get-ChildItem $OUT -Filter 'resp-*.json' | Sort-Object LastWriteTime)) {
  $j = Get-Content $f.FullName -Raw | ConvertFrom-Json
  $req = $j.request
  $resp = $j.response
  $r = $resp.result
  $e = $resp.error
  $pj = ('' + ($req.params | ConvertTo-Json -Compress -Depth 6)); if ($pj.Length -gt 90) { $pj = $pj.Substring(0, 90) + '...' }
  $ts = [string]$j.ts
  if ($r -and $r.ok) {
    $q = $r.meta.queuedMs
    Write-Output ($ts + ' ' + $f.Name + ' ' + $req.method + ' http=' + $j.httpStatus + ' ok=true dur=' + $r.meta.durationMs + ' queuedMs=' + $q + ' params=' + $pj)
  } elseif ($e) {
    Write-Output ($ts + ' ' + $f.Name + ' ' + $req.method + ' http=' + $j.httpStatus + ' ERR code=' + $e.code + ' ' + ('' + $e.data.errorCode) + ' retryable=' + $e.data.retryable + ' origin=' + $e.data.details.origin + ' stage=' + $e.data.details.stage + ' msg=' + ('' + $e.message).Substring(0, [Math]::Min(80, ('' + $e.message).Length)) + ' params=' + $pj)
  } else {
    Write-Output ($ts + ' ' + $f.Name + ' ' + $req.method + ' http=' + $j.httpStatus + ' SHAPE-OTHER params=' + $pj)
  }
}
