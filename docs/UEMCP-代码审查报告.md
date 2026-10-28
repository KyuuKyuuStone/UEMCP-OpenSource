# UEMCP 独立代码审查报告

| 项 | 值 |
|---|---|
| 审查版本 | 实现交付版（Server 0.1.0 / Bridge 0.1.0，2026-10-20） |
| 审查依据 | 《UEMCP-架构设计.md》v0.2.0、《UEMCP-测试计划.md》v0.1.1、`uemcp/README-DEV.md` |
| 审查方式 | 纯静态审查（只读源码 + 对照设计文档），未执行任何运行时验证 |
| 审查角色 | 独立代码审查（不改代码） |

---

## ① 结论

**有条件通过：修复 Critical-1 后可进入联调；Critical-2 修复前不得在多编辑器/多工程环境使用写工具。** 发**开源发布**还须处理全部 Major 并复核"未审范围"。

### 阻断级问题（进入联调前必须处理）

| # | 问题 | 位置 | 一句话影响 |
|---|---|---|---|
| C-1 | Bridge `ERROR_TABLE` 缺 `INVALID_ARGUMENT`，未知码被构造函数改写为 `EXECUTION_ERROR` | `Plugins/UEMCPBridge/Content/Python/uemcp_bridge/errors.py:76-80` | Bridge 端全部参数校验错误（30+ 处调用点）返回错误码 `EXECUTION_ERROR`(-32009/500) 而非 `INVALID_ARGUMENT`(-32602/400)，违反架构 §2.9.3/§2.9.6 契约，测试计划大量错误码断言将失败；且 smoke 自测因 mock-bridge 模拟了正确行为而**掩盖了该缺陷** |
| C-2 | `--project` 的 `projectDir` 比较未做与 hash 相同的规范化 | `uemcp/packages/server/src/bridge/discovery.ts:123`（对照 `discovery.py:28-30`） | 用户传入带尾斜杠的工程路径（Windows 资源管理器复制格式极常见）时，project-hash 来源静默失效并**回退到 `~/.uemcp/bridge.json`（可能是另一工程正在运行的编辑器）**，写操作作用于非预期工程 |

---

## ② 问题清单（按严重度）

### Critical

#### C-1 Bridge 端 `INVALID_ARGUMENT` 被静默改写为 `EXECUTION_ERROR`

- **位置**：
  - `uemcp_bridge/errors.py:76-80`（`RpcError.__init__`：`meta = ERROR_TABLE.get(code); if meta is None: code = "EXECUTION_ERROR"`）
  - `uemcp_bridge/errors.py:11-56`（`ERROR_TABLE` 44 项，**无 `INVALID_ARGUMENT`**，尽管同文件 124-133 行提供了 `invalid_argument()` 辅助构造函数）
  - 调用点（30+ 处）：`handlers/__init__.py:35,40,55,60,74,83,88,92,96,106,111,116,120,138,143,147,151,167,172,197,202,206,216,228,242,252,257,263,277,282,288,301,306`；`handlers/actors.py:689,745`；`handlers/levels.py:238`；`handlers/materials.py:447`
- **触发条件**：任何到达 Bridge 的参数/业务校验失败（未知 action、类型不符、required 缺失、additional property、选择器格式错误等）。
- **影响**：
  1. 返回 `errorCode=EXECUTION_ERROR`、JSON-RPC -32009、HTTP 500（架构 §2.9.3 规定 `INVALID_ARGUMENT` 为 -32602/400，§2.9.5 参数错误为 400/404）；
  2. 客户端无法区分"参数写错"与"内部执行异常"，`details.issues` 虽保留但码名不符 §2.9.6 契约；
  3. 测试计划中依赖桥接侧错误码的用例（TOOL-05/12/15/22、SEC-01(d)(e)(f) 的桥接分支等）将批量失败；
  4. `uemcp/scripts/mock-bridge.mjs:164,198,269` 模拟了**正确的** `INVALID_ARGUMENT`，因此 `README-DEV.md` 宣称的 smoke 65/65 通过不能覆盖真实 Bridge 的此路径——**自测盲区**。
- **修改建议**：在 `ERROR_TABLE` 补 `"INVALID_ARGUMENT": (-32602, 400, False)`；同时审查"未知码改写"策略本身（建议保留原码、仅按默认元数据兜底，避免同类静默改写）。并将 smoke 的错误码用例接入真实 Bridge（或增加桥接端单测）。

#### C-2 `--project` 发现来源在常见输入下静默失效并跨工程回退

- **位置**：`uemcp/packages/server/src/bridge/discovery.ts:123`（`raw.projectDir !== opts.projectDir.replaceAll("\\", "/")`，未去尾斜杠、未做大小写不敏感比较）；hash 计算在 `discovery.ts:23-26` 与 `uemcp_bridge/discovery.py:28-30` 均做了去尾斜杠规范化。
- **触发条件**：`--project "C:\UE5_P\5.4\XQHCPP_54\"`（带尾反斜杠）或大小写不一致输入。此时 hash 文件能命中（hash 用规范化目录计算），但 `projectDir` 直接比较失败 → `continue` → 落入来源 3 `~/.uemcp/bridge.json`。
- **影响**：多编辑器场景下，Server 会静默连接"最近启动"的**其他工程**编辑器；随后 `actor.edit`/`level.control` 等写操作作用于非预期工程。仅留 `bridge_discovery_project_mismatch` warn 日志，客户端无感知。用户显式指定 `--project` 的隔离意图被绕过。
- **修改建议**：两侧比较使用与 hash 相同的 `normalizeProjectDir`（去尾斜杠；Windows 下大小写不敏感比较）；`--project` 指定时若 project-hash 来源失败应硬失败（返回 `BRIDGE_UNAVAILABLE`），**不回退**到 `bridge.json`/默认端口。

---

### Major

#### M-1 `ToolDef.timeoutMs` 声明从未生效，`blueprint.compile` 会在 30s 误报超时

- **位置**：`uemcp/packages/server/src/tools/common.ts:189`（字段定义）——全仓库无任何消费点（已 grep 验证）；`tools/blueprint.ts:25`（声明 60000）vs `tools/blueprint.ts:48-51`（`ctx.bridge.call("blueprint.query", args)` 未传超时，落默认 30000）；`tools/viewportCapture.ts:36`（声明 45000）vs `:50`（硬编码 30000）。
- **触发条件**：编译耗时 >30s 的蓝图（大蓝图常见）。
- **影响**：`BRIDGE_TIMEOUT` 误报（编辑器实际仍在编译，任务无法中断），与架构 §2.6"单工具可声明更高上限（最高 120s）"不符。
- **修改建议**：`bridge.call` 默认取 `def.timeoutMs`；viewport 用声明的 45000 或修正声明。

#### M-2 P2 工具（console/exec）未实现 elicitation 优先，与架构 §6.3-5/§6.4 不一致

- **位置**：`tools/pythonExec.ts`（全文无 `ctx.elicit` 调用）、`tools/consoleCommand.ts`（同）；对照 `tools/actorEdit.ts:49`、`tools/levelControl.ts:56`（有 elicitation 流）。
- **触发条件**：客户端支持 elicitation（`capabilities.elicitation`）+ Server `full --allow-exec/--allow-console` + Bridge 对应开关开启。
- **影响**：架构 §6.3-5 与 §6.4 要求"elicitation 优先，否则开关兼作策略级确认"；当前实现**从不询问**，直接 `confirmationMode:"policy"` 放行。对支持确认流的客户端，每次执行失去用户把关（安全语义弱化为静默）。
- **修改建议**：P2 handler 在调用前尝试 `ctx.elicit`；`declined → CONFIRMATION_DENIED`，`unsupported → 沿用 policy`（保持现行为兜底）。注意 `README-DEV.md §7` 已声明 elicitation 未经运行时验证，修复时一并补测。

#### M-3 `--audit-python-source` 允许审计文件记录 Python 源码原文，与 §6.5"永不记录"红线冲突；审计文件未设 0600

- **位置**：`uemcp/packages/server/src/config.ts:30,102`（CLI 开关）、`tools/audit.ts:118`（`if (includePythonSource) summary.code = code;`）、`audit.ts:33,62`（`mkdir`/`appendFile` 无 mode 参数）。
- **触发条件**：以 `--audit-python-source` 启动并调用 `ue_python_exec`。
- **影响**：架构 §6.5 红线为"**永远**不记录：token、完整 Python 源码"——被调试用开关绕过；`~/.uemcp/audit/*.jsonl` 将明文含源码（可能内嵌密钥），且文件权限未收紧（Windows 下 ACL 默认继承用户目录，风险可控但与 §6.1 token 表"文件权限 0600"的既有实践不一致——Bridge 侧 `discovery.py:60` 已做 chmod 0600）。
- **修改建议**：移除该开关（仅保留 `codeSha256/codeLength`），或至少将源码写入独立的调试文件并显式高危告警；审计目录/文件统一 0600。

#### M-4 写操作在"响应丢失"场景被自动重试，存在重复执行风险

- **位置**：`uemcp/packages/server/src/bridge/client.ts:72-84`（`call()` 对 `BRIDGE_UNAVAILABLE + retryable` 无条件 `invalidate()` 后二次 `attempt`）。
- **触发条件**：第一次请求已到达 Bridge 并入队/执行，但响应在回程丢失（连接中断、对端 reset，fetch 抛 `TypeError` → 归类 `BRIDGE_UNAVAILABLE`）。
- **影响**：`actor.edit`（spawn/duplicate）、`material.params set`、`blueprint compile` 等非幂等写操作被执行两次（重复产物/重复保存）。Bridge 端无法区分"未收到请求"与"响应丢失"。
- **修改建议**：写方法不做自动重试（仅读方法重试）；或内部 RPC 增加幂等 key（`meta.requestId` 服务端去重）。

#### M-5 console 白名单/拒绝表三处定义且内容不一致

- **位置**：① `uemcp/packages/shared/src/schemas/console.ts:16-45`（`CONSOLE_ALLOWLIST` 11 项含 `dumpticks/obj/memreport/camera`；Server 端**未引用**，实为死代码）；② `uemcp_bridge/settings.py:21-29`（`DEFAULT_CONSOLE_ALLOWLIST` 仅 7 项，缺上述 4 项）；③ `uemcp_bridge/handlers/console.py:21-35`（`PERMANENTLY_DENIED` 与 shared `CONSOLE_DENIED` 逐字重复，双处维护）。
- **触发条件**：`ue_console_command` 调用 `dumpticks/obj/memreport/camera` 前缀命令（架构 §5.8 白名单内）。
- **影响**：默认桥接配置下返回 `COMMAND_NOT_ALLOWED`，与架构白名单表不一致；三处表漂移后后续维护必错。
- **修改建议**：确定单一事实来源（建议 Bridge settings 为准、shared 移除或仅作文档）；对齐默认白名单；`PERMANENTLY_DENIED` 单点定义。

#### M-6 速率限制未实现（架构 §6.7、§2.9.2 `RATE_LIMITED`）

- **位置**：`transports/http.ts`（无任何限流中间件）；`uemcp_bridge/server.py`（桥接端亦无限流）。
- **触发条件**：高频请求/失控客户端。
- **影响**：§6.7"每会话 20 req/s、桥接 30 req/s"未落地；会话上限 32 + body 8MiB + 队列 64 仅部分缓解。README-DEV §7 已披露"未实现（P2 选测）"，**属已知偏离**，但发布门槛检查（架构附录 A）与 SEC-14 需要有明确结论（实现或豁免记录）。
- **修改建议**：MVP 至少在 Server HTTP 层实现粗粒度每会话限流，或在架构文档将 §6.7 降级为 P2 并记录裁决。

#### M-7 Windows 下 `allow_reuse_address=True` 可能导致双绑定，端口回退机制被绕过

- **位置**：`uemcp_bridge/server.py:70-72`（`_BridgeHTTPServer.allow_reuse_address = True`）。
- **触发条件**：Windows 上 18778 已被占用（另一编辑器 Bridge 或其他进程）时启动第二个 Bridge。Windows 的 `SO_REUSEADDR` 语义与 Linux 不同，可能允许绑定到已占用端口而非抛 `EADDRINUSE`。
- **影响**：两个进程共享 18778，`/health` 与 `/rpc` 命中不确定实例——发现文件、token 校验、策略门全部可能错位；§2.3 的"18779–18788 顺序回退"失效。
- **修改建议**：Windows 平台设 `allow_reuse_address = False`（或设置 `SO_EXCLUSIVEADDRUSE`），让 bind 冲突正常抛错并走回退链；注意 `--port 0` CI 场景需回归验证。

---

### Minor

| # | 问题 | 位置 | 触发条件 / 影响 | 建议 |
|---|---|---|---|---|
| m-1 | elicitation `accept` 但返回非 JSON 文本时 fail-open 返回 `approved` | `packages/server/src/confirm.ts:44-52` | 客户端异常实现 + 用户实际未勾选 approve → 破坏性操作被放行 | 解析失败按 `declined` 处理 |
| m-2 | `CONNECT_WINDOW_MS` 分支不可达（`AbortSignal.timeout(timeoutMs+5000)` 触发的 `TimeoutError` 时 `elapsed` 必 ≥ 35s，`< 3000` 恒假） | `bridge/client.ts:155-160` | 无运行时错误，但误导维护者以为存在"快速失败→连接层失败"区分 | 删除或重构判定（按异常类型区分连接失败与超时） |
| m-3 | `PythonExecInput.timeoutMs` 默认 10000，但 Server 强制 `Math.max(args.timeoutMs, 30000)` | `packages/shared/src/schemas/python.ts:13`、`tools/pythonExec.ts:44` | 用户设 10s 期望 10s 超时 → 实际 30s；schema 默认值形同虚设 | schema 默认改 30000 或移除 Server 端下限 |
| m-4 | 截图 fallback 只 glob `*.png`，且窗口内第三方 png 可能被误回收 | `uemcp_bridge/handlers/viewport.py:106-121,124-134` | `format=jpeg` 走 fallback 必 `CAPTURE_FAILED`；`Saved/Screenshots` 中恰有他方新 png 时返回错误文件 | fallback 按扩展名过滤并校验 mtime ≥ started_at；记录 warning |
| m-5 | Bridge 错误消息混入中文（`"需要 C++ 辅助模块（P2）"`）与其余英文不一致 | `uemcp_bridge/handlers/blueprints.py:334` | 面向英文客户端的 message 混排 | 统一英文 |
| m-6 | Bridge 发现文件多写 `projectPath` 字段（架构 §2.4 schema 无此字段） | `uemcp_bridge/server.py:371-372` | 无害；多工程工具若依赖该字段属未定义行为 | 删除或写入架构 schema |
| m-7 | Server 端未强制 Content-Type JSON（`express.json({type: () => true})`）；架构 §6.1 要求强制 | `transports/http.ts:118` | Host/Origin 校验已缓解主要 CSRF 面；与 Bridge 端 415 行为不一致 | Server 侧同样校验并 415 |
| m-8 | initialize `params` 非对象时 `{...params}` 展开字符串为索引对象后才被 SDK 拒绝 | `transports/http.ts:206-208` | 无实害（SDK 兜底），仅边界行为不洁 | patch 前判 `isJsonObject(params)` |
| m-9 | 截图孤儿文件：`CAPTURE_TIMEOUT` 后任务仍可能完成写文件，`Saved/UEMCP/captures/` 无清理机制 | `handlers/viewport.py:246-262` | 长期使用磁盘缓慢膨胀 | 超时分支尝试删除目标文件；或启动时清理过期 captures |
| m-10 | Bridge `ERROR_TABLE` 含 `SESSION_NOT_FOUND(-32001)`，违反"**-32001 专用于协议层 SESSION_NOT_FOUND**"的命名规则（当前无调用点，防御性清除） | `uemcp_bridge/errors.py:13` | 未来误用会与协议层冲突 | 从表中移除 |
| m-11 | `actor_ref` 的 `objectPath` 与 `actorPath` 同值（均为 `get_path_name()`） | `uemcp_bridge/handlers/__init__.py:412-413` | 与 §5.2 ActorRef 字段语义（ObjectPath 格式）可能不符，依赖两者的客户端会拿到相同值 | 按 UE 语义区分或文档标注 |
| m-12 | Server logger 字段不截断（§6.7 日志字段 2 KiB）；Bridge 端已实现（1 KiB/16 KiB） | `packages/server/src/logger.ts:15-24` | 异常长字段（如桥接 URL、错误消息）撑爆日志行 | 写日志前截断 |
| m-13 | `blueprint` 的 `save:true`（写盘）不触发 Server 审计（审计仅在 `action=compile` 时记录），且无确认流 | `tools/blueprint.ts:37,53`（`isWrite` 仅依据 action） | `action:"query", save:true` 静默写盘、无审计记录 | `isWrite` 计入 `save===true`，补审计 |

---

### 疑点（无充分证据，需实现方/架构师确认）

| # | 疑点 | 位置 | 说明 |
|---|---|---|---|
| Q-1 | Server 读截图文件无目录约束 | `tools/viewportCapture.ts:74`（`readFile(data.path)`） | 信任 Bridge 返回路径（同机 + token）。若 Bridge 被伪造（架构明示不防本机恶意进程）则可读任意文件并 base64 外传。属纵深防御缺失还是接受域内风险，请架构师裁决 |
| Q-2 | `hideEditorUI` 参数被解析后丢弃 | `uemcp_bridge/handlers/viewport.py:158` | schema 向用户承诺隐藏编辑器 UI，桥接实际未实现（`take_high_res_screenshot` 是否支持该能力未验证）。若不支持应从 schema 移除或标注降级 warning |
| Q-3 | JSON-RPC batch（数组）请求被拒为 400 | `transports/http.ts:161-214` | `isJsonObject` 拒数组 → 非 initialize → 400 `INVALID_REQUEST`。MCP `2025-03-26` 支持 batch；架构文档未提及 batch 语义，需裁决（当前实现=不支持，行为对错取决于文档补全） |
| Q-4 | `ue_python_exec` 返回 stdout/stderr 捕获 | `handlers/python_exec.py:83-84`（schema 默认 `captureOutput:true`） | 测试计划 §1.2 只承诺 console 无回显；python 的输出捕获超出 §5.9 出参 Schema 与否需对照 §5.9 逐字段核对（本次未逐字段比对） |
| Q-5 | `status.ts:42` 向客户端暴露 `policies.destructive` 等服务端开关状态 | `tools/status.ts` | 是否符合 §5.1 policies 字段契约未逐项核对；一般无害（本机自我描述），列为待核对项 |

---

## ③ 审查范围与依据

### 已审文件（静态逐行/重点段审查）

**MCP Server（Node/TypeScript，`uemcp/`）**
- 入口/配置/基础设施：`packages/server/src/index.ts`、`config.ts`、`logger.ts`、`policy.ts`、`audit.ts`、`confirm.ts`
- 传输层：`transports/http.ts`（安全中间件/会话/错误处理全量）、`transports/stdio.ts`
- MCP 路由：`mcp/buildServer.ts`、`mcp/registerTools.ts`
- 桥接链路：`bridge/discovery.ts`、`bridge/client.ts`、`bridge/watchdog.ts`
- 工具：`tools/common.ts`、`pythonExec.ts`、`actorEdit.ts`、`consoleCommand.ts`、`viewportCapture.ts`、`blueprint.ts`（handle 主体）；其余工具（status/actorQuery/assetSearch/levelControl/materialParams）经 grep 交叉验证了策略门、zod 校验、审计调用的一致性
- shared：`errors.ts`（错误码表与架构 §2.9.3 逐项核对）、`toolNames.ts`（RPC 方法表与 §2.8 逐项核对一致）、`schemas/python.ts`、`schemas/viewport.ts`、`schemas/console.ts`
- scripts：`mock-bridge.mjs`、`smoke.mjs`（错误码相关行抽查）

**Bridge（UE Python 插件，`Plugins/UEMCPBridge/`）**
- `server.py`（HTTP 面/token/端口回退/发现发布全量）、`security.py`（回环/Host/Origin/token 全量）、`dispatcher.py`（线程模型全量）、`rpc.py`（路由/权限门/超时全量）、`errors.py`（全量）、`settings.py`（全量）、`discovery.py`（全量）、`serialization.py`（全量）、`init_unreal.py`（全量）
- handlers：`console.py`、`python_exec.py`、`viewport.py`（137-280 主体）、`levels.py`（open/save 段）、`blueprints.py`（325-470 段）、`actors.py`（748-842 handle_edit + dry_run + selector 白名单）、`__init__.py`（校验助手 1-100、UE 助手 310-514、resolve_actor/resolve_actor_class 全量）

**设计文档**：架构 v0.2.0 §2.3-2.9（端口/发现/线程/RPC/错误模型）、§5.0-5.11（抽查）、§6.1-6.7（全量）；测试计划 v0.1.1 全量；README-DEV.md 全量（其 §7 自报的未实现项已并入本报告评估）。

### 一致性核对结论（通过项）

- Server↔Bridge 的 RPC 方法名（12 个）与架构 §2.8 表**完全一致**（`shared/toolNames.ts` vs `uemcp_bridge/rpc.py:45-58`）。
- 工具级错误码 44 项与架构 §2.9.3 数字码/HTTP 码一致（`shared/errors.ts` vs `uemcp_bridge/errors.py`，除 C-1 的缺失项）。
- 三策略注册与收窄（D12）：`policy.ts` 的可见性矩阵、`narrowedActions` 与 §5.11/PROTO-03 预期集合一致；read-only 下混合工具 readOnlyHint=true。
- 双重权限门：Bridge 侧 `rpc.enforce_gates`（入队前）+ handler 内二次检查，错误码 `PERMISSION_DENIED`/`EXEC_DISABLED` 与 D6 gate 契约一致；console 白名单拒绝 `COMMAND_NOT_ALLOWED` 与 `PERMISSION_DENIED` 分离正确。
- 错误模型主干：工具失败 200+isError、信封/未知工具 400/-32602（完整目录判断）、未知 method 404/-32601、会话 404/-32001、Host 421/Origin 403、`UNSAVED_CHANGES → CONFIRMATION_REQUIRED` 固定顺序（levels.py:139-152）均符合 §2.9/§2.9.7。
- 线程模型：HTTP 线程不触碰 `unreal`（`bridge.ping/capabilities` 除外，均为无 UE 依赖的纯数据）；队列 64、超时上限 120s、过期任务入队前拦截（`dispatcher.py:113-116`）符合 §2.6。
- token：32 字节 CSPRNG、base64url、`hmac.compare_digest` 常量时间、`X-UEMCP-Token` 头传递、发现文件 chmod 0600（best effort）符合 §6.6。

---

## ④ 未审范围与未执行验证

### 未审范围（本次静态审查未覆盖，不构成结论）

1. `handlers/actors.py` 中段（约 200-690 行：query 过滤/排序/分页、set_properties 白名单具体实现、spawn 执行体）；`handlers/materials.py`、`handlers/assets.py`、`handlers/status.py` 的大部分行——仅验证了策略门/审计的调用存在性，未逐行审 UE API 用法与返回字段契约。
2. shared 其余 schema（actors/levels/materials/assets/blueprints/status/common）与架构 §5.1-§5.10 出入参 Schema 的**逐字段**比对（本次仅抽查 python/viewport/console 三份）。
3. `scripts/smoke.mjs`、`mock-bridge.mjs` 全文逻辑（仅抽查错误码相关行）。
4. `Plugins/UEMCPBridge/Tests/smoke_bridge.py`、`README.md`、`.uplugin` 元数据。
5. 架构文档 §3.4（旧版 SSE 细节）、§4（选型）、§7-§10（目录/附录）未逐条核对实现。

### 未执行验证（全部留给测试计划执行阶段）

1. **未启动任何进程**：Server/`pnpm build`/`smoke.mjs`/真实 UE 编辑器均未运行——README-DEV 宣称的 65/65 与构建结果**未复核**，且如 C-1 所示 smoke 存在系统性盲区（mock 桥接掩盖真实 Bridge 行为）。
2. elicitation 确认流（含 m-1 fail-open 分支）无运行时证据（README-DEV §7 亦自报未验证）。
3. Windows 双绑定行为（M-7）未实测；端口回退链未实测。
4. C-2 的尾斜杠场景未构造实测用例（结论基于代码路径推演，证据充分：`discovery.ts:23-26,123` 与 `discovery.py:28-30` 规范化不对称）。
5. 性能/压测（SEC-14 P2 选测）不在本次范围。

### 仍需架构判断的事项

- Q-1（截图文件读取的信任边界）、Q-3（batch 请求语义）、M-3（审计源码开关是否保留）、M-6（限流实现或正式豁免）、m-11（objectPath 语义）——建议主管/架构师裁决后落入实现。

---

*审查人：代码审查（独立会话）；报告生成：2026-10-20。本报告不含代码修改。*

---

## 第二轮针对性复审（2026-10-20）

> 复审任务：只复核 Server 侧 7 项修复（Critical-2、Major-1/2/3/4/5/6）相关改动，确认修复正确且未引入回归。
> 主管已复跑：`pnpm typecheck`/`build` 通过、`node scripts/smoke.mjs` 71/71 通过（本轮复审未重复执行，见"未执行验证"）。

### 复审范围（逐文件）

- `packages/server/src/bridge/discovery.ts`（normalize 共用、目录扫描兜底、--project 硬失败）
- `packages/server/src/bridge/client.ts`（timeoutMs 消费、clamp、retriable 语义、401 映射）
- `packages/server/src/transports/http.ts`（每会话限流）
- `packages/server/src/tools/pythonExec.ts`、`consoleCommand.ts`（elicitation 优先）
- `packages/server/src/audit.ts`、`config.ts`、`index.ts`（删开关、0600）
- `packages/shared/src/schemas/console.ts`（删死代码）
- 全部 10 个工具的 `bridge.call` 调用点（超时与重试一致性，grep 全量核对）

### 逐项修复结论

| 修复项 | 结论 | 关键证据 |
|---|---|---|
| Critical-2（--project 跨工程回退） | **通过** | discovery.ts:117-157：`--project` 存在时 hash 命中→`equalProjectDir` 比较；未命中→目录扫描兜底（L124-140，修复大小写差异场景）；扫描仍无命中/pid 失败/health 失败均 `return null`（L141-155）。来源 3（bridge.json）/来源 4（默认端口）只在未指定 `--project` 时可达（L117 提前返回）——**硬失败语义成立，完全不回退**（重点①）。normalizeProjectDir 为 hash 与比较共用（L26-37），尾斜杠与大小写输入均不再误判 |
| Major-1（timeoutMs 不生效） | **通过** | client.ts:83 `Math.min(Math.max(1000, timeoutMs), 120000)`；10 个调用点全部传 `def.timeoutMs`（重点⑥）：actorEdit 30000、blueprint 60000、viewportCapture 45000、pythonExec `Math.max(args.timeoutMs,30000)`≤120000，其余 30000；meta.timeoutMs 传 clamp 后值（client.ts:137） |
| Major-2（P2 elicitation） | **通过** | pythonExec.ts:43-45、consoleCommand.ts:42-44 在 `bridge.call` 前无条件 `ctx.elicit`；declined → `CONFIRMATION_DENIED`（审计 decision:"denied"/confirmationMode:"elicitation"）；unsupported → policy 兜底（工具可见前提即开关已开，符合 D11）；confirmationSwitch 仅在 policy 时记录（pythonExec.ts:81、consoleCommand.ts:75）——**审计可区分两种确认来源**（重点⑤） |
| Major-3（审计红线/0600） | **通过**（2 项 Minor 清理残留，见下） | config.ts `ServerOptions`/`loadConfig` 已无 `auditPythonSource`（index.ts、tools/common.ts 无残留，grep 验证）；audit.ts:82-85 `summarizeArgs` 收敛为 2 参、python 仅 hash/长度（L118-124）；**0600 在文件创建时生效**：audit.ts:64 `open(file, "a", 0o600)`（mode 仅新文件生效，已有文件追加保持原权限——满足重点④，且优于 Bridge 侧的事后 chmod 方案）；Windows ACL 近似已在注释声明 |
| Major-4（写不重试） | **通过** | client.ts:29-36 `retriable` 默认 false；写方法（actorEdit/consoleCommand/pythonExec）省略 opts 即不自动重试；混合工具 `retriable: !isWrite`（levelControl.ts:81、materialParams.ts:48、blueprint.ts:48），三组 `LEVEL/MATERIAL/BLUEPRINT_WRITE_ACTIONS`（shared schemas levels.ts:32-37、materials.ts:64-67、blueprints.ts:38）与 Bridge 端 `rpc.py WRITE_ACTIONS` 完全一致——**写 action 判定全覆盖**（重点②）；读方法显式 `retriable: true`（status/actorQuery/assetSearch/viewportCapture）；未重试的 UNAVAILABLE 消息追加提示（client.ts:101-110） |
| Major-5（白名单单一来源） | **通过** | shared console.ts 死代码已删（L15 注释）；grep 全仓无 `CONSOLE_ALLOWLIST/CONSOLE_DENIED` 引用残留（mock-bridge.mjs:43 为测试脚本自有表，不属 Server/Bridge 契约） |
| Major-6（限流） | **通过** | http.ts:43-58 令牌桶：key=sessionId、20 req/s、突发 40；挂在会话校验**之后**（L258-266、L328-337）——伪造 sid 无法灌桶；429 经 `sendRpcError` 返回 JSON-RPC 顶层 error（无 `result`、无 isError）符合协议层形态（重点③）；桶清理覆盖 DELETE（L292）与 TTL sweeper（L355） |
| levelControl/actorEdit 一致性 | **通过** | actorEdit.ts:94 传 `timeoutMs` 且不重试；levelControl.ts:81 `timeoutMs` + `retriable:!isWrite`；elicit/delete-confirm 确认流未见改动 |

### 新发现问题（本轮改动引入或复审中新暴露）

均为 Minor，不阻断：

1. **N-1 `--audit-python-source` 解析残留**（`config.ts:29`）：`parseArgs` 仍将其识别为布尔参数，但已无任何消费者——传入被**静默忽略**，无安全影响（不会记录源码）。建议下次清理时从布尔列表移除。
2. **N-2 审计目录权限**（`audit.ts:33,62`）：`mkdir` 未传 mode，文件 0600 已达标，但 Linux 下目录可能为 755（可列举文件名/日期，内容不可读）。Windows 用户目录 ACL 已受限，风险极低。可选：目录 0700。
3. **N-3 `equalProjectDir` 大小写不敏感的平台语义**（`discovery.ts:31-33`）：`toLowerCase` 比较在 Linux（大小写敏感 FS）上可能把两个仅大小写不同的工程目录判为同一。MVP 承诺 Windows（测试计划 §2.2），且需同机 `~/.uemcp/bridges/` 下恰有两个此类记录才触发，风险极低。记录为跨平台观察项。

### 遗留观察（非本轮回归，未在修复范围）

- 上轮 m-3（python `timeoutMs` schema 默认 10s vs Server 强制 ≥30s 语义混乱）未修——行为可用。
- 上轮 m-13（blueprint `{action:"query", save:true}` 的 isWrite=false → 可自动重试且不审计）未修——保存操作幂等性尚可，风险低；与 Bridge 端 `WRITE_ACTIONS={compile}` 口径一致。
- 上轮 m-2（client.ts CONNECT_WINDOW_MS 死分支）未修——无运行时影响。
- 401→`BRIDGE_UNAVAILABLE`（client.ts:142-150）映射正确且 retryable，配合只读方法的自动重试可实现 token 轮换自愈；写方法返回带提示的错误由用户决定重发——语义合理。

### 复审结论

**放行：7 项修复全部通过，无回归，可进入联调。** N-1/N-2/N-3 三个 Minor 不阻断（均无安全影响），建议随下次代码变更顺手清理。遗留观察项（m-3/m-13/m-2）维持上轮定级，不阻塞。

### 复审的未执行验证

- 未重复执行 typecheck/build/smoke（主管已复跑 71/71，本轮纯静态复核）。
- 限流的突发行为（40 突发后第 41 个 429）依赖 smoke 断言，未实际压测复核。
- `--project` 硬失败路径未构造实测（静态推演：`return null` 三处出口均在来源 3/4 代码之前）。
- 0600 在 Windows 的 ACL 近似效果未实测（Node 在 Windows 将 0o600 映射为受限 ACL，注释已声明近似语义）。
- elicitation 分支（approved/declined）仍无运行时验证（README-DEV §7 既有声明不变）。
