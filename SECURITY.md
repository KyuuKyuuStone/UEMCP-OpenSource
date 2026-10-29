# Security Policy

UEMCP is a **local developer tool**: the MCP server and the editor bridge both bind to `127.0.0.1` only, and all privileged operations are gated on both sides. This document covers supported versions, private reporting, the high-risk switches, and what we deliberately never log.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| < 0.1 | No |

Only the latest release and the current `main` receive security fixes.

## Reporting a vulnerability

Please **do not open a public issue**. Use one of these private channels:

1. **GitHub Security Advisories (preferred)** — open the repository's *Security* tab and choose *Report a vulnerability*. The report stays private until a fix is published.
2. **Email (placeholder)** — `security@example.com` if advisories are unavailable.

Please include:

- affected version / commit and engine version (UE 5.4 or 5.7);
- the MCP client and transport in use;
- reproduction steps, expected vs. actual behaviour, and the error code;
- any log excerpt **with tokens and source code redacted**.

## Response expectations

- **Acknowledgement** within 5 business days.
- **Triage and severity** within 10 business days.
- For confirmed high-severity issues we aim to ship a fix or mitigation as soon as practical, then publish a coordinated advisory. Please give us reasonable time before public disclosure.

## High-risk switches

Privileged behaviour is off by default and requires **both** the server policy and the bridge configuration to allow it:

| Switch | Server side | Bridge side | What it enables |
| --- | --- | --- | --- |
| Writes | `--policy standard` (or `full`) | `allowWrite: true` | `ue_actor_edit`, level save/open, material writes, Blueprint compile |
| Console | `--policy full --allow-console` | `allowConsole: true` | `ue_console_command` (allowlist-restricted) |
| Python | `--policy full --allow-exec` | `allowExec: true` | `ue_python_exec` — arbitrary Python on the editor game thread |

`allowExec` is equivalent to handing the editor process to the caller: there is no sandbox and a running snippet cannot be interrupted. Do not enable it for demos, screen recordings, or CI.

The bridge also enforces a global rate limit (default 30 req/s, token bucket). Each rejected request returns `RATE_LIMITED` without touching the editor.

## What we never log

- **Tokens**: the bridge token is generated per editor start, compared in constant time, and only written to the local discovery file (`~/.uemcp/bridge.json`, mode 0600 where supported). It never appears in audit logs or error details.
- **Python source**: `ue_python_exec` audit records store `codeSha256`, `codeLength` and `mode` — not the source.
- **Secrets in details**: error `details` are capped at 16 KiB and the server audit log never records tokens or full source.

## Never post these publicly

- the bridge token or the contents of `~/.uemcp/bridge.json`;
- complete Python snippets sent to `ue_python_exec`;
- discovery files, private keys, or API keys found in a project;
- unredacted editor logs that may contain any of the above.

If you accidentally exposed a token, restart the editor — a new token is generated on every start.

---

## 中文摘要

- **支持版本**：0.1.x；更早版本不再接收安全修复。
- **私密上报**：优先使用 GitHub Security Advisories（仓库 *Security* → *Report a vulnerability*），其次邮件占位 `security@example.com`；**不要**开公开 issue。
- **响应时限**：5 个工作日内确认，10 个工作日内给出定级与处置意见；高危问题尽快修复后再协同披露。
- **高风险开关**：`allowExec` / `allowConsole` / `allowWrite` 均为双端门（Server 策略 × Bridge 配置），默认全关；`allowExec` 等于把编辑器进程交给调用方，无沙箱、不可中断。
- **不记录**：token（每次启动轮换，仅写入 `~/.uemcp/bridge.json`）、完整 Python 源码（只记 hash/长度/模式）、错误 details 中的敏感内容。
- **请勿公开**：token、`bridge.json` 内容、完整 Python 代码、含密钥的发现文件或未脱敏日志。若不慎泄露 token，重启编辑器即可轮换。
