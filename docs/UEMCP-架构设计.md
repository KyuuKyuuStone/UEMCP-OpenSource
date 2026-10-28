# UEMCP 架构设计与工具清单

| 项 | 值 |
|---|---|
| 文档版本 | 0.2.0 |
| 日期 | 2026-10-20 |
| 状态 | 已合并 v0.1.1 裁决（架构基线） |
| 目标引擎 | Unreal Engine 5.4.4（本机已验证） |
| 目标产品 | 客户端无关的 UE 编辑器 MCP 服务 |
| 许可证 | MIT |

## 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.2.0 | 2026-10-20 | 合并《UEMCP 架构裁决补充》v0.1.1 的 7 项裁决。实现与验收以本文为准；补充文档保留作决策记录。 |
| 0.1.0 | 2026-10-20 | 初版架构设计与工具清单。 |

v0.1.1 裁决落点：

| 裁决 | 内容 | 合并章节 |
|---|---|---|
| D1 | 工具级错误码统一映射 | §2.9、§3.3、§5.0.1、§5.2–§5.11 |
| D1b | `INVALID_ARGUMENT` 与协议层 `INVALID_PARAMS` 分离 | §2.9、§3.3、§5.0.1 |
| D2 | 旧版 SSE 兼容基线 | §3.4、§3.5.3、§8.4 A6、§8.5、§9.2 |
| D6 | 双重权限门错误码 | §2.9、§5.8、§5.9、§6.3、§6.4、§10.5 |
| D10 | 端口冲突行为 | §2.3、§2.7、§8.3 R4、§9.2、§10.5、附录 A |
| D11 | `--allow-destructive` 生效范围 | §5.0.3、§5.8、§5.9、§6.3、§6.4、§9.2、附录 A |
| D12 | read-only 下混合工具注册方式 | §1.4、§5.0.3、§5.0.4、§5.11、§9.2、附录 A |

---

## 0. 结论速览

### 0.1 一句话结论

UEMCP 采用 **MCP Server（Node.js/TypeScript，独立进程，默认 `127.0.0.1:18777`）+ UE 编辑器内 Python Bridge（Python Editor Script Plugin，纯 Python 插件，默认 `127.0.0.1:18778`）** 的双进程结构；MCP 侧以 **Streamable HTTP `/mcp`** 为主传输，同端口挂 **旧版 SSE `/sse`** 兼容端点，另提供 **stdio** 启动模式；UE 侧 MVP 只用 Python API，**不做编译型 C++ 插件**。MVP 固定 10 个工具，危险能力（控制台、Python 执行、删除）默认不存在于 `tools/list` 中。

### 0.2 关键决策表

| 决策点 | 选择 | 主要理由 | 放弃项 |
|---|---|---|---|
| MCP Server 语言 | TypeScript + 官方 `@modelcontextprotocol/sdk` | Streamable HTTP/SSE/stdio 三种 transport 官方实现齐全；`npx` 分发对任意客户端最省事；zod 直接产出 JSON Schema | Python FastMCP、Go 手写 |
| MCP 主传输 | Streamable HTTP，`POST/GET/DELETE /mcp` | MCP 2025-03-26 之后的主线；天然支持会话与流式 | 仅 stdio、仅 SSE |
| 兼容传输 | 旧版 HTTP+SSE（`/sse` + `/messages`）、stdio | 覆盖旧客户端与命令行客户端 | WebSocket（MVP 不需要） |
| UE 执行层 | Python Editor Script Plugin（纯 Python 插件） | 5.4 零编译、跨平台分发、改代码即生效；覆盖 Actor/关卡/资产/材质/截图 | C++ 插件（P2 作为能力补充） |
| MCP ↔ UE 通信 | HTTP JSON-RPC 2.0 + 可选 SSE 事件流 | 实现简单、可用 curl 排障、Python 标准库即可；无额外依赖 | WebSocket、命名管道 |
| 数据校验 | zod（服务端）+ 手写校验（桥接端） | 单一 Schema 来源，同时生成文档与 MCP inputSchema | 双份手写 Schema |
| 仓库形态 | pnpm monorepo：`server/shared/plugin/examples/docs` | 服务端与插件同步发版；文档随代码生成 | 两个独立仓库 |
| 安全默认值 | read-only（混合工具只读动作收窄）+ 桥接 token + 仅回环；P2 默认隐藏 | 本地工具仍有 RCE 风险，默认最小能力 | 默认开放写/执行 |
| MVP 工具数 | 10 | 满足覆盖要求，避免工具爆炸 | 每类能力一个工具 |
| 工具错误返回 | HTTP 200 + `isError:true` + `structuredContent.error` | 工具执行失败是 in-band 语义，客户端需读取错误码并纠正参数 | 4xx/5xx 映射工具错误 |
| read-only 工具集合 | 7 个：4 个纯只读 + 3 个混合工具的只读动作（Schema 收窄） | 保留查询价值，同时让模型在工具列表阶段就看到写动作不可用 | 整体隐藏混合工具 |
| 端口冲突 | MCP Server 失败退出（exit 2）；桥接按 18778–18788 再临时端口回退 | 固定客户端 URL 不能静默换端口；桥接通过发现文件可透明回退 | MCP Server 自动换端口 |
| 危险操作确认 | `--allow-destructive` 只管 P1 破坏性操作；console/exec 各由 `--allow-console`/`--allow-exec` 兼作策略级确认 | 避免一个开关放大到任意代码执行 | 统一用一个开关豁免全部确认 |

### 0.3 需求内部矛盾与取舍（先裁决，再设计）

| # | 矛盾点 | 取舍建议 | 影响 |
|---|---|---|---|
| 1 | “任意 MCP 客户端” vs 参考项目内嵌 Claude Code CLI/UI | **不内嵌任何客户端 UI**。MCP 协议就是唯一边界；参考项目只借鉴工具分类与双进程结构 | 用户用现成客户端接入；项目不提供聊天窗口 |
| 2 | “10 个工具以内” vs “覆盖 9 类能力且权限细分” | 按**能力域**合并工具，按 **action/op 细分权限**。例如 Actor 查询与编辑拆两个，关卡所有动作合并为一个 | 单个工具的参数分支较多，但工具面板可控 |
| 3 | “Python 任意代码执行” vs “安全模型” | 明确**不能沙箱**任意 Python。采用“默认不存在 + 双重开关 + 仅回环 + 审计”的**能力隔离**，不是“执行隔离” | 开启 exec 后等价于把编辑器交给调用方 |
| 4 | “参考 UnrealClaude 的蓝图/动画蓝图能力” vs UE 5.4 Python 能力 | 5.4 Python **没有蓝图节点创建/连线 API**。MVP 只做蓝图**只读查询与编译**；节点编辑、动画蓝图编辑延后到 P2 的 C++ 辅助模块 | MVP 工具清单第 10 项明确标注能力缺口 |
| 5 | “Streamable HTTP 为主” vs “SSE 兼容” | 同端口同时提供 `/mcp` 与 `/sse`，共享同一套会话注册与工具实现；SSE 只做薄适配层 | 少量额外代码；客户端不必二选一 |
| 6 | “同时支持 stdio 和 HTTP” | 同一二进制，**按启动参数二选一**，不推荐一个进程同时承载两种 MCP 传输 | 部署简单；需要两个进程时由客户端各起一个 |
| 7 | “用户自己写代码” vs 架构完整性 | 文档给到 Schema、目录、函数签名与伪代码；MVP 不引入数据库、消息队列、前端 | 认知负担低，可直接落地 |

---

## 1. 目标与非目标

### 1.1 目标

1. **客户端无关**：Claude Code、Cursor、cc-heihei、自研 HTTP 客户端、脚本都能接入；不依赖某个客户端的私有能力。
2. **编辑器内真实执行**：工具调用直接作用于当前打开的 UE 5.4 编辑器，而不是离线解析 `.uasset` 或操作工程文件。
3. **本地优先**：默认只绑定 `127.0.0.1`，开箱即用，不需要部署。
4. **可审计**：每个写操作与危险操作都有结构化日志。
5. **可分发**：UE 侧为纯 Python 插件，放进 `Plugins/` 并启用即可；MCP 侧可 `npx` 或单文件二进制运行。
6. **可扩展**：工具 Schema 集中定义；后续增加 C++ 辅助模块不改变 MCP 对外契约。

### 1.2 非目标

1. **不做内嵌 AI 聊天 UI**：不实现 Claude Code CLI 包装、不实现聊天面板。
2. **不操作打包后的运行时游戏**：只服务编辑器进程；Shipping 包内无 Python、无该插件。
3. **不做远程/多人服务**：不监听 `0.0.0.0`，不做多租户、账号体系、云部署。
4. **不提供 Python 沙箱**：`exec` 类工具默认隐藏，开启后即为受信任本地代码执行。
5. **MVP 不做蓝图节点级编辑、动画蓝图编辑、Sequencer、Niagara 专用编辑**。
6. **不保证任意 UE 版本**：MVP 只承诺 5.4.x；跨版本策略见 §8.2。
7. **不做资产导入/导出、Source Control 操作、打包构建**（后续可扩展）。
8. **不做控制台输出捕获**（UE Python 层无法可靠拿到控制台回显，MVP 明确返回 `outputAvailable:false`）。

### 1.3 MVP 边界清单

| 纳入 MVP | 不纳入 MVP |
|---|---|
| 编辑器状态、当前关卡、选中 Actor、视口相机 | PIE 内的 Actor 操作 |
| Actor 查询、生成、删除、变换、受控属性修改、复制、选择 | 蓝图组件层级重建、任意 UPROPERTY 反射写入 |
| 关卡打开、保存、新建、脏包列表（另存为延后） | 关卡流送（Level Streaming）管理 |
| 资产搜索、依赖/引用查询 | 资产导入/导出、重命名/移动、批量修复重定向器 |
| 材质实例参数读取/设置、创建实例 | 材质节点图编辑 |
| 视口/PIE 截图 | 编辑器 UI 截图、Slate 控件操作 |
| 控制台命令（白名单、默认隐藏） | 控制台输出回读 |
| Python 执行（默认隐藏） | Python 调试器集成、代码沙箱 |
| 蓝图变量/组件/图/编译状态只读查询、编译 | 蓝图节点创建/连线、动画蓝图状态机编辑 |

### 1.4 成功判据

- 三类客户端（Claude Code HTTP、Cursor、通用 curl/HTTP）都能完成 `initialize → tools/list → tools/call`。
- 在样例工程里，一条脚本可完成“创建 Actor → 查询 → 改变换 → 截图 → 删除”闭环。
- read-only 模式下，纯写工具（`ue_actor_edit`）与 P2 工具不出现在 `tools/list` 中；P0/P1 混合工具以**只读动作收窄的 inputSchema** 出现（见 §5.11）；直接调用未注册工具返回 `TOOL_DISABLED`。
- 桥接进程不可达时，MCP Server 不崩溃，工具返回 `BRIDGE_UNAVAILABLE`。
- 审计日志包含时间、工具、参数摘要、结果、耗时，且不含 token 与完整 Python 源码。

---

## 2. 总体架构

### 2.1 组件与职责

```
┌──────────────────────────┐
│ MCP 客户端（任选）        │
│ - Claude Code            │
│ - Cursor                 │
│ - cc-heihei / 自研       │
└────────────┬─────────────┘
             │ MCP 协议
             │ stdio 或 Streamable HTTP(:18777/mcp) 或 旧 SSE(:18777/sse)
             ▼
┌─────────────────────────────────────────────────────────────┐
│ UEMCP Server（Node.js / TypeScript，独立进程）              │
│ - MCP 协议与会话管理（Mcp-Session-Id）                      │
│ - 工具注册、zod 校验、outputSchema                          │
│ - 策略门（read-only / standard / full）                     │
│ - 桥接发现（~/.uemcp/bridges/*.json）                        │
│ - 审计日志（~/.uemcp/audit/*.jsonl）                         │
│ - 统一错误映射                                              │
└────────────┬────────────────────────────────────────────────┘
             │ 内部协议：HTTP JSON-RPC 2.0
             │ POST http://127.0.0.1:18778/rpc
             │ Header: X-UEMCP-Token
             │ 可选 GET /events（SSE 事件/日志）
             ▼
┌─────────────────────────────────────────────────────────────┐
│ UEMCPBridge（UE 5.4 编辑器内，Python 插件）                 │
│ - ThreadingHTTPServer（工作线程）                           │
│ - 游戏线程调度队列（Slate post-tick）                        │
│ - 每个能力域一个 handler                                    │
│ - 能力探测（capabilities）                                  │
│ - 写操作事务与 dry-run                                      │
└────────────┬────────────────────────────────────────────────┘
             │ unreal.* Python API（仅游戏线程）
             ▼
┌─────────────────────────────────────────────────────────────┐
│ UE 5.4 编辑器：World / Actor / AssetRegistry / Viewport      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 为什么是两个进程

| 方案 | 结论 | 原因 |
|---|---|---|
| 单进程（MCP 逻辑跑在编辑器 Python 里） | 拒绝 | stdio 被编辑器进程占用难以控制；Python 版本/依赖受引擎约束；崩溃会带崩编辑器；客户端配置复杂 |
| 双进程（推荐） | 采用 | MCP Server 可独立重启、独立升级；stdio/HTTP/SSE 都由成熟的 Node SDK 处理；桥接层只做编辑器适配 |
| 三进程（MCP + 中继 + 插件） | 拒绝 | 无必要复杂度 |

### 2.3 端口与进程规划

| 端口 | 归属 | 协议 | 端点 | 绑定 | 说明 |
|---|---|---|---|---|---|
| 18777 | UEMCP Server | HTTP | `/mcp`、`/sse`、`/messages`、`/health` | `127.0.0.1` | MCP 对外统一入口 |
| 18778 | UEMCPBridge | HTTP | `/rpc`、`/health`、`/events` | `127.0.0.1` | MCP Server 专用内部通道（默认端口） |
| 18779–18788 | UEMCPBridge 回退区间 | HTTP | 同上 | `127.0.0.1` | 18778 被占用时按序尝试；再失败则用系统临时端口 |
| — | stdio | stdio | — | — | 由客户端拉起，不监听端口 |
| 18789 | 预留 | WebSocket | `/ws` | `127.0.0.1` | P2 可选，当前不实现 |

配置优先级（两者一致）：**命令行参数 > 环境变量 > 发现文件 > 默认值**。

- `UEMCP_HTTP_PORT`（默认 `18777`）
- `UEMCP_BRIDGE_PORT`（默认 `18778`；冲突时按 §2.3 的端口回退规则处理）
- `UEMCP_BRIDGE_URL`
- `UEMCP_BRIDGE_TOKEN`
- `UEMCP_AUTH_TOKEN`（MCP 入口可选鉴权）

端口冲突行为（已裁决，两端不同）：

- **MCP Server（18777）**：`EADDRINUSE` 或其他 bind 失败时 **2 秒内退出，退出码 2**，stderr 输出一行 JSON：
  ```json
  {"level":"error","event":"http_bind_failed","host":"127.0.0.1","port":18777,"code":"EADDRINUSE","message":"listen EADDRINUSE: address already in use 127.0.0.1:18777"}
  ```
  不自动换端口、不重试、不写发现文件。用户换端口必须显式传 `--port`（或 `UEMCP_HTTP_PORT`），并同步修改客户端 URL。`--port 0` 仅用于 CI/测试，实际端口写入启动日志与 `/health`。
- **桥接（默认 18778）**：启动时先删除本项目陈旧发现文件；依次尝试配置端口、`18779`–`18788`，最后尝试系统临时端口（bind 0）。第一个成功绑定的端口为实际端口，写入发现文件的 `port`/`url`。全部失败时只写编辑器日志 `[UEMCP] bridge_bind_failed`，不写可用发现文件，MCP Server 侧表现为 `BRIDGE_UNAVAILABLE`。
- **客户端发现**：MCP 客户端固定使用配置的 `http://127.0.0.1:<port>/mcp`；桥接的实际端口由 MCP Server 从发现文件读取，客户端无需感知。

### 2.4 发现机制（Bridge Discovery）

桥接端启动时写入两个文件（原子写，先写 `.tmp` 再 `os.replace`）：

1. `~/.uemcp/bridges/<projectHash>.json`：按工程目录区分，支持未来多编辑器。
2. `~/.uemcp/bridge.json`：最近启动的编辑器，便于默认发现。

`projectHash`：工程目录规范化（统一 `/`、去尾斜杠）后取 SHA-1 十六进制前 16 位。

```json
{
  "schemaVersion": 1,
  "pid": 1234,
  "projectDir": "C:/UE5_P/5.4/XQHCPP_54",
  "projectFile": "XQHCPP_54.uproject",
  "host": "127.0.0.1",
  "port": 18778,
  "url": "http://127.0.0.1:18778",
  "token": "base64url-32-bytes",
  "ueVersion": "5.4.4",
  "pluginVersion": "0.1.0",
  "bridgeProtocol": 1,
  "capabilities": {
    "python": true,
    "screenshot": true,
    "blueprintRead": true,
    "blueprintNodeRead": false,
    "blueprintCompile": true,
    "animBlueprintEdit": false,
    "assetRegistry": true,
    "console": true
  },
  "startedAt": "2026-10-20T10:00:00Z"
}
```

MCP Server 的解析顺序：

1. `--bridge-url` / `UEMCP_BRIDGE_URL`
2. `--project <dir>` → 读取对应 `projectHash` 文件
3. `~/.uemcp/bridge.json`
4. `http://127.0.0.1:18778` + `UEMCP_BRIDGE_TOKEN`

**校验规则（必须全部满足才可使用）**：

- 文件结构合法，`schemaVersion === 1`。
- `pid` 对应进程存活（Node 用 `process.kill(pid, 0)`；Windows 上捕获异常判断）。
- 对 `url` 发起 `GET /health`，返回 `{ "app": "uemcp-bridge", "ok": true }`。
- 返回的 `pid` / `startedAt` 与文件一致（防止读到上一次启动的残留文件）。
- 若指定了 `--project`，`projectDir` 必须匹配。

任何一项失败都视为陈旧发现，转向下一来源；全部失败则工具调用返回 `BRIDGE_UNAVAILABLE`。

### 2.5 请求链路（一次写操作）

```
Client → POST /mcp (tools/call ue_actor_edit)
  → MCP Server 校验 zod / 会话 / 策略
  → 审计：开始
  → POST http://127.0.0.1:18778/rpc {method:"actor.edit", params}
     → Bridge HTTP 工作线程校验 token / 参数
     → 入队到游戏线程
     → Slate post-tick 执行：with ScopedEditorTransaction(...)
         → EditorActorSubsystem.SpawnActorFromClass / DestroyActor / SetActorTransform
       → 设置结果 / 异常
     → HTTP 线程被唤醒，返回 JSON-RPC result
  → MCP Server 映射为 structuredContent
  → 审计：结束
Client ← 200 / SSE 流 / JSON-RPC error
```

### 2.6 编辑器内线程模型

UE 的 `unreal.*` API 不是线程安全的，**所有调用必须在游戏线程**。桥接采用“HTTP 工作线程 + 单队列 + Slate tick 泵”：

```python
# plugin/UEMCPBridge/Content/Python/uemcp_bridge/dispatcher.py（节选）
import queue
import threading
import unreal

class _Job:
    __slots__ = ("fn", "done", "result", "error", "cancelled")
    def __init__(self, fn):
        self.fn = fn
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.cancelled = False

class GameThreadDispatcher:
    def __init__(self, max_queue=64):
        self._q = queue.Queue(maxsize=max_queue)
        self._tick_handle = unreal.register_slate_post_tick_callback(self._on_tick)
        unreal.register_python_shutdown_callback(self.shutdown)

    def _on_tick(self, _delta_seconds):
        # 一次 tick 最多处理 1 个写任务，避免长时间卡住编辑器
        try:
            job = self._q.get_nowait()
        except queue.Empty:
            return
        if job.cancelled:
            job.done.set()
            return
        try:
            job.result = job.fn()
        except Exception as exc:
            job.error = exc
        finally:
            job.done.set()

    def call(self, fn, timeout_s):
        job = _Job(fn)
        self._q.put(job, timeout=0.5)   # 队列满 → queue.Full → BRIDGE_BUSY
        if not job.done.wait(timeout_s):
            job.cancelled = True
            raise TimeoutError("game-thread job timed out")
        if job.error:
            raise job.error
        return job.result

    def shutdown(self):
        if self._tick_handle:
            unreal.unregister_slate_post_tick_callback(self._tick_handle)
            self._tick_handle = None
```

约束：

- 队列上限 64；满时立即返回 `BRIDGE_BUSY`，不无限堆积。
- 默认请求超时 30s，单工具可声明更高上限（最高 120s）。
- HTTP 客户端断开时标记 `cancelled`；**已经进入执行的任务无法中断**。
- 读操作也走同一队列，保证与写操作不交错。
- 桥接 HTTP 使用 `ThreadingHTTPServer`，daemon 线程；监听地址固定 `127.0.0.1`。

### 2.7 为什么 MVP 不用 WebSocket

| 维度 | HTTP JSON-RPC + SSE | WebSocket |
|---|---|---|
| 依赖 | Python 标准库 `http.server` 即可 | 需要 `websockets` 或自实现握手 |
| 调试 | `curl` 直接可测 | 需要 ws 客户端 |
| 请求-响应 | 天然一一对应 | 需要自建 id/关联 |
| 服务端推送 | `/events` SSE 足够（日志、进度） | 原生双向，但 MVP 无高频双向需求 |
| 反向代理/工具链 | 简单 | 复杂 |

结论：MVP 用 HTTP；若 P2 需要“编辑器事件实时推送 + 低延迟取消”，再在 18789 加 WebSocket，内部协议保持不变（18779–18788 保留给桥接端口回退）。

### 2.8 内部 RPC 协议

请求：

```json
{
  "jsonrpc": "2.0",
  "id": "6f1c2d9e-7a1b-4c3d-9e0f-123456789abc",
  "method": "actor.edit",
  "params": { "operations": [], "dryRun": false },
  "meta": { "timeoutMs": 30000, "traceId": "trc_01H..." }
}
```

成功：

```json
{
  "jsonrpc": "2.0",
  "id": "6f1c2d9e-7a1b-4c3d-9e0f-123456789abc",
  "result": { "ok": true, "data": {}, "warnings": [], "meta": {} }
}
```

失败：

```json
{
  "jsonrpc": "2.0",
  "id": "6f1c2d9e-7a1b-4c3d-9e0f-123456789abc",
  "error": {
    "code": -32006,
    "message": "Actor not found",
    "data": {
      "errorCode": "ACTOR_NOT_FOUND",
      "retryable": false,
      "details": { "selector": { "kind": "actorPath", "value": "PersistentLevel.X" } }
    }
  }
}
```

RPC 方法表：

| RPC method | 对应工具 | 最低策略 |
|---|---|---|
| `bridge.ping` | 公共 | 无 |
| `bridge.capabilities` | `ue_editor_status` | read-only |
| `editor.status` | `ue_editor_status` | read-only |
| `actor.query` | `ue_actor_query` | read-only |
| `actor.edit` | `ue_actor_edit` | standard（delete 需 destructive） |
| `level.control` | `ue_level_control` | read-only / standard |
| `asset.search` | `ue_asset_search` | read-only |
| `material.params` | `ue_material_params` | read-only / standard |
| `viewport.capture` | `ue_viewport_capture` | read-only |
| `console.command` | `ue_console_command` | full + console 开关 |
| `python.exec` | `ue_python_exec` | full + exec 开关 |
| `blueprint.query` | `ue_blueprint` | read-only / standard（compile） |

### 2.9 错误模型

#### 2.9.1 三层分离

| 层 | 失败类型 | 对外形态 | HTTP | 顶层 JSON-RPC |
|---|---|---|---|---|
| MCP 协议层 | JSON 解析失败、JSON-RPC 信封错误、未知 method、会话缺失/过期、鉴权失败、请求体超限、HTTP 层限流 | JSON-RPC `error` | 非 200 | 有 `error` |
| MCP 工具层 | 已知工具的参数校验失败、对象不存在、策略拒绝、桥接不可达/超时/忙、编辑器执行异常 | `CallToolResult` | **200** | **无 `error`**，有 `result` |
| 桥接内部层 | 编辑器执行异常 | JSON-RPC `error`（仅 Server↔Bridge） | 见 §2.9.5 | 有 `error`，**不直接暴露给客户端** |

固定规则：

1. **只要请求已经成功路由到一个已知工具的 `tools/call`，任何执行失败都是 HTTP 200。**
2. `isError=true`、`structuredContent.ok=false`、`structuredContent.error` 必须同时存在；成功时 `isError=false`、`ok=true`、无 `error`。
3. 禁止“HTTP 4xx/5xx + 工具错误对象”或“HTTP 200 + 顶层 JSON-RPC error”的混合形态。
4. 对外只认字符串 `code`；数字码只用于桥接内部与本文映射表。
5. 成功但有警告（`rolledBack:false`、`outputAvailable:false`、图像过大只返回路径）仍为 `isError=false`，写 `warnings[]`。
6. `content[0].text` 以 `"<CODE>: <message>"` 开头，便于不支持结构化内容的客户端。
7. `error.details` 必须是 JSON 对象，上限 16 KiB（超出截断并附 `detailsTruncated:true`）。

#### 2.9.2 协议层错误码（对外非 200）

| code | HTTP | JSON-RPC | 说明 |
|---|---|---|---|
| `PARSE_ERROR` | 400 | -32700 | JSON 解析失败 |
| `INVALID_REQUEST` | 400 | -32600 | JSON-RPC 信封结构错误 |
| `METHOD_NOT_FOUND` | 404 | -32601 | 未知 JSON-RPC method |
| `INVALID_PARAMS` | 400 | -32602 | `tools/call` 信封错误或未知工具名（见 §2.9.4） |
| `SESSION_NOT_FOUND` | 404 | -32001 | 会话缺失、未知或过期 |
| `UNAUTHORIZED` | 401 | -32019 | MCP 入口 Bearer token 错误/缺失（启用鉴权时） |
| `PAYLOAD_TOO_LARGE` | 413 | -32011 | HTTP 请求体超过 8 MiB |
| `RATE_LIMITED` | 429 | -32012 | HTTP 中间件限流，尚未进入工具 |
| `INTERNAL` | 500 | -32603 | 协议层未捕获异常 |

补充：

- 协议层响应没有 `CallToolResult`，因此不存在 `isError` 字段。
- Host/Origin 拒绝使用 HTTP 421/403 + `INVALID_REQUEST`。
- `PAYLOAD_TOO_LARGE`、`RATE_LIMITED` 在工具层也可能出现（见下表），靠 HTTP 状态与“是否存在 `result`”区分层位。

#### 2.9.3 工具级错误码

| code | Bridge JSON-RPC | Bridge HTTP | MCP HTTP | isError | retryable | 含义 |
|---|---|---|---|---|---|---|
| `INVALID_ARGUMENT` | -32602 | 400 | 200 | true | false | 工具参数未通过 Schema 或业务校验 |
| `INTERNAL` | -32603 | 500 | 200 | true | false | 工具层未分类内部错误（协议层见 §2.9.2） |
| `ACTOR_NOT_FOUND` | -32044 | 404 | 200 | true | false | 选择器未命中任何 Actor |
| `AMBIGUOUS_SELECTOR` | -32021 | 409 | 200 | true | false | 选择器命中多个 Actor |
| `CLASS_NOT_FOUND` | -32022 | 404 | 200 | true | false | Actor 类名/类路径无法解析 |
| `ASSET_NOT_FOUND` | -32023 | 404 | 200 | true | false | 资产路径不存在或不是资产 |
| `TRANSACTION_FAILED` | -32024 | 409 | 200 | true | false | 事务执行/取消失败 |
| `LEVEL_NOT_FOUND` | -32025 | 404 | 200 | true | false | 关卡路径不存在 |
| `LEVEL_LOAD_FAILED` | -32026 | 500 | 200 | true | false | 打开关卡返回失败或抛异常 |
| `UNSAVED_CHANGES` | -32027 | 409 | 200 | true | false | 存在未保存包且未允许丢弃 |
| `SEARCH_TIMEOUT` | -32028 | 504 | 200 | true | true | 资产搜索超过时限，可带部分结果 |
| `ASSET_REGISTRY_UNAVAILABLE` | -32029 | 503 | 200 | true | true | AssetRegistry 未就绪/不可用 |
| `MATERIAL_NOT_FOUND` | -32030 | 404 | 200 | true | false | 材质路径不存在 |
| `NOT_A_MATERIAL` | -32031 | 400 | 200 | true | false | 目标对象不是材质/材质实例 |
| `NOT_AN_INSTANCE` | -32032 | 409 | 200 | true | false | 对非 `MaterialInstanceConstant` 执行 set |
| `PARAM_NOT_FOUND` | -32033 | 404 | 200 | true | false | 材质参数名不存在 |
| `TYPE_MISMATCH` | -32034 | 400 | 200 | true | false | 参数类型与声明不一致 |
| `ALREADY_EXISTS` | -32035 | 409 | 200 | true | false | 目标资产路径已存在 |
| `CAPTURE_FAILED` | -32036 | 500 | 200 | true | false | 截图任务创建/写文件失败 |
| `CAPTURE_TIMEOUT` | -32037 | 504 | 200 | true | true | 截图任务超时 |
| `PIE_NOT_RUNNING` | -32038 | 409 | 200 | true | false | 请求 PIE 截图但 PIE 未运行 |
| `BLUEPRINT_NOT_FOUND` | -32039 | 404 | 200 | true | false | 蓝图路径不存在 |
| `NOT_A_BLUEPRINT` | -32040 | 400 | 200 | true | false | 目标资产不是 `UBlueprint` |
| `GRAPH_NOT_FOUND` | -32041 | 404 | 200 | true | false | 指定图名不存在 |
| `COMPILE_FAILED` | -32042 | 500 | 200 | true | false | 蓝图编译返回错误/仍有编译错误 |
| `EXEC_DISABLED` | -32043 | 403 | 200 | true | false | 桥接 `allowExec=false`，拒绝 Python 执行 |
| `BRIDGE_UNAVAILABLE` | -32000 | 503 | 200 | true | true | 桥接未启动/不可达/发现文件无效 |
| `BRIDGE_TIMEOUT` | -32020 | 504 | 200 | true | true | 游戏线程任务超时 |
| `BRIDGE_BUSY` | -32002 | 429 | 200 | true | true | 队列满/编辑器忙 |
| `PERMISSION_DENIED` | -32003 | 403 | 200 | true | false | 策略或桥接权限门拒绝（非 exec） |
| `TOOL_DISABLED` | -32004 | 403 | 200 | true | false | 工具未在当前策略/开关组合中注册 |
| `CONFIRMATION_REQUIRED` | -32005 | 428 | 200 | true | false | 需要确认但未满足 |
| `NOT_FOUND` | -32006 | 404 | 200 | true | false | 通用资源不存在（优先使用具体码） |
| `CONFLICT` | -32007 | 409 | 200 | true | false | 通用冲突（优先使用具体码） |
| `UNSUPPORTED` | -32008 | 501 | 200 | true | false | 当前引擎/平台不支持 |
| `EXECUTION_ERROR` | -32009 | 500 | 200 | true | false | 编辑器执行异常（未分类） |
| `EDITOR_UNSAFE_STATE` | -32010 | 409 | 200 | true | true | PIE/编译/加载中，重试可能成功 |
| `PAYLOAD_TOO_LARGE` | -32011 | 413 | 200 | true | false | **工具级**结果/图像超限 |
| `RATE_LIMITED` | -32012 | 429 | 200 | true | true | **工具级**限流 |
| `SAVE_FAILED` | -32013 | 500 | 200 | true | false | 保存资产/关卡失败 |
| `PYTHON_ERROR` | -32014 | 500 | 200 | true | false | Python 异常，含 traceback |
| `RESULT_NOT_SERIALIZABLE` | -32015 | 500 | 200 | true | false | 返回值无法 JSON 化 |
| `CAPABILITY_UNAVAILABLE` | -32016 | 501 | 200 | true | false | 能力探测为 false |
| `COMMAND_NOT_ALLOWED` | -32017 | 403 | 200 | true | false | 控制台命令被白名单/拒绝表拦住 |
| `CONFIRMATION_DENIED` | -32018 | 403 | 200 | true | false | 用户在 elicitation 中拒绝 |

命名规则：

- 具体错误优先于通用错误：能用 `MATERIAL_NOT_FOUND` 就不返回 `NOT_FOUND`。
- 禁止同义码：不新增 `TIMEOUT`、`MATERIAL_INSTANCE_NOT_FOUND`、`BP_NOT_FOUND` 等别名。
- **`-32001` 专用于 `SESSION_NOT_FOUND`**；`BRIDGE_TIMEOUT` 使用 `-32020`，不得复用 `-32001`。
- **`TIMEOUT` 已退役**：Python/搜索/截图的超时分别使用 `BRIDGE_TIMEOUT`、`SEARCH_TIMEOUT`、`CAPTURE_TIMEOUT`。

#### 2.9.4 `INVALID_ARGUMENT` 的唯一返回形态

| 场景 | 对外 code | HTTP | JSON-RPC 顶层 |
|---|---|---|---|
| `tools/call` 信封不合法：`params` 非对象、缺少 `name`、`name` 非字符串、`arguments` 非对象、`arguments` 为数组、**完整工具目录中不存在的工具名** | `INVALID_PARAMS` | 400 | `error.code = -32602` |
| 已知工具，`arguments` 未通过该工具 inputSchema（类型、enum、required、additionalProperties、范围） | `INVALID_ARGUMENT` | **200** | 无 error；`result.isError=true` |

边界规则：

- 工具存在性按**完整工具目录（10 个）**判断，不按当前可见集合判断。完整目录中不存在 → `INVALID_PARAMS`；存在但未注册（策略/开关）→ 策略层返回 `TOOL_DISABLED`。
- zod 校验只针对 `arguments` 内容；信封校验在路由层单独做。
- 校验顺序：信封 → 完整目录存在性 → 策略/开关 → zod → 业务校验。
- `INVALID_ARGUMENT` 的 `details.issues` 为 `[{path, code, message}]`。

工具层示例：

```json
{
  "jsonrpc": "2.0",
  "id": 13,
  "result": {
    "content": [{ "type": "text", "text": "INVALID_ARGUMENT: sections[0] must be one of ..." }],
    "structuredContent": {
      "ok": false,
      "error": {
        "code": "INVALID_ARGUMENT",
        "message": "sections[0] must be one of ...",
        "retryable": false,
        "details": {
          "issues": [{ "path": ["sections", 0], "code": "invalid_enum_value", "message": "..." }]
        }
      },
      "meta": { "requestId": "req_...", "durationMs": 1 }
    },
    "isError": true
  }
}
```

#### 2.9.5 桥接内部 HTTP 与转换规则

| 桥接错误类别 | 桥接 HTTP |
|---|---|
| 参数/选择器/对象不存在 | 400 或 404 |
| 权限/开关拒绝 | 403 |
| 状态冲突（PIE、脏包、已存在、事务失败） | 409 |
| 请求/结果过大 | 413 |
| 队列满/限流 | 429 |
| 超时 | 504 |
| 未分类执行异常 | 500 |
| 能力不支持 | 501 |

MCP Server 转换规则：

- 连接拒绝、端口不可达、连接超时 → `BRIDGE_UNAVAILABLE`。
- 收到合法 JSON-RPC error → 按 `data.errorCode` 映射；未知 errorCode → `INTERNAL`。
- 收到非 JSON 响应或 HTTP 5xx 且无合法 JSON-RPC body → `INTERNAL`（`details.bridgeHttpStatus`），不要误报为 `BRIDGE_UNAVAILABLE`。
- 桥接返回 429/504 且带 JSON-RPC error → `BRIDGE_BUSY` / `BRIDGE_TIMEOUT`。

#### 2.9.6 `details` 必填契约

| code | 必填 `details` 字段 |
|---|---|
| `INVALID_ARGUMENT` | `issues: [{path, code, message}]` |
| `ACTOR_NOT_FOUND` | `selector: {kind, value}`，`matches: []` |
| `AMBIGUOUS_SELECTOR` | `selector`，`matches: [{actorPath, name, label, class}]`（≥2） |
| `CLASS_NOT_FOUND` | `className` |
| `ASSET_NOT_FOUND` | `assetPath` |
| `TRANSACTION_FAILED` | `rolledBack: boolean`，`reason` |
| `LEVEL_NOT_FOUND` | `levelPath` |
| `LEVEL_LOAD_FAILED` | `levelPath`，`reason` |
| `UNSAVED_CHANGES` | `dirtyPackages: [string]` |
| `SEARCH_TIMEOUT` | `timeoutMs`，`partial: {total, returned, assets}`（可为空） |
| `ASSET_REGISTRY_UNAVAILABLE` | `loading: boolean` |
| `MATERIAL_NOT_FOUND` | `path` |
| `NOT_A_MATERIAL` | `path`，`actualClass` |
| `NOT_AN_INSTANCE` | `path`，`actualClass` |
| `PARAM_NOT_FOUND` | `parameterName`，`parameterType`，`availableParameters: [string]`（≤50） |
| `TYPE_MISMATCH` | `parameterName`，`expected`，`actual` |
| `ALREADY_EXISTS` | `path` |
| `CAPTURE_FAILED` | `target`，`reason` |
| `CAPTURE_TIMEOUT` | `target`，`timeoutMs` |
| `PIE_NOT_RUNNING` | `target: "pie"` |
| `BLUEPRINT_NOT_FOUND` | `blueprintPath` |
| `NOT_A_BLUEPRINT` | `path`，`actualClass` |
| `GRAPH_NOT_FOUND` | `blueprintPath`，`graphName` |
| `COMPILE_FAILED` | `blueprintPath`，`errors: [string]`，`warnings: [string]` |
| `EXEC_DISABLED` | `gate: "bridge.allowExec"` |
| `PERMISSION_DENIED` | `gate: "bridge.allowWrite" \| "bridge.allowConsole" \| "server.policy"` |
| `TOOL_DISABLED` | `gate: "server.policy" \| "server.allowConsole" \| "server.allowExec"` |
| `BRIDGE_TIMEOUT` | `timeoutMs`，`phase: "game_thread" \| "capture" \| "search"` |

#### 2.9.7 `UNSAVED_CHANGES` 与 `CONFIRMATION_REQUIRED` 的判定顺序

`ue_level_control {action:"open"}`：

| 条件 | 返回 |
|---|---|
| 有脏包且 `allowDiscardUnsaved=false` | `UNSAVED_CHANGES`（与 `confirm` 无关） |
| 有脏包、`allowDiscardUnsaved=true`、`confirm=false`，且未满足破坏性确认 | `CONFIRMATION_REQUIRED` |
| 有脏包、`allowDiscardUnsaved=true`、`confirm=true`，或 elicitation 已批准，或 `--allow-destructive` | 执行打开 |
| 无脏包 | 执行打开 |

`save_all` 在 `confirm=false` 时返回 `CONFIRMATION_REQUIRED`，而不是 `UNSAVED_CHANGES`。

---

## 3. 传输层设计

### 3.1 传输矩阵

| 传输 | 端点 | 适用客户端 | 会话 | MVP |
|---|---|---|---|---|
| Streamable HTTP | `POST/GET/DELETE http://127.0.0.1:18777/mcp` | Claude Code、Cursor、自研 | `Mcp-Session-Id` | 主 |
| 旧版 HTTP+SSE | `GET /sse` + `POST /messages?sessionId=` | 老版本客户端 | `sessionId` 查询参数 | 兼容 |
| stdio | 客户端拉起进程 | Claude Code、cc-heihei、CLI | 进程级 | 支持 |

三种传输共享同一套 `McpServer` 构建函数、工具注册、策略与审计；**禁止为不同传输复制工具实现**。

### 3.2 stdio

启动：

```bash
uemcp --transport stdio
# 或
npx -y @uemcp/server --transport stdio
```

规则：

- **stdout 只允许 MCP 帧**（一行一个 JSON-RPC 对象）；所有日志写 stderr。
- 启动时仍通过 HTTP 连接编辑器桥接；桥接不可达不阻止 MCP 启动，工具调用返回 `BRIDGE_UNAVAILABLE`。
- 进程退出时关闭桥接连接与审计文件；不负责关闭编辑器。
- stderr 日志格式：`{"level":"info","event":"bridge_connected","url":"...","ts":"..."}`，便于客户端收集。

### 3.3 Streamable HTTP

端点：`http://127.0.0.1:18777/mcp`

请求头：

```http
Content-Type: application/json
Accept: application/json, text/event-stream
Mcp-Session-Id: <初始化后返回>
MCP-Protocol-Version: 2025-06-18
Authorization: Bearer <可选>
```

行为：

| 方法 | 路径 | 行为 |
|---|---|---|
| `POST` | `/mcp` | 接收 JSON-RPC。初始化请求（无 session）创建会话并在响应头返回 `Mcp-Session-Id`。请求可返回 `application/json` 或 `text/event-stream` |
| `GET` | `/mcp` | 建立服务端→客户端 SSE 流；需要有效 `Mcp-Session-Id` |
| `DELETE` | `/mcp` | 终止会话，清理资源，返回 `204` |

会话规则：

- 会话 ID：`crypto.randomUUID()`；不透明，不编码用户信息。
- TTL：30 分钟空闲；每 60s 清扫一次。
- 上限：32 个并发会话；超限返回 `429`。
- 未知/过期会话：`404` + JSON-RPC error `-32001`（`Session not found`），客户端应重新 `initialize`。
- 初始化之外的请求缺少 `Mcp-Session-Id`：`400`。
- `notifications/initialized`、通知、响应：返回 `202 Accepted`，无 body。
- **工具层错误**：已路由到已知工具的 `tools/call` 执行失败一律 `HTTP 200` + `result.isError=true` + `structuredContent.error`（见 §2.9）；禁止用 4xx/5xx 表示工具执行失败。
- **信封/未知工具**：`tools/call` 的 `params`/`name`/`arguments` 结构错误、或被请求的名字不在完整工具目录中 → `400` + `INVALID_PARAMS`（`-32602`）。已知工具但未在当前策略中注册 → `200` + `TOOL_DISABLED`。

初始化示例（通用 HTTP 客户端）：

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

后续调用：

```bash
curl -s -X POST http://127.0.0.1:18777/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Mcp-Session-Id: <上一步响应头>' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

安全校验（HTTP 层中间件）：

- 仅接受 `Host: 127.0.0.1:<port>`、`localhost:<port>`；其他 Host 返回 `421`（防 DNS rebinding）。
- 若存在 `Origin`，必须为 `http://127.0.0.1:<port>` / `http://localhost:<port>` / `null`；否则 `403`。
- 不发送 `Access-Control-Allow-Origin: *`；默认不启用 CORS。
- 请求体上限 8 MiB；图像响应上限 8 MiB（原始字节），超过则改 `returnMode=file` 或报 `PAYLOAD_TOO_LARGE`。

健康检查：

```http
GET http://127.0.0.1:18777/health
```

```json
{
  "ok": true,
  "name": "uemcp",
  "version": "0.1.0",
  "protocolVersions": ["2025-06-18", "2025-03-26", "2024-11-05"],
  "transports": ["streamable-http", "sse", "stdio"],
  "sessions": 1,
  "uptimeSec": 123,
  "bridge": {
    "connected": true,
    "url": "http://127.0.0.1:18778",
    "ueVersion": "5.4.4",
    "pluginVersion": "0.1.0",
    "projectDir": "C:/UE5_P/5.4/XQHCPP_54"
  }
}
```

健康检查不返回 token、不执行编辑器调用，只使用缓存状态；`bridge.connected` 由后台探活维护（每 5s 一次，超时 1s）。

### 3.4 旧版 SSE 兼容

端点：

- `GET /sse`：建立 SSE 流。
- 首个事件：

```text
event: endpoint
data: /messages?sessionId=3f2b9c1e-...
```

- 客户端随后向 `/messages?sessionId=...` POST JSON-RPC；服务端返回 `202 Accepted`，真正的响应通过 SSE 流下发。
- 每 15s 发送注释心跳 `: ping`。
- 会话与 Streamable HTTP 使用同一 `SessionRegistry`，但 transport 类型不同。
- 通过 `--disable-legacy-sse` 可关闭。
- 兼容目标：暂不支持 Streamable HTTP 的旧版 Cursor/自研客户端。文档中标注为 **deprecated compatibility**。

**SSE 兼容验收基线（已裁决）**：

| 基线 | 对象 | 性质 |
|---|---|---|
| 自研脚本 | `examples/generic/sse_client.py`（仅 Python 标准库） | **必测**；退出码 0 即通过，FAIL 则 SSE 兼容判定为 FAIL |
| 客户端证据 | **Cursor 0.45.11**（0.45 系列为 MCP 引入期、以 SSE 远程配置为主的版本线） | 可安装时必须测；不可安装或客户端本身不支持 SSE 记 N/A |
| 替代规则 | 若 0.45.11 不可得，使用 **0.45.x 系列最早可安装版本**并记录实际版本 | 不得用 0.46+ 作为旧版 SSE 基线 |

脚本流程：`GET /sse` → 解析 `event: endpoint` 与 `data:` → `POST initialize` → `notifications/initialized`（断言 202）→ `tools/list`（断言工具数）→ `tools/call ue_editor_status`（断言 `ok==true`）。退出码：0 通过、1 断言失败、2 传输失败、3 超时、4 SSE 解析失败。

判定：自研脚本 FAIL → FAIL；脚本 PASS 且 Cursor 不可安装/本身不支持 SSE → PASS（Cursor 部分 N/A）；脚本 PASS 且 Cursor 可安装、支持 SSE 但因服务端缺陷失败 → FAIL。

实现要点（TypeScript 伪代码）：

```ts
// http.ts
const streamable = new Map<string, StreamableHTTPServerTransport>();
const legacy = new Map<string, SSEServerTransport>();

app.post("/mcp", async (req, res) => {
  const sid = req.header("mcp-session-id");
  if (!sid) {
    if (!isInitialize(req.body)) return sendRpcError(res, 400, -32600, "Missing session");
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      onsessioninitialized: (id) => streamable.set(id, transport),
    });
    transport.onclose = () => streamable.delete(transport.sessionId!);
    await buildMcpServer().connect(transport);
    return transport.handleRequest(req, res, req.body);
  }
  const transport = streamable.get(sid);
  if (!transport) return sendRpcError(res, 404, -32001, "Session not found");
  return transport.handleRequest(req, res, req.body);
});

app.get("/mcp", (req, res) => {
  const transport = streamable.get(req.header("mcp-session-id") ?? "");
  if (!transport) return sendRpcError(res, 404, -32001, "Session not found");
  return transport.handleRequest(req, res);
});

app.delete("/mcp", async (req, res) => {
  const transport = streamable.get(req.header("mcp-session-id") ?? "");
  if (!transport) return res.status(404).end();
  await transport.close();
  res.status(204).end();
});

app.get("/sse", async (req, res) => {
  const transport = new SSEServerTransport("/messages", res);
  legacy.set(transport.sessionId, transport);
  transport.onclose = () => legacy.delete(transport.sessionId);
  await buildMcpServer().connect(transport);
});

app.post("/messages", async (req, res) => {
  const transport = legacy.get(String(req.query.sessionId ?? ""));
  if (!transport) return res.status(404).end();
  await transport.handlePostMessage(req, res, req.body);
  res.status(202).end();
});
```

> SDK 版本以 `@modelcontextprotocol/sdk` ≥ 1.12 为准。若使用旧版 SDK 的 `server.tool()` 注册方式，需同步调整。

### 3.5 客户端接入配置

#### 3.5.1 Claude Code — Streamable HTTP（推荐）

```bash
claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp
```

启用可选鉴权：

```bash
claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp \
  --header "Authorization: Bearer ${UEMCP_AUTH_TOKEN}"
```

项目级 `.mcp.json`：

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

> 若当前 Claude Code 版本对 `.mcp.json` 的环境变量展开有限制，直接写明文本地 token 或省略鉴权（仅回环）。

#### 3.5.2 Claude Code / cc-heihei / CLI — stdio

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

Windows 上若客户端不解析 `npx.cmd`：

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

#### 3.5.3 Cursor — Streamable HTTP

`.cursor/mcp.json`（项目）或 `~/.cursor/mcp.json`（全局）：

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

若客户端版本不支持 Streamable HTTP，改用旧版 SSE：

```json
{
  "mcpServers": {
    "uemcp": {
      "url": "http://127.0.0.1:18777/sse"
    }
  }
}
```

> Cursor 不同版本对 `url` 的语义（SSE vs Streamable HTTP）不同；以实际版本的 MCP 设置为准，两种端点都可用。
>
> 旧版 SSE 的验收基线固定为 **Cursor 0.45.11**（或 0.45.x 最早可得版本，须记录）；0.46+ 的 `url` 语义可能已转向 Streamable HTTP，不能作为旧版 SSE 基线。必测脚本为 `examples/generic/sse_client.py`，详见 §3.4。

#### 3.5.4 通用 HTTP 客户端

最小调用序列：

1. `POST /mcp` `initialize`，记录 `Mcp-Session-Id`。
2. `POST /mcp` `notifications/initialized`（202）。
3. `POST /mcp` `tools/list`（带 session 头）。
4. `POST /mcp` `tools/call`。

注意：

- `Accept` 必须同时包含 `application/json` 与 `text/event-stream`。
- 服务端可能以 SSE 格式响应，客户端需按 `data:` 行解析。
- 每次请求带 `MCP-Protocol-Version`（初始化后）。

### 3.6 协议版本与降级

- 支持：`2025-06-18`（首选）、`2025-03-26`、`2024-11-05`。
- 初始化时按客户端 `protocolVersion` 协商；不支持则返回服务端最高支持版本，由客户端决定是否继续。
- 旧 SSE 端点按 `2024-11-05` 语义工作。
- 当新协议字段（如 `structuredContent` / `outputSchema` / `elicitation`）不可用时：
  - 仍返回 `content` 文本摘要；
  - `structuredContent` 作为普通字段保留（多数客户端会忽略）；
  - 危险操作确认退化为策略开关（见 §6）。

---

## 4. UE 5.4 侧实现选型

### 4.1 Python Editor Script Plugin vs C++ 插件

| 维度 | Python Editor Script Plugin | C++ 插件 |
|---|---|---|
| 安装 | 引擎自带（Experimental），`.uplugin` 可自动启用 | 需随引擎版本编译，Windows 需 VS 工具链 |
| 5.4 兼容 | 引擎自带，直接可用 | 每个版本重编译；二进制不跨版本 |
| 分发 | 纯文本插件，zip 即可；跨平台 | 需分发二进制或源码，用户编译 |
| 开发效率 | 改完重启 Python/重载即可 | 编译链接，迭代慢 |
| Editor API 覆盖 | Actor/关卡/资产/材质/截图/大部分编辑器子系统 | 全部，包括蓝图节点图、动画蓝图 |
| 蓝图节点编辑 | **不可用**（无公开 Python API） | 可用（`UEdGraphSchema_K2`） |
| 动画蓝图 | 只读有限；不可编辑 | 可用 |
| 控制台输出捕获 | 不可用 | 可用（`FOutputDevice`） |
| 性能 | 一般；GIL；单游戏线程 | 高 |
| 线程模型 | 所有调用切游戏线程 | 可精细控制 |
| 打包运行时 | 不进入 Shipping | 可控制 |
| 安全面 | 任意 Python 即 RCE | 可控函数面 |
| 维护成本 | 低 | 高 |

### 4.2 推荐

**MVP 采用 Python Editor Script Plugin，以“纯 Python 插件”形式分发。**

理由：

1. 用户目标是 5.4、编辑器内自动化，Python 覆盖了 10 个 MVP 工具的**主路径**；缺口只在蓝图节点级编辑与控制台输出回显，而这两项已被 MVP 明确排除。
2. 零编译是最重要的分发优势：开源项目用户下载插件目录、启用 Python 插件即可。
3. 代码可读、可热改，便于社区贡献。
4. C++ 的优势集中在蓝图/动画节点编辑与输出捕获；这些恰好是 MVP 明确排除的能力，不需要为此付出编译与跨版本成本。

**P2 增加可选 C++ 辅助模块**，只在检测到模块时启用高级工具；MCP 对外 Schema 不变。例如：

- `UEMCPGraphBridge`：蓝图节点创建、连线、动画蓝图状态机。
- `UEMCPLogCapture`：控制台命令输出回显。

插件清单（MVP，无 C++ 模块）：

```json
{
  "FileVersion": 3,
  "Version": 1,
  "VersionName": "0.1.0",
  "FriendlyName": "UEMCP Bridge",
  "Description": "Local MCP bridge for Unreal Engine 5.4 editor automation.",
  "Category": "Scripting",
  "CreatedBy": "UEMCP contributors",
  "CanContainContent": true,
  "IsBetaVersion": true,
  "Installed": false,
  "Modules": [],
  "Plugins": [
    { "Name": "PythonScriptPlugin", "Enabled": true },
    { "Name": "EditorScriptingUtilities", "Enabled": true }
  ]
}
```

说明：

- `PythonScriptPlugin` 是引擎自带的 Python Editor Script Plugin 的插件名。
- `EditorScriptingUtilities` 提供 `EditorLevelLibrary` 等旧兼容层；MVP 主要用子系统，但启用它可提高旧脚本兼容性。若不想引入，可去掉，代码不得依赖它。
- `CanContainContent: true` 才会扫描 `Content/Python/init_unreal.py`。

### 4.3 5.4 API 能力核对

已在本机 `UE 5.4.4` 的引擎源码中确认存在：

| 能力 | 5.4 API | 说明 |
|---|---|---|
| Actor 全量/选中 | `unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()` / `get_selected_level_actors()` | 已确认 |
| Actor 生成/销毁/复制 | `spawn_actor_from_class` / `destroy_actor` / `duplicate_actor` | 已确认 |
| Actor 变换 | `set_actor_transform` | 已确认 |
| Actor 按路径查找 | `get_actor_reference(path)` | 已确认 |
| 关卡打开/保存/新建 | `unreal.LevelEditorSubsystem.load_level` / `save_current_level` / `save_all_dirty_levels` / `new_level` | 已确认 |
| 脏包列表 | `unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()` | `UEditorLoadingAndSavingUtils` 在 UnrealEd，已确认 |
| 编辑器世界/游戏世界 | `unreal.UnrealEditorSubsystem.get_editor_world()` / `get_game_world()` | 已确认 |
| 视口相机 | `UnrealEditorSubsystem.get_level_viewport_camera_info` / `set_level_viewport_camera_info` | 已确认 |
| 资产列表/查找 | `unreal.EditorAssetSubsystem.list_assets` / `find_asset_data` / `load_asset` / `save_asset` | 已确认 |
| 资产依赖/引用 | `unreal.AssetRegistryHelpers.get_asset_registry().get_dependencies` / `get_referencers` | `IAssetRegistry` 有 UFUNCTION 包装，已确认 |
| 材质参数 | `unreal.MaterialEditingLibrary` 的 get/set scalar/vector/texture/static switch | 已确认 |
| 创建材质实例 | `MaterialInstanceConstantFactoryNew` + `AssetToolsHelpers.get_asset_tools().create_asset` | 已确认 |
| 截图 | `unreal.AutomationLibrary.take_high_res_screenshot(...)` | 类经 `ScriptName="AutomationLibrary"` 暴露，已确认；输出路径/PIE 行为需 PoC 验证 |
| 控制台 | `unreal.SystemLibrary.execute_console_command(world, command)` | 已确认；无输出回显 |
| 蓝图编译/图查找 | `unreal.BlueprintEditorLibrary.compile_blueprint` / `find_event_graph` / `find_graph` | 已确认 |
| 事务 | `with unreal.ScopedEditorTransaction("desc") as tx: ... tx.cancel()` | 已确认 |
| 游戏线程泵 | `unreal.register_slate_post_tick_callback(fn)` | 已确认 |
| 关闭清理 | `unreal.register_python_shutdown_callback(fn)` | 已确认 |

蓝图数据读取（变量、组件、图）通过 `get_editor_property`；节点级读取（`graph.get_editor_property('nodes')`）依赖反射，**未列入稳定契约**，标记为 experimental。

### 4.4 插件加载与分发

加载链：

1. 项目启用 `UEMCPBridge`（`Plugins/UEMCPBridge/UEMCPBridge.uplugin`）。
2. 插件声明启用 `PythonScriptPlugin`。
3. 引擎启动编辑器，Python 插件扫描所有启用插件的 `Content/Python/`，执行 `init_unreal.py`。
4. `init_unreal.py` 读取配置，启动桥接 HTTP 服务，写发现文件。
5. 编辑器退出时注册的 shutdown 回调停止服务并删除发现文件（仅当 PID 匹配）。

`init_unreal.py` 要点：

```python
import unreal

def _start():
    try:
        from uemcp_bridge.server import BridgeServer
        BridgeServer.instance().start()
    except Exception as exc:
        unreal.log_error(f"[UEMCP] failed to start bridge: {exc}")

# 延迟到编辑器完全就绪
unreal.register_slate_post_tick_callback(lambda _dt: _start())
```

实现时应确保只启动一次（模块级标志），并在 `is_editor()` 为真时启动。

配置来源（优先级从高到低）：

1. 环境变量：`UEMCP_BRIDGE_PORT`、`UEMCP_BRIDGE_ALLOW_WRITE`、`UEMCP_BRIDGE_ALLOW_EXEC`、`UEMCP_BRIDGE_TOKEN_FILE`
2. `Saved/UEMCP/bridge-settings.json`
3. 默认值：端口 18778、只读、禁止 exec

```json
{
  "port": 18778,
  "allowWrite": true,
  "allowExec": false,
  "allowConsole": false,
  "consoleAllowlist": ["stat", "show", "r.", "sg.", "viewmode", "log", "help"],
  "maxQueueSize": 64,
  "requestTimeoutMs": 30000
}
```

---

## 5. 工具清单

### 5.0 通用约定

#### 5.0.1 返回封装

所有工具返回 MCP `CallToolResult`：

```json
{
  "content": [
    { "type": "text", "text": "actor.query: 12 actors returned (limit 50)" }
  ],
  "structuredContent": {
    "ok": true,
    "data": {},
    "warnings": [],
    "meta": {
      "requestId": "req_01H...",
      "durationMs": 12,
      "ueVersion": "5.4.4",
      "pluginVersion": "0.1.0"
    }
  },
  "isError": false
}
```

失败：

```json
{
  "content": [
    { "type": "text", "text": "ACTOR_NOT_FOUND: Actor not found: PersistentLevel.X" }
  ],
  "structuredContent": {
    "ok": false,
    "error": {
      "code": "ACTOR_NOT_FOUND",
      "message": "Actor not found: PersistentLevel.X",
      "retryable": false,
      "details": {
        "selector": { "kind": "actorPath", "value": "PersistentLevel.X" },
        "matches": []
      }
    },
    "meta": { "requestId": "req_01H...", "durationMs": 3 }
  },
  "isError": true
}
```

`structuredContent` 必须同时满足工具的 `outputSchema`。对不支持 `structuredContent` 的客户端，`content[0].text` 是人类的简短摘要，不是完整数据的替代。

**错误形态固定规则（与 §2.9 一致）**：

- 成功：`isError=false`（或缺省）、`structuredContent.ok=true`、无 `error`。
- 工具执行失败：`isError=true`、`structuredContent.ok=false`、`structuredContent.error` 必须存在，且 **HTTP 状态恒为 200**。
- 禁止“HTTP 4xx/5xx + 工具错误对象”或“HTTP 200 + 顶层 JSON-RPC error”的混合形态。
- 协议层错误（信封/未知 method/会话/鉴权/请求体超限）不产生 `CallToolResult`，按 §2.9.2 返回顶层 JSON-RPC error。
- 成功但有警告（`rolledBack:false`、`outputAvailable:false`、图像过大只返回路径）仍为 `isError=false`，写入 `warnings[]`。
- `content[0].text` 固定以 `"<CODE>: <message>"` 开头。

#### 5.0.2 共享类型（JSON Schema `$defs`）

以下定义被各工具引用，放在 `packages/shared/src/schemas/common.ts` 生成的 `$defs` 中。

```json
{
  "$defs": {
    "Vec3": {
      "type": "object",
      "additionalProperties": false,
      "required": ["x", "y", "z"],
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" },
        "z": { "type": "number" }
      }
    },
    "Rotator": {
      "type": "object",
      "additionalProperties": false,
      "required": ["pitch", "yaw", "roll"],
      "properties": {
        "pitch": { "type": "number" },
        "yaw": { "type": "number" },
        "roll": { "type": "number" }
      }
    },
    "Selector": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "value"],
      "properties": {
        "kind": { "enum": ["actorPath", "objectPath", "name", "label"] },
        "value": { "type": "string", "minLength": 1, "maxLength": 512 }
      }
    },
    "ActorRef": {
      "type": "object",
      "additionalProperties": false,
      "required": ["actorPath", "name", "class"],
      "properties": {
        "actorPath": { "type": "string", "description": "关卡内路径，例如 PersistentLevel.SM_Chair_2" },
        "objectPath": { "type": "string", "description": "完整对象路径" },
        "name": { "type": "string" },
        "label": { "type": "string" },
        "class": { "type": "string" },
        "classPath": { "type": "string" },
        "levelPath": { "type": "string" }
      }
    },
    "AssetRef": {
      "type": "object",
      "additionalProperties": false,
      "required": ["packageName", "objectPath", "assetName", "class"],
      "properties": {
        "packageName": { "type": "string", "examples": ["/Game/Materials/M_Chair"] },
        "objectPath": { "type": "string", "examples": ["/Game/Materials/M_Chair.M_Chair"] },
        "assetName": { "type": "string" },
        "class": { "type": "string" },
        "classPath": { "type": "string" },
        "packagePath": { "type": "string" },
        "isRedirector": { "type": "boolean" },
        "diskSize": { "type": "integer", "minimum": 0 }
      }
    },
    "Transform": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "location": { "$ref": "#/$defs/Vec3" },
        "rotation": { "$ref": "#/$defs/Rotator" },
        "scale": { "$ref": "#/$defs/Vec3" }
      }
    },
    "Error": {
      "type": "object",
      "required": ["code", "message", "retryable"],
      "properties": {
        "code": { "type": "string" },
        "message": { "type": "string" },
        "retryable": { "type": "boolean" },
        "details": { "type": "object" }
      }
    }
  }
}
```

#### 5.0.3 权限级别与确认

| 级别 | 名称 | 生效策略 | 默认可见 |
|---|---|---|---|
| P0 | read | `read-only` / `standard` / `full` | 是 |
| P1 | write | `standard` / `full` | 是 |
| P2 | dangerous | `full` + 独立开关 | 否 |

- 工具可见性在 `tools/list` 阶段过滤；**隐藏工具直接调用返回 `TOOL_DISABLED`**，`details.gate` 标明来源。
- **read-only 注册规则（D12）**：
  - 纯 P0 工具全部注册：`ue_editor_status`、`ue_actor_query`、`ue_asset_search`、`ue_viewport_capture`；
  - P0/P1 混合工具注册，但 `inputSchema` 的 `action` enum 收窄到只读动作：`ue_level_control`（`get_current`/`list_dirty`）、`ue_material_params`（`list`/`get`）、`ue_blueprint`（`query`）；
  - 纯 P1 工具（`ue_actor_edit`）不注册；
  - P2 工具不注册。
  - 因此 read-only 共 **7 个**工具（详见 §5.11）。
- 混合工具的写 action 在 read-only 下由收窄 Schema 拒绝 → 工具层 `INVALID_ARGUMENT`；若绕过 Schema 直达 handler，二次校验返回 `PERMISSION_DENIED`（`details.gate="server.policy"`）。
- P1 中的破坏性操作（删除 Actor、覆盖未保存内容、批量保存）确认规则：
  1. 客户端声明 `elicitation` 能力时，发起 `elicitation/create` 让用户确认；
  2. 否则要求服务端以 `--allow-destructive` 启动；
  3. 两者都没有 → `CONFIRMATION_REQUIRED`。
- P2 工具：`ue_console_command`、`ue_python_exec`。它们**不使用** `--allow-destructive`：
  1. 客户端支持 elicitation 时，每次调用都询问；
  2. 客户端不支持 elicitation 时，`--allow-console` / `--allow-exec` 本身作为**策略级确认**；
  3. 对应开关未开 → 工具不注册，调用返回 `TOOL_DISABLED`。
- 所有 P1/P2 调用写审计；`confirmationMode ∈ {"elicitation","policy","none"}`。

#### 5.0.4 工具注解（MCP annotations）

| 工具 | readOnlyHint | destructiveHint | idempotentHint | openWorldHint |
|---|---|---|---|---|
| `ue_editor_status` | true | false | true | false |
| `ue_actor_query` | true | false | true | false |
| `ue_actor_edit` | false | true | false | false |
| `ue_level_control` | false | true | false | false |
| `ue_asset_search` | true | false | true | false |
| `ue_material_params` | false | false | false | false |
| `ue_viewport_capture` | true | false | false | false |
| `ue_console_command` | false | true | false | false |
| `ue_python_exec` | false | true | false | true |
| `ue_blueprint` | false | false | false | false |

> 混合工具（`ue_level_control`、`ue_material_params`、`ue_blueprint`）的注解随策略模式变化：read-only 下三者 `readOnlyHint=true`、`destructiveHint=false`（Schema 已收窄为只读动作）；standard/full 下 `readOnlyHint=false`，`destructiveHint` 按表值（`ue_level_control=true`，因为可丢弃未保存内容/批量保存；`ue_material_params`/`ue_blueprint=false`）。

---

### 5.1 `ue_editor_status`

**用途**：返回编辑器、当前关卡、选中 Actor、视口相机、能力探测与当前策略。是所有客户端的第一入口。

**权限**：P0，无需确认。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "sections": {
      "type": "array",
      "items": { "enum": ["editor", "level", "selection", "viewport", "capabilities", "policies"] },
      "default": ["editor", "level", "selection", "capabilities"]
    },
    "selectionLimit": { "type": "integer", "minimum": 0, "maximum": 200, "default": 20 }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "properties": {
    "editor": {
      "type": "object",
      "properties": {
        "ueVersion": { "type": "string" },
        "pluginVersion": { "type": "string" },
        "bridgeProtocol": { "type": "integer" },
        "processId": { "type": "integer" },
        "isPieRunning": { "type": "boolean" },
        "isSimulating": { "type": "boolean" },
        "isCompiling": { "type": "boolean" },
        "isAssetRegistryLoading": { "type": "boolean" }
      }
    },
    "level": {
      "type": "object",
      "properties": {
        "path": { "type": "string" },
        "name": { "type": "string" },
        "isDirty": { "type": "boolean" },
        "isPartitioned": { "type": "boolean" },
        "dirtyPackageCount": { "type": "integer" }
      }
    },
    "selection": {
      "type": "object",
      "properties": {
        "count": { "type": "integer" },
        "actors": { "type": "array", "items": { "$ref": "#/$defs/ActorRef" } },
        "truncated": { "type": "boolean" }
      }
    },
    "viewport": {
      "type": "object",
      "properties": {
        "cameraLocation": { "$ref": "#/$defs/Vec3" },
        "cameraRotation": { "$ref": "#/$defs/Rotator" },
        "width": { "type": "integer" },
        "height": { "type": "integer" }
      }
    },
    "capabilities": {
      "type": "object",
      "properties": {
        "python": { "type": "boolean" },
        "screenshot": { "type": "boolean" },
        "blueprintRead": { "type": "boolean" },
        "blueprintNodeRead": { "type": "boolean" },
        "blueprintCompile": { "type": "boolean" },
        "animBlueprintEdit": { "type": "boolean" },
        "assetRegistry": { "type": "boolean" },
        "console": { "type": "boolean" }
      }
    },
    "policies": {
      "type": "object",
      "properties": {
        "mode": { "enum": ["read-only", "standard", "full"] },
        "write": { "type": "boolean" },
        "exec": { "type": "boolean" },
        "destructive": { "type": "boolean" }
      }
    }
  }
}
```

**错误码**：`BRIDGE_UNAVAILABLE`、`BRIDGE_TIMEOUT`、`INTERNAL`。

**实现要点**：

- `ueVersion`：`unreal.SystemLibrary.get_engine_version()`。
- PIE：`UnrealEditorSubsystem.get_game_world() is not None`；仿真：`LevelEditorSubsystem` 无直接查询，可用 `unreal.LevelEditorSubsystem.editor_play_simulate` 的状态或编辑器世界 `is_simulating`；MVP 可返回 `false` 并标注未验证。
- 脏包：`unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()`；当前关卡是否脏：比较世界包名。
- 选中：`EditorActorSubsystem.get_selected_level_actors()`。
- 视口：`UnrealEditorSubsystem.get_level_viewport_camera_info(out_location, out_rotation)`（Python 以返回值形式给出）。
- 能力探测：启动时缓存 `hasattr` 检查结果，不做每次调用重探测。

---

### 5.2 `ue_actor_query`

**用途**：按类、名称、标签、目录查询关卡或选中 Actor；分页返回。

**权限**：P0，无需确认。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "scope": { "enum": ["level", "selection"], "default": "level" },
    "filter": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "class": { "type": "string", "maxLength": 256, "description": "类名或类路径，匹配派生类" },
        "nameContains": { "type": "string", "maxLength": 200 },
        "labelContains": { "type": "string", "maxLength": 200 },
        "tags": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "maxProperties": 20
        },
        "folders": {
          "type": "array",
          "items": { "type": "string" },
          "maxItems": 10
        },
        "hasComponentClass": { "type": "string", "maxLength": 256 }
      }
    },
    "fields": {
      "type": "array",
      "items": { "enum": ["identity", "transform", "bounds", "tags", "components", "mobility", "folder"] },
      "default": ["identity", "transform", "tags"]
    },
    "limit": { "type": "integer", "minimum": 1, "maximum": 1000, "default": 50 },
    "offset": { "type": "integer", "minimum": 0, "maximum": 100000, "default": 0 },
    "sortBy": { "enum": ["name", "label", "class", "path"], "default": "name" }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "required": ["total", "returned", "actors", "truncated"],
  "properties": {
    "total": { "type": "integer" },
    "returned": { "type": "integer" },
    "truncated": { "type": "boolean" },
    "actors": {
      "type": "array",
      "items": {
        "allOf": [{ "$ref": "#/$defs/ActorRef" }],
        "type": "object",
        "properties": {
          "transform": { "$ref": "#/$defs/Transform" },
          "bounds": {
            "type": "object",
            "properties": {
              "origin": { "$ref": "#/$defs/Vec3" },
              "extent": { "$ref": "#/$defs/Vec3" }
            }
          },
          "tags": { "type": "array", "items": { "type": "string" } },
          "mobility": { "enum": ["static", "stationary", "movable"] },
          "folderPath": { "type": "string" },
          "components": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": { "type": "string" },
                "class": { "type": "string" }
              }
            }
          }
        }
      }
    }
  }
}
```

**错误码**：`INVALID_ARGUMENT`、`CLASS_NOT_FOUND`、`BRIDGE_UNAVAILABLE`、`BRIDGE_BUSY`、`INTERNAL`。

**实现要点**：

```python
actors = (
    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    if scope == "level"
    else unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors()
)
```

- 类过滤：`class` 含 `/` 时用 `unreal.load_class(None, class_path)`；否则先尝试 `getattr(unreal, name)`，再回退 `unreal.load_class(None, f"/Script/Engine.{name}")`。未找到 → `CLASS_NOT_FOUND`（`details.className`）。
- 标签：`actor.tags`。
- 标签匹配语义：所有给定键值对都必须存在（AND）。
- 组件过滤：`actor.get_components_by_class(unreal.ActorComponent)`。
- 排序在过滤后、分页前执行。
- 大关卡上限 1000 返回，`truncated` 标记。

---

### 5.3 `ue_actor_edit`

**用途**：批量生成、删除、变换、复制、选择 Actor，以及修改受控属性白名单。

**权限**：P1；`delete` 操作属于破坏性变更，需确认。PIE 运行中一律拒绝（`EDITOR_UNSAFE_STATE`）。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["operations"],
  "properties": {
    "operations": {
      "type": "array",
      "minItems": 1,
      "maxItems": 50,
      "items": {
        "oneOf": [
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["op", "class"],
            "properties": {
              "op": { "const": "spawn" },
              "class": { "type": "string", "maxLength": 256 },
              "assetPath": { "type": "string", "maxLength": 512 },
              "location": { "$ref": "#/$defs/Vec3" },
              "rotation": { "$ref": "#/$defs/Rotator" },
              "scale": { "$ref": "#/$defs/Vec3" },
              "label": { "type": "string", "maxLength": 128 },
              "tags": { "type": "array", "items": { "type": "string" }, "maxItems": 20 },
              "folderPath": { "type": "string", "maxLength": 256 },
              "selectAfterSpawn": { "type": "boolean", "default": false }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["op", "selector"],
            "properties": {
              "op": { "const": "delete" },
              "selector": { "$ref": "#/$defs/Selector" },
              "confirm": { "type": "boolean", "default": false }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["op", "selector"],
            "properties": {
              "op": { "const": "set_transform" },
              "selector": { "$ref": "#/$defs/Selector" },
              "location": { "$ref": "#/$defs/Vec3" },
              "rotation": { "$ref": "#/$defs/Rotator" },
              "scale": { "$ref": "#/$defs/Vec3" },
              "snapToGrid": { "type": "boolean", "default": false }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["op", "selector", "properties"],
            "properties": {
              "op": { "const": "set_properties" },
              "selector": { "$ref": "#/$defs/Selector" },
              "properties": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "label": { "type": "string", "maxLength": 128 },
                  "hidden": { "type": "boolean" },
                  "mobility": { "enum": ["static", "stationary", "movable"] },
                  "folderPath": { "type": "string", "maxLength": 256 },
                  "tags": { "type": "array", "items": { "type": "string" }, "maxItems": 20 },
                  "staticMesh": { "type": "string", "maxLength": 512 },
                  "materials": {
                    "type": "object",
                    "additionalProperties": { "type": "string" },
                    "maxProperties": 20
                  }
                }
              }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["op", "selector"],
            "properties": {
              "op": { "const": "duplicate" },
              "selector": { "$ref": "#/$defs/Selector" },
              "count": { "type": "integer", "minimum": 1, "maximum": 50, "default": 1 },
              "offset": { "$ref": "#/$defs/Vec3" },
              "labelSuffix": { "type": "string", "maxLength": 64, "default": "_copy" }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["op", "selector"],
            "properties": {
              "op": { "const": "select" },
              "selector": { "$ref": "#/$defs/Selector" },
              "mode": { "enum": ["replace", "add", "remove"], "default": "replace" }
            }
          }
        ]
      }
    },
    "atomic": { "type": "boolean", "default": true, "description": "失败时通过事务取消回滚" },
    "dryRun": { "type": "boolean", "default": false },
    "transactionName": { "type": "string", "maxLength": 128, "default": "UEMCP Actor Edit" }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "required": ["dryRun", "results", "summary"],
  "properties": {
    "dryRun": { "type": "boolean" },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["index", "op", "ok"],
        "properties": {
          "index": { "type": "integer" },
          "op": { "type": "string" },
          "ok": { "type": "boolean" },
          "created": { "type": "array", "items": { "$ref": "#/$defs/ActorRef" } },
          "modified": { "type": "array", "items": { "type": "string" } },
          "deleted": { "type": "array", "items": { "type": "string" } },
          "error": { "$ref": "#/$defs/Error" }
        }
      }
    },
    "summary": {
      "type": "object",
      "properties": {
        "requested": { "type": "integer" },
        "succeeded": { "type": "integer" },
        "failed": { "type": "integer" },
        "rolledBack": { "type": "boolean" }
      }
    }
  }
}
```

**错误码**：`INVALID_ARGUMENT`、`ACTOR_NOT_FOUND`、`AMBIGUOUS_SELECTOR`、`CLASS_NOT_FOUND`、`ASSET_NOT_FOUND`、`CONFIRMATION_REQUIRED`、`CONFIRMATION_DENIED`、`PERMISSION_DENIED`、`EDITOR_UNSAFE_STATE`、`TRANSACTION_FAILED`、`BRIDGE_BUSY`、`BRIDGE_TIMEOUT`、`INTERNAL`。

**确认要求**：`delete` 操作需要确认（elicitation 或 `--allow-destructive`）；`dryRun=true` 不需要确认。`--allow-console`/`--allow-exec` 不参与本工具确认。桥接 `allowWrite=false` 时返回 `PERMISSION_DENIED`（`details.gate="bridge.allowWrite"`）。错误码与 `details` 契约见 §2.9.3/§2.9.6。

**实现要点**：

```python
with unreal.ScopedEditorTransaction(transaction_name) as tx:
    try:
        for op in operations:
            apply_op(op)
    except Exception:
        if atomic:
            tx.cancel()
        raise
```

- `dryRun`：解析选择器、验证类/资产存在，不执行任何变更；返回预计的 `created/modified/deleted`。
- 选择器解析规则：
  - `actorPath` / `objectPath`：精确匹配 `get_path_name(actor)` 或 actor 路径；
  - `name` / `label`：必须唯一，否则 `AMBIGUOUS_SELECTOR`（`details.matches` 返回候选）。
- `spawn`：`EditorActorSubsystem.spawn_actor_from_class(cls, location, rotation)`；`scale` 通过 `set_actor_scale3d`；`assetPath` 加载后按组件类型设置（StaticMeshActor → `static_mesh`，SkeletalMeshActor → `skeletal_mesh_component`）。
- `set_properties` 只允许白名单；其余属性明确拒绝，提示使用 `ue_python_exec`（若开启）。
- `materials` 映射键为组件名或材质槽索引字符串；实现时通过 `actor.get_components_by_class(unreal.MeshComponent)` 匹配。
- `select`：`set_selected_level_actors`；`mode=add/remove` 时先取当前选中集合再计算。
- 事务边界：一个工具调用一个事务；`save` 不在此工具内执行。
- PIE 守卫：`UnrealEditorSubsystem.get_game_world() is not None` → `EDITOR_UNSAFE_STATE`。

---

### 5.4 `ue_level_control`

**用途**：查询当前关卡与脏包；打开、保存、新建关卡。

**权限**：查询 P0；打开/保存/新建 P1。打开时若存在未保存修改，需要 `allowDiscardUnsaved + confirm`。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["action"],
  "properties": {
    "action": { "enum": ["get_current", "list_dirty", "open", "save_current", "save_all", "new"] },
    "levelPath": { "type": "string", "maxLength": 512, "description": "如 /Game/Maps/Demo" },
    "templatePath": { "type": "string", "maxLength": 512 },
    "partitioned": { "type": "boolean", "default": false },
    "allowDiscardUnsaved": { "type": "boolean", "default": false },
    "confirm": { "type": "boolean", "default": false }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "name": { "type": "string" },
    "previousPath": { "type": "string" },
    "isDirty": { "type": "boolean" },
    "isPartitioned": { "type": "boolean" },
    "saved": { "type": "boolean" },
    "packages": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "name": { "type": "string" },
          "isMap": { "type": "boolean" }
        }
      }
    }
  }
}
```

**错误码**：`INVALID_ARGUMENT`、`LEVEL_NOT_FOUND`、`LEVEL_LOAD_FAILED`、`UNSAVED_CHANGES`、`CONFIRMATION_REQUIRED`、`SAVE_FAILED`、`EDITOR_UNSAFE_STATE`、`PERMISSION_DENIED`、`BRIDGE_BUSY`、`BRIDGE_TIMEOUT`。

**确认要求**：

- `open` 且存在脏包（判定顺序固定）：
  1. `allowDiscardUnsaved=false` → `UNSAVED_CHANGES`（`details.dirtyPackages`），与 `confirm` 无关；
  2. `allowDiscardUnsaved=true` 且 `confirm=false`，且无 elicitation 批准/`--allow-destructive` → `CONFIRMATION_REQUIRED`；
  3. `allowDiscardUnsaved=true` 且 `confirm=true`，或 elicitation 已批准/`--allow-destructive` → 执行打开。
- `save_all`：需 `confirm=true`（批量覆盖磁盘），或 elicitation 已批准/`--allow-destructive`；否则 `CONFIRMATION_REQUIRED`。
- `save_current`：无需额外确认。
- PIE 运行中：打开/新建/保存全部拒绝，除非 P2 的显式 `force`（MVP 不提供）。
- 错误码与 `details` 契约见 §2.9.3/§2.9.6。

**实现要点**：

```python
level_ss = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor_ss = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

# 当前关卡
world = editor_ss.get_editor_world()
level = level_ss.get_current_level()

# 脏包
dirty = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
```

- `open`：先校验 PIE、脏包、路径存在（`unreal.EditorAssetSubsystem.does_asset_exist` 或文件检查），再 `level_ss.load_level(path)`。
- `save_current`：`level_ss.save_current_level()`；失败返回 `SAVE_FAILED`。
- `save_all`：`level_ss.save_all_dirty_levels()`。
- `new`：`level_ss.new_level(path, partitioned)` 或 `new_level_from_template(path, template)`。
- `isPartitioned`：`world.get_editor_property("world_partition")` 或 `world.is_partitioned_world()`；若 Python 不可用，返回 `false` 并附 warning。
- `open` 前如活动编辑器有未保存内容，`load_level` 可能弹窗；桥接必须避免 UI 阻塞：预检脏包并直接失败。

---

### 5.5 `ue_asset_search`

**用途**：按路径/名称/类搜索资产；查询依赖与反向引用。

**权限**：P0，无需确认。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "query": { "type": "string", "maxLength": 256, "description": "匹配资产名或包路径，不区分大小写" },
    "path": { "type": "string", "maxLength": 512, "default": "/Game" },
    "classNames": {
      "type": "array",
      "items": { "type": "string", "maxLength": 128 },
      "maxItems": 20
    },
    "recursive": { "type": "boolean", "default": true },
    "includeRedirectors": { "type": "boolean", "default": false },
    "includeDependencies": { "type": "boolean", "default": false },
    "includeReferencers": { "type": "boolean", "default": false },
    "dependencyDepth": { "type": "integer", "minimum": 1, "maximum": 3, "default": 1 },
    "dependencyFlags": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "hard": { "type": "boolean", "default": true },
        "soft": { "type": "boolean", "default": true },
        "management": { "type": "boolean", "default": false },
        "searchableName": { "type": "boolean", "default": false }
      }
    },
    "limit": { "type": "integer", "minimum": 1, "maximum": 500, "default": 100 },
    "offset": { "type": "integer", "minimum": 0, "default": 0 },
    "sortBy": { "enum": ["path", "class", "name"], "default": "path" }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "required": ["total", "returned", "assets", "truncated"],
  "properties": {
    "total": { "type": "integer" },
    "returned": { "type": "integer" },
    "truncated": { "type": "boolean" },
    "assets": { "type": "array", "items": { "$ref": "#/$defs/AssetRef" } },
    "dependencies": {
      "type": "object",
      "additionalProperties": { "type": "array", "items": { "type": "string" } }
    },
    "referencers": {
      "type": "object",
      "additionalProperties": { "type": "array", "items": { "type": "string" } }
    }
  }
}
```

**错误码**：`INVALID_ARGUMENT`、`ASSET_REGISTRY_UNAVAILABLE`、`SEARCH_TIMEOUT`、`BRIDGE_BUSY`、`BRIDGE_TIMEOUT`、`INTERNAL`。

**错误详情**：`SEARCH_TIMEOUT` 的 `details` 含 `timeoutMs` 与可选 `partial`；`ASSET_REGISTRY_UNAVAILABLE` 含 `loading`。完整契约见 §2.9.6。

**实现要点**：

```python
registry = unreal.AssetRegistryHelpers.get_asset_registry()
assets = registry.get_assets_by_path(unreal.Name(path), recursive)
# 过滤：asset.asset_name / asset.package_name / asset.asset_class_path
```

- 类过滤按短类名或类路径匹配；`asset.asset_class_path` 在 5.4 为 `TopLevelAssetPath`，取 `asset_class_path.asset_name`。
- `isRedirector`：`unreal.AssetRegistryHelpers.is_redirector(asset_data)`。
- 依赖：

```python
opts = unreal.AssetRegistryDependencyOptions()
opts.set_editor_property("include_hard_package_references", True)
opts.set_editor_property("include_soft_package_references", True)
deps = registry.get_dependencies(package_name, opts)
```

- 反向引用：`registry.get_referencers(package_name, opts)`。
- BFS 深度 ≤ 3；全局节点上限 1000；种子资产最多 50 个；结果去重。
- 过滤后再排序，再分页；`total` 是过滤后的总数。
- 大工程可能较慢：默认 `limit=100`，超时 20s；超时返回 `SEARCH_TIMEOUT` 并附已完成的 `partial` 结果（`details.partial`）。

---

### 5.6 `ue_material_params`

**用途**：读取材质/材质实例的参数，设置材质实例参数，创建材质实例。

**权限**：`list`/`get` 为 P0；`set`/`create_instance` 为 P1。无需确认。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["action"],
  "properties": {
    "action": { "enum": ["list", "get", "set", "create_instance"] },
    "materialPath": { "type": "string", "maxLength": 512 },
    "instancePath": { "type": "string", "maxLength": 512 },
    "parameterNames": {
      "type": "array",
      "items": { "type": "string", "maxLength": 128 },
      "maxItems": 100
    },
    "parameters": {
      "type": "array",
      "maxItems": 50,
      "items": {
        "oneOf": [
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["name", "type", "value"],
            "properties": {
              "name": { "type": "string", "maxLength": 128 },
              "type": { "const": "scalar" },
              "value": { "type": "number" }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["name", "type", "value"],
            "properties": {
              "name": { "type": "string", "maxLength": 128 },
              "type": { "const": "vector" },
              "value": {
                "type": "object",
                "additionalProperties": false,
                "required": ["r", "g", "b", "a"],
                "properties": {
                  "r": { "type": "number" },
                  "g": { "type": "number" },
                  "b": { "type": "number" },
                  "a": { "type": "number" }
                }
              }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["name", "type", "value"],
            "properties": {
              "name": { "type": "string", "maxLength": 128 },
              "type": { "const": "texture" },
              "value": { "type": "string", "maxLength": 512 }
            }
          },
          {
            "type": "object",
            "additionalProperties": false,
            "required": ["name", "type", "value"],
            "properties": {
              "name": { "type": "string", "maxLength": 128 },
              "type": { "const": "staticSwitch" },
              "value": { "type": "boolean" }
            }
          }
        ]
      }
    },
    "save": { "type": "boolean", "default": false }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "properties": {
    "materialPath": { "type": "string" },
    "instancePath": { "type": "string" },
    "created": { "type": "boolean" },
    "saved": { "type": "boolean" },
    "parameters": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "type": { "enum": ["scalar", "vector", "texture", "staticSwitch"] },
          "value": {},
          "editable": { "type": "boolean" }
        }
      }
    }
  }
}
```

**错误码**：`INVALID_ARGUMENT`、`MATERIAL_NOT_FOUND`、`NOT_A_MATERIAL`、`NOT_AN_INSTANCE`、`PARAM_NOT_FOUND`、`TYPE_MISMATCH`、`ALREADY_EXISTS`、`SAVE_FAILED`、`PERMISSION_DENIED`、`BRIDGE_BUSY`。

**错误详情**：`NOT_AN_INSTANCE`/`NOT_A_MATERIAL` 含 `actualClass`；`PARAM_NOT_FOUND` 含 `availableParameters`；`ALREADY_EXISTS` 含 `path`。完整契约见 §2.9.6。桥接 `allowWrite=false` 时返回 `PERMISSION_DENIED`（`details.gate="bridge.allowWrite"`）。

**实现要点**：

- 加载：`unreal.EditorAssetSubsystem.load_asset(path)`。
- 枚举参数：

```python
mel = unreal.MaterialEditingLibrary
scalars = mel.get_scalar_parameter_names(mat)
vectors = mel.get_vector_parameter_names(mat)
textures = mel.get_texture_parameter_names(mat)
switches = mel.get_static_switch_parameter_names(mat)
```

> Python 对单个 out 参数通常直接返回数组；若 SDK 返回 tuple，取第一个元素。PoC 时确认。

- `get`：材质实例用 `get_material_instance_scalar_parameter_value(mic, name)` 等；基础材质可能无法读取当前值，返回 `editable=false` 与参数名。
- `set`：**只允许 `MaterialInstanceConstant`**。基础材质需要重编译且影响所有使用者，MVP 拒绝并返回 `NOT_AN_INSTANCE`。
- 设置后调用 `mel.update_material_instance(mic)`；`save=true` 时 `EditorAssetSubsystem.save_asset(instance_path, False)`。
- `create_instance`：

```python
factory = unreal.MaterialInstanceConstantFactoryNew()
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
mic = asset_tools.create_asset(asset_name, package_path, unreal.MaterialInstanceConstant, factory)
mel.set_material_instance_parent(mic, parent_material)
mel.update_material_instance(mic)
```

- 创建前检查 `EditorAssetSubsystem.does_asset_exist(instance_path)` → `ALREADY_EXISTS`。
- 同名参数重复出现 → `INVALID_ARGUMENT`。
- 材质参数名不存在 → `PARAM_NOT_FOUND`，`details.availableParameters` 返回该类型可用名称（最多 50 个）。

---

### 5.7 `ue_viewport_capture`

**用途**：截取关卡视口或 PIE 画面，返回 MCP image 内容或文件路径。

**权限**：P0，无需确认；但截图可能包含屏幕内容，写入审计。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "target": { "enum": ["level_viewport", "pie"], "default": "level_viewport" },
    "width": { "type": "integer", "minimum": 64, "maximum": 7680, "default": 1280 },
    "height": { "type": "integer", "minimum": 64, "maximum": 4320, "default": 720 },
    "format": { "enum": ["png", "jpeg"], "default": "png" },
    "jpegQuality": { "type": "integer", "minimum": 1, "maximum": 100, "default": 90 },
    "camera": {
      "default": { "mode": "current" },
      "oneOf": [
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["mode"],
          "properties": { "mode": { "const": "current" } }
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["mode", "actorPath"],
          "properties": {
            "mode": { "const": "actor" },
            "actorPath": { "type": "string", "maxLength": 512 },
            "distanceMultiplier": { "type": "number", "minimum": 0.5, "maximum": 10, "default": 2.5 }
          }
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["mode", "location", "rotation"],
          "properties": {
            "mode": { "const": "explicit" },
            "location": { "$ref": "#/$defs/Vec3" },
            "rotation": { "$ref": "#/$defs/Rotator" }
          }
        }
      ]
    },
    "returnMode": { "enum": ["image", "file"], "default": "image" },
    "hideEditorUI": { "type": "boolean", "default": true },
    "timeoutMs": { "type": "integer", "minimum": 1000, "maximum": 30000, "default": 15000 }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "required": ["path", "width", "height", "format", "bytes"],
  "properties": {
    "path": { "type": "string" },
    "width": { "type": "integer" },
    "height": { "type": "integer" },
    "format": { "enum": ["png", "jpeg"] },
    "bytes": { "type": "integer" },
    "capturedAt": { "type": "string", "format": "date-time" }
  }
}
```

MCP 返回：

- `returnMode=image` 且文件 ≤ 8 MiB：额外返回 `{ "type": "image", "data": "<base64>", "mimeType": "image/png" }`。
- 超过上限：仅返回文件路径，附 warning `IMAGE_TOO_LARGE_FOR_INLINE`。
- `returnMode=file`：只返回 `data.path`。

**错误码**：`INVALID_ARGUMENT`、`CAPTURE_FAILED`、`CAPTURE_TIMEOUT`、`PIE_NOT_RUNNING`、`ACTOR_NOT_FOUND`、`CAPABILITY_UNAVAILABLE`、`PAYLOAD_TOO_LARGE`、`BRIDGE_TIMEOUT`。

**错误详情**：`PIE_NOT_RUNNING` 含 `target="pie"`；`CAPTURE_TIMEOUT` 含 `timeoutMs`；`CAPTURE_FAILED` 含 `reason`。完整契约见 §2.9.6。

**实现要点（PoC 必须验证）**：

```python
task = unreal.AutomationLibrary.take_high_res_screenshot(
    width, height, absolute_png_path
)
# 轮询 task.is_task_done()，由 tick 回调驱动，避免阻塞游戏线程
```

- 输出目录：`<Project>/Saved/UEMCP/captures/<uuid>.png`。
- `AutomationLibrary` 的文件名参数行为（是否按绝对路径写入、是否自动加扩展名/子目录）需在 5.4.4 实测；若不可控，则：
  1. 传唯一文件名；
  2. 截获前后 `Saved/Screenshots/` 最新文件；
  3. 移动到目标路径。
- `camera=explicit`：截图前 `UnrealEditorSubsystem.set_level_viewport_camera_info(location, rotation)`，截图后恢复原相机。
- `camera=actor`：根据 Actor bounds 计算 `origin + forward * radius * distanceMultiplier`，朝向 Actor 中心。
- `target=pie`：要求 `get_game_world() is not None`，否则 `PIE_NOT_RUNNING`。
- `hideEditorUI=true`：高分辨率截图默认只含游戏画面，不含编辑器 UI；若需要含 UI 的截图，MVP 不支持。
- 超时由桥接计时器控制；任务未完成 → `CAPTURE_TIMEOUT`，不删除已生成的部分文件。

---

### 5.8 `ue_console_command`

**用途**：向编辑器/PIE 世界执行控制台命令。

**权限**：P2。**默认隐藏**。需要同时满足：

1. 服务端策略 `full`；
2. 服务端 `--allow-console`；
3. 桥接 `allowConsole=true`；
4. 命令匹配白名单；
5. 确认：客户端支持 elicitation 时每次询问；否则 `--allow-console` 本身作为策略级确认（`--allow-destructive` **不适用**）。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["command"],
  "properties": {
    "command": { "type": "string", "minLength": 1, "maxLength": 2000 },
    "worldContext": { "enum": ["editor", "pie"], "default": "editor" },
    "timeoutMs": { "type": "integer", "minimum": 1000, "maximum": 30000, "default": 5000 },
    "captureOutput": { "type": "boolean", "default": false }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "required": ["command", "dispatched", "outputAvailable"],
  "properties": {
    "command": { "type": "string" },
    "dispatched": { "type": "boolean" },
    "output": { "type": ["string", "null"] },
    "outputAvailable": { "type": "boolean" },
    "durationMs": { "type": "integer" }
  }
}
```

**错误码**：`TOOL_DISABLED`、`PERMISSION_DENIED`、`COMMAND_NOT_ALLOWED`、`CONFIRMATION_REQUIRED`、`CONFIRMATION_DENIED`、`EDITOR_UNSAFE_STATE`、`BRIDGE_TIMEOUT`、`INTERNAL`。

**门位映射**：服务端开关未开 → `TOOL_DISABLED`（`details.gate="server.allowConsole"`）；桥接 `allowConsole=false` → `PERMISSION_DENIED`（`details.gate="bridge.allowConsole"`）；命令本身不允许 → `COMMAND_NOT_ALLOWED`。**不得使用 `EXEC_DISABLED`**（该码专用于 Python 执行门）。

**白名单（默认）**：

```text
stat, show, r., sg., viewmode, log, help, dumpticks, obj, memreport, camera
```

**永久拒绝（即使用户配置也不允许）**：

```text
quit, exit, restart, shutdown, reconnect, open, exec, py, python, delete, rm, crash, bugit
```

原因：`py`/`exec` 可绕过 Python 开关；`quit`/`restart` 会破坏会话；`open` 会切换关卡并弹窗。

**实现要点**：

```python
ctx = editor_world if worldContext == "editor" else game_world
unreal.SystemLibrary.execute_console_command(ctx, command)
```

- 输出捕获：MVP **不支持**。`captureOutput=true` 时返回 `outputAvailable=false` 并附 warning `OUTPUT_CAPTURE_UNSUPPORTED`。需要回显时使用 `ue_python_exec`。
- 命令执行是同步的；无法保证超时后停止。`timeoutMs` 只用于响应等待。
- 审计记录完整命令（不含敏感数据），但可在配置中关闭。

---

### 5.9 `ue_python_exec`

**用途**：在编辑器游戏线程执行 Python 代码/表达式。

**权限**：P2。**默认隐藏**。需要同时满足：

1. 服务端策略 `full`；
2. 服务端 `--allow-exec`；
3. 桥接 `allowExec=true`；
4. 确认：客户端支持 elicitation 时每次询问；否则 `--allow-exec` 本身作为策略级确认（`--allow-destructive` **不适用**），审计记录 `confirmationMode:"policy"`。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["code"],
  "properties": {
    "code": { "type": "string", "minLength": 1, "maxLength": 65536 },
    "mode": { "enum": ["exec", "eval"], "default": "exec" },
    "resultExpression": { "type": "string", "maxLength": 4096, "description": "exec 执行后可选求值，结果作为 result 返回" },
    "timeoutMs": { "type": "integer", "minimum": 1000, "maximum": 120000, "default": 10000 },
    "captureOutput": { "type": "boolean", "default": true }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "required": ["mode", "result", "stdout", "stderr", "timedOut"],
  "properties": {
    "mode": { "enum": ["exec", "eval"] },
    "result": {},
    "stdout": { "type": "string" },
    "stderr": { "type": "string" },
    "durationMs": { "type": "integer" },
    "timedOut": { "type": "boolean" }
  }
}
```

**错误码**：`TOOL_DISABLED`、`EXEC_DISABLED`、`PERMISSION_DENIED`、`CONFIRMATION_REQUIRED`、`PYTHON_ERROR`、`BRIDGE_TIMEOUT`、`RESULT_NOT_SERIALIZABLE`、`PAYLOAD_TOO_LARGE`、`INTERNAL`。

**门位映射**：服务端 `--allow-exec` 未开 → `TOOL_DISABLED`（`details.gate="server.allowExec"`）；桥接 `allowExec=false` → `EXEC_DISABLED`（`details.gate="bridge.allowExec"`）。`TIMEOUT` 字符串已退役，执行超时统一返回 `BRIDGE_TIMEOUT`（`details.phase="game_thread"`）。

**实现要点**：

```python
import contextlib, io, traceback

stdout, stderr = io.StringIO(), io.StringIO()
scope = {"__name__": "__uemcp__", "unreal": unreal}
try:
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exec(compile(code, "<uemcp>", "exec"), scope)
    if result_expression:
        value = eval(compile(result_expression, "<uemcp-result>", "eval"), scope)
except Exception:
    raise PythonExecError(traceback.format_exc())
```

- **超时不可强制中断**：代码在游戏线程内执行。`timeoutMs` 只限制 HTTP 等待；超时后返回 `BRIDGE_TIMEOUT`，并附 `details.stillRunning=true`。文档与工具描述中必须写明“不要写死循环/长时间阻塞代码”。
- 返回值 JSON 化规则：
  - `None`、`bool`、`int`、`float`、`str` → 原样；
  - `list`/`tuple`/`dict` → 递归；
  - `unreal.Vector` / `Rotator` / `LinearColor` → `{x,y,z}` / `{pitch,yaw,roll}` / `{r,g,b,a}`；
  - `unreal.Name` / `Text` → 字符串；
  - `unreal.Object` → `unreal.SystemLibrary.get_path_name(obj)`；
  - 其他 → 若有 `to_dict` 调用；否则 `repr()` 截断 2000 字符并附 warning；
  - 无法序列化的循环引用 → `RESULT_NOT_SERIALIZABLE`。
- 审计：记录 `codeSha256`、`codeLength`、`mode`、`durationMs`；默认**不记录源码**，可用 `--audit-python-source` 开启（不推荐）。
- 桥接端额外要求：`allowExec` 默认 false；生产/演示环境不要开启。
- 该工具的执行结果是不可信输入，MCP Server 需按普通数据返回，不得执行其中内容。

---

### 5.10 `ue_blueprint`

**用途**：查询蓝图结构（父类、变量、组件、图、接口、编译状态）；触发编译。节点级读取为 experimental。

**权限**：`query` P0；`compile` P1。无需确认。

**入参 Schema**：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["action"],
  "properties": {
    "action": { "enum": ["query", "compile"] },
    "blueprintPath": { "type": "string", "maxLength": 512 },
    "include": {
      "type": "array",
      "items": { "enum": ["parent", "variables", "components", "graphs", "interfaces", "compileState"] },
      "default": ["parent", "variables", "graphs", "compileState"]
    },
    "graphName": { "type": "string", "maxLength": 256 },
    "includeNodes": { "type": "boolean", "default": false },
    "nodeLimit": { "type": "integer", "minimum": 1, "maximum": 2000, "default": 500 },
    "save": { "type": "boolean", "default": false }
  }
}
```

**出参 `data` Schema**：

```json
{
  "type": "object",
  "required": ["blueprintPath"],
  "properties": {
    "blueprintPath": { "type": "string" },
    "parentClass": { "type": "string" },
    "variables": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "type": { "type": "string" },
          "defaultValue": { "type": "string" },
          "instanceEditable": { "type": "boolean" },
          "exposeOnSpawn": { "type": "boolean" },
          "replicated": { "type": "boolean" }
        }
      }
    },
    "components": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "class": { "type": "string" },
          "parent": { "type": ["string", "null"] }
        }
      }
    },
    "graphs": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "kind": { "enum": ["event", "function", "macro", "other"] },
          "nodeCount": { "type": "integer" }
        }
      }
    },
    "interfaces": { "type": "array", "items": { "type": "string" } },
    "compileState": {
      "type": "object",
      "properties": {
        "status": { "enum": ["unknown", "up_to_date", "dirty", "error"] },
        "errors": { "type": "integer" },
        "warnings": { "type": "integer" }
      }
    },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "guid": { "type": "string" },
          "class": { "type": "string" },
          "title": { "type": "string" },
          "x": { "type": "integer" },
          "y": { "type": "integer" },
          "pins": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": { "type": "string" },
                "direction": { "enum": ["input", "output"] },
                "type": { "type": "string" },
                "linkedTo": { "type": "array", "items": { "type": "string" } }
              }
            }
          }
        }
      }
    }
  }
}
```

**错误码**：`INVALID_ARGUMENT`、`BLUEPRINT_NOT_FOUND`、`NOT_A_BLUEPRINT`、`GRAPH_NOT_FOUND`、`CAPABILITY_UNAVAILABLE`、`COMPILE_FAILED`、`PERMISSION_DENIED`、`BRIDGE_BUSY`、`BRIDGE_TIMEOUT`。

**错误详情**：`COMPILE_FAILED` 含 `errors`/`warnings`；`GRAPH_NOT_FOUND` 含 `blueprintPath`/`graphName`；`NOT_A_BLUEPRINT` 含 `actualClass`。完整契约见 §2.9.6。桥接 `allowWrite=false` 时 P1 的 `compile` 返回 `PERMISSION_DENIED`。

**实现要点**：

```python
bp = unreal.EditorAssetSubsystem.load_asset(path)
if not isinstance(bp, unreal.Blueprint):
    raise NotABlueprint()
parent = bp.get_editor_property("parent_class")
variables = bp.get_editor_property("new_variables")
ubergraphs = bp.get_editor_property("ubergraph_pages")
functions = bp.get_editor_property("function_graphs")
macros = bp.get_editor_property("macro_graphs")
```

- 变量类型：`FBPVariableDescription.var_type` 是 `EdGraphPinType`，通过 `pin_category` / `pin_sub_category` / `pin_sub_object` 拼成可读字符串（如 `float`、`object:StaticMesh`、`struct:Vector`）。
- 组件：`bp.get_editor_property("component_templates")`；SCS 继承层级需遍历 `simple_construction_script`，MVP 只返回模板列表并附 warning。
- 图：`ubergraph_pages`（event）、`function_graphs`、`macro_graphs`；若指定 `graphName` 且找不到 → `GRAPH_NOT_FOUND`。
- 节点：`graph.get_editor_property("nodes")`。该访问依赖反射，**不是稳定 API**：
  - 失败时返回 `nodes: []` + warning `NODE_INSPECTION_UNSTABLE`；
  - 成功时仅返回只读快照；
  - 能力探测 `blueprintNodeRead` 初始为 `false`，首次成功后置 `true`。
- 编译：`unreal.BlueprintEditorLibrary.compile_blueprint(bp)`；编译结果通过 `bp.get_editor_property("status")` 读取（`BS_UpToDate` / `BS_Dirty` / `BS_Error` 等枚举）。若无法读取，`status="unknown"`，附 warning。
- **不支持**：节点创建、连线、删除、变量增删、动画蓝图状态机编辑 → `CAPABILITY_UNAVAILABLE`，`details.suggestion="需要 C++ 辅助模块（P2）"`。
- `save=true`：`EditorAssetSubsystem.save_asset(path, False)`。

---

### 5.11 工具与策略矩阵

| 工具 | 级别 | read-only | standard | full | 默认隐藏 | 确认 |
|---|---|---|---|---|---|---|
| `ue_editor_status` | P0 | ✓ | ✓ | ✓ | 否 | 否 |
| `ue_actor_query` | P0 | ✓ | ✓ | ✓ | 否 | 否 |
| `ue_actor_edit` | P1 | ✗ | ✓ | ✓ | 否 | delete 需确认 |
| `ue_level_control` | P0/P1 | 收窄：`get_current`/`list_dirty` | ✓ | ✓ | 否 | 覆盖/批量保存需确认 |
| `ue_asset_search` | P0 | ✓ | ✓ | ✓ | 否 | 否 |
| `ue_material_params` | P0/P1 | 收窄：`list`/`get` | ✓ | ✓ | 否 | 否 |
| `ue_viewport_capture` | P0 | ✓ | ✓ | ✓ | 否 | 否 |
| `ue_console_command` | P2 | ✗ | ✗ | ✓（需 `--allow-console`） | 是 | 是 |
| `ue_python_exec` | P2 | ✗ | ✗ | ✓（需 `--allow-exec`） | 是 | 是 |
| `ue_blueprint` | P0/P1 | 收窄：`query` | ✓ | ✓ | 否 | 否 |

> P2 的“默认隐藏=是”指未开对应开关时不注册；只有 `full + --allow-console` / `full + --allow-exec` 后才会出现在 `tools/list`。

各启动组合的工具数：

| 启动组合 | 工具数 | 集合 |
|---|---|---|
| `read-only` | **7** | 4 个纯 P0 + 3 个混合工具的只读动作 |
| `standard` | 8 | 上列 + `ue_actor_edit` |
| `full`（未开 P2 开关） | 8 | 同 standard |
| `full + --allow-console` | 9 | + `ue_console_command` |
| `full + --allow-exec` | 9 | + `ue_python_exec` |
| `full + 两者` | 10 | 全部 |

read-only 的 Schema 收窄规则（注册时生成，不在调用时临时过滤）：

| 工具 | 允许的 `action` enum |
|---|---|
| `ue_level_control` | `["get_current", "list_dirty"]` |
| `ue_material_params` | `["list", "get"]` |
| `ue_blueprint` | `["query"]` |

调用语义：

- 客户端按收窄 Schema 调用写 action → zod 拒绝 → 工具层 `INVALID_ARGUMENT`（`details.issues`）。
- 若绕过 Schema 直达 handler，二次校验返回 `PERMISSION_DENIED`（`details.gate="server.policy"`），且不得产生副作用。
- 混合工具的注解随模式变化：read-only 下 `readOnlyHint=true`，standard/full 下 `false`。
- “默认隐藏”或未注册的工具不会出现在 `tools/list` 中；直接调用返回 `TOOL_DISABLED`，错误信息不透露工具细节。

---

## 6. 安全模型

### 6.1 威胁模型

| 威胁 | 场景 | 对策 |
|---|---|---|
| 其他本机进程调用 | 任意程序访问 18777/18778 | 回环绑定 + 桥接 token + 可选 MCP token + Host/Origin 校验 |
| 恶意网页发起请求（DNS rebinding/CSRF） | 浏览器访问本地端口 | Host/Origin 白名单；不返回 CORS 通配；Content-Type 强制 JSON |
| 提示注入诱导模型执行危险操作 | 模型读到恶意资产名/日志后调用 exec | 默认隐藏 exec/console；工具描述明确风险；策略门在服务端而非模型 |
| Token 泄漏 | 发现文件被读取 | 文件权限 0600；每次编辑器启动轮换；token 只在本机文件与内存 |
| 误操作删除/覆盖 | 模型误调 delete/save_all | dryRun、破坏性确认、审计、PIE/未保存预检 |
| 拒绝服务 | 大量请求/超长请求 | 请求体 8 MiB、队列 64、速率限制 20 rps、单任务超时 |
| 日志泄漏源码 | Python 源码含密钥 | 默认只记录 hash 与长度 |

**明确不解决的威胁**：本机恶意程序读取进程内存或 `bridge.json` 后取得 token；用户主动开启 exec 后模型执行任意代码。这是本地开发工具的固有边界，必须在 README 中写明。

### 6.2 网络面

- 强制 `127.0.0.1` 绑定，**没有**“允许局域网”的开关（如未来需要，必须显式 `--bind 0.0.0.0` 并打印高危警告）。
- TCP peer 地址必须是 `127.0.0.1` 或 `::1`；否则直接断开。
- HTTP `Host` 必须是 `127.0.0.1:<port>` 或 `localhost:<port>`。
- `Origin` 若存在，只允许同源回环或 `null`。
- 不启用 CORS；不处理预检请求（`OPTIONS` 返回 405）。
- 桥接 token 通过 `X-UEMCP-Token` 传递；不放在 URL query，避免日志泄漏。
- MCP 入口可选 `Authorization: Bearer <token>`；未配置时仅依赖回环 + Host 校验。

### 6.3 权限门

服务端策略：

```text
read-only : 注册 4 个纯 P0 + 3 个混合工具的只读动作（Schema 收窄）= 7；看不到 ue_actor_edit/P2
standard  : 上列 + ue_actor_edit = 8；P2 不可见
full      : 同 standard = 8；P2 需各自开关（仅 console 9 / 仅 exec 9 / 两者 10）
```

独立开关：

| 开关 | 位置 | 默认 | 作用 |
|---|---|---|---|
| `--allow-destructive` | MCP Server | off | **仅 P1**：无 elicitation 时允许 delete/覆盖/批量保存 |
| `--allow-console` | MCP Server | off | 使 `ue_console_command` 可见；无 elicitation 时作为该工具的策略级确认 |
| `--allow-exec` | MCP Server | off | 使 `ue_python_exec` 可见；无 elicitation 时作为该工具的策略级确认 |
| `allowWrite` | 桥接配置 | false | 桥接侧硬开关，拒绝 P1 |
| `allowConsole` | 桥接配置 | false | 桥接侧硬开关，拒绝控制台 |
| `allowExec` | 桥接配置 | false | 桥接侧硬开关，拒绝 Python |

**双重执行**：MCP Server 与桥接端都校验；任何一端关闭即拒绝。这样即使 token 泄漏，未开启 exec 的编辑器仍不能被任意代码执行。

**门位与错误码（D6）**：

| 拒绝位置 | 条件 | code | `details.gate` |
|---|---|---|---|
| MCP Server 未注册 | read-only/standard；或 P2 开关未开 | `TOOL_DISABLED` | `server.policy` / `server.allowConsole` / `server.allowExec` |
| 桥接写权限门 | Server 已放行，桥接 `allowWrite=false` | `PERMISSION_DENIED` | `bridge.allowWrite` |
| 桥接控制台门 | Server 已放行，桥接 `allowConsole=false` | `PERMISSION_DENIED` | `bridge.allowConsole` |
| 桥接执行门 | Server 已放行，桥接 `allowExec=false` | `EXEC_DISABLED` | `bridge.allowExec` |
| 命令白名单/拒绝表 | 命令本身不允许 | `COMMAND_NOT_ALLOWED` | — |

桥接拒绝必须发生在游戏线程入队之前，不得产生任何编辑器副作用。`EXEC_DISABLED` 专用于 Python 执行门，不用于 console。

确认流程：

1. 客户端在 `initialize` 中声明 `capabilities.elicitation`。
2. 危险调用到达时，服务端发送 `elicitation/create`：

```json
{
  "method": "elicitation/create",
  "params": {
    "message": "UEMCP 请求执行危险操作：删除 3 个 Actor。是否允许？",
    "requestedSchema": {
      "type": "object",
      "properties": {
        "approve": { "type": "boolean", "title": "允许" }
      },
      "required": ["approve"]
    }
  }
}
```

3. 用户拒绝 → `CONFIRMATION_DENIED`；客户端不支持 elicitation 且未开 `--allow-destructive` → `CONFIRMATION_REQUIRED`。
4. `--allow-destructive` 只跳过 P1 破坏性交互，审计记 `confirmationMode:"policy"`。
5. P2（console/exec）：客户端支持 elicitation 时每次询问；否则对应 `--allow-console`/`--allow-exec` 作为策略级确认，审计记 `confirmationMode:"policy"`。**`--allow-destructive` 不参与 P2。**

### 6.4 任意代码执行类工具的默认隐藏策略

| 工具 | 默认 | 开启条件 | 额外保护 |
|---|---|---|---|
| `ue_python_exec` | 不注册 | 服务端 `full + --allow-exec` **且** 桥接 `allowExec=true` | elicitation 优先，否则 `--allow-exec` 策略确认；源码 hash 审计、超时告警、结果 JSON 化 |
| `ue_console_command` | 不注册 | 服务端 `full + --allow-console` **且** 桥接 `allowConsole=true` | elicitation 优先，否则 `--allow-console` 策略确认；白名单 + 永久拒绝表 |

- `tools/list` 不返回隐藏工具；日志中也不要打印隐藏工具的存在。
- 桥接能力门拒绝：`allowExec=false` → `EXEC_DISABLED`；`allowConsole=false` → `PERMISSION_DENIED`（`details.gate` 标明来源）。`--allow-destructive` 对 P2 不生效。
- 文档中必须明确：“开启 exec 等于把编辑器进程的控制权交给调用方”。
- 不建议在录屏、演示、CI 中开启 exec。

### 6.5 审计日志

路径：`~/.uemcp/audit/YYYY-MM-DD.jsonl`，每天一个文件，JSON Lines。

字段：

```json
{
  "ts": "2026-10-20T10:12:33.123Z",
  "requestId": "req_01H...",
  "sessionId": "mcp-session-uuid",
  "client": { "name": "claude-code", "version": "2.x" },
  "transport": "streamable-http",
  "tool": "ue_actor_edit",
  "rpcMethod": "actor.edit",
  "policyMode": "standard",
  "decision": "allowed",
  "confirmationMode": "elicitation",
  "argsSummary": {
    "operationCount": 3,
    "ops": ["spawn", "set_transform", "delete"],
    "dryRun": false
  },
  "durationMs": 42,
  "ok": true,
  "errorCode": null,
  "ueVersion": "5.4.4",
  "pluginVersion": "0.1.0"
}
```

规则：

- 永远不记录：token、完整 Python 源码、纹理/截图 base64、绝对用户路径中的用户名（可选脱敏）。
- Python 执行记录：`codeSha256`、`codeLength`、`mode`。
- 控制台记录：完整命令（可配置为 hash）。
- 审计写入失败不应阻塞工具调用，但必须在 stderr 打警告；连续失败 3 次则在 `/health` 中标记 `auditDegraded=true`。
- 日志轮转：按天；保留 30 天；启动时清理过期文件（可配置）。

### 6.6 Token

- 桥接 token：32 字节随机数，base64url；每次编辑器启动重新生成。
- 存储：`bridge.json`（0600）与进程内存；不写入项目目录。
- MCP 入口 token：可选，用户通过 `UEMCP_AUTH_TOKEN` 或 `--auth-token` 配置；不自动生成（避免客户端配置复杂）。
- 比较：常量时间比较（Node `crypto.timingSafeEqual`）。
- 失败：`401` + `{"error":"unauthorized"}`；不返回 token 是否存在的细节。
- 轮换：编辑器重启即轮换；MCP Server 每次调用前可重新读取发现文件（或监听文件变化），避免旧 token 卡死。

### 6.7 其他限制

- 速率限制：每会话 20 req/s，突发 40；桥接端全局 30 req/s。
- 并发：单编辑器同时执行 1 个任务；其余排队。
- 请求体 / 响应体上限：8 MiB / 16 MiB。
- 图像内联上限：8 MiB 原始字节。
- 字符串截断：日志字段 2 KiB；错误 `message` 1 KiB；`details` 16 KiB。
- 不接受绝对文件路径作为 Python 执行的工作目录；MVP 不提供 `cwd` 参数。
- 不执行任何来自工具参数的 shell 命令。

---

## 7. 目录结构、许可证与商标

### 7.1 Monorepo 目录

```text
uemcp/
├─ package.json                     # pnpm workspace 根
├─ pnpm-workspace.yaml
├─ tsconfig.base.json
├─ LICENSE                          # MIT
├─ README.md
├─ TRADEMARK.md                     # 商标免责声明
├─ CONTRIBUTING.md
├─ SECURITY.md
├─ .gitignore
├─ .editorconfig
├─ .github/
│  └─ workflows/
│     ├─ ci.yml                     # lint + test + build
│     └─ release.yml                # npm + 插件 zip
├─ packages/
│  ├─ shared/
│  │  ├─ package.json
│  │  └─ src/
│  │     ├─ index.ts
│  │     ├─ toolNames.ts            # 工具名常量
│  │     ├─ schemas/
│  │     │  ├─ common.ts            # Vec3/Rotator/Selector/ActorRef/AssetRef
│  │     │  ├─ status.ts
│  │     │  ├─ actors.ts
│  │     │  ├─ levels.ts
│  │     │  ├─ assets.ts
│  │     │  ├─ materials.ts
│  │     │  ├─ viewport.ts
│  │     │  ├─ console.ts
│  │     │  ├─ python.ts
│  │     │  └─ blueprints.ts
│  │     ├─ errors.ts               # 错误码枚举 + 映射
│  │     └─ types.ts
│  └─ server/
│     ├─ package.json               # bin: uemcp
│     ├─ tsup.config.ts
│     └─ src/
│        ├─ index.ts                # CLI 入口
│        ├─ config.ts               # 参数/环境变量
│        ├─ mcp/
│        │  ├─ buildServer.ts       # 注册工具
│        │  ├─ registerTools.ts
│        │  └─ annotations.ts
│        ├─ transports/
│        │  ├─ http.ts              # /mcp + /health
│        │  ├─ sse.ts               # /sse + /messages
│        │  └─ stdio.ts
│        ├─ bridge/
│        │  ├─ discovery.ts
│        │  ├─ client.ts            # JSON-RPC + 重试
│        │  └─ watchdog.ts          # /health 探活
│        ├─ policy.ts
│        ├─ audit.ts
│        ├─ confirm.ts              # elicitation 封装
│        └─ tools/
│           ├─ status.ts
│           ├─ actorQuery.ts
│           ├─ actorEdit.ts
│           ├─ levelControl.ts
│           ├─ assetSearch.ts
│           ├─ materialParams.ts
│           ├─ viewportCapture.ts
│           ├─ consoleCommand.ts
│           ├─ pythonExec.ts
│           └─ blueprint.ts
├─ plugin/
│  └─ UEMCPBridge/
│     ├─ UEMCPBridge.uplugin
│     ├─ Resources/
│     │  └─ Icon128.png
│     ├─ Config/
│     │  └─ DefaultUEMCPBridge.ini  # 可选，Python 也可读 JSON
│     └─ Content/
│        └─ Python/
│           ├─ init_unreal.py
│           └─ uemcp_bridge/
│              ├─ __init__.py
│              ├─ server.py         # ThreadingHTTPServer
│              ├─ rpc.py            # 路由 + JSON-RPC 封装
│              ├─ dispatcher.py     # 游戏线程队列
│              ├─ discovery.py      # bridge.json 原子写
│              ├─ settings.py
│              ├─ security.py       # token/回环/Origin
│              ├─ errors.py
│              ├─ serialization.py  # UE 类型 → JSON
│              └─ handlers/
│                 ├─ __init__.py
│                 ├─ status.py
│                 ├─ actors.py
│                 ├─ levels.py
│                 ├─ assets.py
│                 ├─ materials.py
│                 ├─ viewport.py
│                 ├─ console.py
│                 ├─ python_exec.py
│                 └─ blueprints.py
├─ examples/
│  ├─ claude-code/
│  │  └─ .mcp.json
│  ├─ cursor/
│  │  └─ .cursor/mcp.json
│  ├─ generic/
│  │  ├─ curl.md
│  │  └─ python_client.py
│  ├─ policies/
│  │  ├─ read-only.json
│  │  ├─ standard.json
│  │  └─ full.json
│  └─ scripts/
│     ├─ smoke_test.mjs
│     └─ edit_actor_demo.py
├─ docs/
│  ├─ UEMCP-架构设计.md            # 本文
│  ├─ install.md
│  ├─ protocol.md
│  ├─ tools.md                     # 由 shared/schemas 生成
│  ├─ security.md
│  ├─ troubleshooting.md
│  └─ changelog.md
└─ scripts/
   ├─ install-plugin.mjs           # 复制/链接插件到项目
   ├─ gen-tool-docs.ts
   └─ package-plugin.mjs           # 生成 plugin zip
```

### 7.2 关键实现文件职责

| 文件 | 职责 |
|---|---|
| `packages/shared/src/schemas/*.ts` | 唯一 Schema 来源；同时导出 zod 与 JSON Schema |
| `packages/server/src/mcp/buildServer.ts` | 根据策略注册可见工具，设置 `listChanged` |
| `packages/server/src/transports/http.ts` | `/mcp`、`/health`、会话、Host/Origin、鉴权 |
| `packages/server/src/bridge/client.ts` | 发现、token、JSON-RPC、超时、重试 |
| `packages/server/src/policy.ts` | 策略矩阵、工具过滤、确认策略 |
| `packages/server/src/audit.ts` | JSONL 写入、脱敏、轮转 |
| `plugin/.../dispatcher.py` | 唯一游戏线程入口 |
| `plugin/.../rpc.py` | RPC 方法到 handler 的映射 |
| `plugin/.../serialization.py` | UE 类型到 JSON 的统一转换 |
| `plugin/.../init_unreal.py` | 编辑器启动/关闭生命周期 |

### 7.3 技术栈与依赖

MCP Server：

- Node.js ≥ 20（`npx` 分发；CI 使用 20 与 22）。
- TypeScript 5.x，严格模式。
- `@modelcontextprotocol/sdk`（Streamable HTTP / SSE / stdio）。
- `zod`（Schema 与校验）。
- `express` 或 Node `http`（推荐 Express，中间件简单）。
- `pino` 或轻量 JSON logger（日志写 stderr）。
- 测试：`vitest`；HTTP 集成测试用 `undici`。

UE 侧：

- 仅 Python 标准库 + `unreal` 模块；**不要求 pip 安装任何包**。
- `http.server.ThreadingHTTPServer`、`json`、`threading`、`queue`、`hashlib`、`secrets`、`base64`。
- 不使用 `requests`、`flask`、`fastapi`，避免引擎 Python 环境依赖问题。

构建与发布：

- `pnpm` workspace；`tsup` 打包为 ESM + CJS（按需）。
- `npm publish` 发布 `@uemcp/server` 与 `@uemcp/shared`。
- 插件 zip 由 `scripts/package-plugin.mjs` 生成，版本与服务端同步。
- 可选 P2：Node SEA / `pkg` 生成单文件二进制，解决“用户没有 Node”的问题。

### 7.4 许可证

MIT。`LICENSE` 内容：

```text
MIT License

Copyright (c) 2026 UEMCP contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

注意：MIT 只覆盖本项目代码；不覆盖 UE 引擎、用户资产、样例工程内容。插件不得附带任何 Epic 版权资产。

### 7.5 商标与免责声明

`TRADEMARK.md` 与 README 顶部使用同一段文本：

```text
Unreal and Unreal Engine are trademarks or registered trademarks of Epic Games, Inc.
in the United States and elsewhere. This project is an independent, community-developed
tool and is not affiliated with, endorsed by, or sponsored by Epic Games, Inc.
"Unreal" is used solely to describe compatibility with Unreal Engine.
All other trademarks are the property of their respective owners.
```

补充规则：

- 项目名使用 **UEMCP**，不使用 “UnrealMCP”“EpicMCP” 等可能造成官方关联误解的名称。
- 不复制 Epic 的 Logo、图标风格或 Marketplace 素材。
- `UEMCPBridge.uplugin` 的 `CreatedBy` 写项目维护者，不写 Epic。
- README 中说明：使用本项目需要自行拥有合法的 UE 引擎授权。
- 本段不构成法律意见；正式发布前建议做一次开源合规审查。

### 7.6 README 结构建议

1. 一句话介绍 + 截图/GIF。
2. 功能列表（按工具分类）。
3. 30 秒快速开始：安装插件 → 启动编辑器 → 配置客户端 → 第一次调用。
4. 三种客户端配置（Claude Code / Cursor / 通用）。
5. 安全模型与默认值（大字提示 exec 风险）。
6. 工具清单（链接 `docs/tools.md`）。
7. 兼容性矩阵（UE 5.4.x，Windows 优先）。
8. 故障排查（端口占用、Python 插件未启用、发现文件陈旧）。
9. 贡献指南、许可证、商标声明。

---

## 8. 风险与未决假设

### 8.1 UE 5.4 Python API 能力缺口（重点）

| 能力 | 5.4 Python 现状 | MVP 处理 | 后续 |
|---|---|---|---|
| Actor 增删改查 | 完整 | 直接支持 | — |
| 关卡打开/保存/新建 | 完整（LevelEditorSubsystem） | 直接支持 | 另存为需补 |
| 资产搜索/依赖/引用 | 完整（AssetRegistry + EditorAssetSubsystem） | 直接支持 | 资产导入/移动 |
| 材质实例参数 | 完整 | 直接支持 | 材质节点图编辑需 C++ |
| 视口截图 | 可用（AutomationLibrary），输出路径需验证 | 支持 + PoC 验证 | UI 截图、序列截图 |
| 控制台命令 | 可执行，**无输出回显** | 支持执行，明确 `outputAvailable=false` | C++ OutputDevice |
| 蓝图变量/组件/图/编译 | 可读；编译可用 | 只读查询 + 编译 | — |
| 蓝图节点读取 | `graph.get_editor_property('nodes')` 依赖反射，非稳定 API | experimental，失败降级 | C++ 稳定接口 |
| **蓝图节点创建/连线/删除** | **无公开 Python API** | **不支持**，返回 `CAPABILITY_UNAVAILABLE` | C++ `UEdGraphSchema_K2` |
| **动画蓝图状态机/节点编辑** | **无公开 Python API** | **不支持** | C++ |
| Sequencer | 需 SequencerScripting 插件，API 独立 | 不支持 | P2 可选插件 |
| 编辑器 UI/Slate 操作 | 不可用 | 不支持 | 不计划 |
| 撤销/重做 | `ScopedEditorTransaction` 可用；保存类操作不可回滚 | 写操作包事务，明确边界 | 更细粒度事务 |
| 多编辑器实例 | 发现文件需按工程区分 | 数据结构预留，MVP 单实例 | P2 支持 |
| 打包运行时 | Python 仅编辑器 | 明确仅编辑器 | 不计划 |

### 8.2 跨版本兼容策略

MVP 只承诺 **UE 5.4.x**（主验证 5.4.4）。策略：

1. **插件版本标记**：`UEMCPBridge.uplugin` 的 `EngineVersion` 写 `5.4.0`。
2. **能力探测而非版本分支**：启动时 `hasattr` / `getattr` 探测关键 API，写入 `capabilities`；缺失则隐藏对应工具。
3. **兼容层**：`plugin/.../compat.py` 集中处理已知差异：
   - `TopLevelAssetPath` vs 旧 `class_names`；
   - `EditorLevelLibrary`（EditorScriptingUtilities）vs `LevelEditorSubsystem`；
   - `get_editor_property` 字段名差异；
   - `AssetRegistryDependencyOptions` 字段名差异。
4. **5.5+**：单独发布分支/版本，不承诺同一 zip 跨版本；CI 增加 5.5 工程冒烟。
5. **客户端协议**：MCP 支持 2024-11-05 → 2025-06-18，协商降级。
6. **语义化版本**：服务端与插件同版本号；破坏性变更升 minor（0.x 阶段）并在 CHANGELOG 标注。
7. **禁止**在代码中硬编码引擎版本行为；所有分支必须有对应能力探测。

### 8.3 风险表

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 5.4 Python 缺少蓝图节点编辑，用户预期落差 | 高 | 中 | 文档与工具描述明确；P2 给 C++ 路线 |
| R2 | `AutomationLibrary` 截图路径/PIE 行为与预期不符 | 中 | 中 | PoC 首日验证；准备 `HighResShot` 回退 |
| R3 | Python 插件未启用/编辑器未重启，桥接不启动 | 中 | 高 | 安装文档；`/health` 与 `ue_editor_status` 明确报错；启动日志写 `Saved/Logs` |
| R4 | 端口冲突 | 中 | 低 | MCP Server bind 失败 2 秒内 exit 2（不换端口）；桥接按 18778–18788 再临时端口回退并更新发现文件；两端均输出明确错误 |
| R5 | 任意 Python 执行导致编辑器卡死 | 中 | 高 | 默认隐藏；超时告警；文档禁止死循环；独立队列 |
| R6 | 大工程资产搜索超时 | 中 | 中 | 分页、limit、超时、partial 结果 |
| R7 | MCP 客户端对 Streamable HTTP 支持不一 | 高 | 中 | 同端口提供 SSE；文档给出三种配置 |
| R8 | 客户端不支持 elicitation，危险确认失效 | 高 | 中 | P1 用 `--allow-destructive`；P2 用 `--allow-console`/`--allow-exec` 兼作策略确认；默认拒绝 |
| R9 | 发现文件陈旧（强杀编辑器） | 中 | 中 | PID 存活 + `/health` 双重校验 |
| R10 | 跨版本 API 变化 | 高 | 中 | 能力探测 + 兼容层 + 分版本发布 |
| R11 | 商标/命名争议 | 低 | 中 | UEMCP 中性命名 + 明确免责声明 |
| R12 | npm 供应链风险 | 中 | 高 | lockfile、依赖最小化、CI 审计、发布 provenance |
| R13 | 审计日志含敏感信息 | 中 | 中 | 默认只记录 hash 与摘要；脱敏规则 |
| R14 | 多编辑器实例互相覆盖发现文件 | 低 | 中 | 按工程 hash 分文件；默认取最近 |
| R15 | 用户没有 Node 环境 | 中 | 中 | `npx` 文档；P2 单文件二进制 |

### 8.4 未决假设（PoC 必须验证）

| # | 假设 | 验证方式 | 失败时的方案 |
|---|---|---|---|
| A1 | 启用 `PythonScriptPlugin` 后，插件的 `Content/Python/init_unreal.py` 会自动执行 | 启动编辑器，看日志与 `/health` | 改用项目 `Config/DefaultEngine.ini` 的 Python 启动脚本，或提示用户手动执行 |
| A2 | `AutomationLibrary.take_high_res_screenshot` 在 5.4.4 编辑器可用，且能指定输出位置 | 截图脚本 + 检查 `Saved/Screenshots` | 改用控制台 `HighResShot` + 文件监听 |
| A3 | `graph.get_editor_property('nodes')` 可访问节点数组 | 读取一个 BP 的 EventGraph | 关闭节点读取能力，标记 `blueprintNodeRead=false` |
| A4 | `AssetRegistry.get_dependencies` 的 Python 参数为 `(package_name, options)` | 调用并打印 | 使用 `K2_GetDependencies` 包装名或降级为资产搜索 |
| A5 | Claude Code 当前版本支持 `--transport http` 与自定义 header | 实机连接 | 使用 stdio 模式 |
| A6 | Cursor **0.45.11**（或 0.45.x 最早可得版本）可通过 `/sse` 接入；自研 `examples/generic/sse_client.py` 通过 | 实机连接 + 脚本（退出码 0） | 脚本失败即 FAIL；Cursor 不可安装或本身不支持 SSE 记 N/A；0.46+ 的 Streamable HTTP 行为另测 |
| A7 | UE 5.4 嵌入式 Python 包含 `http.server`、`ssl`、`hashlib`、`secrets` | `python -c` 导入测试 | 只使用确认存在的标准库模块 |
| A8 | `ScopedEditorTransaction.cancel()` 能回滚本次操作 | 故意让第二个 op 失败，检查第一个 op | `atomic` 降级为“尽力回滚”，返回 `rolledBack=false` |
| A9 | 用户接受“仅编辑器、无运行时” | README 明确 | 无（这是产品定位） |
| A10 | 桥接监听 `127.0.0.1` 不需要管理员权限 | 启动测试 | 换端口/提示 |
| A11 | 编辑器中同时只有一个 UEMCP 实例 | 默认单实例 | 按工程 hash 区分，P2 多实例 |

### 8.5 PoC 验证清单（按顺序执行）

1. 启用插件，启动编辑器，确认 `~/.uemcp/bridges/<hash>.json` 生成。
2. `curl http://127.0.0.1:18778/health` 返回 `app=uemcp-bridge`。
3. 用错误 token 调 `/rpc` → 401；用正确 token → `bridge.ping` 成功。
4. 非回环地址访问 → 连接被拒绝（确认绑定为 `127.0.0.1`）。
5. `editor.status` 返回 5.4.4、当前关卡、选中 Actor。
6. `actor.query` 返回至少 1 个 Actor；分页与过滤正确。
7. `actor.edit` 在 `dryRun=true` 下不改变场景；真实 spawn 后可在关卡中看到；delete 在未开启 destructive 时被拒绝。
8. `level.control get_current` 与 `list_dirty` 正确；save 后脏包数量下降。
9. `asset.search` 在 `/Game` 下返回资产；依赖查询非空。
10. `material.params` 对任一 MIC 读取参数；设置并读回一致。
11. `viewport.capture` 生成 PNG，尺寸正确；PIE 截图在 PIE 运行时成功。
12. `blueprint` 查询一个 BP 的变量与图；编译成功。
13. `python.exec` 在默认配置下不可见；开启双开关后可执行并返回结果。
14. stdio 模式下 Claude Code 能列出与调用工具。
15. HTTP 模式下 Cursor 能连接；SSE 端点由 `examples/generic/sse_client.py`（退出码 0）与 Cursor 0.45.x 基线验证（见 §3.4）。
16. 强制结束编辑器进程，重启 MCP Server，确认陈旧发现文件被忽略。

---

## 9. 分阶段实施建议

### 9.1 阶段 0：PoC（只验证高风险假设）

**范围**：

- 插件骨架 + `init_unreal.py` + 桥接 HTTP + token + 发现文件。
- `bridge.ping`、`editor.status`、`python.exec`（手工开启）。
- MCP Server stdio，仅注册 2 个工具。
- 完成 §8.5 的 1–5、13、14、16 项。

**验收标准**：

- [ ] 编辑器启动后自动生成发现文件，PID/`startedAt` 正确。
- [ ] `/health` 返回 UE 5.4.4 与插件版本。
- [ ] 错误 token 被拒绝；正确 token 可调用 `editor.status`。
- [ ] Claude Code stdio 能列出工具并拿到编辑器状态。
- [ ] 连续 100 次 `editor.status` 不崩溃，平均耗时 < 100ms。
- [ ] 编辑器关闭后进程/端口释放，发现文件删除。
- [ ] 截图、节点读取、资产依赖三项实验有明确结论（可用/不可用/替代方案）。

**退出条件**：A1、A2、A3、A4、A7、A8 有结论；任一关键假设失败则调整 MVP 范围，不带着未知进入下一阶段。

### 9.2 阶段 1：MVP（可开源发布）

**范围**：

- 全部 10 个工具。
- 三种传输（Streamable HTTP、SSE、stdio）。
- 策略门、确认、审计、速率限制。
- 三层错误模型与统一序列化。
- 安装文档、工具文档生成、三类客户端示例。
- 单元测试 + 集成冒烟 + CI。

**验收标准**：

- [ ] 三客户端（Claude Code HTTP、Cursor、curl）均可 `initialize → tools/list → tools/call`。
- [ ] read-only：`tools/list` 恰含 **7 个**工具（4 个纯 P0 + 3 个混合工具的只读动作，Schema 收窄）；纯 P1/P2 不可见；调用未注册 P1/P2 返回 `TOOL_DISABLED`；混合工具写 action 返回 `INVALID_ARGUMENT` 且无副作用。
- [ ] standard：`tools/list` 恰含 8 个工具；P2 不可见。
- [ ] full（未开 P2 开关）：8 个；仅 console 9 个；仅 exec 9 个；两者 10 个。
- [ ] full + exec：`ue_python_exec` 可见且可执行；未开桥接 `allowExec` 时返回 `EXEC_DISABLED`。
- [ ] 工具层错误统一 HTTP 200 + `isError:true` + `structuredContent.error`；协议层错误才使用非 200；`INVALID_ARGUMENT`（工具层）与 `INVALID_PARAMS`（协议层）分层正确。
- [ ] `--allow-destructive` 只豁免 P1 破坏性操作；console/exec 由各自开关兼作无 elicitation 时的策略确认。
- [ ] Actor 闭环：spawn → query → set_transform → capture → delete（destructive 开启）。
- [ ] 关卡：open/save/save_all/new 在临时工程通过；有脏包且未确认时拒绝 open。
- [ ] 资产：搜索、分页、依赖、引用结果正确；大工程超时返回部分结果。
- [ ] 材质：list/get/set/create_instance；非 MIC 设置被拒绝。
- [ ] 截图：PNG/JPEG 尺寸正确；超过 8 MiB 时只返回路径。
- [ ] 蓝图：query 变量/组件/图/编译状态；compile 成功；节点编辑请求返回 `CAPABILITY_UNAVAILABLE`。
- [ ] HTTP 会话：初始化返回 session；缺头 400；过期/未知 404；DELETE 204；TTL 生效。
- [ ] SSE：`examples/generic/sse_client.py` 退出码 0；Cursor 0.45.11（或 0.45.x 替代）完成一次工具调用，或按 §3.4 规则记 N/A。
- [ ] 端口：18777 被占时 MCP Server 2 秒内 exit 2 且 stderr 含 `http_bind_failed`；18778 被占时桥接回退到 18779–18788（或临时端口）并更新发现文件。
- [ ] 安全：Host/Origin 校验生效；非回环不可达；token 不出现在日志。
- [ ] 审计：每个 P1/P2 调用一条 JSONL；无源码/ token/ base64。
- [ ] 稳定性：桥接断开时工具返回 `BRIDGE_UNAVAILABLE`，Server 不退出。
- [ ] 文档：`docs/tools.md` 由 Schema 生成且与实现一致。
- [ ] 许可证与商标声明齐全。

**发布门槛（架构把关）**：

- [ ] 没有绕过游戏线程调度直接调用 `unreal` 的路径。
- [ ] 没有在 MCP Server 侧复制工具业务逻辑（只做校验/策略/映射）。
- [ ] 没有默认开启 exec/console。
- [ ] 没有监听 `0.0.0.0` 的代码路径。
- [ ] 所有写入工具都有 `dryRun` 或明确的确认/回滚说明。
- [ ] 错误码覆盖所有 handler 分支。
- [ ] 跨版本行为没有硬编码版本号分支（除能力探测）。

### 9.3 阶段 2：扩展

**候选能力（按价值排序）**：

1. C++ 辅助模块：蓝图节点创建/连线、变量增删、动画蓝图状态机（最大差异化）。
2. 控制台输出捕获（C++ `FOutputDevice`）。
3. 多编辑器实例与工程选择器。
4. WebSocket 事件流（编辑器事件、长任务进度、取消）。
5. 资产导入/导出、重命名/移动、重定向器修复。
6. Sequencer/关卡流送/Niagara 专用工具。
7. UE 5.5/5.6 兼容矩阵。
8. 单文件二进制分发（Node SEA）。
9. 可视化策略配置（编辑器内 Settings UI）。
10. `ue_level_control save_as`。

**验收标准**：

- 每个新能力先补 `capabilities` 探测与 Schema，再实现 handler。
- C++ 模块缺失时，原有 10 个工具行为不变。
- 新工具默认 P1 或 P2，不默认开放。
- 跨版本 CI 至少覆盖 5.4.4 与一个相邻版本。
- 新传输/新客户端不影响现有三类接入。

---

## 10. 附录

### 10.1 关键 TypeScript 类型（服务端）

```ts
// packages/shared/src/types.ts
export type PolicyMode = "read-only" | "standard" | "full";

export interface ToolMeta {
  requestId: string;
  durationMs: number;
  ueVersion?: string;
  pluginVersion?: string;
}

export interface ToolOk<T> {
  ok: true;
  data: T;
  warnings: string[];
  meta: ToolMeta;
}

export interface ToolErr {
  ok: false;
  error: {
    code: ErrorCode;
    message: string;
    retryable: boolean;
    details?: Record<string, unknown>;
  };
  meta: ToolMeta;
}

export type ToolResult<T> = ToolOk<T> | ToolErr;
```

### 10.2 工具注册示例

```ts
// packages/server/src/mcp/registerTools.ts（节选）
import { z } from "zod";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { ActorQueryInput, ActorQueryOutput } from "@uemcp/shared";
import { bridge } from "../bridge/client.js";
import { policy } from "../policy.js";

export function registerTools(server: McpServer, mode: PolicyMode) {
  server.registerTool(
    "ue_actor_query",
    {
      title: "Query Unreal Actors",
      description:
        "Query actors in the current editor level or selection. Read-only. " +
        "Supports class/name/label/tag filters and pagination.",
      inputSchema: ActorQueryInput.shape,
      outputSchema: ActorQueryOutput,
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (args) => {
      const res = await bridge.call("actor.query", args);
      return {
        content: [{ type: "text", text: summarizeActorQuery(res) }],
        structuredContent: res,
        isError: !res.ok,
      };
    },
  );

  if (mode !== "read-only") {
    server.registerTool("ue_actor_edit", { /* ... */ }, async (args) => {
      // policy + confirmation + audit
    });
  }

  if (mode === "full" && policy.allowExec) {
    server.registerTool("ue_python_exec", { /* ... */ }, async (args) => {
      // confirmation required
    });
  }
}
```

### 10.3 桥接 HTTP handler 伪代码

```python
# plugin/UEMCPBridge/Content/Python/uemcp_bridge/server.py（节选）
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .dispatcher import GameThreadDispatcher
from .security import verify_token, is_loopback, valid_host
from .rpc import dispatch
from .errors import rpc_error

class Handler(BaseHTTPRequestHandler):
    server_version = "UEMCPBridge/0.1.0"

    def do_POST(self):
        if self.path != "/rpc":
            return self._not_found()
        if not is_loopback(self.client_address[0]) or not valid_host(self.headers.get("Host")):
            return self._deny(403)
        if not verify_token(self.headers.get("X-UEMCP-Token")):
            return self._deny(401)

        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 8 * 1024 * 1024:
            return self._deny(413)

        try:
            req = json.loads(self.rfile.read(length))
        except Exception:
            return self._json(rpc_error(None, -32700, "PARSE_ERROR", "Invalid JSON"))

        try:
            result = dispatch(req["method"], req.get("params") or {},
                              timeout_s=self.server.settings.request_timeout_s)
            return self._json({"jsonrpc": "2.0", "id": req.get("id"), "result": result})
        except RpcAppError as exc:
            return self._json(rpc_error(req.get("id"), exc.rpc_code,
                                        exc.error_code, exc.message, exc.details))
        except Exception as exc:
            return self._json(rpc_error(req.get("id"), -32603,
                                        "INTERNAL", str(exc)))

    def log_message(self, fmt, *args):
        # 不走默认 stderr 文本日志，交给统一 logger
        return
```

### 10.4 最小安装步骤（面向用户）

1. 安装 UE 5.4。
2. 将 `UEMCPBridge` 复制到 `<Project>/Plugins/UEMCPBridge`。
3. 编辑器启用 **Python Editor Script Plugin**（插件会自动声明依赖）。
4. 重启编辑器，确认 `Saved/UEMCP/bridge-settings.json` 与 `~/.uemcp/bridge.json` 生成。
5. 启动 MCP Server：

```bash
npx -y @uemcp/server --transport http --policy standard
```

6. 在客户端添加 `http://127.0.0.1:18777/mcp`。
7. 调用 `ue_editor_status` 验证。

### 10.5 故障排查表

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `BRIDGE_UNAVAILABLE` | 编辑器未启动/插件未启用/Python 插件未加载 | 看 `Saved/Logs/*.log` 中 `[UEMCP]`；确认发现文件 |
| 408/504 超时 | 游戏线程繁忙/长任务 | 等待；检查是否在编译/PIE；增大 `timeoutMs` |
| `TOOL_DISABLED` | 服务端策略或独立开关未开 | 按 `details.gate` 调整 `--policy`/`--allow-console`/`--allow-exec` |
| `PERMISSION_DENIED` | 桥接 `allowWrite`/`allowConsole=false` | 修改桥接配置并重启编辑器；`details.gate` 指明门位 |
| `EXEC_DISABLED` | 桥接 `allowExec=false` | 开启桥接 `allowExec`；该码专用于执行门 |
| `INVALID_ARGUMENT` | 工具参数未通过 Schema（含 read-only 收窄后的写 action） | 按 `details.issues` 修正参数或切换策略 |
| `CONFIRMATION_REQUIRED` | P1 未开 `--allow-destructive`；或 P2 未开对应开关且客户端无 elicitation | P1 开 `--allow-destructive`；console/exec 开各自开关或换支持 elicitation 的客户端 |
| MCP Server 端口占用 | 18777 被其他进程占用 | 进程 2 秒内 exit 2；用 `--port` 换端口并同步修改客户端 URL |
| 桥接端口占用 | 18778 被占用 | 自动回退 18779–18788/临时端口；检查发现文件 `port`/`url` 是否更新 |
| 截图失败 | `AutomationLibrary` 不可用/PIE 未运行 | 看 `capabilities.screenshot`；运行 PoC 验证脚本 |
| 蓝图节点为空 | 反射访问失败 | 预期行为；`blueprintNodeRead=false`，P2 用 C++ |
| 控制台无输出 | 已知限制 | 使用 `ue_python_exec` |
| 发现文件陈旧 | 编辑器被强杀 | 检查 PID；删除 `~/.uemcp/bridge.json` 后重启 |

### 10.6 参考资料

- Model Context Protocol 规范（Streamable HTTP、SSE、stdio、tools、elicitation）。
- `@modelcontextprotocol/sdk`（TypeScript）。
- Unreal Engine 5.4 Python API：`unreal.EditorActorSubsystem`、`unreal.LevelEditorSubsystem`、`unreal.EditorAssetSubsystem`、`unreal.MaterialEditingLibrary`、`unreal.BlueprintEditorLibrary`、`unreal.AutomationLibrary`、`unreal.ScopedEditorTransaction`。
- 参考项目：Natfii/UnrealClaude（工具分类与双进程结构参考；本项目不复用其内嵌 Claude Code UI 与 5.7 绑定）。
- Epic Games 商标与开源使用政策。

---

## 附录 A：架构门槛检查表（发布前逐项核对）

- [ ] MCP 对外只暴露 10 个工具，命名与本文一致。
- [ ] 所有工具都有 `inputSchema` 与 `outputSchema`，且实现与 Schema 一致。
- [ ] 所有写操作经过游戏线程 dispatcher，没有直接在 HTTP 线程调用 `unreal`。
- [ ] 所有 P1/P2 调用写审计；无 token、无完整源码、无 base64。
- [ ] 默认策略为 `read-only`；read-only 恰含 7 个工具（4 个纯 P0 + 3 个混合工具只读动作，Schema 收窄）；exec/console 默认不可见。
- [ ] MCP 与桥接均只绑定 `127.0.0.1`。
- [ ] 桥接 token 每次启动轮换；发现文件原子写、权限 0600。
- [ ] 未知/过期会话返回 404；初始化缺 session 返回 400。
- [ ] Host/Origin 校验生效；无 CORS 通配。
- [ ] `BRIDGE_UNAVAILABLE`/超时/忙/权限错误可区分且可重试语义正确；工具层错误一律 HTTP 200 + `isError`。
- [ ] read-only 下纯写工具直接调用返回 `TOOL_DISABLED`；混合工具写 action 返回 `INVALID_ARGUMENT`，且无副作用、不泄漏实现细节。
- [ ] 破坏性操作有确认或显式策略开关；`--allow-destructive` 不豁免 console/exec。
- [ ] MCP Server 端口占用以 exit 2 失败退出；桥接端口冲突可回退并被发现文件正确发布。
- [ ] SSE 必测脚本退出码 0；Cursor 0.45.x 基线按 §3.4 记录 PASS/N/A/FAIL。
- [ ] 不承诺 Python 不具备的能力；蓝图节点/动画编辑明确标注 P2。
- [ ] 跨版本仅通过能力探测分支，无硬编码版本判断。
- [ ] 许可证、商标免责声明、安全说明齐全。
