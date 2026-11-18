# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2026-11-18

### Changed

- Version bump 0.1.5 → 0.1.6: `SERVER_VERSION` (`uemcp/packages/server/src/mcp/buildServer.ts`, flows into `serverInfo.version` and `/health`) and `packages/server/package.json`; the offline artifact is now `uemcp-server-0.1.6.tgz`, named by `scripts/pack-server.ps1 -Version 0.1.6` (the artifact name comes from the script's `-Version` parameter, not from `package.json`). The root README (CN and EN) download links, tgz file name and install command now point at the v0.1.6 release assets.
- Documentation synced with the 0.1.5 second-batch acceptance: root README and `uemcp/README-DEV.md` self-test counts corrected (smoke 87/87, `node --test` 82 cases; `outputSchema` registration documented as delivered), and `docs/UEMCP-架构设计.md` §6.5 audit-retention wording now matches shipped behaviour (`RETENTION_DAYS = 30` fixed constant, not configurable).

### Fixed

Server-side items from the 0.1.5 second batch — all present in this release and covered by the four release gates (build / typecheck / test / smoke) run on this tree:

- Bridge watchdog: on a transport drop the server keeps the last-known bridge identity (`instanceId` / `buildHash` / `buildTime` / `sourcePath` / `capabilities` / `rateLimit` / `policies` / `bridgeProtocol` / `schemaVersion`) instead of silently clearing it; `markDown` clears the cache completely so no stale data is ever presented as current.
- Audit records now carry the bridge error provenance (`origin` / `stage`), an effective-policy snapshot (`policySnapshot`: server mode/source/switches plus bridge policies and rate limit), the discovery `schemaVersion`, and — while a bridge connection is up — the bridge build identity; read-only tool calls are audited like every other tool; the `initialize` handler backfills `clientInfo`, fixing the previously always-absent `client` field; stdio records carry no `sessionId` (HTTP only).
- Audit retention is the fixed `RETENTION_DAYS = 30` constant, purged at startup; 3 consecutive audit-write failures now also warn on stderr, in addition to flagging `auditDegraded=true` in `/health`.
- Discovery files gained `stale` / `staleReason` / `staleAt`; an unexpected `schemaVersion` logs a `discovery_schema_version_mismatch` warning instead of being silently accepted; `/health` passes the extended fields through.
- `viewport.capture`: the server bounds the call at 20 s and pre-checks the pixel-streaming capability, returning `CAPABILITY_UNAVAILABLE` when the environment cannot serve it.
- Tool `outputSchema`: `registerTools` publishes the success/failure dual-shape schema for every visible tool (asserted by the smoke policy matrix and a regression test).

> 以下四条来自业务团队《UEMCP v0.1.4 复测缺陷单》（编号 D1–D4）。**代码修复随 0.1.6 合入，合入后复核**——下列条目描述的是修复后的行为。
>
> The four entries below come from the business team's v0.1.4 defect report (D1–D4). **The code fixes land with 0.1.6 and have been re-verified after merge** — the entries below describe the fixed behaviour.

- **D1**: `ue_viewport_capture` now passes `activateWindow` through to the bridge (the 0.1.4 server schema rejected it with `INVALID_ARGUMENT: Unrecognized key`, so the parameter only worked when calling the bridge port directly). A successful capture returns `activation{requested, ok, editorPid, foregroundPid, hwnd, isIconic, alreadyForeground}`.
- **D2**: `log.query` level inference now recognises implicit `LogXxx:` lines (no explicit `: Error:` / `: Warning:` / `: Display:` / `: Verbose:` segment → counted as `Log`); lines that match no rule keep `level=null` and are excluded from `levels` filtering, and the response reports an `unclassified` count. In 0.1.4, `levels:["Log"]` silently missed implicit `LogXxx:` lines (`matched 0`).
- **D3**: `object.reflect` resolves bare class names (e.g. `CustomDomainCmdHandler`) via derived-class/instance search instead of requiring a full object path; on failure the error carries `candidates` with the matched full paths.
- **D4**: `object.call` accepts `captureLog:true` — the call returns the log lines captured inside the call window (`logLines[{lineNo, level, text}]`), so `void` functions no longer leave the caller with only `{"returned":null,"returnedVoid":true}`.

## [0.1.4] - 2026-10-30

Plugin and server now share the version number (`0.1.4`), and `/health` reports `buildHash` / `sourcePath` so an upgrade can be verified instead of assumed.

### Added

- **Generic primitives** — no change to the user's own framework is required:
  - `ue_reflect` (`object.reflect`): list the callable functions exposed by any object or level actor.
  - `ue_call_function` (`object.call`): call any `BlueprintCallable` function by name with JSON arguments and return its return value (`returnedVoid:true` for void). Write-class: not registered under `read-only`; needs bridge `allowWrite`.
  - `ue_log_query` (`log.query`): search the editor log by regex/level/time window; read-only and restricted to the project's `Saved/Logs/` directory.
- `ue_pie_control` (`pie.control`): start/stop/restart/query Play-In-Editor, optional `simulate`. Play-In-Editor no longer requires `--allow-exec` — write actions only pass the `allowWrite` gate, and `status` stays available under read-only.
- `ue_policy_explain`: per-tool visibility with the reason (`server.policy` / `--allow-console` / `--allow-exec`).
- `viewport.capture`: optional `activateWindow` (restore + verify foreground), absolute `path`, plus `sha256` / `mtime` / `bytes` / `stats{uniqueColors, nonZeroRatio, isBlack}`; a file that lands within a 500 ms grace after a timeout is returned with `partial:true` instead of failing.
- `/health`: `buildHash` (sha256 over every plugin Python file), `buildTime`, `sourcePath` (the plugin directory actually loaded) and `instanceId`.
- No-engine self-check count grew to 16 (`check_plugin_version.py`, `test_pie_control.py`, `test_viewport_capture.py`, `test_object_call.py`, `test_log_query.py`).

### Fixed

- **Session pool never shrank**: when the pool is full the server LRU-evicts idle streamable sessions (sessions holding a live SSE stream are never evicted) instead of rejecting `initialize` with 429; 429 carries `retryAfterMs`, `initialize` advertises `Mcp-Session-Expires-In-Ms`, and `404 -32001` carries `hint: "reinitialize"` + `ttlMs`. The cap is configurable via `--max-sessions` / `UEMCP_MAX_SESSIONS`.
- `viewport.capture` with `activateWindow` now **fails fast** with `EDITOR_UNSAFE_STATE` (`reason=window_not_foreground`) when the window stays minimized or cannot be brought forward, instead of waiting for the timeout.
- `blueprint.query` now reads real structure where the engine allows it: parent class / generated class / Blueprint type / `EventGraph` / `UserConstructionScript` / `AnimGraph` (Asset Registry tags plus named graph lookup). Variable lists and per-graph node counts remain unreadable — the response says so via `variablesUnavailable` rather than returning a fake empty array.
- JSON and SSE responses carry an explicit `charset=utf-8`.
- `check_plugin_version.py` guards against `.uplugin` and code versions drifting apart.

## [Unreleased]

### Added

- Bilingual README (中文 / English) with a language switcher, plus a download section that links the release archives directly.
- GitHub Actions CI (build, typecheck, test and smoke on `windows-latest`) and issue templates for bug reports and feature requests.
- `SECURITY.md`, `CHANGELOG.md`, `CONTRIBUTING.md` and a pull-request template.
- Documented known limitation: when the editor window loses focus, UE throttles ticks (about 3.1 fps in our test) and `viewport.capture` may return `CAPTURE_TIMEOUT`; keep the window foreground, raise `timeoutMs`, or retry.
- Offline-installable server package (`uemcp-server-0.1.0.tgz`, an esbuild full bundle); the official `pnpm pack` artifact is not distributable because `@uemcp/shared` is not on the npm registry.
- Roadmap document (`docs/UEMCP-路线图.md`: done / in progress / planned / explicitly out of scope, each with a reason and an alternative) plus documented notes on three usage pitfalls: `Plugins/` upgrade backups shadowing the new build, identifying builds via `/health` `buildHash` / `sourcePath` (new in this release), and two error-prone Python binding return types (`project_world_to_screen` → `Vector2D`, `TraceTypeQuery` member names).
- Session-pool hardening: when the pool is full the server now LRU-evicts the least-recently-active idle streamable session (sessions holding an open standalone SSE stream are never evicted) instead of rejecting every `initialize` with 429; a pool that is truly full (all sessions hold live SSE streams) returns 429 with `retryAfterMs` and the current pool size, `initialize` responses advertise the idle TTL via `Mcp-Session-Expires-In-Ms`, `404 -32001` errors carry `hint: "reinitialize"` plus `ttlMs` so clients can self-heal, and the pool cap is configurable via `--max-sessions` / `UEMCP_MAX_SESSIONS` (default 32; `--session-ttl-ms` / `--session-sweep-ms` remain configurable for the 30 min idle TTL and the 60 s sweep).

### Changed

- README now states UE 5.4 / 5.7 support (tested on 5.4.4 / 5.7.4) and the current count of no-engine self-check scripts (16).
- README Cursor note now points to the verified `/sse` fallback instead of leaving the 0.46+ `/mcp` path unexplained.
- Test harness prefers `Saved/Logs/<ProjectName>.log` and adds an optional foreground/capture-retry assist (`-NoFocusAssist` to disable).
- Documentation cleanup: removed the pre-implementation README draft and replaced internal session IDs and local paths in `docs/` with placeholders.
- README known limitations now cover `list_dirty` after spawn/delete, the current `blueprint.query` data limits, and that `delete` confirmation is enforced by the server rather than the bridge.

### Fixed

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
