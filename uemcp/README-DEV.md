# UEMCP Server — 开发文档（MVP）

面向开发者：构建、运行、自测。产品设计见 `Docs/UEMCP-架构设计.md`（v0.2.0，单一事实来源）。

## 1. 目录结构

```text
uemcp/
├─ package.json               # pnpm workspace 根
├─ pnpm-workspace.yaml
├─ tsconfig.base.json
├─ README-DEV.md              # 本文
├─ scripts/
│  ├─ mock-bridge.mjs         # 本地 mock bridge（HTTP JSON-RPC，自测用）
│  └─ smoke.mjs               # Server 自测脚本（61 项断言）
├─ packages/shared/           # @uemcp/shared：工具名、zod Schema、错误码、类型
│  └─ src/
│     ├─ index.ts  toolNames.ts  errors.ts  types.ts
│     └─ schemas/ common.ts status.ts actors.ts levels.ts assets.ts
│                  materials.ts viewport.ts console.ts python.ts blueprints.ts
└─ packages/server/           # @uemcp/server：CLI、传输、bridge、策略、审计、工具
   ├─ tsup.config.ts
   └─ src/
      ├─ index.ts             # CLI 入口（bin: uemcp）
      ├─ config.ts  logger.ts  policy.ts  audit.ts  confirm.ts
      ├─ mcp/    buildServer.ts registerTools.ts annotations.ts
      ├─ transports/ http.ts（/mcp /sse /messages /health） stdio.ts
      ├─ bridge/ discovery.ts client.ts watchdog.ts
      └─ tools/  status.ts actorQuery.ts actorEdit.ts levelControl.ts
                 assetSearch.ts materialParams.ts viewportCapture.ts
                 consoleCommand.ts pythonExec.ts blueprint.ts index.ts
```

技术栈：Node ≥ 20（本机 24.18）、TypeScript 5.x、`@modelcontextprotocol/sdk` 1.32.1、zod 3.25、express 4.21、tsup 8、`zod-to-json-schema` 3.25。

## 2. 构建

```bash
cd uemcp
pnpm install         # 1. 安装依赖（顺序必须是 install → build → typecheck → smoke → test）
pnpm build           # 2. = pnpm -r build（shared: tsc；server: tsup → dist/index.js）
pnpm typecheck       # 3. 两个包 tsc --noEmit（必须在 build 之后：干净树上先跑会报 TS2307 找不到构建产物引用，双重实测确认）
node scripts/smoke.mjs   # 4. Server 自测（mock bridge，无需真实 Bridge；见 §5；也可 pnpm smoke）
pnpm test            # 5. 单元/黑盒测试（node --test，用例见 uemcp/tests/）
```

> 顺序约束：`typecheck` 依赖 `build` 产物（干净树上 typecheck 先于 build 必报 TS2307），`smoke`/`test` 依赖 build 产出的 `dist/index.js`。

实测输出（2026-10-20）：`pnpm install` Done（178 包）；`pnpm build` shared `tsc` 无错误、server `tsup` ESM+DTS `Build success`；`pnpm typecheck` 两包 Done，无错误。

> 首次 install 若提示 `Ignored build scripts: esbuild`，`pnpm-workspace.yaml` 已含 `allowBuilds: esbuild: true`，重跑 `pnpm install` 即可。

## 3. 运行

```bash
# HTTP（默认 127.0.0.1:18777；默认策略 read-only）
node packages/server/dist/index.js --transport http --policy standard

# stdio（stdout 仅 MCP 帧，日志走 stderr）
node packages/server/dist/index.js --transport stdio

# P2 工具（full + 开关；桥接端还需对应 allowConsole/allowExec）
node packages/server/dist/index.js --transport http --policy full \
  --allow-console --allow-exec --allow-destructive

# 常用参数
#   --port N / --policy read-only|standard|full / --disable-legacy-sse
#   --bridge-url URL / --bridge-token T / --project <dir> / --auth-token T
#   --session-ttl-ms N / --session-sweep-ms N   （TTL 覆盖，测试用，D4）
# 环境变量：UEMCP_HTTP_PORT UEMCP_BRIDGE_URL UEMCP_BRIDGE_TOKEN UEMCP_AUTH_TOKEN
#           UEMCP_POLICY UEMCP_ALLOW_DESTRUCTIVE/CONSOLE/EXEC UEMCP_AUDIT_DIR
```

端口被占：**2 秒内 exit code 2**，stderr 一行 `{"level":"error","event":"http_bind_failed",...}`，不换端口不重试（§2.3/D10）。

客户端接入：`POST/GET/DELETE http://127.0.0.1:18777/mcp`（Streamable HTTP）；`GET /sse` + `POST /messages?sessionId=`（旧版 SSE）；`GET /health`。

## 4. 服务部署（不要用前台/临时后台方式运行）

前台或随 agent/终端会话启动的后台进程会在会话结束时被回收（实测：启动约 2 分钟后 exit 1、无堆栈）。**请用分离进程脚本运行**：

```powershell
# 启动（Start-Process 分离进程 + 隐藏窗口；stdout/stderr 重定向到 logs/；写 logs/server.pid）
powershell -ExecutionPolicy Bypass -File scripts\start-server.ps1 -Port 18777 -Policy standard
#   可选：-ExtraArgs "--allow-console --allow-exec --allow-destructive"
#   日志：logs\server-YYYY-MM-DD.log（应用 JSON 日志，含启动参数/pid/端口/bridge 变化/退出原因）
#         logs\server-stdout|stderr-YYYY-MM-DD.log（进程级输出）
#   /health 暴露 pid 与 logPath，可核对实际进程与日志位置

# 停止（按 logs/server.pid）
powershell -ExecutionPolicy Bypass -File scripts\stop-server.ps1
```

进程健壮性：`uncaughtException` → 记录（含堆栈）后 exit 1；`unhandledRejection` → 记录不退出（避免瞬态 rejection 打断本地服务）；`SIGINT/SIGTERM/SIGBREAK` → 记录信号名与时间后清理退出。日志双写 stderr + `logs/server-YYYY-MM-DD.log`（按天切换，`UEMCP_LOG_DIR` 可覆盖目录）。

实测（2026-10-20）：`start-server.ps1 -Port 18877 -Policy standard` → /health ok（pid/logPath 暴露，bridge.connected=true 连接真实 18778 桥接）；3 分钟存活观察通过（uptimeSec=201，pid 不变）；调用方 shell 结束后进程仍存活（分离进程）；tools/call ue_editor_status 经真实 Bridge 返回 5.4.4-35576357 真实数据；`stop-server.ps1` 后端口关闭、pid 文件删除。

## 5. 自测（Bridge 尚未就绪 → mock bridge）

```bash
node scripts/smoke.mjs
```

smoke 自行完成：临时 HOME → 启动 mock bridge（写 `~/.uemcp/bridge.json` 发现文件）→ 启动多个策略的 Server（走真实发现链路）→ 61 项断言 → 清理。

**实测结果（2026-10-20，Node v24.18.0，审查修复后）：`SMOKE RESULT: 71/71 passed`**

覆盖（对应测试计划用例编号）：

| 验证点 | 用例 |
|---|---|
| /health（含 bridge.connected、无 token 泄漏） | §3.3 |
| initialize（session 头、版本协商 2025-06-18 / 2024-11-05 / 未来版本回退） | PROTO-01/17 |
| notifications/initialized 202 空 body | PROTO-02 |
| tools/list 策略矩阵：read-only=7（混合工具 action enum 收窄 + readOnlyHint）、standard=8、full+双开关=10 | PROTO-03、SEC-01(a) |
| tools/call 成功封装（ok/data/warnings/meta、policies.mode 服务端填充） | PROTO-04、TOOL-01 近似 |
| 协议层错误：非法 JSON 400/-32700、未知 method 404/-32601、arguments 数组 400/-32602 INVALID_PARAMS、未知工具 400/-32602、缺会话 400、未知会话 404/-32001 | PROTO-05/06/10/11/12b/12c |
| 工具层错误：sections 非法 → 200+isError+INVALID_ARGUMENT+issues[]+content 前缀；filter.class 未知 → CLASS_NOT_FOUND+details.className | PROTO-12、TOOL-05(c) |
| 隐藏工具直调：ue_actor_edit → TOOL_DISABLED gate=server.policy；ue_python_exec → gate=server.allowExec；混合工具写 action → INVALID_ARGUMENT | SEC-01(b)(c)(d)(e)(f) |
| 双重权限门：桥接 allowExec=false → EXEC_DISABLED gate=bridge.allowExec；allowConsole=false → PERMISSION_DENIED gate=bridge.allowConsole | SEC-11、SEC-11c |
| P2 正常路径：python eval 1+1 → result=2；console quit → COMMAND_NOT_ALLOWED；stat fps → dispatched+outputAvailable=false | TOOL-32、TOOL-31 |
| viewport.capture returnMode=image：小 PNG → image 内容块（base64/PNG 头校验）；>8MiB → 无 image 块 + IMAGE_TOO_LARGE_FOR_INLINE 降级 | TOOL-26 |
| --project 发现：尾斜杠规范化命中、大小写不敏感匹配（目录扫描）、不匹配硬失败 BRIDGE_UNAVAILABLE 且不回退 bridge.json | 审查 Critical-2 |
| 速率限制：并发突发 >40 → 429/-32012 RATE_LIMITED（协议层形态，无 result），限流前 200，退避后恢复 | 审查 Major-6、SEC-14 |
| Host 421 / Origin 403（INVALID_REQUEST 层位） | SEC-04/05 |
| DELETE /mcp 204 → 后续 404/-32001 | PROTO-07 |
| 审计：P2 记录含 codeSha256/codeLength、无源码原文、无 token | SEC-12、TOOL-33 近似 |
| 桥接不可达 → BRIDGE_UNAVAILABLE retryable 且 /health 存活 | RES-03 |
| 端口占用 → exit 2、stderr http_bind_failed JSON、2s 内 | RES-06 |
| stdio：stdout 逐行合法 JSON-RPC、tools/list=8、stderr JSON 日志 | PROTO-16 |
| 会话 TTL 过期（--session-ttl-ms）→ 404/-32001 | PROTO-08 |
| 32 会话上限 → 第 33 个 initialize 429 | PROTO-09 |
| 默认参数启动：127.0.0.1:18777、默认 read-only=7 工具 | SEC-02 |

旧版 SSE 单独验证（手工脚本，未纳入 smoke）：
`GET /sse` → `Content-Type: text/event-stream`，首个事件 `event: endpoint / data: /messages?sessionId=<uuid>` → `POST /messages` initialize 返回 **202** → 响应经 SSE 流下发（`protocolVersion: 2024-11-05` 回显）；`--disable-legacy-sse` 后 `GET /sse` → **404**（PROTO-13/14/15 的服务端侧行为）。

## 6. 实现契约要点（与架构文档的对应）

- **错误模型（§2.9）**：工具失败一律 HTTP 200 + `isError:true` + `structuredContent.error`（`content[0].text` 以 `"<CODE>: <message>"` 开头）；信封/未知工具 400 + `-32602 INVALID_PARAMS`；未知 method 404 + `-32601`；非法 JSON 400 + `-32700`；会话 404 + `-32001`。为此**未使用** SDK `registerTool`（其 zod 自动校验无法携带 structuredContent.error），改用低层 `setRequestHandler` 自控 tools/call 与 tools/list 路由（`src/mcp/registerTools.ts`）。
- **策略（§5.0.3/§5.11/D12）**：注册全部 10 个工具（handler 内做策略门）；tools/list 按策略过滤；read-only 下 3 个混合工具注册收窄 schema（zod 层拒绝写 action → INVALID_ARGUMENT；handler 二次校验 → PERMISSION_DENIED gate=server.policy）。
- **确认（§6.3/D11）**：delete/save_all/open 丢弃未保存内容 → elicitation 优先（未实测，见 §7），否则 `--allow-destructive`；console/exec 由各自开关兼作策略级确认（审计 confirmationMode=policy + confirmationSwitch）。
- **发现（§2.4）**：--bridge-url > --project（bridges/<sha1-16>.json）> ~/.uemcp/bridge.json > 默认 18778；校验 schemaVersion/pid 存活/GET /health（app=uemcp-bridge、pid、startedAt 一致）；陈旧逐级跳过；调用失败自动重发现一次（token 轮换自愈）。--project 匹配的平台语义：Windows 大小写不敏感、POSIX 大小写敏感（复审 Minor-3）。
- **viewport.capture 内联（§5.7 + 主管裁决）**：桥接仅返回文件路径；Server 读文件（同机）base64 编码，≤8 MiB 输出 image 内容块，超限/无路径/读失败降级 file + `IMAGE_TOO_LARGE_FOR_INLINE`；桥接若返回 `base64Data` 则优先（向前兼容）。
- **审计（§6.5）**：`~/.uemcp/audit/YYYY-MM-DD.jsonl`（UEMCP_AUDIT_DIR 可覆盖，文件创建 mode 0600、目录 mode 0700）；P1/P2 记录；python 仅 codeSha256/codeLength——**永不记录源码**（审查 Major-3：已删除 --audit-python-source 开关，传旧参数报 Unknown option 并退出）；console 记全文；写失败不阻塞、连续 3 次 `/health` 标 `auditDegraded:true`；启动清理 30 天前文件。
- **速率限制（§6.7，审查 Major-6）**：HTTP 层每会话令牌桶 20 req/s、突发 40；超限协议层 429 + `-32012 RATE_LIMITED`（无 result）；stdio 不适用；会话结束清桶。
- **桥接重试（审查 Major-4）**：`bridge.call` 仅对显式 `retriable:true` 的只读/幂等方法（status/actor.query/asset.search/viewport.capture/只读 action）在 BRIDGE_UNAVAILABLE 时自动重发现重试一次；写方法（actor.edit/level 写 action/material set/blueprint compile/console/python）不自动重试，直接返回可重试错误并提示确认后重发。HTTP 401（token 被拒）按 BRIDGE_UNAVAILABLE 处理以触发重发现。
- **工具级超时（审查 Major-1）**：`ToolDef.timeoutMs` 已消费（blueprint 60s / viewport.capture 45s / 其余 30s / python.exec 用户 timeoutMs 与 30s 取大），client 统一 clamp 上限 120s（§2.6）。
- **console/exec 确认（审查 Major-2）**：与 actorEdit 同模式——elicitation 优先（approved → confirmationMode=elicitation；declined → CONFIRMATION_DENIED），客户端不支持时 `--allow-console`/`--allow-exec` 兼作策略级确认（policy + confirmationSwitch 入审计）。
- **console 白名单单一来源（审查 Major-5）**：Server 端不再维护第二份白名单/拒绝表（shared 中的死代码已删除），单一来源在 Bridge 侧（§5.8）。
- **传输（§3）**：Streamable HTTP（POST 建/用会话、GET SSE 流、DELETE 204）；旧 SSE（/sse endpoint 事件 + /messages + 15s `: ping` 心跳）；stdio。会话 TTL 30min/60s 清扫、上限 32（429）。Host 白名单 421、Origin 白名单 403、OPTIONS 405、body 8MiB 413、可选 Bearer 401（timingSafeEqual）。

## 7. 变更文件清单

全部新增于 `uemcp/` 下（未改动 UE 工程其他文件、Docs、Content、Plugins）：

```text
uemcp/package.json  pnpm-workspace.yaml  tsconfig.base.json  .gitignore  README-DEV.md
uemcp/scripts/mock-bridge.mjs  uemcp/scripts/smoke.mjs
uemcp/scripts/start-server.ps1  uemcp/scripts/stop-server.ps1   # 服务部署（§4）
uemcp/packages/shared/package.json  tsconfig.json  src/{index,toolNames,errors,types}.ts  src/schemas/*.ts（11 个）
uemcp/packages/server/package.json  tsconfig.json  tsup.config.ts
  src/{index,config,logger,policy,audit,confirm}.ts
  src/mcp/{buildServer,registerTools,annotations}.ts
  src/transports/{http,stdio}.ts
  src/bridge/{discovery,client,watchdog}.ts
  src/tools/*.ts（common + 10 工具 + index）
```

## 8. 未覆盖项 / 风险 / 待架构确认

**自测未覆盖（需真实 UE 桥接或专用客户端，留给测试计划执行阶段）**
- L2 工具功能全部（TOOL-01~29）：需真实编辑器。
- 旧版 SSE 客户端基线 `examples/generic/sse_client.py`（PROTO-14 脚本基线）与 Cursor 0.45.x（CLIENT-05）：脚本属测试资产，未包含在本交付。
- elicitation 确认流（SEC-08/09/10 的 elicit 分支、CONFIRMATION_DENIED）：无 elicitation 客户端；实现基于 SDK `getClientCapabilities().elicitation` + `sendElicitation`，**未经运行时验证**。
- RES-01/02/04/05/07/09（真实插件发现文件生命周期）、SEC-03（非回环，绑定性保证）、SEC-06（桥接 token 三态）、SEC-13（审计降级模拟）、CLIENT-01~06。
- 每会话 20 req/s 限流已实现（审查 Major-6，见 §6；SEC-14 可测）；跨会话全局限流（桥接端 30 rps）属桥接侧，未实现。
- `examples/`、`docs/`、`LICENSE` 等开源发布件：不在本次任务范围。

**待架构确认（文档未覆盖处按最保守实现）**
1. **协议版本协商**：SDK 1.32 的最新版本为 `2025-11-25`（超出架构 §3.6 三版本表）。实现按文档强制三版本：未知/未来版本统一按 `2025-06-18` 协商回显（满足 PROTO-17 判定）。**主管已裁决：接受此处理**；若需接受 2025-11-25 请更新文档。
2. **outputSchema**：附录 A 发布门槛要求全部工具有 outputSchema；因自控路由 + 成功/失败两种 structuredContent 形态，MVP 未注册（避免与 §2.9.4 错误形态冲突）。**主管已裁决：延后至发布前补充，不阻塞 MVP。**
3. **level_control open 的确认注入**：`--allow-destructive` 开启时 Server 向桥注入 `confirm:true`（等价 §2.9.7 第三行「--allow-destructive → 执行打开」）；save_all 同理。**主管已裁决：接受（语义等价）。**
4. **TOOL_DISABLED gate 取值**：P2 工具（console/exec）无论策略档位，gate 恒为 `server.allowConsole`/`server.allowExec`（依 SEC-01(c)/SEC-15 判定；§2.9.6 的 `server.policy` 仅用于 P1 `ue_actor_edit`）。
5. **会话上限 429 的 errorCode** 用 `RATE_LIMITED`/-32012（§2.9.2 表中 429 的唯一映射）。

**已按裁决修复（2026-10-20 第二轮）**
- **viewport.capture 内联编码**：桥接只返回 `path/width/height/format/bytes/capturedAt`（不返回 base64）。Server 侧读取捕获文件（同机）编码 base64：≤8 MiB 输出 image 内容块（mimeType 按 format），>8 MiB、无路径或读失败按 §5.7 降级 file + warning `IMAGE_TOO_LARGE_FOR_INLINE`；若未来桥接返回 `data.base64Data` 则优先使用（向前兼容）。smoke 新增 4 条断言（61 → 65）。

**已按审查报告修复（2026-10-20 第三轮，65 → 71）**
- Critical-2 `bridge/discovery.ts`：抽出 `normalizeProjectDir`（斜杠统一/去尾，hash 与比较共用；比较大小写不敏感）；hash 文件名未命中时扫描 `bridges/` 按 projectDir 内容匹配（兼容大小写差异）；显式 `--project` 时任何失败**硬失败返回 null**（→ BRIDGE_UNAVAILABLE），禁止回退 bridge.json/默认端口。
- Major-1 `tools/*.ts` + `bridge/client.ts`：工具级超时全量消费，clamp 120s。
- Major-2 `tools/consoleCommand.ts` / `tools/pythonExec.ts`：elicitation 优先。
- Major-3 `audit.ts` / `config.ts`：删除 `--audit-python-source`（红线：永不记源码）；审计文件 open mode 0600。
- Major-4 `bridge/client.ts` + 各工具：写方法禁自动重试（`retriable` 显式声明，默认 false）。
- Major-6 `transports/http.ts`：每会话令牌桶限流（20 rps / 突发 40 → 429 + -32012）。
- Major-5 `shared/src/schemas/console.ts`：删除 CONSOLE_ALLOWLIST/CONSOLE_DENIED 死代码（单一来源在 Bridge）。
- smoke 环境隔离：`UEMCP_BRIDGE_PORT=18999`，防止本机真实 UEMCPBridge（18778）干扰"全部发现来源失败"类断言。

**已知限制**
- stdio 模式下协议层预校验（信封/未知工具 400）不经过 HTTP 层，由低层 handler 抛 `McpError(InvalidParams)` 承担（JSON-RPC 层等价）。
- Windows 下 smoke 的 stdio 子进程如强杀会触发 libuv 断言打印（测试脚本现象，与服务端无关；脚本已改为 stdin.end() 优雅退出）。
- 审计 sessionId 依赖 SDK `extra.sessionId`（HTTP 传输有值；stdio 无）。
