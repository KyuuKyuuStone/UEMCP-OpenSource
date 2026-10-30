# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Bilingual README (中文 / English) with a language switcher, plus a download section that links the release archives directly.
- GitHub Actions CI (build, typecheck, test and smoke on `windows-latest`) and issue templates for bug reports and feature requests.
- `SECURITY.md`, `CHANGELOG.md`, `CONTRIBUTING.md` and a pull-request template.
- Documented known limitation: when the editor window loses focus, UE throttles ticks (about 3.1 fps in our test) and `viewport.capture` may return `CAPTURE_TIMEOUT`; keep the window foreground, raise `timeoutMs`, or retry.
- Offline-installable server package (`uemcp-server-0.1.0.tgz`, an esbuild full bundle); the official `pnpm pack` artifact is not distributable because `@uemcp/shared` is not on the npm registry.
- Roadmap document (`docs/UEMCP-路线图.md`: done / in progress / planned / explicitly out of scope, each with a reason and an alternative) plus documented notes on three usage pitfalls: `Plugins/` upgrade backups shadowing the new build, identifying builds via `/health` `buildHash` / `sourcePath` (new in this release), and two error-prone Python binding return types (`project_world_to_screen` → `Vector2D`, `TraceTypeQuery` member names).

### Changed

- README now states UE 5.4 / 5.7 support (tested on 5.4.4 / 5.7.4) and the current count of no-engine self-check scripts (11).
- README Cursor note now points to the verified `/sse` fallback instead of leaving the 0.46+ `/mcp` path unexplained.
- Test harness prefers `Saved/Logs/<ProjectName>.log` and adds an optional foreground/capture-retry assist (`-NoFocusAssist` to disable).
- Documentation cleanup: removed the pre-implementation README draft and replaced internal session IDs and local paths in `docs/` with placeholders.
- README known limitations now cover `list_dirty` after spawn/delete, the current `blueprint.query` data limits, and that `delete` confirmation is enforced by the server rather than the bridge.

### Fixed

- Harness could read a newer unrelated log (`cef3.log`) instead of the project log, causing a false failure.
- `viewport.capture` no longer blocks until the server-side 45 s timeout: the bridge now bounds the capture itself, reports `CAPTURE_TIMEOUT` with render-environment diagnostics, and stops forcing the game view. Root cause confirmed as UE throttling ticks (~3 fps) while the editor window is minimized or unfocused — foreground capture was measured at 132–976 ms.
- `blueprint.query` no longer returns an "empty success": when parent class, variables and graphs are all empty the handler raises `UNSUPPORTED` with per-property diagnostics. Reading blueprint structure still depends on engine Python exposure and remains unreliable.
- `blueprint.query` now reads real structure where the engine allows it: `parentClass`, `generatedClass` and `blueprintType` come from Asset Registry tags (verified on 5.4.4: `Actor`), and `EventGraph` / `UserConstructionScript` / `AnimGraph` are discovered through `BlueprintEditorLibrary.find_graph`. `variables` stay unavailable because `UBlueprint.NewVariables` is a protected property — the response now says `variablesUnavailable=NEW_VARIABLES_PROTECTED_IN_ENGINE_PYTHON` instead of returning an empty list.
- JSON and SSE responses (`/mcp`, `/health`, error envelopes) now carry an explicit `charset=utf-8`, so clients that default to Latin-1 (e.g. PowerShell 5.1 `Invoke-WebRequest`) no longer garble non-ASCII names.


## [0.1.0] - 2026-10-28

First public release. Distributed as three release assets: `UEMCPBridge-5.4.zip`, `UEMCPBridge-5.7.zip` and `SHA256SUMS.txt`.

### Added

- **UEMCPBridge** — a pure-Python editor plugin (no C++ modules, no build step) that exposes `/health`, `/rpc` and `/events` on loopback and runs every `unreal.*` call through a single game-thread queue.
- **10 MCP tools** — editor status, actor query/edit, level control, asset search, material parameters, viewport capture, Blueprint query/compile, console commands and Python execution.
- **Three transports** — Streamable HTTP (`/mcp`), legacy SSE (`/sse`) and stdio.
- **Dual permission gates** — server policy × bridge configuration, with `allowWrite`, `allowConsole` and `allowExec` off by default.
- **Bridge-side global rate limiting** — 30 req/s token bucket with `RATE_LIMITED` (HTTP 429) before a job is queued.
- **Tool-level `outputSchema`** — structured results with `structuredContent.error` on failures.
- **UE 5.7 compatibility** — per-call-point audit against UE 5.4.4 and 5.7.4, with dual-engine packages.
- Discovery files under `~/.uemcp/`, token rotation on every editor start, audit logging that excludes tokens and Python source, and the `CAPABILITY_UNAVAILABLE` boundary for Blueprint node editing.

[Unreleased]: https://github.com/KyuuKyuuStone/UEMCP-OpenSource/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases/tag/v0.1.0
