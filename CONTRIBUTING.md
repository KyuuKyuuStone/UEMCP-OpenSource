# Contributing to UEMCP

Thanks for helping. This project has two halves — a TypeScript MCP server (`uemcp/`) and a pure-Python editor plugin (`UEMCPBridge/`) — and both are covered by CI. Keep changes small and verify them locally before opening a pull request.

## Development environment

- **Node.js >= 20** and **pnpm 11** (or corepack)
- **Unreal Engine 5.4 or 5.7** for the plugin side; no C++ toolchain is required
- Windows is the primary platform (the editor plugin's self-checks and the smoke harness assume it)

Install dependencies once:

```bash
cd uemcp
pnpm install
```

## Local verification (run in this order)

`typecheck` consumes the declaration files emitted by `build`, so it **must run after** `build`. Running it first — or against a stale `dist/` — reports phantom errors; that ordering mistake is the root cause of DEF-1.

```bash
cd uemcp
cmd /c pnpm build        # 1. emit packages/*/dist and .d.ts
pnpm typecheck           # 2. type-check against the fresh output
pnpm test                # 3. node --test: unit + black-box
pnpm smoke               # 4. end-to-end smoke against a mock bridge
```

The four commands above are exactly what CI runs. If they pass locally, CI should pass too.

Notes:

- `cmd /c pnpm build` is used on Windows so the pnpm shim is resolved the same way CI resolves it.
- Tests use dedicated ports (18999/19001–19008 for smoke, 19101–19199 for unit tests) and never touch a running editor or the default 18777/18778 ports.
- Plugin-side, engine-free checks live in `UEMCPBridge/Tests/`; run them with Python 3.11+ (`python UEMCPBridge/Tests/check_error_codes.py`, etc.). Tests that need an editor are documented in `UEMCPBridge/Tests/SMOKE-REAL-ENGINE.md`.

## Pull requests

- **Keep it small** — one concern per PR makes review and bisecting possible.
- **Bring tests** — add or update a test for behaviour changes; a bug fix without a regression test will usually be sent back.
- **Do not edit files owned by another change** — avoid drive-by formatting, renames, or reordering in files unrelated to your fix. If you must touch them, explain why in the PR.
- **Describe verification** — paste the four commands you ran and their results.
- **No secrets** — never commit tokens, `bridge.json`, private keys, or editor logs containing them (see `SECURITY.md`).

Open a pull request against `main` and fill in the template. Maintainers may ask for a rebase; please keep the history readable.
