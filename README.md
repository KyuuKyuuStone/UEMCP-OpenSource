<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-on-dark.svg">
    <img src="assets/logo.svg" alt="UEMCP logo" width="150">
  </picture>
</p>

<p align="center"><a href="#中文">中文</a> · <a href="#english">English</a></p>

<p align="center"><sub>品牌素材 / Brand assets：<a href="assets/README.md">assets/README.md</a></sub></p>

# UEMCP

> **Unreal and Unreal Engine are trademarks or registered trademarks of Epic Games, Inc. in the United States and elsewhere. This project is an independent, community-developed tool and is not affiliated with, endorsed by, or sponsored by Epic Games, Inc. "Unreal" is used solely to describe compatibility with Unreal Engine. All other trademarks are the property of their respective owners.**

## 中文

UEMCP 是**客户端无关**的 Unreal Engine 5.4/5.7 编辑器 MCP（Model Context Protocol）服务：用 Claude Code、Cursor 或任意 HTTP 客户端，通过标准 MCP 协议操作**当前打开的编辑器**——查询与编辑 Actor、管理关卡、搜索资产、调整材质实例参数、截取视口、查询与编译蓝图。

- **客户端无关**：MCP 协议是唯一边界，不内嵌聊天 UI（Streamable HTTP / 旧版 SSE / stdio 三种传输）。
- **仅编辑器**：直接作用于编辑器进程，不解析离线 `.uasset`，不支持打包后的运行时游戏。
- **本地优先**：默认只绑定 `127.0.0.1`，开箱即用，无需部署。
- **UE 侧零编译**：纯 Python 插件，不需要 C++ 工具链；UE 侧仅依赖 Python 标准库。

> 适用引擎：UE **5.4 / 5.7**（实测 5.4.4 / 5.7.4）。状态：MVP（v0.1.0），API 可能随迭代调整。

---

### 特性（MVP 10 个工具）

| 工具 | 用途 | 默认可见 |
|---|---|---|
| `ue_editor_status` | 编辑器/当前关卡/选中 Actor/视口相机/能力/策略总览 | 是 |
| `ue_actor_query` | 按类/名称/标签/目录查询 Actor，分页返回 | 是 |
| `ue_actor_edit` | 批量生成/删除/变换/复制/选择 Actor、修改受控属性（事务+回滚+dryRun） | standard 起 |
| `ue_level_control` | 查询当前关卡与脏包；打开/保存/新建关卡 | 是（写动作 standard 起） |
| `ue_asset_search` | 按路径/名称/类搜索资产；查询依赖与反向引用 | 是 |
| `ue_material_params` | 读取材质/实例参数；设置材质实例参数；创建实例 | 是（写动作 standard 起） |
| `ue_viewport_capture` | 截取关卡视口或 PIE 画面（PNG/JPEG，返回图片或文件路径） | 是 |
| `ue_blueprint` | 查询蓝图结构（父类/变量/组件/图/编译状态）；触发编译（节点级读取为 experimental） | 是 |
| `ue_console_command` | 执行控制台命令（白名单限制） | **默认隐藏** |
| `ue_python_exec` | 在编辑器游戏线程执行 Python（无沙箱） | **默认隐藏** |

**明确不支持**：PIE 内 Actor 操作、蓝图节点创建/连线/动画蓝图编辑（需 P2 C++ 模块）、材质节点图编辑、资产导入/导出/移动、控制台输出回读、编辑器 UI/Slate 操作、Sequencer/Niagara、远程多人服务。

---

### 架构

```text
┌──────────────────────────┐
│ MCP 客户端（任选）        │  Claude Code / Cursor / curl / 自研
└────────────┬─────────────┘
             │ MCP 协议：stdio 或 Streamable HTTP(:18777/mcp) 或 旧版 SSE(:18777/sse)
             ▼
┌──────────────────────────────────────────────┐
│ UEMCP Server（Node.js/TypeScript，:18777）    │
│ 会话管理 / 策略门 / 桥接发现 / 审计 / 限流    │
└────────────┬─────────────────────────────────┘
             │ HTTP JSON-RPC 2.0 + X-UEMCP-Token
             ▼
┌──────────────────────────────────────────────────────┐
│ UEMCPBridge（UE 5.4/5.7 编辑器内，纯 Python，:18778）│
│ ThreadingHTTPServer + 游戏线程单队列                 │
└────────────┬─────────────────────────────────────────┘
             │ unreal.* Python API（仅游戏线程）
             ▼
        UE 5.4/5.7 编辑器（World / Actor / AssetRegistry / Viewport）
```

- 桥接启动后写发现文件 `~/.uemcp/`；Server 自动发现并校验（pid/health 双重校验，陈旧文件自动跳过）。
- 编辑器内所有 `unreal.*` 调用经游戏线程队列执行，HTTP 线程零引擎调用。
- 默认端口：Server `18777`（被占则**失败退出**，显式换端口）；Bridge `18778`（被占则自动回退 18779–18788）。

---

### 环境要求

- Unreal Engine **5.4.x** + PythonScriptPlugin + EditorScriptingUtilities（引擎自带；实测 5.4.4）
- Unreal Engine **5.7.x** + 同上三个插件（引擎自带；实测 5.7.4）
- Node.js **>= 20**、pnpm 11（或 corepack）
- 无需 Python 包管理（UE 侧仅标准库）；无需 C++ 编译

### 下载

当前版本 **v0.1.0**，三个附件（[全部版本](https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases)）：

- UE 5.4 插件包：<https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases/download/v0.1.0/UEMCPBridge-5.4.zip>
- UE 5.7 插件包：<https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases/download/v0.1.0/UEMCPBridge-5.7.zip>
- 校验和：<https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases/download/v0.1.0/SHA256SUMS.txt>

安装三步：

1. 解压到 `<YourProject>/Plugins/`，得到 `Plugins/UEMCPBridge/`。
2. 启用 `UEMCPBridge`、`PythonScriptPlugin`、`EditorScriptingUtilities`（`.uproject` 写法见下节）。
3. 启动编辑器后执行 `curl http://127.0.0.1:18778/health`，返回 `"app":"uemcp-bridge"` 即就绪。

> 不用发行包时，把仓库里的 `UEMCPBridge/` 目录放进 `Plugins/` 等价。

> 插件为纯 Python，下载后无需编译：解压到 `Plugins/` 后由编辑器直接加载。

### 安装（UE 侧插件）

1. 复制 `UEMCPBridge/` 到 `<Project>/Plugins/UEMCPBridge/`。
2. 在 `<Project>.uproject` 启用三个插件：

```json
"Plugins": [
  { "Name": "UEMCPBridge", "Enabled": true },
  { "Name": "PythonScriptPlugin", "Enabled": true },
  { "Name": "EditorScriptingUtilities", "Enabled": true }
]
```

3. 启动编辑器（桥接自动拉起），验证：

```bash
curl -s http://127.0.0.1:18778/health
# 预期 "app": "uemcp-bridge"，含 ueVersion / port / pid / capabilities
```

### 在生产项目中使用

接到真实工程前，按这个顺序做：

1. **先备份，或确保版本控制是干净的。** 插件不会自动存盘，但编辑器里的改动会被后续保存写入工程；没有备份就不要开始。
2. **第一轮只用只读。** 默认策略就是 `read-only`（7 个只读工具）。先用 `editor.status` / `actor.query` / `asset.search` 核对返回是否符合预期；大工程重点看 `asset.search` 的耗时与 `SEARCH_TIMEOUT`（默认 20s，可用 `searchTimeoutMs` 调大）。
3. **写操作先 `dryRun`。** `actor.edit` 支持 `dryRun: true` 预演，确认变更清单后再真实执行；真实写入在编辑器事务内完成，**可用 `Ctrl+Z` 撤销**。
4. **`allowWrite` 按需临时开启，用完立即关闭。** Server 用 `--policy standard`，Bridge 设 `"allowWrite": true`，两边都要开；Bridge 配置只在启动时读取，**改完立即改回 `false` 并重启编辑器**。
5. **截图/视口操作时保持编辑器窗口在前台。** 无焦点时 UE 会把 tick 降到约 3 fps，`viewport.capture` 可能返回 `CAPTURE_TIMEOUT`；保持窗口可见，或增大 `timeoutMs`，或重试。
6. **生产环境不要开 `allowExec` / `allowConsole`**，除非你清楚这是把编辑器控制权交出去——无沙箱，执行也不可中断。
7. **多人/多会话并发要留余量。** Server 侧每会话 20 req/s、Bridge 全局 30 req/s；多人同时使用或批量调用可能收到 `RATE_LIMITED`（HTTP 429），退避后重试。

### 构建与运行（Server 侧）

```bash
cd uemcp
pnpm install
pnpm build          # 产物：packages/server/dist/index.js
pnpm typecheck      # 可选：类型检查
```

```bash
# 前台运行（HTTP，默认 127.0.0.1:18777，默认策略 read-only）
node packages/server/dist/index.js --transport http --policy standard

# stdio 模式（stdout 仅 MCP 帧，日志走 stderr）
node packages/server/dist/index.js --transport stdio
```

Windows 长驻建议用分离进程脚本（避免随终端会话被回收）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-server.ps1 -Port 18777 -Policy standard
powershell -ExecutionPolicy Bypass -File scripts\stop-server.ps1
```

常用参数：`--port N`、`--policy read-only|standard|full`、`--project <dir>`（多工程时建议显式指定）、`--bridge-url`、`--auth-token`、`--allow-destructive`、`--allow-console`、`--allow-exec`、`--disable-legacy-sse`。完整参数与环境变量见 [uemcp/README-DEV.md](uemcp/README-DEV.md)。

### MCP 客户端接入

**Claude Code（HTTP，推荐）**：

```bash
claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp
claude mcp list        # 预期：uemcp ✓ Connected
```

**Claude Code / CLI（stdio 配置）**：

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

**Cursor**（`.cursor/mcp.json`；按客户端版本二选一）：

Cursor 0.45.x（旧版 SSE 基线，D2 裁决）：

```json
{ "mcpServers": { "uemcp": { "url": "http://127.0.0.1:18777/sse" } } }
```

Cursor 0.46+：

```json
{ "mcpServers": { "uemcp": { "url": "http://127.0.0.1:18777/mcp" } } }
```

> 注：0.46+ 的 `/mcp`（Streamable HTTP）**未实测**；需要稳定接入时可回退到旧版 `/sse`（0.45.x 实测可用，架构 §3.4）。

**任意 HTTP 客户端（curl）**：

```bash
curl -s -D - -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0.0.0"}}}'
# 从响应头取 Mcp-Session-Id，后续请求携带该头即可 tools/list、tools/call
# 完整四步序列见 HANDOFF.md §5.4
```

### 安全默认与开启写操作

默认一切只读、仅回环、双向权限门（Server 策略 × Bridge 配置）、审计日志（不含 token 与 Python 源码）、Host/Origin 校验、令牌桶限流；桥接 token 每次编辑器启动轮换。详见 [UEMCPBridge/README.md](UEMCPBridge/README.md) 与架构文档 §6。

开启顺序（两端都要开）：

1. **写操作**：Server `--policy standard` 起；Bridge 在 `<Project>/Saved/UEMCP/bridge-settings.json` 设 `"allowWrite": true`（或环境变量 `UEMCP_BRIDGE_ALLOW_WRITE`）后重启编辑器。
2. **控制台 / Python**（默认隐藏，风险自担）：Server `--policy full --allow-console` / `--allow-exec`；Bridge 对应 `allowConsole` / `allowExec`。每次调用仍需确认（支持 elicitation 的客户端会弹确认；否则开关即策略级确认并记入审计）。

> ⚠️ **本机开发工具的固有风险**：开启 `ue_python_exec` 等于把编辑器进程控制权交给调用方（无沙箱、执行不可中断）；本机恶意程序读取 `~/.uemcp/bridge.json` 可取得桥接 token。这是本地开发工具的固有边界，请在可信环境使用；不要在录屏、演示、CI 中开启 exec。

### 测试

```bash
cd uemcp
pnpm smoke        # Server 自测：SMOKE RESULT: 71/71 passed
pnpm test         # node --test：单测 + 黑盒 36 项
pnpm typecheck && pnpm build
```

UE 侧自检（无需引擎的 11 个脚本 + 需 UnrealEditor-Cmd 的冒烟）见 [UEMCPBridge/README.md](UEMCPBridge/README.md) §7。测试端口约定：smoke 用 18999/19001–19008、单测用 19101–19199，避开真实服务端口 18777/18778。

### 目录结构

```text
├─ UEMCPBridge/        # UE 5.4/5.7 纯 Python 插件（桥接 + 自测脚本）
├─ uemcp/              # MCP Server（pnpm workspace：packages/shared + packages/server）
│  ├─ packages/shared/ # 工具名、zod Schema、错误码（@uemcp/shared）
│  ├─ packages/server/ # CLI、传输、发现、策略、审计、10 工具（@uemcp/server）
│  ├─ scripts/         # smoke.mjs、mock-bridge.mjs、start/stop-server.ps1
│  └─ tests/           # node --test 单测与黑盒
├─ docs/               # 架构设计 v0.2.0、裁决记录、测试计划与报告、代码审查报告
├─ LICENSE             # MIT
└─ HANDOFF.md          # 接手者指南（含完整快速开始与发布清单）
```

### 文档索引

| 文档 | 内容 |
|---|---|
| [docs/UEMCP-架构设计.md](docs/UEMCP-架构设计.md) | 架构基线 v0.2.0：端口/发现/错误模型/10 工具 Schema/安全模型 |
| [docs/UEMCP-架构裁决补充.md](docs/UEMCP-架构裁决补充.md) | 7 项关键决策记录（错误码表/确认流/端口策略等） |
| [uemcp/README-DEV.md](uemcp/README-DEV.md) | 开发者文档：构建/运行/部署/自测/实现契约/已知限制 |
| [UEMCPBridge/README.md](UEMCPBridge/README.md) | UE 侧：安装/配置/安全/RPC 方法表/自测 |
| [docs/UEMCP-测试执行报告.md](docs/UEMCP-测试执行报告.md) | 实测结论与覆盖范围 |
| [docs/UEMCP-代码审查报告.md](docs/UEMCP-代码审查报告.md) | 两轮审查记录 |
| [HANDOFF.md](HANDOFF.md) | 接手者指南（项目状态/已知限制/发布清单/待办） |

### 已知限制

- 蓝图节点创建/连线/删除与动画蓝图编辑**不支持**（`CAPABILITY_UNAVAILABLE`，需 P2 C++ 模块）。
- PIE 运行中的 Actor 编辑**不支持**：写操作返回 `EDITOR_UNSAFE_STATE`，只读查询仍可用。
- 本插件只作用于编辑器进程：不解析离线 `.uasset`，不操作打包后的运行时。
- 编辑器窗口失去焦点时，UE 会降低 tick 频率（实测约 3.1 fps），`viewport.capture` 可能因拿不到新帧而返回 `CAPTURE_TIMEOUT`（HTTP 504 / `-32037` / `retryable=true`，错误契约本身是正确的）。把编辑器窗口保持在前台或可见，或增大 `timeoutMs`，或重试即可。

### License

[MIT](LICENSE) © 2026 UEMCP contributors。MIT 仅覆盖本项目代码，不覆盖 Unreal Engine 及用户资产；使用本项目需自行拥有合法的 UE 引擎授权。

### 贡献与反馈

<!-- TODO: 补充 CONTRIBUTING.md、Issue/PR 指引、行为准则链接 -->
- Bug 反馈与功能建议：请开 Issue（附 UE 版本、客户端、`/health` 输出与错误码）。
- 安全问题：请勿公开披露，通过私有渠道联系维护者（占位：待补 SECURITY.md）。

## English

UEMCP is a **client-agnostic** MCP (Model Context Protocol) service for the Unreal Engine 5.4/5.7 editor. Point Claude Code, Cursor, or any HTTP client at it and drive **the editor that is currently open** over the standard MCP protocol: query and edit actors, manage levels, search assets, tune material-instance parameters, capture the viewport, and inspect or compile Blueprints.

- **Client-agnostic**: MCP is the only boundary. No chat UI is embedded (Streamable HTTP, legacy SSE, and stdio transports).
- **Editor-only**: acts on the editor process; does not parse offline `.uasset` files and does not drive packaged runtime games.
- **Local-first**: binds to `127.0.0.1` only by default; works out of the box, no deployment.
- **No C++ on the UE side**: a pure Python plugin with no C++ toolchain; the UE side depends on the Python standard library only.

> Engine: UE **5.4 / 5.7** (tested on 5.4.4 / 5.7.4). Status: MVP (v0.1.0); APIs may change between iterations.

---

### Features (10 MVP tools)

| Tool | What it does | Visible by default |
|---|---|---|
| `ue_editor_status` | Editor, current level, selected actors, viewport camera, capabilities and policy overview | Yes |
| `ue_actor_query` | Query actors by class, name, label or folder; paginated results | Yes |
| `ue_actor_edit` | Batch spawn, delete, transform, duplicate or select actors; edit a controlled set of properties (transaction + rollback + dryRun) | standard and above |
| `ue_level_control` | Inspect the current level and dirty packages; open, save or create levels | Yes (write actions: standard and above) |
| `ue_asset_search` | Search assets by path, name or class; query dependencies and referencers | Yes |
| `ue_material_params` | Read material and material-instance parameters; set instance parameters; create instances | Yes (write actions: standard and above) |
| `ue_viewport_capture` | Capture the level viewport or the PIE frame (PNG/JPEG; inline image or file path) | Yes |
| `ue_blueprint` | Inspect Blueprint structure (parent class, variables, components, graphs, compile state); trigger a compile (node-level reads are experimental) | Yes |
| `ue_console_command` | Run console commands (allowlist-restricted) | **Hidden** |
| `ue_python_exec` | Run Python on the editor game thread (no sandbox) | **Hidden** |

**Explicitly not supported**: actor edits while PIE is running; Blueprint node creation, wiring and animation Blueprint editing (needs a P2 C++ module); material graph editing; asset import, export or move; console output capture; editor UI/Slate automation; Sequencer/Niagara; remote multi-user service.

---

### Architecture

```text
┌──────────────────────────┐
│ MCP client (any)         │  Claude Code / Cursor / curl / your own
└────────────┬─────────────┘
             │ MCP: stdio, Streamable HTTP (:18777/mcp), or legacy SSE (:18777/sse)
             ▼
┌──────────────────────────────────────────────┐
│ UEMCP Server (Node.js/TypeScript, :18777)    │
│ sessions / policy / discovery / audit / rate limit │
└────────────┬─────────────────────────────────┘
             │ HTTP JSON-RPC 2.0 + X-UEMCP-Token
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ UEMCPBridge (inside the UE 5.4/5.7 editor, pure Python, :18778) │
│ ThreadingHTTPServer + single game-thread queue                  │
└────────────┬────────────────────────────────────────────────────┘
             │ unreal.* Python API (game thread only)
             ▼
        UE 5.4/5.7 editor (World / Actor / AssetRegistry / Viewport)
```

- After startup the bridge writes discovery files under `~/.uemcp/`; the server discovers and validates them (pid + health double check; stale files are skipped).
- Every `unreal.*` call runs on the game-thread queue; HTTP threads never call the engine.
- Default ports: server `18777` (if taken it **exits**, so pick another port explicitly); bridge `18778` (if taken it falls back to 18779–18788).

---

### Requirements

- Unreal Engine **5.4.x** + PythonScriptPlugin + EditorScriptingUtilities (bundled with the engine; tested on 5.4.4)
- Unreal Engine **5.7.x** + the same three plugins (bundled with the engine; tested on 5.7.4)
- Node.js **>= 20**, pnpm 11 (or corepack)
- No Python packaging on the UE side (standard library only); no C++ build

### Download

Current release: **v0.1.0**, three assets ([all releases](https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases)):

- UE 5.4 plugin: <https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases/download/v0.1.0/UEMCPBridge-5.4.zip>
- UE 5.7 plugin: <https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases/download/v0.1.0/UEMCPBridge-5.7.zip>
- Checksums: <https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases/download/v0.1.0/SHA256SUMS.txt>

Install in three steps:

1. Unzip into `<YourProject>/Plugins/` so that you get `Plugins/UEMCPBridge/`.
2. Enable `UEMCPBridge`, `PythonScriptPlugin` and `EditorScriptingUtilities` (see the `.uproject` snippet below).
3. Start the editor, then run `curl http://127.0.0.1:18778/health`; a response containing `"app":"uemcp-bridge"` means the bridge is up.

> Prefer source? Copy the repository's `UEMCPBridge/` directory into `Plugins/` instead.

> The plugin is pure Python: there is no build step after download — unzip it into `Plugins/` and the editor loads it directly.

### Install (UE plugin)

1. Copy `UEMCPBridge/` to `<Project>/Plugins/UEMCPBridge/`.
2. Enable the three plugins in `<Project>.uproject`:

```json
"Plugins": [
  { "Name": "UEMCPBridge", "Enabled": true },
  { "Name": "PythonScriptPlugin", "Enabled": true },
  { "Name": "EditorScriptingUtilities", "Enabled": true }
]
```

3. Start the editor (the bridge starts automatically) and verify:

```bash
curl -s http://127.0.0.1:18778/health
# expect "app": "uemcp-bridge" plus ueVersion / port / pid / capabilities
```

### Using it on a real project

Before pointing it at a production project, work through this list in order:

1. **Back up first, or make sure version control is clean.** The plugin never saves on its own, but editor changes are written to the project by later saves. Do not start without a backup.
2. **Start read-only.** The default policy is `read-only` (7 read-only tools). Check that `editor.status` / `actor.query` / `asset.search` return what you expect; on large projects watch `asset.search` latency and `SEARCH_TIMEOUT` (20 s by default, raise `searchTimeoutMs` if needed).
3. **Rehearse writes with `dryRun`.** `actor.edit` accepts `dryRun: true`; review the planned changes before running for real. Writes run inside an editor transaction, so **`Ctrl+Z` undoes them**.
4. **Turn `allowWrite` on only when needed, and off right after.** Enable both sides: server `--policy standard` and bridge `"allowWrite": true`. The bridge reads its settings at startup, so **set it back to `false` and restart the editor** when you are done.
5. **Keep the editor window in the foreground for captures.** Without focus, UE throttles ticks to about 3 fps and `viewport.capture` may return `CAPTURE_TIMEOUT`; keep the window visible, raise `timeoutMs`, or retry.
6. **Do not enable `allowExec` / `allowConsole` in production** unless you accept handing over control of the editor: there is no sandbox, and a running snippet cannot be interrupted.
7. **Leave headroom for concurrent sessions.** The server allows 20 req/s per session and the bridge 30 req/s globally; concurrent users or batch calls may receive `RATE_LIMITED` (HTTP 429) — back off and retry.

### Build and run (server side)

```bash
cd uemcp
pnpm install
pnpm build          # output: packages/server/dist/index.js
pnpm typecheck      # optional: type check
```

```bash
# foreground HTTP server (127.0.0.1:18777 by default, policy read-only by default)
node packages/server/dist/index.js --transport http --policy standard

# stdio mode (stdout carries MCP frames only; logs go to stderr)
node packages/server/dist/index.js --transport stdio
```

On Windows, run the server as a detached process so it survives terminal sessions:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-server.ps1 -Port 18777 -Policy standard
powershell -ExecutionPolicy Bypass -File scripts\stop-server.ps1
```

Common flags: `--port N`, `--policy read-only|standard|full`, `--project <dir>` (recommended when several projects are open), `--bridge-url`, `--auth-token`, `--allow-destructive`, `--allow-console`, `--allow-exec`, `--disable-legacy-sse`. See [uemcp/README-DEV.md](uemcp/README-DEV.md) for the full flag and environment-variable list.

### Connecting MCP clients

**Claude Code (HTTP, recommended)**:

```bash
claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp
claude mcp list        # expected: uemcp ✓ Connected
```

**Claude Code / CLI (stdio config)**:

```json
{
  "mcpServers": {
    "uemcp": {
      "command": "node",
      "args": ["<repo>/uemcp/packages/server/dist/index.js", "--transport", "stdio", "--policy", "standard"]
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`; pick one depending on the client version):

Cursor 0.45.x (legacy SSE baseline, decision D2):

```json
{ "mcpServers": { "uemcp": { "url": "http://127.0.0.1:18777/sse" } } }
```

Cursor 0.46+:

```json
{ "mcpServers": { "uemcp": { "url": "http://127.0.0.1:18777/mcp" } } }
```

> Note: `/mcp` (Streamable HTTP) on 0.46+ is **not tested yet**; fall back to the legacy `/sse` endpoint when you need a verified path (tested with 0.45.x, architecture §3.4).

**Any HTTP client (curl)**:

```bash
curl -s -D - -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0.0.0"}}}'
# take Mcp-Session-Id from the response headers and send it on tools/list and tools/call
# the full four-step sequence is in HANDOFF.md §5.4
```

### Security defaults and enabling writes

Everything is read-only, loopback-only, and gated on both sides (server policy × bridge config) by default. Audit logs exclude tokens and Python source; Host/Origin checks and token-bucket rate limiting are on; the bridge token rotates on every editor start. See [UEMCPBridge/README.md](UEMCPBridge/README.md) and architecture §6 for details.

Enable writes in this order (both sides must agree):

1. **Writes**: start the server with `--policy standard`; set `"allowWrite": true` in `<Project>/Saved/UEMCP/bridge-settings.json` (or `UEMCP_BRIDGE_ALLOW_WRITE`) and restart the editor.
2. **Console / Python** (hidden by default, at your own risk): server `--policy full --allow-console` / `--allow-exec`; bridge `allowConsole` / `allowExec`. Each call still requires confirmation (elicitation-capable clients prompt; otherwise the switch itself is policy-level confirmation and is audited).

> ⚠️ **Inherent risk of a local developer tool**: enabling `ue_python_exec` hands control of the editor process to the caller (no sandbox, no way to interrupt a running snippet). Any local process can read `~/.uemcp/bridge.json` and obtain the bridge token. This is the inherent boundary of a local development tool: use it in trusted environments only, and never enable exec for screen recordings, demos or CI.

### Testing

```bash
cd uemcp
pnpm smoke        # server self-test: SMOKE RESULT: 71/71 passed
pnpm test         # node --test: unit + black-box, 36 cases
pnpm typecheck && pnpm build
```

UE-side self-checks (11 scripts that need no engine, plus a commandlet smoke test) are documented in [UEMCPBridge/README.md](UEMCPBridge/README.md) §7. Test ports: 18999 and 19001–19008 for smoke, 19101–19199 for unit tests, so the real 18777/18778 ports are never touched.

### Repository layout

```text
├─ UEMCPBridge/        # UE 5.4/5.7 pure-Python plugin (bridge + self-tests)
├─ uemcp/              # MCP server (pnpm workspace: packages/shared + packages/server)
│  ├─ packages/shared/ # tool names, zod schemas, error codes (@uemcp/shared)
│  ├─ packages/server/ # CLI, transports, discovery, policy, audit, 10 tools (@uemcp/server)
│  ├─ scripts/         # smoke.mjs, mock-bridge.mjs, start/stop-server.ps1
│  └─ tests/           # node --test unit and black-box tests
├─ docs/               # architecture v0.2.0, decisions, test plan and report, code review
├─ LICENSE             # MIT
└─ HANDOFF.md          # maintainer guide (quick start and release checklist)
```

### Documentation

| Document | Contents |
|---|---|
| [docs/UEMCP-架构设计.md](docs/UEMCP-架构设计.md) | Architecture baseline v0.2.0: ports, discovery, error model, 10-tool schemas, security model |
| [docs/UEMCP-架构裁决补充.md](docs/UEMCP-架构裁决补充.md) | Seven key decisions (error-code table, confirmation flow, port policy, …) |
| [uemcp/README-DEV.md](uemcp/README-DEV.md) | Developer guide: build, run, deploy, self-tests, implementation contracts, known limitations |
| [UEMCPBridge/README.md](UEMCPBridge/README.md) | UE side: install, configuration, security, RPC method table, self-tests |
| [docs/UEMCP-测试执行报告.md](docs/UEMCP-测试执行报告.md) | Test results and coverage |
| [docs/UEMCP-代码审查报告.md](docs/UEMCP-代码审查报告.md) | Two rounds of code review |
| [HANDOFF.md](HANDOFF.md) | Maintainer guide (status, known limitations, release checklist, TODO) |

### Known limitations

- Blueprint node creation, wiring, deletion and animation Blueprint editing are **not supported** (`CAPABILITY_UNAVAILABLE`; needs a P2 C++ module).
- Actor edits inside PIE are **not supported**: write operations return `EDITOR_UNSAFE_STATE`; read-only queries still work.
- The plugin acts on the editor process only: it does not parse offline `.uasset` files and does not operate on packaged runtimes.
- When the editor window loses focus, UE throttles ticks (about 3.1 fps in our test), so `viewport.capture` may return `CAPTURE_TIMEOUT` (HTTP 504 / `-32037` / `retryable=true`; the error contract itself is correct). Keep the editor window foreground or visible, raise `timeoutMs`, or retry.

### License

[MIT](LICENSE) © 2026 UEMCP contributors. MIT covers this project's code only; it does not cover Unreal Engine or user assets. You must hold a valid Unreal Engine license to use this project.

### Contributing

<!-- TODO: add CONTRIBUTING.md, issue/PR guidelines and a code-of-conduct link -->
- Bugs and feature requests: open an issue (include your UE version, MCP client, `/health` output and error code).
- Security: do not disclose publicly; contact the maintainers privately (placeholder: SECURITY.md pending).
