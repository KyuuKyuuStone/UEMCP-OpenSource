# UEMCP

> **Unreal and Unreal Engine are trademarks or registered trademarks of Epic Games, Inc. in the United States and elsewhere. This project is an independent, community-developed tool and is not affiliated with, endorsed by, or sponsored by Epic Games, Inc. "Unreal" is used solely to describe compatibility with Unreal Engine. All other trademarks are the property of their respective owners.**

UEMCP 是**客户端无关**的 Unreal Engine 5.4 编辑器 MCP（Model Context Protocol）服务：用 Claude Code、Cursor 或任意 HTTP 客户端，通过标准 MCP 协议操作**当前打开的编辑器**——查询与编辑 Actor、管理关卡、搜索资产、调整材质实例参数、截取视口、查询与编译蓝图。

- **客户端无关**：MCP 协议是唯一边界，不内嵌聊天 UI（Streamable HTTP / 旧版 SSE / stdio 三种传输）。
- **仅编辑器**：直接作用于编辑器进程，不解析离线 `.uasset`，不支持打包后的运行时游戏。
- **本地优先**：默认只绑定 `127.0.0.1`，开箱即用，无需部署。
- **UE 侧零编译**：纯 Python 插件，不需要 C++ 工具链；UE 侧仅依赖 Python 标准库。

> 适用引擎：UE **5.4.x**（5.4.4 实测）。状态：MVP（v0.1.0），API 可能随迭代调整。

---

## 特性（MVP 10 个工具）

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

## 架构

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
┌──────────────────────────────────────────────┐
│ UEMCPBridge（UE 5.4 编辑器内，纯 Python，:18778）│
│ ThreadingHTTPServer + 游戏线程单队列          │
└────────────┬─────────────────────────────────┘
             │ unreal.* Python API（仅游戏线程）
             ▼
        UE 5.4 编辑器（World / Actor / AssetRegistry / Viewport）
```

- 桥接启动后写发现文件 `~/.uemcp/`；Server 自动发现并校验（pid/health 双重校验，陈旧文件自动跳过）。
- 编辑器内所有 `unreal.*` 调用经游戏线程队列执行，HTTP 线程零引擎调用。
- 默认端口：Server `18777`（被占则**失败退出**，显式换端口）；Bridge `18778`（被占则自动回退 18779–18788）。

---

## 环境要求

- Unreal Engine **5.4.x** + PythonScriptPlugin + EditorScriptingUtilities（引擎自带）
- Node.js **>= 20**、pnpm 11（或 corepack）
- 无需 Python 包管理（UE 侧仅标准库）；无需 C++ 编译

## 安装（UE 侧插件）

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

## 构建与运行（Server 侧）

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

## MCP 客户端接入

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

> 注：0.46+ 的 `/mcp`（Streamable HTTP）**未实测**，若客户端改走 Streamable HTTP 再验证；旧版 SSE 端点始终可用（架构 §3.4）。

**任意 HTTP 客户端（curl）**：

```bash
curl -s -D - -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0.0.0"}}}'
# 从响应头取 Mcp-Session-Id，后续请求携带该头即可 tools/list、tools/call
# 完整四步序列见 HANDOFF.md §5.4
```

## 安全默认与开启写操作

默认一切只读、仅回环、双向权限门（Server 策略 × Bridge 配置）、审计日志（不含 token 与 Python 源码）、Host/Origin 校验、令牌桶限流。详见 [UEMCPBridge/README.md](UEMCPBridge/README.md) 与架构文档 §6。

开启顺序（两端都要开）：

1. **写操作**：Server `--policy standard` 起；Bridge 在 `<Project>/Saved/UEMCP/bridge-settings.json` 设 `"allowWrite": true`（或环境变量 `UEMCP_BRIDGE_ALLOW_WRITE`）后重启编辑器。
2. **控制台 / Python**（默认隐藏，风险自担）：Server `--policy full --allow-console` / `--allow-exec`；Bridge 对应 `allowConsole` / `allowExec`。每次调用仍需确认（支持 elicitation 的客户端会弹确认；否则开关即策略级确认并记入审计）。

> ⚠️ **本机开发工具的固有风险**：开启 `ue_python_exec` 等于把编辑器进程控制权交给调用方（无沙箱、执行不可中断）；本机恶意程序读取 `~/.uemcp/bridge.json` 可取得桥接 token。这是本地开发工具的固有边界，请在可信环境使用；不要在录屏、演示、CI 中开启 exec。

## 测试

```bash
cd uemcp
pnpm smoke        # Server 自测：SMOKE RESULT: 71/71 passed
pnpm test         # node --test：单测 + 黑盒 36 项
pnpm typecheck && pnpm build
```

UE 侧自检（无需引擎的 8 个脚本 + 需 UnrealEditor-Cmd 的冒烟）见 [UEMCPBridge/README.md](UEMCPBridge/README.md) §7。测试端口约定：smoke 用 18999/19001–19008、单测用 19101–19199，避开真实服务端口 18777/18778。

## 目录结构

```text
├─ UEMCPBridge/        # UE 5.4 纯 Python 插件（桥接 + 自测脚本）
├─ uemcp/              # MCP Server（pnpm workspace：packages/shared + packages/server）
│  ├─ packages/shared/ # 工具名、zod Schema、错误码（@uemcp/shared）
│  ├─ packages/server/ # CLI、传输、发现、策略、审计、10 工具（@uemcp/server）
│  ├─ scripts/         # smoke.mjs、mock-bridge.mjs、start/stop-server.ps1
│  └─ tests/           # node --test 单测与黑盒
├─ docs/               # 架构设计 v0.2.0、裁决记录、测试计划与报告、代码审查报告
├─ LICENSE             # MIT
└─ HANDOFF.md          # 接手者指南（含完整快速开始与发布清单）
```

## 文档索引

| 文档 | 内容 |
|---|---|
| [docs/UEMCP-架构设计.md](docs/UEMCP-架构设计.md) | 架构基线 v0.2.0：端口/发现/错误模型/10 工具 Schema/安全模型 |
| [docs/UEMCP-架构裁决补充.md](docs/UEMCP-架构裁决补充.md) | 7 项关键决策记录（错误码表/确认流/端口策略等） |
| [uemcp/README-DEV.md](uemcp/README-DEV.md) | 开发者文档：构建/运行/部署/自测/实现契约/已知限制 |
| [UEMCPBridge/README.md](UEMCPBridge/README.md) | UE 侧：安装/配置/安全/RPC 方法表/自测 |
| [docs/UEMCP-测试执行报告.md](docs/UEMCP-测试执行报告.md) | 实测结论与覆盖范围 |
| [docs/UEMCP-代码审查报告.md](docs/UEMCP-代码审查报告.md) | 两轮审查记录 |
| [HANDOFF.md](HANDOFF.md) | 接手者指南（项目状态/已知限制/发布清单/待办） |

## License

[MIT](LICENSE) © 2026 UEMCP contributors。MIT 仅覆盖本项目代码，不覆盖 Unreal Engine 及用户资产；使用本项目需自行拥有合法的 UE 引擎授权。

## 贡献与反馈

<!-- TODO: 补充 CONTRIBUTING.md、Issue/PR 指引、行为准则链接 -->
- Bug 反馈与功能建议：请开 Issue（附 UE 版本、客户端、`/health` 输出与错误码）。
- 安全问题：请勿公开披露，通过私有渠道联系维护者（占位：待补 SECURITY.md）。
