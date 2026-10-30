# Pack the MCP server into an offline-installable tarball.
#
# The official `pnpm pack` artifact is not distributable: the server depends on
# the private workspace package `@uemcp/shared`, which is not published to npm.
# We therefore bundle everything with esbuild and hand-write a minimal manifest
# with no runtime dependencies.
#
# Usage:
#   pwsh -NoProfile -File scripts/pack-server.ps1 -Version 0.1.3
#   pwsh -NoProfile -File scripts/pack-server.ps1 -Version 0.1.3 -OutDir dist-release

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$OutDir = "dist-release",
  [switch]$KeepStage
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$uemcpDir = Join-Path $repoRoot "uemcp"
$serverEntry = Join-Path $uemcpDir "packages/server/src/index.ts"

if (-not (Test-Path $serverEntry)) { throw "server entry not found: $serverEntry" }

$esbuild = Get-ChildItem (Join-Path $uemcpDir "node_modules/.pnpm") -Directory -Filter "@esbuild+win32-x64*" |
  ForEach-Object { Join-Path $_.FullName "node_modules/@esbuild/win32-x64/esbuild.exe" } |
  Where-Object { Test-Path $_ } |
  Select-Object -First 1
if (-not $esbuild) { throw "esbuild not found under uemcp/node_modules/.pnpm (run pnpm install first)" }

$stage = Join-Path $env:TEMP ("uemcp-server-stage-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$pkg = Join-Path $stage "package"
New-Item -ItemType Directory -Path (Join-Path $pkg "dist") -Force | Out-Null

$bundle = Join-Path $pkg "dist/index.js"
& $esbuild $serverEntry --bundle --platform=node --format=esm --target=node20 "--outfile=$bundle" `
  "--banner:js=import { createRequire } from 'module'; const require = createRequire(import.meta.url);" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "esbuild failed with exit $LASTEXITCODE" }

Copy-Item (Join-Path $repoRoot "LICENSE") $pkg -Force
Copy-Item (Join-Path $repoRoot "README.md") $pkg -Force

$manifest = [ordered]@{
  name        = "@uemcp/server"
  version     = $Version
  description = "MCP server bridging AI clients to the Unreal Engine editor (UEMCP)"
  type        = "module"
  bin         = @{ uemcp = "dist/index.js" }
  main        = "dist/index.js"
  engines     = @{ node = ">=20" }
  files       = @("dist", "README.md", "LICENSE")
  license     = "MIT"
  dependencies = @{}
} | ConvertTo-Json -Depth 5
[IO.File]::WriteAllText((Join-Path $pkg "package.json"), $manifest, (New-Object Text.UTF8Encoding($false)))

Push-Location $pkg
try {
  $tgzName = (cmd /c "npm pack --silent" | Select-Object -Last 1).Trim()
} finally {
  Pop-Location
}
if ($LASTEXITCODE -ne 0 -or -not $tgzName) { throw "npm pack failed" }

$outPath = if ([IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $repoRoot $OutDir }
New-Item -ItemType Directory -Path $outPath -Force | Out-Null
$final = Join-Path $outPath $tgzName
Move-Item (Join-Path $pkg $tgzName) $final -Force

$size = (Get-Item $final).Length
$hash = (Get-FileHash $final -Algorithm SHA256).Hash.ToLower()
Write-Output ("pack-server: {0} ({1:N0} B, sha256 {2})" -f $tgzName, $size, $hash)

if (-not $KeepStage) { Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue }
