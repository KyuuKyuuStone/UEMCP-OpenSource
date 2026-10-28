# UEMCP 交接文档（HANDOFF）

> **读者**：接手本项目的 AI / 开发者。读完本文 + 三份核心文档（见 §11 索引）即可上手。
> **本文日期**：2026-10-20。所有端口、命令、路径均已与当前代码核对；与代码冲突时**以代码为准**并在 Issue 中记录。

---

## 1. 项目定位与当前状态

**一句话**：UEMCP 是客户端无关的 Unreal Engine 5.4 编辑器 MCP 服务——任意 MCP 客户端（Claude Code / Cursor / curl）通过标准 MCP 协议操作当前打开的编辑器（Actor 增删改查、关卡、资产、材质实例、截图、蓝图查询/编译），双进程架构（Node MCP Server + UE 编辑器内纯 Python 桥接），本地优先（仅绑定 127.0.0.1），MIT。

| 项 | 值 |
|---|---|
| 版本 | MCP Server `@uemcp/server` 0.1.0 + `@uemcp/shared` 0.1.0；UEMCPBridge 0.1.0（`UEMCPBridge.uplugin`） |
| 架构基线 | `docs/UEMCP-架构设计.md` **v0.2.0**（单一事实来源，已合并 7 项裁决 D1/D1b/D2/D6/D10/D11/D12） |
| 完成度 | **MVP 完成并已通过测试**：smoke 71/71；单测+黑盒测试 36/36（两次运行稳定）；`pnpm typecheck` / `pnpm build` 均 exit 0；测试报告 v1.2 最终轮 **PASS 10 / FAIL 0 / UNTESTED 0**，6 个缺陷全部验证修复，**产品缺陷 0** |
| 测试结论适用范围 | Server 0.1.0 + Bridge 0.1.0（含全部修复）+ UE 5.4.4-35576357 + Windows 11 + 样例工程（`docs/UEMCP-测试执行报告.md` §6） |
| 代码规模 | 104 个文件（不含 node_modules/dist/__pycache__），约 954 KB（932 KiB） |

---

## 2. 目录结构与职责

```text
UEMCP-OpenSource/
├─ HANDOFF.md                    # 本文（接手 AI 指南）
├─ README.md                     # 面向开源用户的说明
├─ LICENSE                       # MIT（2026 UEMCP contributors）
├─ .gitignore                    # 已含 node_modules/dist/logs/__pycache__/.env/.test-run 等
├─ UEMCPBridge/                  # UE 5.4 编辑器侧：纯 Python 插件（无 C++，零编译）
│  ├─ UEMCPBridge.uplugin        # Type=Editor, EngineVersion 5.4.0, Modules=[]；依赖 PythonScriptPlugin + EditorScriptingUtilities
│  ├─ README.md                  # UE 侧安装/配置/安全/RPC 方法表/自测（核心文档 ③）
│  ├─ Content/Python/
│  │  ├─ init_unreal.py          # 编辑器启动钩子：延迟 1 个 Slate tick 拉起 Bridge，失败只写日志不阻断
│  │  └─ uemcp_bridge/
│  │     ├─ server.py            # ThreadingHTTPServer：/health /rpc /events；端口回退；Windows SO_EXCLUSIVEADDRUSE
│  │     ├─ rpc.py               # RPC 路由 + 权限门（游戏线程入队前执行）+ 写方法集合 WRITE_ACTIONS
│  │     ├─ dispatcher.py        # 游戏线程单队列（Slate post-tick 泵），队列 64、超时上限 120s
│  │     ├─ discovery.py         # 发现文件原子写（~/.uemcp/）、按 PID+token 删除、projectHash 计算
│  │     ├─ security.py          # token（32B base64url 常量时间比较）/ 回环 / Host / Origin
│  │     ├─ settings.py          # 配置：环境变量 > Saved/UEMCP/bridge-settings.json > 默认值；DEFAULT_CONSOLE_ALLOWLIST
│  │     ├─ errors.py            # ERROR_TABLE（44+ 错误码 → JSON-RPC 码/HTTP 状态）
│  │     ├─ serialization.py     # UE 类型 → JSON（FQuat→欧拉、FTransform、AssetRef/ActorRef 等）
│  │     └─ handlers/            # 12 个 RPC method 的 handler（status/actors/levels/assets/materials/viewport/console/python_exec/blueprints）
│  └─ Tests/                     # smoke_bridge.py（需引擎）+ 8 个纯 Python 自检 + 2 个引擎探针
├─ uemcp/                        # MCP Server：pnpm workspace
│  ├─ package.json               # packageManager: pnpm@11.22.0；engines node>=20；scripts: build/typecheck/smoke/test
│  ├─ pnpm-workspace.yaml        # packages/*；allowBuilds: esbuild
│  ├─ README-DEV.md              # 构建运行自测/实现契约/§8 已知限制（核心文档 ②）
│  ├─ packages/shared/           # @uemcp/shared：10 工具名、zod Schema（11 文件）、错误码表、类型
│  ├─ packages/server/           # @uemcp/server：bin=uemcp
│  │  ├─ src/index.ts            # CLI 入口（未知参数 fatal exit 1）
│  │  ├─ src/config.ts           # 13 个 CLI 参数 + 环境变量解析
│  │  ├─ src/transports/         # http.ts（/mcp /sse /messages /health + 会话 + Host/Origin + 限流）stdio.ts
│  │  ├─ src/mcp/                # buildServer/registerTools（低层 setRequestHandler，为携带 structuredContent.error）/annotations
│  │  ├─ src/bridge/             # discovery.ts（发现链 + --project 硬失败）client.ts（超时 clamp 120s/读写重试语义）watchdog.ts
│  │  ├─ src/tools/              # 10 个工具定义 + common.ts（策略门/审计/elicit 封装）+ index.ts
│  │  └─ src/{policy,audit,confirm,logger}.ts
│  ├─ scripts/
│  │  ├─ smoke.mjs               # Server 自测（71 项断言，mock bridge 走真实发现链路）
│  │  ├─ mock-bridge.mjs         # 本地 mock bridge（stdout 首行 {port,token,home}）
│  │  └─ start-server.ps1 / stop-server.ps1   # Windows 分离进程部署（logs/server.pid + 按天日志）
│  └─ tests/                     # node --test：server.blackbox.test.mjs（17）+ shared.schemas.test.mjs（19）
└─ docs/
   ├─ UEMCP-架构设计.md           # v0.2.0 架构基线（核心文档 ①）
   ├─ UEMCP-架构裁决补充.md        # D1/D1b/D2/D6/D10/D11/D12 决策记录（已并入 v0.2.0）
   ├─ UEMCP-测试计划.md           # 86 条用例与判定标准
   ├─ UEMCP-测试执行报告.md       # v1.2：6 缺陷修复验证 + 未测项清单 §5
   ├─ UEMCP-代码审查报告.md       # 2 Critical/7 Major/13 Minor + 第二轮复审（7 项修复全部通过）
   └─ UEMCP-README草稿.md         # ⚠️ 实现前旧草稿（"代码尚未实现"），已过时，发布前应删除或重写
```

---

## 3. 架构说明

完整设计见 `docs/UEMCP-架构设计.md` §2；以下为接手所需的最小集。

```text
┌──────────────────────────┐
│ MCP 客户端（任选）        │  Claude Code / Cursor / curl / 自研
└────────────┬─────────────┘
             │ MCP 协议：stdio 或 Streamable HTTP(:18777/mcp) 或 旧版 SSE(:18777/sse)
             ▼
┌──────────────────────────────────────────────┐
│ UEMCP Server（Node.js/TypeScript，:18777）    │
│ 会话管理(Mcp-Session-Id, TTL 30min, 上限 32) │
│ 策略门 read-only/standard/full + P2 开关      │
│ 桥接发现(~/.uemcp/) / 看门狗 / 审计 / 限流    │
└────────────┬─────────────────────────────────┘
             │ HTTP JSON-RPC 2.0 + X-UEMCP-Token
             │ POST http://127.0.0.1:18778/rpc（GET /health /events）
             ▼
┌──────────────────────────────────────────────┐
│ UEMCPBridge（UE 5.4 编辑器内，纯 Python）     │
│ ThreadingHTTPServer + 游戏线程单队列          │
│ 权限门在入队前；写操作包 ScopedEditorTransaction│
└────────────┬─────────────────────────────────┘
             │ unreal.* Python API（仅游戏线程）
             ▼
        UE 5.4 编辑器（World / Actor / AssetRegistry / Viewport）
```

关键机制（细节均在架构文档对应章节）：

- **发现链**（§2.4）：`--bridge-url` > `--project <dir>`（读 `~/.uemcp/bridges/<sha1-16>.json`，比较平台语义：Windows 大小写不敏感；**指定 `--project` 时任何失败硬失败，不回退**）> `~/.uemcp/bridge.json` > 默认 `127.0.0.1:18778`。发现文件校验 schemaVersion/pid 存活/`GET /health`（app=uemcp-bridge 且 pid、startedAt 一致）；陈旧逐级跳过；调用失败自动重发现一次（token 轮换自愈）。
- **端口策略**（D10）：MCP Server 端口被占 → **2 秒内 exit 2**，stderr 一行 `{"event":"http_bind_failed",...}`，不换端口；桥接端被占 → 18778 → 18779–18788 → 系统临时端口，实际端口写入发现文件。
- **游戏线程队列**（§2.6）：所有 `unreal.*` 调用经单队列（上限 64，满则 `BRIDGE_BUSY`）；每 tick 最多 1 个任务；超时上限 120s；**已进入执行的任务无法中断**。
- **错误模型**（D1/D1b，裁决补充 §1–§3）：已路由到已知工具的执行失败一律 **HTTP 200 + `isError:true` + `structuredContent.error`**（`content[0].text` 以 `"<CODE>: <message>"` 开头）；协议层失败（信封/未知工具/会话/限流）才用非 200 + 顶层 JSON-RPC error。对外只认字符串错误码，完整表见裁决补充 §2.4（`BRIDGE_TIMEOUT` 为 -32020，`-32001` 专用于 `SESSION_NOT_FOUND`）。
- **双重权限门**（D6）：Server 策略/开关（`TOOL_DISABLED`，gate=server.policy/allowConsole/allowExec）+ Bridge 配置（`PERMISSION_DENIED` gate=bridge.allowWrite/allowConsole；`EXEC_DISABLED` gate=bridge.allowExec）。
- **确认**（D11）：elicitation 优先，拒绝 → `CONFIRMATION_DENIED`；客户端不支持时 `--allow-destructive`（仅 P1：delete/open 丢弃未保存/save_all）与 `--allow-console`/`--allow-exec`（各自兼作 P2 策略级确认）兜底，审计记 `confirmationMode` + `confirmationSwitch`。
- **read-only 下混合工具**（D12）：`ue_level_control`/`ue_material_params`/`ue_blueprint` 仍注册但 action enum 收窄（2/2/1 个只读 action），写 action 被 zod 拒绝为 `INVALID_ARGUMENT`。工具数：read-only=7、standard=8、full=8、full+单开关=9、full+双开关=10。
- **限流**：HTTP 层每会话令牌桶 20 req/s 突发 40 → 429 + `-32012 RATE_LIMITED`（在会话校验之后，伪造 sid 不灌桶）。
- **重试语义**（审查 Major-4）：仅显式 `retriable:true` 的只读方法在 `BRIDGE_UNAVAILABLE` 时自动重发现重试一次；写方法不自动重试（防重复执行），返回可重试错误由用户确认后重发。401（token 被拒）按 `BRIDGE_UNAVAILABLE` 处理触发重发现。

---

## 4. 环境要求

| 项 | 要求 | 备注 |
|---|---|---|
| Unreal Engine | **5.4.x**（主验证 5.4.4-35576357）；不承诺其他版本 | 架构 §8.2 跨版本策略 |
| UE 插件 | PythonScriptPlugin + EditorScriptingUtilities（引擎自带；UEMCPBridge.uplugin 已声明依赖） | |
| Node.js | **>= 20**（实测 Node v24.18.0） | `package.json` engines 字段 |
| pnpm | **11.22.0**（`packageManager` 字段锁定；corepack 可自动获取） | |
| UE 侧 Python 依赖 | 无（仅标准库 + `unreal` 模块，不要求 pip） | |
| Server 依赖 | @modelcontextprotocol/sdk ^1.32.1、express ^4.21.2、zod ^3.25.0、zod-to-json-schema ^3.24.0、tsup ^8.3.0 | lockfile 已提交 |

**Windows 注意事项**（当前验证平台）：

- Server 部署用 `scripts/start-server.ps1`（分离进程）；前台运行会在终端会话结束时被回收（README-DEV §4）。
- 桥接端已设 `allow_reuse_address=False` + `SO_EXCLUSIVEADDRUSE`（Windows 双绑定修复，审查 M-7；`server.py:77-92`）。
- `--project` 目录比较 Windows 大小写不敏感（POSIX 敏感，跨平台观察项 N-3）。
- smoke 的 stdio 子进程强杀会触发 libuv 断言打印——测试脚本现象，与服务端无关（脚本已改 stdin.end() 优雅退出）。
- 审计文件 `open(file,"a",0o600)` 在 Windows 上映射为受限 ACL（近似语义，audit.ts 注释已声明）。

---

## 5. 快速开始

### 5.1 UE 侧（编辑器内桥接）

1. 复制 `UEMCPBridge/` 到 `<Project>/Plugins/UEMCPBridge/`。
2. 在 `<Project>.uproject` 的 `Plugins` 数组确认/添加三项启用（参考原工程做法，见 `UEMCPBridge/README.md` §2）：

```json
"Plugins": [
  { "Name": "UEMCPBridge", "Enabled": true },
  { "Name": "PythonScriptPlugin", "Enabled": true },
  { "Name": "EditorScriptingUtilities", "Enabled": true }
]
```

3. 启动编辑器。`init_unreal.py` 在第一个 Slate tick 后自动启动桥接（默认 `127.0.0.1:18778`，被占则回退 18779–18788，再临时端口），写发现文件 `~/.uemcp/bridges/<projectHash>.json` 与 `~/.uemcp/bridge.json`。
4. 验证：

```bash
curl -s http://127.0.0.1:18778/health
# 预期："app": "uemcp-bridge"，含 ueVersion / port / pid / capabilities
```

失败排查：看 `Saved/Logs/*.log` 中 `[UEMCP]` 行（启动失败不阻断编辑器）。

### 5.2 Server 侧（构建与运行）

```bash
cd uemcp
pnpm install        # 首次若提示 Ignored build scripts: esbuild，重跑一次即可
pnpm build          # = pnpm -r build（shared: tsc；server: tsup → dist/index.js）
pnpm typecheck      # 两包 tsc --noEmit
```

前台运行（调试用；长驻请用 5.3 的脚本方式）：

```bash
# HTTP：默认 127.0.0.1:18777；默认策略 read-only
node packages/server/dist/index.js --transport http --policy standard

# stdio（stdout 仅 MCP 帧，日志走 stderr）
node packages/server/dist/index.js --transport stdio

# P2 工具（策略 full + 开关；桥接端还需对应 allowConsole/allowExec，见 §7）
node packages/server/dist/index.js --transport http --policy full \
  --allow-console --allow-exec --allow-destructive

# 指定工程（多编辑器/多工程时建议显式指定；失败即硬失败不回退）
node packages/server/dist/index.js --transport http --project "C:/path/to/YourProject"
```

CLI 参数（`src/config.ts` KNOWN_ARGS，13 个，未知参数 fatal exit 1）：
`--transport http|stdio`、`--port N`（默认 18777）、`--policy read-only|standard|full`、`--allow-destructive`、`--allow-console`、`--allow-exec`、`--bridge-url URL`、`--bridge-token T`、`--project <dir>`、`--auth-token T`、`--disable-legacy-sse`、`--session-ttl-ms N`、`--session-sweep-ms N`。

环境变量：`UEMCP_HTTP_PORT`、`UEMCP_POLICY`、`UEMCP_ALLOW_DESTRUCTIVE`、`UEMCP_ALLOW_CONSOLE`、`UEMCP_ALLOW_EXEC`、`UEMCP_BRIDGE_URL`、`UEMCP_BRIDGE_TOKEN`、`UEMCP_AUTH_TOKEN`、`UEMCP_AUDIT_DIR`。优先级：命令行 > 环境变量 > 发现文件 > 默认值。

### 5.3 Windows 服务方式运行（推荐）

```powershell
# 在 uemcp/ 目录下执行
powershell -ExecutionPolicy Bypass -File scripts\start-server.ps1 -Port 18777 -Policy standard
#   可选：-ExtraArgs "--allow-console --allow-exec --allow-destructive"
#   日志：logs\server-YYYY-MM-DD.log（应用 JSON 日志）+ logs\server-stdout|stderr-*.log（进程级）
#   /health 暴露 pid 与 logPath

powershell -ExecutionPolicy Bypass -File scripts\stop-server.ps1   # 按 logs/server.pid 停止
```

### 5.4 MCP 客户端接入

**Claude Code — Streamable HTTP（推荐，已实测 Connected）**：

```bash
claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp
claude mcp list    # 预期：uemcp ✓ Connected
```

**通用 HTTP 客户端（curl 序列，字段以代码为准）**：

```bash
# 1) 初始化：从响应头取 Mcp-Session-Id
curl -s -D - -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0.0.0"}}}'

# 2) initialized 通知：预期 202（注意 Accept 必须含 text/event-stream，缺省 406）
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: <上一步响应头>' \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# 3) 列工具（响应可能为 SSE 帧，按 data: 行解析）
curl -s -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: <上一步响应头>' -H 'MCP-Protocol-Version: 2025-06-18' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# 4) 调用工具
curl -s -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: <上一步响应头>' -H 'MCP-Protocol-Version: 2025-06-18' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ue_editor_status","arguments":{}}}'
```

**stdio（Claude Code / CLI 的 mcpServers 配置）**：

```json
{
  "mcpServers": {
    "uemcp": {
      "command": "node",
      "args": ["<仓库路径>/uemcp/packages/server/dist/index.js", "--transport", "stdio", "--policy", "standard"]
    }
  }
}
```

（npm 发布后可改为 `"command": "npx", "args": ["-y", "@uemcp/server", "--transport", "stdio"]`；当前未发布，用 node 直跑 dist。Windows 下若客户端不解析 npx 可用 `cmd /c` 包装，见架构 §3.5.2。）

**旧版 SSE**：`GET /sse` + `POST /messages?sessionId=`（`--disable-legacy-sse` 可关闭）。Cursor 配置示例见架构 §3.5.3（0.45.x 基线用 SSE，0.46+ 需另测，D2）。

---

## 6. 验证与测试

| 命令（在 `uemcp/` 下） | 预期结果 | 实测 |
|---|---|---|
| `pnpm typecheck` | 两包 tsc --noEmit，exit 0 | ✅ 2026-10-20 |
| `pnpm build` | shared tsc + server tsup（ESM+DTS），exit 0 | ✅ 2026-10-20 |
| `node scripts/smoke.mjs` | `SMOKE RESULT: 71/71 passed` | ✅ 2026-10-20 |
| `pnpm test`（= `node --test`） | server.blackbox 17 + shared.schemas 19 = **36 项全过**，两次运行稳定 | ✅ 2026-10-20 |
| Bridge 纯 Python 自检（无需引擎） | `python UEMCPBridge/Tests/check_error_codes.py` 等 8 个脚本全过 | 见 `UEMCPBridge/README.md` §7 |
| Bridge 冒烟（需 UnrealEditor-Cmd） | `smoke_bridge.py` 自检 + 保持监听 12s | 见 `UEMCPBridge/README.md` §7 |

**端口约定（务必遵守，避免与本机真实服务冲突）**：

- 真实服务：MCP Server `18777`、Bridge `18778`（回退 18779–18788）——测试**不要占用**。
- smoke（`scripts/smoke.mjs`）：mock bridge 用 `UEMCP_BRIDGE_PORT=18999`（隔离真实 18778），Server 实例用 19001–19008，自带临时 HOME。
- `tests/*.test.mjs`（blackbox）：Server 用 **19101..19199** 区段，mock bridge 用 `--port 0`（系统随机），临时 HOME 自理。

**两个新增测试文件覆盖范围**：

- `tests/server.blackbox.test.mjs`（17 项）：启动参数与环境变量（默认 read-only=7 工具、UEMCP_POLICY env、CLI 覆盖 env、UEMCP_HTTP_PORT、未知参数 fatal exit 1 含已删除的 `--audit-python-source`）；安全门控（TOOL_DISABLED gate=server.policy、read-only 收窄 zod 拒绝写 action、EXEC_DISABLED gate=bridge.allowExec、PERMISSION_DENIED gate=bridge.allowWrite、P2 正常路径）；桥接异常映射（未知类 → CLASS_NOT_FOUND、成功信封 data/warnings/meta、PIE_NOT_RUNNING、dead --bridge-url 读/写不自动重试、非 JSON 200 → INTERNAL + bridgeHttpStatus、HTTP 401 → BRIDGE_UNAVAILABLE 触发重发现）。
- `tests/shared.schemas.test.mjs`（19 项）：viewport/actor_query/level_control 的 zod 校验（默认值、strict 拒未知键、边界 64..7680、read-only 收窄 enum 与 policy.ts 一致性）；toolNames 完整目录 10 个与 RPC 映射全量；协议层错误码表（§2.9.2）；工具层错误码表（TIMEOUT 已退役、bridgeJsonRpc 码唯一且不含 -32001）；toolCodeFromJsonRpc 反查。

真实 UE 端集成验证（阶段 B/C）见 `docs/UEMCP-测试执行报告.md`（最终轮 PASS 10 / FAIL 0）。

---

## 7. 配置与安全默认值

**Bridge 配置**（优先级：环境变量 > `<Project>/Saved/UEMCP/bridge-settings.json` > 默认；`settings.py`）：

```json
{
  "port": 18778,
  "allowWrite": false,
  "allowConsole": false,
  "allowExec": false,
  "consoleAllowlist": ["stat", "show", "r.", "sg.", "viewmode", "log", "help", "dumpticks", "obj", "memreport", "camera"],
  "maxQueueSize": 64,
  "requestTimeoutMs": 30000,
  "searchTimeoutMs": 20000
}
```

环境变量：`UEMCP_BRIDGE_PORT`、`UEMCP_BRIDGE_ALLOW_WRITE`、`UEMCP_BRIDGE_ALLOW_CONSOLE`、`UEMCP_BRIDGE_ALLOW_EXEC`、`UEMCP_BRIDGE_TOKEN_FILE`。

**安全默认（全部已实现并有测试覆盖）**：

- **默认只读**：Server 默认策略 `read-only`（7 工具）；Bridge 三个权限门默认全 false。
- **仅回环**：两端强制绑定 127.0.0.1；非回环 peer 直接拒绝；Host 白名单（违规 421）/ Origin 白名单（违规 403）；不启用 CORS，OPTIONS 405；请求体 8 MiB 上限。
- **双向权限门**：Server 策略/开关 × Bridge 配置，任一端关闭即拒绝（gate 字段可区分来源，D6）。
- **token**：32 字节 CSPRNG base64url，每次编辑器启动轮换；`X-UEMCP-Token` 头传递（不放 URL）；常量时间比较；发现文件 chmod 0600（best effort）。MCP 入口可选 Bearer（`--auth-token`，401 用 timingSafeEqual）。
- **审计**：`~/.uemcp/audit/YYYY-MM-DD.jsonl`（UEMCP_AUDIT_DIR 可覆盖）；P1/P2 记录；Python 执行只记 `codeSha256` + `codeLength`——**永不记录源码**（`--audit-python-source` 已删除，传入即 fatal）；console 记全文；写失败不阻塞、连续 3 次 `/health` 标 `auditDegraded:true`；30 天自动清理；文件创建 mode 0600。
- **console 双重限制**：白名单 11 项前缀（单一来源 `settings.py::DEFAULT_CONSOLE_ALLOWLIST`）+ 永久拒绝表（`handlers/console.py::PERMANENTLY_DENIED`：quit/exit/py/exec/open 等，即使配置也不放行）。
- **误操作防护**：写操作 `ScopedEditorTransaction`（atomic 失败回滚）、`dryRun`、PIE 运行中拒绝写（`EDITOR_UNSAFE_STATE`）、权限门在游戏线程入队前执行（拒绝零副作用）。
- **开启写操作的正确姿势**：Server `--policy standard`（P1 可见）+ Bridge `bridge-settings.json` 中 `"allowWrite": true`（或环境变量）；P2 再加各自双端开关。**开启 `allowExec` 等价于把编辑器控制权交给调用方**，生产/演示环境不要开启。

---

## 8. 已知限制与未覆盖项（如实列出，接手后优先补齐）

**自测/测试未覆盖**（来源：README-DEV §8、测试报告 §5、审查报告 §④）：

1. **BRIDGE_TIMEOUT 真实超时路径未覆盖**：smoke/mock 未注入游戏线程超时场景（30s/45s/60s 工具超时与 clamp 120s 仅静态消费验证）。
2. **elicitation 确认流未运行验证**：SEC-08/09/10 的 elicit 分支、CONFIRMATION_DENIED、m-1（fail-open）无运行时证据；policy 分支已由 smoke 覆盖。
3. **跨会话全局限流未实现**：桥接端 30 req/s（§6.7）属 Bridge 侧，未实现；Server 每会话 20 req/s 已实现并有断言。
4. **stdio 预校验差异**：stdio 不经 HTTP 层，协议层预校验（信封/未知工具 400）由低层 handler 抛 `McpError(InvalidParams)` 承担（JSON-RPC 层等价）。
5. **审计 sessionId 差异**：依赖 SDK `extra.sessionId`——HTTP 传输有值，stdio 无。
6. **outputSchema 延后**：附录 A 要求全部工具注册 outputSchema；MVP 未注册（主管裁决：发布前补充，不阻塞）。
7. **协议版本 2025-11-25 未纳入**：SDK 1.32 支持该版本，实现按架构 §3.6 三版本表处理（未知/未来版本统一按 2025-06-18 协商回显；主管已裁决接受；若需支持请更新文档）。
8. **真实 UE 端部分 L2 用例未执行**：TOOL-11（AMBIGUOUS_SELECTOR）、TOOL-22 set、TOOL-15 脏包分支、TOOL-30/31/32/33 P2 真实路径（安全约束未开桥接门）、RES-04/07/08/09（端口回退全占等）、SEC-03/06/13、TOOL-19b/c（SEARCH_TIMEOUT、AssetRegistry 窗口）；客户端 CLIENT-03~06（**Cursor 未安装**）、PROTO-14 脚本基线 `examples/generic/sse_client.py`（**脚本未交付**，服务端侧 SSE 行为已由 runner-sse 验证 6/6）。
9. **压测/实测缺口**：限流突发行为依赖 smoke 断言未独立压测；`--project` 硬失败路径未构造实测（静态推演成立）；0600 的 Windows ACL 近似效果未实测。

**遗留 Minor（审查报告，均不阻断，建议顺手清理）**：

- m-3：`ue_python_exec` schema 默认 timeoutMs 10000 vs Server 强制 ≥30000，语义混乱。
- m-13：`ue_blueprint {action:"query", save:true}` 写盘不计入 isWrite（不自动重试审计缺口，风险低）。
- m-2：`bridge/client.ts` CONNECT_WINDOW_MS 死分支不可达。
- N-2：审计目录 mkdir 未传 mode（文件已 0600；Linux 下目录可能 755）。
- N-3：`equalProjectDir` 大小写不敏感在 Linux 大小写敏感 FS 上的跨平台语义（MVP 承诺 Windows）。

**待架构/主管裁决的疑点**（审查报告 Q 组）：Q-1 Server 读截图文件无目录约束（信任边界）；Q-3 JSON-RPC batch 数组请求语义（当前不支持=400）；m-11 ActorRef.objectPath 与 actorPath 同值；m-4 截图 fallback 只 glob *.png 且可能误回收第三方文件；m-9 CAPTURE_TIMEOUT 后孤儿截图文件无清理；Q-2 `hideEditorUI` 参数被解析后丢弃；O-4 编辑器启动后首次截图可能 BRIDGE_TIMEOUT（复测即成功，建议文档标注或预热）；O-5 delete 后 ≤1s 最终一致性残影。

**能力边界（非缺陷，产品定位）**：蓝图节点创建/连线/删除、动画蓝图编辑 → `CAPABILITY_UNAVAILABLE`（P2 C++ 模块）；控制台无输出回显（`outputAvailable:false`）；Python 无沙箱/不可中断；仅编辑器不操作打包运行时。完整表见 `UEMCPBridge/README.md` §6 与架构 §8.1。

---

## 9. GitHub 发布清单（供接手 AI 执行）

> 本文档不代做发布；以下命令与检查项供执行时复制核对。

1. **仓库名**：建议 `UEMCP`。禁止使用 "UnrealMCP"/"EpicMCP" 等易混淆名称（架构 §7.5）。
2. **许可证**：MIT 已就位（`LICENSE`）。补充建议：README 底部放商标免责声明（本仓库 README.md 已含）。
3. **需包含**：`UEMCPBridge/`（含 `.uplugin`、Python、Tests）、`uemcp/`（含 `pnpm-lock.yaml`，**不含** node_modules/dist）、`docs/`（架构 v0.2.0 + 裁决补充 + 测试计划/报告/审查报告）、`.gitignore`、`LICENSE`、`README.md`。`HANDOFF.md` 是否随仓库公开由维护者决定（内部过程信息较多，可保留、移入 docs/ 或删除）。
4. **需排除（发布前逐项检查）**：
   - [ ] 无 `node_modules/`、`dist/`、`logs/`、`*.tsbuildinfo`
   - [ ] 无 `__pycache__/`、`*.pyc`（已加入 .gitignore）
   - [ ] 无 `.env`、`.heihei/`、`.test-run/`、`*.pid`（已加入 .gitignore）
   - [ ] 无 token/密钥：`~/.uemcp/bridge.json` 类发现文件不在仓库；文档中无 token 明文（已核对）
   - [ ] 绝对路径审查：`UEMCPBridge/README.md` §7 命令含 `C:\UE5_P\5.4\XQHCPP_54` 与引擎安装路径——建议泛化为 `<Project>` / `<EnginePath>`；`docs/UEMCP-测试执行报告.md` 含内部会话 ID、PID、本机用户名路径——发布前评估保留（作为测试证据）或删除
   - [ ] `docs/UEMCP-README草稿.md` 为实现前旧稿（声明"代码尚未实现"，与本仓库现状矛盾）——**发布前删除或重写**
5. **git 操作示例**（确认检查项通过后再执行）：

```bash
cd /c/UE5_P/5.4/UEMCP-OpenSource
git init -b main
git add .
git status                 # 核对暂存清单：不应出现 node_modules/dist/__pycache__/logs
git commit -m "UEMCP MVP: MCP server + UE bridge (UE 5.4), MIT"
git remote add origin git@github.com:<org-or-user>/UEMCP.git
git push -u origin main
```

6. **可选发布件**（架构 §7.1 规划，当前不存在）：`CONTRIBUTING.md`、`SECURITY.md`、`TRADEMARK.md`、`CHANGELOG.md`、GitHub Actions（ci.yml：lint+test+build；release.yml：npm + 插件 zip）、`examples/`（含 D2 要求的 `sse_client.py`）。

---

## 10. 接手后的建议待办（按优先级）

1. **发布门槛补齐**：为 10 个工具补充 `outputSchema`（README-DEV §8 裁决 2：延后至发布前，注意成功/失败两种 structuredContent 形态的兼容，架构附录 A）。
2. **elicitation 运行时验证**：用支持 elicitation 的客户端验证 approved/declined 分支、`CONFIRMATION_DENIED` 与 m-1 fail-open 风险（SEC-08/09/10；README-DEV §8-1）。
3. **D2 基线补齐**：交付 `examples/generic/sse_client.py`（裁决补充 §4.2 有完整规格：CLI、流程、退出码 0–4）并跑通；Cursor 0.45.11 就位后补 CLIENT-05。
4. **真实 UE 端未测项**：TOOL-11/22、TOOL-15 脏包分支、P2 真实路径（TOOL-30/31/32/33）、RES-04/07/08/09（测试报告 §5 全表）。
5. **BRIDGE_TIMEOUT 路径测试**：为 dispatcher 游戏线程超时构造可控长任务用例（mock 注入延迟）。
6. **裁决落文档**：若需支持协议版本 2025-11-25，更新架构 §3.6 并放开协商（README-DEV §8-1）；Q-1（截图读取信任边界）、Q-3（batch 语义）、m-11（objectPath）提请架构师裁决。
7. **遗留 Minor 清理**：m-3、m-13、m-2、N-2、N-3（审查报告；不阻断，随下次代码变更顺手处理）。
8. **限流补全或降级裁决**：桥接端全局 30 req/s 实现，或在架构 §6.7 记录 P2 豁免（审查 M-6 遗留的决策点）。
9. **P2 路线启动**（架构 §9.3）：C++ 辅助模块（蓝图节点编辑/控制台输出捕获）——先补 capabilities 探测与 Schema 再实现。
10. **工程化**：CI（vitest/测试已在，接 GitHub Actions）、CHANGELOG、CONTRIBUTING/SECURITY/TRADEMARK、npm 发布 `@uemcp/server`（发布后 README 的 npx 用法即可生效）。

> 已修复项不要重复做：6 个 DEFECT、审查 Critical-1/2、Major-1~6、Windows 双绑定（M-7）、`--audit-python-source` 删除（含 fatal 行为与测试）、白名单单一来源（Major-5）——均有测试或复审证据（测试报告 §4、审查报告第二轮复审表）。

---

## 11. 关键文件索引

| 文件 | 作用 |
|---|---|
| `docs/UEMCP-架构设计.md` | **单一事实来源**（v0.2.0）：架构、端口、发现、错误模型、10 工具 Schema、安全模型、风险表 |
| `docs/UEMCP-架构裁决补充.md` | D1/D1b/D2/D6/D10/D11/D12 决策记录（错误码全表在 §2.4） |
| `docs/UEMCP-测试计划.md` | 86 条用例与判定标准 |
| `docs/UEMCP-测试执行报告.md` | v1.2 实测结论、6 缺陷闭环、未测项 §5 |
| `docs/UEMCP-代码审查报告.md` | 两轮审查全记录（修复建议与复审证据） |
| `uemcp/README-DEV.md` | 构建/运行/部署/自测 + 实现契约要点 + §8 已知限制 |
| `UEMCPBridge/README.md` | UE 侧安装/配置/安全/RPC 方法表/自测命令 |
| `uemcp/packages/server/src/index.ts` | CLI 入口（bin: uemcp） |
| `uemcp/packages/server/src/config.ts` | 13 个 CLI 参数 + 环境变量 + 未知参数 fatal |
| `uemcp/packages/server/src/tools/index.ts` | 10 个工具注册清单（ALL_TOOLS） |
| `uemcp/packages/shared/src/toolNames.ts` | 工具名常量 + 工具↔RPC method 映射 |
| `uemcp/packages/shared/src/errors.ts` | 错误码表（Server 侧） |
| `uemcp/packages/server/src/transports/http.ts` | /mcp /sse /messages /health + 会话 + Host/Origin + 限流 |
| `uemcp/packages/server/src/bridge/discovery.ts` | 发现链 + --project 硬失败语义 |
| `uemcp/packages/server/src/bridge/client.ts` | JSON-RPC 客户端：超时 clamp、读写重试语义、401 重发现 |
| `uemcp/packages/server/src/policy.ts` | 策略矩阵与收窄（D12） |
| `uemcp/packages/server/src/audit.ts` | 审计写入（0600、脱敏、30 天清理） |
| `UEMCPBridge/Content/Python/init_unreal.py` | 编辑器启动钩子（延迟 1 tick、单次守卫、失败不阻断） |
| `UEMCPBridge/Content/Python/uemcp_bridge/server.py` | ThreadingHTTPServer、端口回退、Windows 独占绑定 |
| `UEMCPBridge/Content/Python/uemcp_bridge/rpc.py` | RPC 路由 + 入队前权限门 + WRITE_ACTIONS |
| `UEMCPBridge/Content/Python/uemcp_bridge/dispatcher.py` | 游戏线程单队列（Slate post-tick 泵） |
| `UEMCPBridge/Content/Python/uemcp_bridge/settings.py` | Bridge 配置默认值 + console 白名单单一来源 |
| `UEMCPBridge/Content/Python/uemcp_bridge/errors.py` | ERROR_TABLE（错误码 → JSON-RPC/HTTP） |
| `uemcp/scripts/smoke.mjs` | Server 自测 71 项（mock bridge + 真实发现链路） |
| `uemcp/scripts/mock-bridge.mjs` | 自测用 mock bridge（stdout 首行 {port,token,home}） |
| `uemcp/scripts/start-server.ps1` / `stop-server.ps1` | Windows 分离进程部署/停止 |
| `uemcp/tests/server.blackbox.test.mjs` | 黑盒 17 项（settings/门控/桥接映射） |
| `uemcp/tests/shared.schemas.test.mjs` | Schema 单测 19 项（校验/收窄/错误码表） |
| `.gitignore` | 已含 node_modules/dist/logs/__pycache__/.env/.test-run/*.pid 等 |

---

*交接完成状态：MVP 代码 + 测试 + 文档齐备，等待 GitHub 发布与后续迭代。本文由技术文档角色依据代码与文档核对编写（2026-10-20）。*
