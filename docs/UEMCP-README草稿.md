# UEMCP — 面向 Unreal Engine 5.4 编辑器的通用 MCP 服务（README 与接入指南 · 草稿）

> **Unreal and Unreal Engine are trademarks or registered trademarks of Epic Games, Inc. in the United States and elsewhere. This project is an independent, community-developed tool and is not affiliated with, endorsed by, or sponsored by Epic Games, Inc. "Unreal" is used solely to describe compatibility with Unreal Engine. All other trademarks are the property of their respective owners.**

| 项 | 值 |
|---|---|
| 文档状态 | **草稿 v0.1.0（2026-10-20）——项目代码尚未实现** |
| 依据材料 | 《UEMCP 架构设计与工具清单》v0.1.0（`Docs/UEMCP-架构设计.md`，下称「架构文档」） |
| 适用引擎 | Unreal Engine 5.4.x（主验证 5.4.4） |
| 读者前提 | 会安装 Node.js 的 UE 开发者 |

> ⚠️ **本文描述的是设计目标与规划行为，不是可用产品的操作手册。** 凡标注「待实现验证」的内容，在首个可用版本发布并实测通过前，**不构成任何操作保证**。逐条状态声明见 [§10 文档状态声明](#10-文档状态声明)。

---

## 1. 项目简介与定位

UEMCP 让任意 MCP 客户端（Claude Code、Cursor、自研 HTTP 客户端、脚本等）通过标准 Model Context Protocol 操作**当前打开的 Unreal Engine 5.4 编辑器**——查询与编辑 Actor、管理关卡、搜索资产、调整材质实例参数、截取视口、查询与编译蓝图等（架构文档 §0.1、§1.1）。

三个定位关键词（架构文档 §1.1）：

- **客户端无关**：MCP 协议是唯一边界，不内嵌任何 AI 聊天 UI，不依赖某个客户端的私有能力（§1.2-1）。
- **仅编辑器**：工具调用直接作用于当前打开的编辑器进程，不解析离线 `.uasset`，**不操作打包后的运行时游戏**（Shipping 包内无 Python、无本插件，§1.2-2）。
- **本地优先**：默认只绑定 `127.0.0.1`，开箱即用，无需部署；不做远程/多人服务（§1.2-3）。

结构一句话（§0.1）：**MCP Server（Node.js/TypeScript 独立进程，默认 `127.0.0.1:18777`）+ UE 编辑器内 Python Bridge（纯 Python 插件，默认 `127.0.0.1:18778`）**。UE 侧 MVP 只用 Python API，不做编译型 C++ 插件（P2 才考虑可选 C++ 辅助模块）。

### 1.1 目标读者

会安装 Node.js、熟悉 UE 编辑器与「插件」菜单的开发者与技术美术。**不需要** C++ 编译环境，**不需要** Python 包管理经验——UE 侧仅使用 Python 标准库 + `unreal` 模块，不要求 pip 安装任何包（§7.3）。

### 1.2 环境前提

| 项 | 要求 | 依据 |
|---|---|---|
| 引擎 | UE 5.4.x（主验证 5.4.4）；不承诺任意 UE 版本 | §8.2、§1.2-6 |
| Node.js | ≥ 20（`npx` 运行 MCP Server；CI 覆盖 20 与 22） | §7.3 |
| UE 插件依赖 | Python Editor Script Plugin（引擎自带，Experimental） | §4.1、§10.4-3 |
| UE 侧 Python 依赖 | 无（仅标准库：`http.server`、`json`、`threading` 等） | §7.3 |
| 操作系统 | Windows 优先；macOS/Linux **待确认**（架构文档仅注明「Windows 优先」，跨平台承诺需架构师确认） | §7.6 |
| MCP 客户端 | 任选其一：Claude Code / Cursor / 通用 HTTP（三类接入配置见 §5） | §1.1-1 |

---

## 2. 特性列表（MVP 边界）

依据架构文档 §1.3「MVP 边界清单」整理。

### 2.1 支持（MVP 交付）

- 编辑器状态、当前关卡、选中 Actor、视口相机查询
- Actor 查询、生成、删除、变换、受控属性修改、复制、选择
- 关卡打开、保存、新建、脏包列表（另存为延后）
- 资产搜索、依赖/引用查询
- 材质实例参数读取/设置、创建材质实例
- 视口/PIE 截图
- 控制台命令（白名单限制、默认隐藏）
- Python 执行（默认隐藏）
- 蓝图变量/组件/图/编译状态**只读**查询、触发编译

### 2.2 明确不支持（避免预期落差）

| 不支持的项 | 说明 |
|---|---|
| PIE 内的 Actor 操作 | §1.3 |
| 蓝图组件层级重建、任意 UPROPERTY 反射写入 | §1.3 |
| 关卡流送（Level Streaming）管理 | §1.3 |
| 资产导入/导出、重命名/移动、批量修复重定向器 | §1.3、§1.2-7 |
| 材质节点图编辑 | §1.3 |
| 编辑器 UI 截图、Slate 控件操作 | §1.3 |
| 控制台输出回读 | UE Python 层无法可靠拿到控制台回显，MVP 明确返回 `outputAvailable:false`（§1.2-8、§5.8） |
| Python 调试器集成、代码沙箱 | §1.3、§1.2-4 |
| 蓝图节点创建/连线、动画蓝图状态机编辑 | UE 5.4 Python 无公开 API；P2 走 C++ 辅助模块（§0.3-4、§8.1） |
| 内嵌 AI 聊天 UI | §1.2-1 |
| 操作打包后的运行时游戏 | §1.2-2 |
| 远程/多人服务、`0.0.0.0` 监听 | §1.2-3、§6.2 |
| Source Control 操作、打包构建 | §1.2-7 |
| Sequencer、Niagara 专用编辑 | §1.2-5 |

---

## 3. 架构一图流

```
┌──────────────────────────┐
│ MCP 客户端（任选）        │
│ - Claude Code            │
│ - Cursor                 │
│ - 自研 / curl            │
└────────────┬─────────────┘
             │ MCP 协议：stdio 或 Streamable HTTP(:18777/mcp) 或 旧版 SSE(:18777/sse)
             ▼
┌─────────────────────────────────────────────────────────────┐
│ UEMCP Server（Node.js/TypeScript，独立进程，:18777）         │
│ - MCP 协议与会话管理、zod 校验                               │
│ - 策略门（read-only / standard / full）                      │
│ - 桥接发现（~/.uemcp/bridges/*.json）、审计日志              │
└────────────┬────────────────────────────────────────────────┘
             │ 内部协议：HTTP JSON-RPC 2.0（X-UEMCP-Token）
             │ POST http://127.0.0.1:18778/rpc
             ▼
┌─────────────────────────────────────────────────────────────┐
│ UEMCPBridge（UE 5.4 编辑器内，纯 Python 插件，:18778）       │
│ - ThreadingHTTPServer + 游戏线程调度队列（Slate post-tick）  │
└────────────┬────────────────────────────────────────────────┘
             │ unreal.* Python API（仅游戏线程）
             ▼
┌─────────────────────────────────────────────────────────────┐
│ UE 5.4 编辑器：World / Actor / AssetRegistry / Viewport     │
└─────────────────────────────────────────────────────────────┘
```

要点（架构文档 §2）：

- 三种传输共享同一套工具实现；一个进程只承载一种 MCP 传输，按启动参数二选一（§0.3-6、§3.1）。
- MCP ↔ UE 之间是内部 HTTP JSON-RPC 2.0，可用 curl 排障；桥接端仅 Python 标准库实现（§0.2）。
- 所有 `unreal.*` 调用经单队列调度到游戏线程执行（§2.6）。
- 完整组件图与端口规划见架构文档 §2.1、§2.3（18779 为 P2 预留 WebSocket，当前不实现）。

---

## 4. 安装与启用

> **本节所有步骤均为「待实现验证」状态**（依据架构文档 §10.4 编写，代码尚未实现）。每步的验证依据与已知风险单独标注。

### 4.1 前置环境

1. 安装 Unreal Engine 5.4（Epic Games Launcher）。
2. 安装 Node.js ≥ 20（<https://nodejs.org/>）。验证：

```bash
node --version
npx --version
```

### 4.2 UE 侧：安装 Python 桥接插件【待实现验证】

1. 将 `UEMCPBridge` 插件目录复制到 `<Project>/Plugins/UEMCPBridge`（§10.4-2）。分发形态为纯文本插件，zip 解压即可，无需编译（§0.2、§4.2）。
2. 在编辑器「编辑 → 插件」中启用 **Python Editor Script Plugin**（插件会自动声明对该插件的依赖，§10.4-3）。
3. 重启编辑器。
4. 验证（§10.4-4）：确认以下文件生成——
   - `<Project>/Saved/UEMCP/bridge-settings.json`
   - `~/.uemcp/bridge.json`（以及 `~/.uemcp/bridges/<projectHash>.json`，§2.4）

已知风险标注：

- **待实现验证（架构文档 A1，§8.4）**：「启用 PythonScriptPlugin 后，插件的 `Content/Python/init_unreal.py` 会自动执行」这一假设需 PoC 实测。失败时的既定备选：改用项目 `Config/DefaultEngine.ini` 的 Python 启动脚本，或提示用户手动执行（§8.4 A1）。
- 加载链说明：编辑器启动 → Python 插件扫描所有启用插件的 `Content/Python/` → 执行 `init_unreal.py` → 启动桥接 HTTP 服务 → 写发现文件；编辑器退出时停止服务并删除发现文件（§4.4）。
- 桥接端默认值：端口 18778、只读、禁止 exec/console（§4.4）。

### 4.3 MCP Server：npx 运行【待实现验证】

```bash
npx -y @uemcp/server --transport http --policy standard
```

（§10.4-5）

- 包名 `@uemcp/server`（§7.3）**尚未发布到 npm，首次发布前该命令不可用**。
- 验证（§10.4-6 之前置）：`GET http://127.0.0.1:18777/health` 返回 `{"ok": true, "name": "uemcp", ...}`，且 `bridge.connected` 为 `true`（§3.3）。
- 健康检查只读缓存状态，不执行编辑器调用（§3.3）。

常用启动参数（仅列架构文档已出现者；**完整 CLI 参数表待实现后确认**）：

| 参数 | 作用 | 依据 |
|---|---|---|
| `--transport stdio \| http` | 传输模式，二选一 | §3.2、§10.4-5 |
| `--policy <read-only\|standard\|full>` | 策略门 | §6.3、§10.4-5 |
| `--allow-destructive` | 无 elicitation 时允许 delete/覆盖/批量保存 | §6.3 |
| `--allow-console` | 允许 `ue_console_command` | §6.3 |
| `--allow-exec` | 允许 `ue_python_exec` | §6.3 |
| `--bridge-url <url>` | 直连桥接地址 | §2.4 |
| `--project <dir>` | 按工程目录匹配发现文件 | §2.4 |
| `--auth-token <token>` | MCP 入口鉴权 | §6.6 |
| `--disable-legacy-sse` | 关闭旧版 `/sse` 端点 | §3.4 |
| `--port` / `--http-port` | 换端口（精确参数名待实现确认） | §10.5 |

环境变量（优先级：命令行 > 环境变量 > 发现文件 > 默认值，§2.3）：

```text
UEMCP_HTTP_PORT      # 默认 18777
UEMCP_BRIDGE_PORT    # 默认 18778
UEMCP_BRIDGE_URL
UEMCP_BRIDGE_TOKEN
UEMCP_AUTH_TOKEN     # MCP 入口可选鉴权
```

### 4.4 连接验证【待实现验证】

在任意已接入客户端（见 §5）调用 `ue_editor_status`，应返回 UE 版本、当前关卡、选中 Actor 与能力探测结果（§10.4-7、§5.1）。或直接：

```bash
curl http://127.0.0.1:18777/health
```

---

## 5. 客户端接入配置

> 以下配置格式依据架构文档 §3.5 与 §3.3 编写，**连接行为均待实现验证**。

### 5.1 Claude Code — Streamable HTTP（推荐）

```bash
claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp
```

启用可选鉴权（§3.5.1）：

```bash
claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp \
  --header "Authorization: Bearer ${UEMCP_AUTH_TOKEN}"
```

项目级 `.mcp.json`（§3.5.1）：

```json
{
  "mcpServers": {
    "uemcp": {
      "type": "http",
      "url": "http://127.0.0.1:18777/mcp",
      "headers": {
        "Authorization": "Bearer ${UEMCP_AUTH_TOKEN}"
      }
    }
  }
}
```

> 若当前 Claude Code 版本对 `.mcp.json` 的环境变量展开有限制，直接写明文本地 token 或省略鉴权（仅回环）（§3.5.1）。
> **待实现验证（A5，§8.4）**：Claude Code 当前版本支持 `--transport http` 与自定义 header 需实机确认；失败时回退 stdio 模式。

### 5.2 Claude Code / CLI — stdio

```json
{
  "mcpServers": {
    "uemcp": {
      "command": "npx",
      "args": ["-y", "@uemcp/server", "--transport", "stdio"]
    }
  }
}
```

Windows 上若客户端不解析 `npx.cmd`（§3.5.2）：

```json
{
  "mcpServers": {
    "uemcp": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@uemcp/server", "--transport", "stdio"]
    }
  }
}
```

### 5.3 Cursor — Streamable HTTP / 旧版 SSE

`.cursor/mcp.json`（项目）或 `~/.cursor/mcp.json`（全局）（§3.5.3）：

```json
{
  "mcpServers": {
    "uemcp": {
      "url": "http://127.0.0.1:18777/mcp",
      "headers": {
        "Authorization": "Bearer ${UEMCP_AUTH_TOKEN}"
      }
    }
  }
}
```

若客户端版本不支持 Streamable HTTP，改用旧版 SSE 端点（§3.5.3）：

```json
{
  "mcpServers": {
    "uemcp": {
      "url": "http://127.0.0.1:18777/sse"
    }
  }
}
```

> Cursor 不同版本对 `url` 的语义（SSE vs Streamable HTTP）不同；以实际版本的 MCP 设置为准，两种端点都可用（§3.5.3）。
> **待实现验证（A6，§8.4）**：Cursor 当前版本对两种端点的实际支持需实机确认。

### 5.4 通用 HTTP / curl

最小调用序列（§3.5.4）：`initialize` → `notifications/initialized`（202）→ `tools/list` → `tools/call`。注意 `Accept` 必须同时含 `application/json` 与 `text/event-stream`（§3.5.4）。

以下示例为 bash 语法（源自架构文档 §3.3；Windows PowerShell 的引号语义不同，建议在 Git Bash/WSL 中执行）。

第 1 步，初始化并从响应头记录 `Mcp-Session-Id`（§3.3）：

```bash
curl -s -D - -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": { "name": "curl", "version": "0.0.0" }
    }
  }'
```

第 2 步，发送 initialized 通知（预期 `202 Accepted`，无 body，§3.3）：

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: <上一步响应头>' \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
```

第 3 步，列出工具（§3.3）：

```bash
curl -s -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: <上一步响应头>' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

第 4 步，调用工具（以 `ue_editor_status` 为例；格式依据 MCP `tools/call` 标准与 §2.5 链路）：

```bash
curl -s -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: <上一步响应头>' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ue_editor_status","arguments":{}}}'
```

> 服务端可能以 SSE 格式（`text/event-stream`）响应，客户端需按 `data:` 行解析（§3.5.4）。会话空闲 TTL 30 分钟；未知/过期会话返回 404，重新 `initialize` 即可（§3.3）。

---

## 6. 工具参考（MVP 共 10 个）

权限级别（§5.0.3）：**P0 = 只读**、**P1 = 写**、**P2 = 危险**。策略模式（§6.3）：`read-only` 只注册 P0；`standard` 注册 P0+P1；`full` 注册全部（P2 仍需独立开关）。

| 工具 | 用途 | 级别 | 各策略下可用性 | 默认隐藏 | 参数细节 |
|---|---|---|---|---|---|
| `ue_editor_status` | 编辑器/当前关卡/选中 Actor/视口相机/能力/策略总览 | P0 | 三种策略均可用 | 否 | 架构文档 §5.1 |
| `ue_actor_query` | 按类/名称/标签/目录查询关卡或选中 Actor，分页返回 | P0 | 三种策略均可用 | 否 | §5.2 |
| `ue_actor_edit` | 批量生成/删除/变换/复制/选择 Actor、修改受控属性白名单 | P1 | read-only 不可用 | 否（`delete` 需确认） | §5.3 |
| `ue_level_control` | 查询当前关卡与脏包；打开/保存/新建关卡 | P0/P1 | read-only 下仅查询 | 否 | §5.4 |
| `ue_asset_search` | 按路径/名称/类搜索资产；查询依赖与反向引用 | P0 | 三种策略均可用 | 否 | §5.5 |
| `ue_material_params` | 读取材质/实例参数；设置实例参数；创建实例 | P0/P1 | read-only 下仅读取 | 否 | §5.6 |
| `ue_viewport_capture` | 截取关卡视口或 PIE 画面，返回 image 内容或文件路径 | P0 | 三种策略均可用 | 否 | §5.7 |
| `ue_console_command` | 向编辑器/PIE 世界执行控制台命令（白名单） | P2 | 仅 full + 双端开关 | **是** | §5.8 |
| `ue_python_exec` | 在编辑器游戏线程执行 Python 代码/表达式 | P2 | 仅 full + 双端开关 | **是** | §5.9 |
| `ue_blueprint` | 查询蓝图结构（父类/变量/组件/图/编译状态）；触发编译；节点级读取为 experimental | P0/P1 | read-only 下仅 query | 否 | §5.10 |

（可用性矩阵依据架构文档 §5.11）

补充说明：

- 各工具完整入参/出参 Schema、错误码与实现要点，见架构文档对应章节（上表「参数细节」列），本文不重复抄写。
- **隐藏工具不会出现在 `tools/list` 中；直接调用返回 `TOOL_DISABLED`**，错误信息不透露工具细节（§5.0.3、§5.11）。
- read-only / standard 下调用 P1/P2 工具同样返回 `TOOL_DISABLED`（§1.4、§5.11）。
- P1 破坏性操作（删除 Actor、覆盖未保存内容、批量保存）额外需要确认：客户端声明 `elicitation` 能力时发起交互确认；否则要求服务端以 `--allow-destructive` 启动；两者都没有则返回 `CONFIRMATION_REQUIRED`（§5.0.3、§6.3）。
- P2 工具开启需**同时满足**双端条件（§5.8、§5.9、§6.4）：服务端策略 `full` + 对应 `--allow-console` / `--allow-exec`，**且**桥接端 `allowConsole=true` / `allowExec=true`，**且**每次调用确认。

---

## 7. 安全说明

依据架构文档 §6 整理。

### 7.1 默认防护

- **默认只读**：默认策略为 `read-only`，写与危险能力默认不存在于 `tools/list`（架构文档附录 A、§0.1）。桥接端默认同样只读、禁止 exec（§4.4）。
- **仅回环绑定**：MCP Server 与桥接均强制绑定 `127.0.0.1`，**没有**「允许局域网」的开关（§6.2）。
- **Host/Origin 校验**：仅接受回环 Host；`Origin` 若存在必须为回环同源或 `null`（防 DNS rebinding）；不启用 CORS、不返回通配头（§3.3、§6.2）。
- **双向权限门**：MCP Server 策略与桥接独立开关（`allowWrite`/`allowConsole`/`allowExec`，默认全关）**双重校验**，任何一端关闭即拒绝——即使 token 泄漏，未开启 exec 的编辑器仍不能被任意代码执行（§6.3）。
- **exec/console 默认隐藏**：这两个工具默认不注册、不出现在 `tools/list`，日志中也不打印其存在（§6.4）。开启后每次调用仍需确认（§6.4）。控制台命令另有白名单与永久拒绝表（`py`/`exec`/`quit`/`open` 等永不放行，§5.8）。
- **审计日志**：每个 P1/P2 调用写一条 JSONL 到 `~/.uemcp/audit/YYYY-MM-DD.jsonl`；**永不记录** token、完整 Python 源码、截图 base64——Python 执行只记录 `codeSha256` 与长度（§6.5）。
- **桥接 token**：32 字节随机数，每次编辑器启动轮换；存储于 `~/.uemcp/bridge.json`（权限 0600）与进程内存，不写入项目目录；常量时间比较（§6.6）。
- **误操作防护**：写操作包 `ScopedEditorTransaction` 事务（失败可回滚）、`dryRun` 支持、PIE/未保存内容预检（§6.1、§5.3、§5.4）。

### 7.2 ⚠️ 本机开发工具的固有风险（必读）

以下为架构文档 §6.1「明确不解决的威胁」原文要点，**必须在 README 中写明**：

> 本机恶意程序读取进程内存或 `bridge.json` 后可取得 token；用户主动开启 exec 后模型可执行任意代码。这是本地开发工具的固有边界。

- **开启 `ue_python_exec` 等于把编辑器进程的控制权交给调用方**（§6.4）。Python 代码在游戏线程内执行，**无法强制中断**——不要写死循环或长时间阻塞代码（§5.9、§2.6）。
- 不建议在录屏、演示、CI 中开启 exec（§6.4）。
- UEMCP 不提供 Python 沙箱：`exec` 类工具默认隐藏，开启后即为受信任本地代码执行（§1.2-4）。
- 使用本项目需自行拥有合法的 UE 引擎授权（§7.5）。

---

## 8. 故障排查

依据架构文档 §10.5 故障排查表与 §8.3 风险表整理。**以下现象与处理方式均待实现验证**（对应实现尚未存在）。

| 现象 | 可能原因 | 处理 | 依据 |
|---|---|---|---|
| 工具返回 `BRIDGE_UNAVAILABLE` | 编辑器未启动/UEMCPBridge 未启用/Python 插件未加载 | 查看 `Saved/Logs/*.log` 中 `[UEMCP]` 前缀日志；确认发现文件已生成 | §10.5、R3 |
| 408/504 超时 | 游戏线程繁忙（编译/PIE 中）、长任务 | 等待编辑器空闲后重试；增大 `timeoutMs` | §10.5 |
| 返回 `TOOL_DISABLED` | 策略或独立开关未开（read-only 下调 P1；exec/console 双端开关未开） | 服务端用 `--policy full --allow-exec` 等；桥接配置同步开启 | §10.5、§6.3 |
| 返回 `CONFIRMATION_REQUIRED` | 客户端不支持 elicitation 且服务端未开 `--allow-destructive` | 开启该开关，或换支持 elicitation 的客户端 | §10.5、R8 |
| 端口占用 | 另一个 MCP Server/桥接占用了 18777/18778 | 换端口启动；检查发现文件 | §10.5、R4 |
| 截图失败 | `AutomationLibrary` 行为与预期不符/PIE 未运行 | 查看 `capabilities.screenshot`；确认 PIE 运行中再截 `target=pie` | §10.5、R2 |
| 蓝图查询 `nodes` 为空 | 节点级读取依赖反射、非稳定 API，访问失败 | 预期降级行为（`blueprintNodeRead=false` + warning）；节点编辑能力需等 P2 C++ 模块 | §10.5、§5.10、A3 |
| 控制台命令无输出 | 已知限制：MVP 不支持输出捕获 | 需要回显时使用 `ue_python_exec`（若已开启） | §10.5、§5.8 |
| 发现文件陈旧 | 编辑器进程被强杀，残留旧 `bridge.json` | 服务端会按 PID/`/health` 双重校验并跳过陈旧文件；必要时删除 `~/.uemcp/bridge.json` 后重启编辑器 | §10.5、R9、§2.4 |
| 编辑器被 Python 卡死 | `ue_python_exec` 执行了死循环/长阻塞代码 | 已进入执行的任务无法中断，只能等待或强杀编辑器；重启后按上文处理陈旧发现文件 | §2.6、R5 |
| 大工程资产搜索超时 | 资产数量大 | 缩小 `path` 范围、降低 `limit`；超时返回 `SEARCH_TIMEOUT` 时可读取 `details.partial` 部分结果 | R6、§5.5 |
| 客户端连不上 Streamable HTTP | 客户端版本不支持该传输 | 改用同端口旧版 SSE 端点 `/sse`，或 stdio 模式 | R7、§3.4、§3.1 |
| `npx` 命令不存在/无 Node 环境 | 未安装 Node.js ≥ 20 | 安装 Node；P2 规划单文件二进制分发 | R15、§7.3 |

---

## 9. 许可证与商标

### 9.1 许可证（MIT）

本项目以 **MIT License** 发布，版权所有 `2026 UEMCP contributors`（§7.4）。完整许可证文本将随仓库 `LICENSE` 文件提供（仓库尚未建立，**待创建**）。

注意（§7.4）：

- MIT 只覆盖本项目代码；**不覆盖** UE 引擎、用户资产、样例工程内容。
- 插件不得附带任何 Epic 版权资产。

### 9.2 商标免责声明

以下文本将同时用于仓库 `TRADEMARK.md` 与 README 顶部（§7.5，英文原文照录）：

> Unreal and Unreal Engine are trademarks or registered trademarks of Epic Games, Inc. in the United States and elsewhere. This project is an independent, community-developed tool and is not affiliated with, endorsed by, or sponsored by Epic Games, Inc. "Unreal" is used solely to describe compatibility with Unreal Engine. All other trademarks are the property of their respective owners.

补充规则（§7.5）：

- 项目名使用 **UEMCP**，不使用 "UnrealMCP""EpicMCP" 等可能造成官方关联误解的名称。
- 不复制 Epic 的 Logo、图标风格或 Marketplace 素材。
- 本节不构成法律意见；正式发布前建议做一次开源合规审查。

---

## 10. 文档状态声明

本节逐条标注本文内容的可信来源与验证状态。**凡「待实现验证」「待确认」内容，不得作为操作保证引用。**

### 10.1 已由架构文档确认（设计层面，本文据实整理）

以下内容在《UEMCP 架构设计与工具清单》v0.1.0 中已有明确设计结论，本文忠实转述、未添加架构文档之外的行为描述：

- 双进程结构、端口规划（18777/18778/18779 预留）与配置优先级（§0.1、§2.1、§2.3）。
- 10 个 MVP 工具的名称、用途、权限级别、默认隐藏属性与策略矩阵（§5.1–§5.11）。
- 三种传输（Streamable HTTP `/mcp`、旧版 SSE `/sse`、stdio）与端点行为（§3.1–§3.4）。
- 三类客户端的配置格式与 curl 调用序列（§3.5、§3.3）。
- MVP 纳入/排除边界（§1.3）。
- 安全模型：默认只读、回环绑定、双向权限门、隐藏策略、审计规则、token 管理（§6）。
- 错误码表与会话规则（§2.9、§3.3）。
- 安装步骤与故障排查表（§10.4、§10.5）。
- 许可证（MIT）与商标免责声明文本（§7.4、§7.5）。

### 10.2 待实现验证（代码尚未实现，以下不构成操作保证）

| # | 内容 | 验证依据 |
|---|---|---|
| V1 | 本文所有命令（`npx -y @uemcp/server ...`、`claude mcp add --transport http ...`、curl 序列）**当前均不可运行**——代码未实现、npm 包未发布 | 全文；§7.3 |
| V2 | 插件 `Content/Python/init_unreal.py` 自动执行的假设 | §8.4 A1 |
| V3 | 截图输出路径/PIE 行为（`AutomationLibrary.take_high_res_screenshot`） | §8.4 A2、R2 |
| V4 | 蓝图节点级读取（反射访问，非稳定 API，失败降级） | §8.4 A3 |
| V5 | `AssetRegistry.get_dependencies` 的 Python 参数形式 | §8.4 A4 |
| V6 | Claude Code 对 `--transport http` 与自定义 header 的支持 | §8.4 A5 |
| V7 | Cursor 对 Streamable HTTP / SSE 端点的实际支持 | §8.4 A6 |
| V8 | UE 5.4 嵌入式 Python 含 `http.server`、`ssl`、`hashlib`、`secrets` 等标准库 | §8.4 A7 |
| V9 | `ScopedEditorTransaction.cancel()` 的回滚效果 | §8.4 A8 |
| V10 | 完整 CLI 参数表（本文仅列架构文档已出现者） | 待实现 `config.ts` 后确认 |
| V11 | npm scope `@uemcp` 可注册性与包名 | 首次发布前确认（§7.3 仅定名） |

### 10.3 待确认（架构文档未覆盖，需指定角色确认）

| # | 待确认项 | 需谁确认 |
|---|---|---|
| C1 | macOS/Linux 支持状态与承诺（架构文档仅注明「Windows 优先」，§7.6） | 架构师 |
| C2 | UE 5.4 内置 Python 的具体版本号（影响用户排障说明） | 开发（PoC 期间） |
| C3 | README 顶部截图/GIF 素材（架构文档 §7.6 建议结构第 1 条，素材不存在） | 产品/开发 |
| C4 | 本文为草稿；正式 README 中的快速开始章节（30 秒上手）待实现完成后依据实测结果重写（§7.6） | 主管（排期） |

---

*本文由技术文档角色依据《UEMCP 架构设计与工具清单》v0.1.0（2026-10-20）编写；未自行发明产品行为或技术结论。随实现迭代更新。*
