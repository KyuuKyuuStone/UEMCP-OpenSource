# UEMCP MVP 测试计划与验收标准

| 项 | 值 |
|---|---|
| 文档版本 | **0.1.1（2026-10-20）——测试计划阶段，全部用例【未执行】** |
| 依据 | 《UEMCP 架构设计与工具清单》**v0.2.0**（`Docs/UEMCP-架构设计.md`，下称「架构文档」；裁决已合并入 v0.2.0）、《UEMCP README 与接入指南（草稿）》（`Docs/UEMCP-README草稿.md`，下称「README」）、《UEMCP 架构裁决补充》v0.1.1（`Docs/UEMCP-架构裁决补充.md`，下称「裁决补充」，仅作决策记录） |
| 状态说明 | **当前项目代码尚未实现**（README V1），本计划只定义测试范围、用例与判定标准，不包含任何执行结果。凡本文描述的预期行为均为设计目标，实测前不构成操作保证。 |

## 变更记录（v0.1.0 → v0.1.1）

按裁决补充 §0 七项裁决更新，未改变「全部未执行」事实：

| 裁决 | 结论摘要 | 受影响用例 |
|---|---|---|
| D1 工具级错误码统一映射 | 工具失败一律 HTTP 200 + `isError:true` + `structuredContent.error`；`TIMEOUT` 退役 | TOOL-10/11/15/19/22/23/25/31、SEC-11、RES-03/10 |
| D1b `INVALID_ARGUMENT` 二义消除 | 协议层改名 `INVALID_PARAMS`（400/-32602）；工具层固定 200 + `isError` | PROTO-12；新增 PROTO-12b/12c |
| D2 SSE 最低客户端基线 | Cursor 0.45.11 + 仓库自研脚本 `examples/generic/sse_client.py` 双基线，脚本必测 | PROTO-14、CLIENT-05；附录新增 A.4 |
| D6 双重权限门错误码 | 按拒绝位置区分：`TOOL_DISABLED`（Server 未注册）/ `PERMISSION_DENIED`（桥接写/console 门）/ `EXEC_DISABLED`（桥接 exec 门） | SEC-11；新增 SEC-11b/11c；TOOL-31 |
| D10 MCP Server 端口冲突 | Server fail-fast：exit code 2，不换端口；桥接端 18778–18788 回退 | RES-06/07 |
| D11 `--allow-destructive` 范围 | 只豁免 P1 破坏性操作；P2 由 `--allow-console`/`--allow-exec` 兼作策略级确认 | TOOL-30/32、SEC-09/10；新增 SEC-15/16 |
| D12 read-only 下混合工具 | 注册但 inputSchema 收窄；read-only 共 7 个工具 | PROTO-03、SEC-01 |

主管另行判定并已写入用例：D3（截图判定 → TOOL-24/26）、D5（压测降 P2 选测 → PROTO-09/SEC-14）、D7（超时用例环境受限可标未测 → TOOL-19）、D8（接受 A8 降级 → TOOL-10）、D9（允许 ACL 模拟 → SEC-13）。D4（TTL 测试参数）转实现方 → PROTO-08 保留并标注依赖条件。

并入修正（架构文档 v0.2.0 对齐）：TOOL-05 (c) 类过滤失败错误码由 `INVALID_ARGUMENT` 修正为 `CLASS_NOT_FOUND`（工具层 HTTP 200 + `isError:true`，`details.className` 必填）。

v0.1.1 小修：依据版本统一为架构文档 v0.2.0（2026-10-20）。

---

## 1. 测试范围与不在范围

### 1.1 测试范围（依据架构文档 §1.3 MVP 边界清单）

| 能力域 | 范围 | 依据 |
|---|---|---|
| MCP 协议一致性 | `initialize` / `tools/list` / `tools/call` / 会话管理（TTL、上限、DELETE）/ 通知 202 / 错误模型 / 协议版本协商 | §2.9、§3.3、§3.6 |
| 传输层 | Streamable HTTP（`POST/GET/DELETE /mcp`）、旧版 SSE（`/sse` + `/messages`）、stdio 三种传输；三种传输共享同一工具实现 | §3.1–§3.4 |
| 工具功能（10 个） | `ue_editor_status`、`ue_actor_query`、`ue_actor_edit`、`ue_level_control`、`ue_asset_search`、`ue_material_params`、`ue_viewport_capture`、`ue_console_command`、`ue_python_exec`、`ue_blueprint` 的正常、边界、异常路径 | §5.1–§5.10 |
| 策略与安全 | read-only / standard / full 三策略过滤、隐藏工具与 `TOOL_DISABLED`、破坏性确认（elicitation / `--allow-destructive`）、回环绑定、Host/Origin 校验、桥接 token、审计日志 | §5.0.3、§5.11、§6 |
| 故障恢复 | Bridge 不可达、发现文件陈旧、端口冲突、编辑器正常退出/强杀后的文件清理、token 轮换 | §2.4、§6.6 |
| 客户端兼容性 | Claude Code（HTTP + stdio）、Cursor（HTTP + SSE）、通用 curl 序列；§1.4 的编辑器操作闭环脚本 | §3.5、§1.4 |
| 环境与分发前提 | 插件安装后发现文件自动生成（假设 A1）、`npx` 运行方式 | §8.4、§10.4 |

### 1.2 不在范围（与 MVP 边界一致，依据 §1.2、§1.3、§1.2-2）

以下内容**不设计用例**；若实测中出现相关行为，一律按「超出 MVP 承诺」记录为观察项，不作为失败：

- PIE 内的 Actor 操作；编辑器 UI/Slate 截图；蓝图节点创建/连线/变量增删；动画蓝图编辑（§1.3）。
- 控制台输出回读（MVP 明确 `outputAvailable:false`，§1.2-8、§5.8）。
- 资产导入/导出、重命名/移动、重定向器修复；Source Control；打包构建（§1.2-7）。
- 远程/多机部署、`0.0.0.0` 监听、多租户（§1.2-3、§6.2）。
- 打包后的运行时游戏（Shipping 包内无 Python，§1.2-2）。
- Python 沙箱与执行中断能力（§1.2-4、§2.6）。
- 性能压测（除 §9.1 规定的「100 次连续调用平均 < 100ms」外，不设吞吐指标）；WebSocket 传输（18779 为 P2 预留，§2.7）。
- macOS/Linux（README C1 待架构师确认，Windows 之外平台仅冒烟不设验收）。

### 1.3 本阶段交付边界

- 本文档为**测试计划**：用例均未执行，无通过/失败结论。
- 执行前提全部满足（见 §7 解除阻塞条件）后，按 §4 用例清单逐条执行并回填结论。

---

## 2. 测试环境矩阵

### 2.1 环境要求

| 项 | 要求 | 备注 | 依据 |
|---|---|---|---|
| 操作系统 | Windows 11（验证机：Windows 11 Pro 10.0.26200） | 跨平台承诺待 README C1 | §7.6 |
| 引擎 | UE 5.4.4（Epic Games Launcher 安装） | 不承诺任意版本 | §8.2 |
| 样例工程 | `C:/UE5_P/5.4/XQHCPP_54`（含至少 1 个关卡、若干静态网格 Actor、1 个 `MaterialInstanceConstant`、1 个蓝图资产） | 工程内容不足时需先造数 | §1.4 |
| UE 插件 | `UEMCPBridge` 复制到 `<Project>/Plugins/UEMCPBridge`；启用 Python Editor Script Plugin（引擎自带 Experimental） | 无需编译 | §4.1、§4.4 |
| Node.js | ≥ 20（`node --version` 输出 v20.x 或 v22.x；CI 覆盖 20 与 22） | `npx` 可用 | §7.3 |
| MCP Server | `npx -y @uemcp/server --transport http --policy <mode>` 运行于 `127.0.0.1:18777` | 包未发布前该命令不可运行（README V1） | §10.4-5 |
| 桥接 | 编辑器内自动启动，`127.0.0.1:18778`，默认只读 | 依赖假设 A1 | §4.4、§8.4 |
| curl | Git Bash 自带 curl（bash 语法；Windows PowerShell 引号语义不同，README §5.4 建议在 Git Bash/WSL 执行） | 所有 curl 用例在 Git Bash 中执行 | README §5.4 |
| 客户端 | Claude Code（当前稳定版）、Cursor（当前稳定版） | 版本基线待裁决（D2） | §3.5 |

### 2.2 执行前提编码（用例「前提」列引用）

| 编码 | 前提 |
|---|---|
| E0 | 仅 Node + MCP Server 可运行；**无需 UE 编辑器**。用于协议层用例（工具调用类用例此时预期 `BRIDGE_UNAVAILABLE`） |
| E1 | E0 + UE 5.4.4 编辑器已打开样例工程，插件已启用且发现文件已生成（RES-01 通过） |
| E2 | E1 + 特定服务端/桥接开关组合，在用例中显式列出（如 `--policy standard`、`--allow-destructive`、桥接 `allowExec=true`） |
| E3 | E1 + 对应 MCP 客户端已安装并配置接入（§3.5） |
| E4 | E1 + 造数完成（样例关卡含已知 Actor 集合、MIC、蓝图；见各用例） |

### 2.3 通用准备与恢复

- 每轮执行前清空/备份 `~/.uemcp/`（发现文件与审计目录），记录 Node/UE 版本号到执行报告。
- 写操作用例使用独立测试关卡 `L_TestUEMCP`（新建），执行后删除该关卡资产，避免污染样例工程。
- 所有 curl 用例的 JSON 体不含中文，避免控制台编码问题（本机控制台 GBK）。

---

## 3. 测试分层

| 层 | 目标 | 覆盖内容 | 用例前缀 | 主要依赖 |
|---|---|---|---|---|
| L1 协议一致性 | MCP 契约可被任意客户端依赖 | initialize/会话/tools 三方法、错误模型（§2.9 全表可触发子集）、SSE/stdio 传输行为、协议版本协商 | PROTO | E0 为主 |
| L2 工具功能 | 10 个工具行为符合 §5 Schema | 每个工具的正常路径、参数边界（maxItems/maxLength/enum）、异常路径（对象不存在、类型不符、PIE 守卫） | TOOL | E1/E2/E4 |
| L3 安全 | §6 安全模型逐条可验证 | 策略过滤、隐藏工具、确认流、回环/Host/Origin、token、审计内容红线 | SEC | E0/E1/E2 |
| L4 故障恢复 | 失败不扩散、状态可自愈 | BRIDGE_UNAVAILABLE、陈旧发现文件、端口冲突、文件清理、token 轮换 | RES | E0/E1 |
| L5 客户端兼容性 | 三类客户端接入承诺兑现 | Claude Code、Cursor、curl；§1.4 闭环脚本 | CLIENT | E3 |

执行顺序约束：RES-01（发现文件生成）必须最先执行，其后 E1 类用例方可运行；PROTO/SEC 的 E0 类用例可在无编辑器时先行。

---

## 4. 用例清单

> 格式说明：每条用例含 用例ID、优先级（P0/P1/P2）、前提、步骤、预期结果、判定标准、依据章节。**当前全部为【未执行】**。
> 「判定标准」为可观察条件；全部满足 = 通过，任一不满足 = 失败（除非 §5.3 缺陷分级判为 Minor 且主管豁免）。

### 4.1 L1 协议一致性（PROTO）

#### PROTO-01 initialize 创建会话并返回服务端信息 【P0】
- 前提：E0；`npx -y @uemcp/server --transport http --policy standard`
- 步骤：执行附录 A.1 第 1 步（POST `/mcp` initialize，`protocolVersion: "2025-06-18"`）。
- 预期：HTTP 200；响应头含 `Mcp-Session-Id`，值为 UUID 格式；响应体 `result.protocolVersion` ∈ {`2025-06-18`,`2025-03-26`,`2024-11-05`}；`result.serverInfo.name` 非空；会话数 `/health` 的 `sessions` 增加 1。
- 判定：以上 5 项全部成立。
- 依据：§3.3（会话 ID 用 `crypto.randomUUID()`）、§3.3 健康检查。

#### PROTO-02 initialized 通知返回 202 无 body 【P0】
- 前提：E0，已取得会话 ID（PROTO-01）。
- 步骤：附录 A.1 第 2 步，POST `notifications/initialized`（无 id），用 `-w "%{http_code}"` 取状态码。
- 预期：HTTP 202；响应 body 为空。
- 判定：状态码 == 202 且 body 长度 0。
- 依据：§3.3「notifications/initialized、通知、响应：返回 202 Accepted，无 body」。

#### PROTO-03 tools/list 工具集合与策略矩阵一致 【P0】
- 前提：E0；分别以五种启动组合启动 Server 并各自完成 initialize：① `--policy read-only`；② `--policy standard`；③ `--policy full`（无 P2 开关）；④ `--policy full --allow-console`；⑤ `--policy full --allow-console --allow-exec`。
- 步骤：附录 A.1 第 3 步 tools/list，解析 `result.tools[].name`、各工具 `inputSchema` 与 `annotations`。
- 预期（裁决补充 §8.1/§8.2，D12）：
  - 工具名集合**完全相等**（集合比对，禁止用「包含」代替）：① 恰为 **7** 个 {`ue_editor_status`,`ue_actor_query`,`ue_asset_search`,`ue_viewport_capture`,`ue_level_control`,`ue_material_params`,`ue_blueprint`}；② 恰为 **8** 个（① ∪ {`ue_actor_edit`}）；③ 恰为 **8** 个（P2 未开开关不出现）；④ 恰为 **9** 个（③ ∪ {`ue_console_command`}）；⑤ 恰为 **10** 个。
  - read-only 下三个混合工具的 `inputSchema.properties.action.enum` 收窄为：`ue_level_control` == `["get_current","list_dirty"]`、`ue_material_params` == `["list","get"]`、`ue_blueprint` == `["query"]`；且这三个工具 `annotations.readOnlyHint == true`、`destructiveHint == false`。
  - standard/full 组合下混合工具 `readOnlyHint == false`；每个工具均含 `inputSchema`；`ue_editor_status` 的 annotations 符合 §5.0.4（readOnlyHint=true 恒定）。
- 判定：五组集合相等断言、收窄断言、readOnlyHint 断言全部成立。
- 依据：裁决补充 §8（D12）、§5.11、§5.0.3、§5.0.4。
- 【未执行】

#### PROTO-04 tools/call 成功返回封装 【P0】
- 前提：E1（standard 策略）。
- 步骤：tools/call `ue_editor_status`，检查响应结构。
- 预期：HTTP 200；`result.isError` 为 false 或缺省；`result.structuredContent.ok` == true；`result.structuredContent.data` 含 `editor`/`level`/`selection`/`capabilities` 键；`structuredContent.meta.requestId`、`durationMs`、`ueVersion` 存在；`content[0].type == "text"`。
- 判定：以上结构字段全部存在且 `ok==true`。
- 依据：§5.0.1 返回封装。

#### PROTO-05 非初始化请求缺少会话头 → 400 【P0】
- 前提：E0。
- 步骤：POST `/mcp` tools/list，不带 `Mcp-Session-Id`。
- 预期：HTTP 400。
- 判定：状态码 == 400。
- 依据：§3.3「初始化之外的请求缺少 Mcp-Session-Id：400」。

#### PROTO-06 未知/过期会话 → 404 + -32001 【P0】
- 前提：E0。
- 步骤：POST `/mcp` tools/list，带 `Mcp-Session-Id: 00000000-0000-0000-0000-000000000000`。
- 预期：HTTP 404；body 为 JSON-RPC error，`error.code` == -32001，message 含 `Session not found`。
- 判定：状态码与 error.code 均符合。
- 依据：§3.3「未知/过期会话：404 + JSON-RPC error -32001」。

#### PROTO-07 DELETE /mcp 终止会话 【P1】
- 前提：E0，已建会话。
- 步骤：DELETE `/mcp`（带会话头）→ 再用同一会话 POST tools/list。
- 预期：DELETE 返回 204；后续 POST 返回 404 + -32001。
- 判定：两步状态码均符合。
- 依据：§3.3 DELETE 行为。

#### PROTO-08 会话空闲 TTL 过期 【P1】
- 前提：E0；TTL 缩短方式**依赖实现提供测试参数**（如启动参数/环境变量覆盖 TTL，主管判定 D4 转实现方：实现未提供时，本用例按 30 分钟真实等待执行或标注【未测】）。
- 步骤：建会话后空闲超过 TTL（构造方式见 D4 裁决结果），再 POST tools/list。
- 预期：HTTP 404 + -32001。
- 判定：状态码与 error.code 符合。
- 依据：§3.3「TTL 30 分钟空闲；每 60s 清扫」。
- 【未执行】

#### PROTO-09 会话数上限 32，超限 429 【P2】
- 前提：E0；需要脚本并发建立 33 个会话。
- 步骤：循环 initialize 33 次（各自独立会话），记录第 33 次响应。
- 预期：前 32 次 200；第 33 次 HTTP 429。
- 判定：第 33 次状态码 == 429。
- 依据：§3.3「上限 32 个并发会话；超限返回 429」。
- 【未执行】（是否纳入必测见裁决 D5）

#### PROTO-10 非法 JSON → PARSE_ERROR 400/-32700 【P0】
- 前提：E0。
- 步骤：POST `/mcp`，body 为 `{invalid`。
- 预期：HTTP 400；JSON-RPC error `code` == -32700。
- 判定：状态码与 error.code 符合。
- 依据：§2.9 错误码表。

#### PROTO-11 未知 method → METHOD_NOT_FOUND 【P0】
- 前提：E0，有效会话。
- 步骤：POST `/mcp` `{"jsonrpc":"2.0","id":9,"method":"foo/bar","params":{}}`。
- 预期：HTTP 404；error.code == -32601。
- 判定：状态码与 error.code 符合。
- 依据：§2.9（`METHOD_NOT_FOUND` 404/-32601）。

#### PROTO-12 工具层参数校验失败 → 200 + isError + INVALID_ARGUMENT 【P0】
- 前提：E1（standard）；请求已成功路由到已注册工具。
- 步骤：tools/call `ue_editor_status`，`arguments: {"sections":["不存在的section"]}`（违反 enum）。
- 预期（裁决补充 §3.5，固定唯一形态，禁止多选）：HTTP **200**；响应**无顶层 JSON-RPC `error`**；`result.isError == true`；`result.structuredContent.ok == false`；`result.structuredContent.error.code == "INVALID_ARGUMENT"`；`error.details.issues` 为数组且非空（每项含 `path`/`code`/`message`）；`content[0].text` 以 `"INVALID_ARGUMENT: "` 开头。
- 判定：以上全部成立；**出现 HTTP 400 或顶层 `error` 即失败**（协议层不得使用 `INVALID_ARGUMENT`，裁决补充 §11-3）。
- 依据：裁决补充 §3.1/§3.5（D1b）、§2.5 details 契约。
- 【未执行】

#### PROTO-12b tools/call 信封错误（arguments 为数组）→ 协议层 INVALID_PARAMS 【P0】
- 前提：E0，有效会话（PROTO-01）。
- 步骤：POST `/mcp` tools/call，`params: {"name":"ue_editor_status","arguments":["not","an","object"]}`。
- 预期：HTTP **400**；顶层 JSON-RPC `error.code == -32602`；`error.data.errorCode == "INVALID_PARAMS"`；无 `result`、无 `isError` 字段。
- 判定：HTTP 状态、-32602、字符串码三者均符合。
- 依据：裁决补充 §3.1/§1.6（D1b）。
- 【未执行】

#### PROTO-12c tools/call 未知工具名 → 协议层 INVALID_PARAMS 【P0】
- 前提：E0，有效会话。
- 步骤：tools/call，`name: "ue_no_such_tool"`（不在完整 10 工具目录中）。
- 预期：HTTP **400**；顶层 `error.code == -32602`、`error.data.errorCode == "INVALID_PARAMS"`。
- 判定：符合。**边界**：完整目录内但被策略隐藏的工具名（如 read-only 下调用 `ue_actor_edit`）**不属于**本用例——按裁决补充 §3.3 应返回 200 + `TOOL_DISABLED`（见 SEC-01 (b)）。
- 依据：裁决补充 §3.3（工具存在性按完整工具目录判断）。
- 【未执行】

#### PROTO-13 GET /mcp 建立服务端 SSE 流 【P1】
- 前提：E0，有效会话。
- 步骤：`curl -N -D - --max-time 5` GET `/mcp`（带会话头与 `Accept: text/event-stream`）。
- 预期：响应 `Content-Type` 含 `text/event-stream`；连接在 --max-time 内保持打开（curl 以超时退出属预期，退出码 28）；期间无 HTTP 错误状态。
- 判定：Content-Type 正确且未返回 4xx/5xx。
- 依据：§3.3 GET `/mcp` 行为。

#### PROTO-14 旧版 SSE 端点完成一次工具调用（脚本基线） 【P1】
- 前提：E1；仓库自研脚本 `examples/generic/sse_client.py`（仅 Python 标准库；规格与退出码语义见裁决补充 §4.2，附录 A.4 给出命令）。
- 步骤：`python examples/generic/sse_client.py --url http://127.0.0.1:18777/sse --expect-tools 8 --timeout 10`（standard 策略下 8 个工具；若以其他策略启动，`--expect-tools` 同步调整为 7/9/10）→ 检查进程退出码与 JSON 摘要输出。
- 预期：退出码 **0**；脚本依序完成——GET `/sse`（`Accept: text/event-stream`）收到 `event: endpoint` 事件 → 解析 `data: /messages?sessionId=...` → POST `initialize`（`protocolVersion:"2024-11-05"`）并在 SSE 流中按 `id` 匹配到响应 → POST `notifications/initialized`（HTTP **202**）→ POST tools/list（工具数 == `--expect-tools`）→ POST tools/call `ue_editor_status`（`result.structuredContent.ok == true`）。
- 判定：退出码 == 0 即通过；退出码 1/2/3/4 分别按裁决补充 §4.2 语义记录（断言失败 / 传输失败 / 超时 / SSE 解析失败）并判失败。
- 依据：裁决补充 §4.1/§4.2/§4.5（D2）、§3.4。

#### PROTO-15 `--disable-legacy-sse` 关闭旧端点 【P1】
- 前提：E0；Server 以 `--transport http --disable-legacy-sse` 启动。
- 步骤：GET `/sse`。
- 预期：HTTP 404。
- 判定：状态码 == 404。
- 依据：§3.4「通过 --disable-legacy-sse 可关闭」。

#### PROTO-16 stdio：stdout 仅 MCP 帧，日志走 stderr 【P1】
- 前提：E0；`npx -y @uemcp/server --transport stdio`，由脚本驱动 stdin/stdout。
- 步骤：向 stdin 依序写 initialize → initialized → tools/list（每行一个 JSON），同时分离捕获 stdout/stderr。
- 预期：stdout 每行均为合法 JSON-RPC 对象（共 3 行响应，无任何非 JSON 行）；stderr 出现至少 1 条 JSON 日志（如 `{"level":...,"event":...}`）；桥接未启动时 initialize 仍成功。
- 判定：stdout 可逐行 `JSON.parse` 且 stderr 含 JSON 日志；工具调用在 E0 下返回 `BRIDGE_UNAVAILABLE` 不令进程退出。
- 依据：§3.2（stdout 只允许 MCP 帧；桥接不可达不阻止 MCP 启动）。
- 【未执行】

#### PROTO-17 协议版本协商 【P1】
- 前提：E0。
- 步骤：分别以 `protocolVersion: "2024-11-05"` 与一个未来版本 `"2999-01-01"` 发送 initialize。
- 预期：2024-11-05 请求 → 响应 `result.protocolVersion == "2024-11-05"`；未来版本 → 响应返回服务端支持的版本（∈ 三版本表），不报错中断。
- 判定：响应版本 ∈ {2025-06-18, 2025-03-26, 2024-11-05} 且与协商规则一致。
- 依据：§3.6。

### 4.2 L2 工具功能（TOOL）

#### 4.2.1 ue_editor_status（§5.1）

#### TOOL-01 正常返回四段数据 【P0】
- 前提：E1/E4（standard）。
- 步骤：tools/call `ue_editor_status`，默认参数。
- 预期：`data.editor.ueVersion` 以 `5.4` 开头；`data.level.path` 非空且等于样例关卡路径；`data.selection.count` ≥ 0；`data.capabilities.python == true`；`data.policies.mode == "standard"`。
- 判定：上述字段存在且值符合。
- 依据：§5.1 出参 Schema、§8.5-5。

#### TOOL-02 sections 参数过滤输出 【P2】
- 前提：E1。
- 步骤：tools/call，`sections: ["editor"]`。
- 预期：`data` 仅含 `editor` 键（或其余键为空/缺省——以实际行为记录）；HTTP 200 且 `ok==true`。
- 判定：`editor.ueVersion` 存在且无 selection 数据。
- 依据：§5.1 入参 `sections`。

#### 4.2.2 ue_actor_query（§5.2）

#### TOOL-03 scope=level 全量查询 【P0】
- 前提：E4：测试关卡内预先放置 3 个 StaticMeshActor。
- 步骤：tools/call `ue_actor_query`，`{"scope":"level","limit":50}`。
- 预期：`data.total` ≥ 3；`data.returned` == `data.actors.length`；每个 actor 含 `actorPath`/`name`/`class`（ActorRef 必填字段）；`truncated` 为布尔值。
- 判定：total/returned/actors.length 三者关系成立且必填字段齐全。
- 依据：§5.2 出参 required、§8.5-6。

#### TOOL-04 分页与排序 【P0】
- 前提：E4（同上，≥3 个 Actor）。
- 步骤：两次调用：`{"scope":"level","limit":2,"offset":0,"sortBy":"name"}` 与 `{"scope":"level","limit":2,"offset":2,"sortBy":"name"}`。
- 预期：两次结果 `actors` 无重复路径；两批并集的按 name 排序顺序与 `total` 数量一致；第二批 `returned` == total-2（当 total≥3）。
- 判定：无重复且 offset 生效。
- 依据：§5.2（排序在过滤后、分页前执行）、§8.5-6「分页与过滤正确」。

#### TOOL-05 过滤与无效类名 【P1】
- 前提：E4（同上）。
- 步骤：三次调用：(a) `filter.class="StaticMeshActor"`；(b) `filter.nameContains="<已知Actor名子串>"`；(c) `filter.class="NoSuchClassXYZ"`。
- 预期：(a)(b) 返回子集且每个 actor 类名/名称匹配过滤条件；(c) HTTP 200 + `isError==true`，`structuredContent.error.code == "CLASS_NOT_FOUND"`，`error.details.className == "NoSuchClassXYZ"`（架构文档 v0.2.0 按 D1 对齐：类名无法解析为工具级 `CLASS_NOT_FOUND`，不再使用 `INVALID_ARGUMENT`）。
- 判定：(a)(b) 结果集是全量的子集；(c) 错误码 == CLASS_NOT_FOUND 且 `details.className` 符合。
- 依据：§5.2、架构文档 v0.2.0、裁决补充 §2.4/§2.5（D1）。

#### 4.2.3 ue_actor_edit（§5.3）

#### TOOL-06 dryRun 不改变场景 【P0】
- 前提：E4（standard）。
- 步骤：记录当前 `actor_query` total → tools/call `ue_actor_edit`，operations 为 1 个 spawn，`dryRun:true` → 再次 `actor_query` 取 total。
- 预期：两次 total 相等；返回 `data.dryRun==true` 且 `results[0]` 含预计 `created` 描述；场景中无新 Actor。
- 判定：total 前后不变且 dryRun 标记正确。
- 依据：§5.3 dryRun 定义、§8.5-7。

#### TOOL-07 spawn 后查询可见 【P0】
- 前提：E4（standard）。
- 步骤：`ue_actor_edit` spawn `class:"StaticMeshActor"`、`location:{x:0,y:0,z:100}`、`label:"UEMCP_T_Spawn1"` → `ue_actor_query` `filter.labelContains:"UEMCP_T_Spawn1"`。
- 预期：edit 返回 `results[0].ok==true` 且 `created[0].name` 非空；query 返回恰好 1 个 Actor，其 transform.location.z ≈ 100。
- 判定：两步结果均符合。
- 依据：§5.3 spawn、§8.5-7「真实 spawn 后可在关卡中看到」。

#### TOOL-08 set_transform 读回一致 【P0】
- 前提：E4 + 已存在 TOOL-07 创建的 Actor。
- 步骤：`ue_actor_edit` `set_transform` selector={kind:"label",value:"UEMCP_T_Spawn1"}，`location:{x:200,y:300,z:400}` → `ue_actor_query` 读回 transform。
- 预期：读回 location 各分量与设定值一致（浮点容差 ±0.01）。
- 判定：三轴分量误差在容差内。
- 依据：§5.3 set_transform、§1.4 闭环要求。

#### TOOL-09 duplicate 按 offset 复制 【P1】
- 前提：E4 + 目标 Actor。
- 步骤：`duplicate`，`count:3`，`offset:{x:100,y:0,z:0}`。
- 预期：返回 `created` 数组长度 3；query 中出现 3 个新 Actor，label 均带 `labelSuffix`（默认 `_copy`），x 坐标依次 +100。
- 判定：数量、后缀、坐标增量均符合。
- 依据：§5.3 duplicate 入参。

#### TOOL-10 atomic 失败回滚（假设 A8） 【P1】
- 前提：E4（standard + `--allow-destructive`）；桥接 `allowWrite=true`。
- 步骤：一次调用传 2 个 operation：op1 spawn 合法 Actor、op2 set_transform selector 指向不存在 Actor（预期 `ACTOR_NOT_FOUND`）→ 失败后 `actor_query` 检查 op1 的产物。
- 预期：op2 失败表现为工具层错误（HTTP 200 + `isError==true`；op2 选择器不存在的错误码为 `ACTOR_NOT_FOUND`，若整体事务取消则以 `TRANSACTION_FAILED` 收敛，其 `error.details.rolledBack` 为布尔值且 `details.reason` 存在，裁决补充 §2.5）；`summary.failed ≥ 1`；主分支下 `summary.rolledBack==true` 且 op1 产生的 Actor **不存在**于场景（事务已取消）。
- 判定（主管判定 D8：接受 A8 降级）：主分支 `rolledBack==true` 且场景无残留 = 通过；若实测 `rolledBack==false` 且场景残留，按架构文档 A8 既定备选接受降级——判定为「通过（降级）」，但必须同时满足：返回 `warnings[]` 非空、`details.rolledBack==false` 与场景实际一致、报告记录「A8 结论 = 失败方案启用」。两者之外的形态 = 失败。
- 依据：§5.3 事务边界、§8.4 A8、裁决补充 §2.4/§2.5（D1）。
- 【未执行】

#### TOOL-11 选择器歧义 → AMBIGUOUS_SELECTOR 【P1】
- 前提：E4：场景中存在 ≥2 个同 label Actor（用 duplicate count=2 造数，手动改同名）。
- 步骤：`set_transform`，selector={kind:"label", value:"<重复label>"}。
- 预期：HTTP **200**（工具层，无顶层 `error`）；`isError==true`；`error.code == "AMBIGUOUS_SELECTOR"`；`error.details.selector` == `{kind:"label",value:"<重复label>"}`；`details.matches` 为数组且**长度 ≥2**（每项含 `actorPath`/`name`/`label`/`class`）。
- 判定：HTTP 200 + 错误码 + `matches.length ≥ 2` 全部成立。
- 依据：§5.3 选择器解析规则、裁决补充 §2.4/§2.5（D1）。
- 【未执行】

#### TOOL-12 set_properties 白名单外属性拒绝 【P2】
- 前提：E4 + 目标 Actor（standard）。
- 步骤：`set_properties`，properties 传白名单外键（如 `{"bCanBeDamaged":true}`——该键不在 §5.3 白名单 enum 中，Schema `additionalProperties:false` 应先拒）。
- 预期：arguments 的 zod 校验（工具层）返回 HTTP 200 + `isError==true` + `INVALID_ARGUMENT`（additionalProperties 拒收，`details.issues` 非空，裁决补充 §3.3）；若绕过 Schema 直达 handler，则 handler 二次校验返回明确拒绝并提示使用 `ue_python_exec`。两种形态均记录。
- 判定：非 2xx 或 isError==true，且错误信息含「白名单/whitelist/ue_python_exec」之一。
- 依据：§5.3「set_properties 只允许白名单；其余属性明确拒绝」。
- 【未执行】

#### 4.2.4 ue_level_control（§5.4）

#### TOOL-13 get_current 与 list_dirty 【P0】
- 前提：E1（standard，已打开样例关卡）。
- 步骤：(a) `action:"get_current"`；(b) `action:"list_dirty"`。
- 预期：(a) `data.path`/`name` 非空，`isDirty` 为布尔；(b) `data.packages` 为数组，每项含 `path`/`isMap`。
- 判定：两调用的必填字段存在。
- 依据：§5.4 出参、§8.5-8。

#### TOOL-14 save_current 后脏包下降 【P0】
- 前提：E4 + 场景有未保存修改（由 TOOL-07 spawn 产生）。
- 步骤：`list_dirty` 记录 N → `save_current` → `list_dirty` 再查。
- 预期：save 返回 `saved==true`；第二次 dirty 包含数 < N（或当前关卡不再是脏包）。
- 判定：脏包计数下降。
- 依据：§5.4、§8.5-8「save 后脏包数量下降」。
- 【未执行】（save 是写盘操作，执行后需清理测试关卡）

#### TOOL-15 有脏包时 open 的固定拒绝顺序 【P1】
- 前提：E4：场景脏 + 存在第二个关卡 `/Game/Maps/L_TestUEMCP_B`。
- 步骤：(a) `action:"open"`, `levelPath:"/Game/Maps/L_TestUEMCP_B"`（不带 allowDiscardUnsaved/confirm）；(b) 同参数加 `allowDiscardUnsaved:true, confirm:false`；(c) 先 `list_dirty` 确认脏包。
- 预期（裁决补充 §2.6 固定顺序）：(a) HTTP 200 + `isError==true`，`error.code == "UNSAVED_CHANGES"`，`details.dirtyPackages` 为非空字符串数组；(b) `error.code == "CONFIRMATION_REQUIRED"`；(c) 两步之后当前关卡均未切换（`get_current` 验证）；无脏包时 open 直接执行（作为 (d) 附加验证：save 后重复 (a)，预期成功打开）。
- 判定：三态与固定顺序全部符合——`UNSAVED_CHANGES`（未允许丢弃）→ `CONFIRMATION_REQUIRED`（已允许丢弃但未确认）→ 执行打开（已确认或无脏包）。
- 依据：§5.4 确认要求、裁决补充 §2.6（D1）、§8.5-7。
- 【未执行】

#### TOOL-16 new + open 正常路径 【P1】
- 前提：E4（standard + `--allow-destructive`，无脏包——先 save）。
- 步骤：`action:"new"`, `levelPath:"/Game/Maps/L_TestUEMCP_Tmp"` → `get_current` → `action:"open"` 回原关卡。
- 预期：new 后 `get_current` 返回新路径；open 后返回原关卡路径；两步均 `ok==true`。
- 判定：路径切换正确。
- 依据：§5.4。
- 【未执行】

#### 4.2.5 ue_asset_search（§5.5）

#### TOOL-17 /Game 基础搜索 【P0】
- 前提：E1（standard，AssetRegistry 就绪——`ue_editor_status` 的 `isAssetRegistryLoading==false`）。
- 步骤：`{"query":"<样例工程已知资产名子串>","path":"/Game"}`。
- 预期：`data.total` ≥ 1；每个资产含 `packageName`/`objectPath`/`assetName`/`class`（AssetRef 必填）；默认不含 Redirector（`includeRedirectors=false`）。
- 判定：total≥1 且必填字段齐全。
- 依据：§5.5、§8.5-9。

#### TOOL-18 分页与类过滤 【P0】
- 前提：E1。
- 步骤：`{"query":"","path":"/Game","classNames":["MaterialInstanceConstant"],"limit":10,"offset":0}` 与 `limit:10,"offset":10`。
- 预期：两批无重复 packageName；每项 `class` 含 `MaterialInstanceConstant`；`limit` 被尊重。
- 判定：无重复且类过滤生效。
- 依据：§5.5。

#### TOOL-19 依赖与反向引用（假设 A4）及超时/注册表降级 【P1】
- 前提：E4：存在已知依赖对（MIC 依赖其父材质）。
- 步骤：(a) `{"query":"<MIC名>","includeDependencies":true,"includeReferencers":true}`；(b) 变体一（`SEARCH_TIMEOUT`，主管判定 D7：**样例工程资产量不足时环境受限，可标注【未测】**，不得写成通过）：以最大范围构造慢查询（如 `path:"/"`、`recursive:true`、深度 BFS 组合），观察是否在 20s 超时；(c) 变体二（`ASSET_REGISTRY_UNAVAILABLE`）：在 `ue_editor_status` 显示 `isAssetRegistryLoading==true` 的启动窗口期内调用搜索。
- 预期：(a) HTTP 200，`data.dependencies[<package>]` 数组含父材质包名，无 `PYTHON_ERROR`/`INTERNAL`（A4 参数形式若不成立，记录实际异常作为 A4 结论）；(b) 若触发：HTTP 200 + `isError==true` + `error.code=="SEARCH_TIMEOUT"` + `retryable==true` + `details.timeoutMs` 存在且 `details.partial` 为对象（可为空，裁决补充 §2.5）；(c) 若触发：`error.code=="ASSET_REGISTRY_UNAVAILABLE"` + `retryable==true` + `details.loading==true`。
- 判定：(a) 必测；依赖非空且含预期父材质；(b)(c) 触发时按上述 details 断言判定，未触发或环境不足时标注【未测】并写明原因。
- 依据：§5.5 实现要点、§8.4 A4、§8.5-9、裁决补充 §2.4/§2.5（D1）。

#### 4.2.6 ue_material_params（§5.6）

#### TOOL-20 list/get 参数 【P0】
- 前提：E4：存在含标量参数 `Param1` 的 MIC `/Game/Materials/MI_Test`。
- 步骤：(a) `action:"list"`, `instancePath`；(b) `action:"get"`, `parameterNames:["Param1"]`。
- 预期：(a) `parameters` 数组含 scalar 类型项，名称含 `Param1`；(b) 返回该参数当前值与 `editable` 字段。
- 判定：参数名出现在 list 且 get 返回值。
- 依据：§5.6、§8.5-10。

#### TOOL-21 set 后读回一致 【P0】
- 前提：E4（standard）+ 同上 MIC。
- 步骤：`action:"set"`, `parameters:[{"name":"Param1","type":"scalar","value":0.75}]` → `action:"get"` 读回。
- 预期：set 返回 `ok==true`；读回值 == 0.75（浮点容差 1e-4）。
- 判定：读回一致。
- 依据：§5.6、§8.5-10「设置并读回一致」。

#### TOOL-22 对基础材质 set → NOT_AN_INSTANCE 【P1】
- 前提：E4：父材质 `/Game/Materials/M_Test`（非实例）。
- 步骤：`action:"set"`, `materialPath:<父材质>`, parameters 一项。
- 预期：HTTP **200**（工具层）；`isError==true`；`error.code == "NOT_AN_INSTANCE"`；`error.details.path` == 父材质路径且 `details.actualClass` 存在（含实际类名字符串）。
- 判定：HTTP 200 + 错误码 + `details.path`/`details.actualClass` 齐全。
- 依据：§5.6、裁决补充 §2.4/§2.5（D1）。
- 【未执行】

#### TOOL-23 create_instance 与 ALREADY_EXISTS 【P1】
- 前提：E4（standard）。
- 步骤：(a) `create_instance` 新路径；(b) 重复同路径调用。
- 预期：(a) `created==true`，资产存在（asset_search 可查到）；(b) HTTP 200 + `isError==true`，`error.code == "ALREADY_EXISTS"`，`error.details.path` == 重复创建的目标路径。
- 判定：两步均符合。
- 依据：§5.6 create_instance、ALREADY_EXISTS 检查。
- 【未执行】（创建后需清理资产）

#### 4.2.7 ue_viewport_capture（§5.7）

#### TOOL-24 level_viewport PNG 截图 【P0】
- 前提：E1/E4；输出目录 `<Project>/Saved/UEMCP/captures/` 可写。
- 步骤：`{"target":"level_viewport","width":640,"height":480,"format":"png","returnMode":"file"}`。
- 预期：`ok==true`；`data.path` 指向的文件存在且大小 > 0；`data.width==640`、`data.height==480`、`format=="png"`；PNG 文件头（前 8 字节）为 `\x89PNG\r\n\x1a\n`。
- 判定（主管判定 D3）：**通过标准 = 文件存在 + 大小 > 0 + PNG 头 + 尺寸字段正确**；像素非空校验列为观察项，不作为通过判定。
- 依据：§5.7、§8.4 A2、§8.5-11。
- 【未执行】

#### TOOL-25 PIE 截图守卫与成功 【P1】
- 前提：E1。两段执行：(a) PIE 未运行；(b) 手工点击 PIE 运行中。
- 步骤：(a) `{"target":"pie"}`；(b) PIE 运行后同参数再调。
- 预期：(a) HTTP 200 + `isError==true`，`error.code == "PIE_NOT_RUNNING"`，`error.details.target == "pie"`；(b) 成功，文件存在且 PNG 头正确。
- 判定：守卫（错误码 + `details.target`）与成功两段均符合。
- 依据：§5.7（target=pie 要求 game world 非空）、裁决补充 §2.5（D1）、§8.5-11。
- 【未执行】

#### TOOL-26 returnMode=image 内联返回与超限分支 【P2】
- 前提：E1。
- 步骤：(a) `{"width":320,"height":240,"returnMode":"image"}`；(b) 变体（超限）：构造接近 7680×4320 的高复杂度场景截 PNG，观察内联是否超 8 MiB（场景复杂度不足无法触发时标注【未测】）。
- 预期：(a) MCP 响应 `content` 数组含 `{"type":"image","mimeType":"image/png","data":"<base64>"}`；base64 解码后为合法 PNG；`structuredContent.data.bytes` 与解码长度一致；(b) 若触发超限：HTTP **200**（工具层，不得与协议层混淆）+ `isError==false`（成功但有警告）+ `warnings` 含 `IMAGE_TOO_LARGE_FOR_INLINE` 且只返回文件路径；若实现以工具级 `PAYLOAD_TOO_LARGE` 返回，则为 200 + `isError==true` + `error.code=="PAYLOAD_TOO_LARGE"`（裁决补充 §2.4 两形态均符合设计，记录实际；协议层 413 形态见 RES-10 (a)）。
- 判定：(a) image 内容块存在且解码为合法 PNG；(b) 触发时层位断言正确（必有 `result`、HTTP 200）。
- 依据：§5.7 MCP 返回规则、裁决补充 §1.3/§2.4（D1）。
- 【未执行】

#### 4.2.8 ue_blueprint（§5.10）

#### TOOL-27 query 变量与图 【P0】
- 前提：E4：蓝图 `/Game/Blueprints/BP_Test`（含 ≥1 变量、EventGraph）。
- 步骤：`{"action":"query","blueprintPath":"...","include":["parent","variables","graphs","compileState"]}`。
- 预期：`parentClass` 非空；`variables` 含已知变量名；`graphs` 数组含 `EventGraph`（kind=event）；`compileState.status` ∈ 四枚举。
- 判定：四段数据符合。
- 依据：§5.10、§8.4 A3、§8.5-12。

#### TOOL-28 compile 成功 【P1】
- 前提：E4（standard）+ 蓝图处于 dirty（手动改动变量默认值不保存编译）。
- 步骤：`{"action":"compile","blueprintPath":"..."}` → 再 `query` compileState。
- 预期：compile 返回 `ok==true` 无 `COMPILE_FAILED`；query `status` ∈ {`up_to_date`,`unknown`}（若无法读取按 §5.10 附 warning）。
- 判定：compile 无错误且状态转为 up_to_date 或明确 unknown+warning。
- 依据：§5.10 编译要点、§8.5-12。
- 【未执行】

#### TOOL-29 节点读取降级行为（A3） 【P2】
- 前提：E4。
- 步骤：`{"action":"query","graphName":"EventGraph","includeNodes":true}`。
- 预期（两种均可接受，记录实际）：(a) `nodes` 数组返回且能力 `blueprintNodeRead` 置 true；(b) `nodes:[]` + warning `NODE_INSPECTION_UNSTABLE`，`capabilities.blueprintNodeRead==false`。
- 判定：两种形态之一出现即为通过（此为 A3 的设计内降级，非缺陷）；同时无 `CAPABILITY_UNAVAILABLE` 之外的崩溃。
- 依据：§5.10 节点访问非稳定 API、§8.4 A3。
- 【未执行】

#### 4.2.9 ue_console_command（§5.8）

#### TOOL-30 双开关开启后执行白名单命令 【P1】
- 前提：E2：Server `--policy full --allow-console` + 桥接 `allowConsole=true`。**不需要** `--allow-destructive`——裁决补充 §7.1（D11）：`--allow-console` 兼作该工具的策略级确认，审计记 `confirmationMode:"policy"`；console/exec 的能力门不是确认门。
- 步骤：tools/list 确认可见 → tools/call `{"command":"stat fps","worldContext":"editor"}`。
- 预期：`data.dispatched==true`；`data.outputAvailable==false`（MVP 无回显；成功但有警告 → `isError==false`、`warnings[]` 含 `OUTPUT_CAPTURE_UNSUPPORTED`）；`data.command=="stat fps"`。
- 判定：dispatched==true 且 outputAvailable==false。
- 依据：§5.8、裁决补充 §7.1/§7.2（D11）、§1.3。
- 【未执行】

#### TOOL-31 永久拒绝表命令与桥接控制台门区分 【P0】
- 前提：E2：(a) 同 TOOL-30（双端 console 门全开）；(b) 变体：Server `--policy full --allow-console` + 桥接 `allowConsole=false`。
- 步骤：(a) 依次调用 `{"command":"quit"}`、`{"command":"py import os"}`、`{"command":"exec something"}`；(b) 调用 `{"command":"stat fps"}`。
- 预期：(a) 三者均 HTTP 200 + `isError==true`，`error.code == "COMMAND_NOT_ALLOWED"`；编辑器未退出（`/health` 仍 200）；(b) `error.code == "PERMISSION_DENIED"` 且 `error.details.gate == "bridge.allowConsole"`（裁决补充 §5.1：桥接能力门 ≠ 白名单拒绝，两码不得混用）。
- 判定：(a) 错误码符合且编辑器存活；(b) 错误码与 `details.gate` 符合。
- 依据：§5.8 永久拒绝表、裁决补充 §5.1/§5.5（D6）。
- 【未执行】

#### 4.2.10 ue_python_exec（§5.9）

#### TOOL-32 双开关开启后 eval 返回结果 【P1】
- 前提：E2：Server `--policy full --allow-exec` + 桥接 `allowExec=true`。**不需要** `--allow-destructive`——裁决补充 §7.1（D11）：`--allow-exec` 兼作策略级确认。
- 步骤：tools/call `{"code":"1+1","mode":"eval"}`。
- 预期：`data.result == 2`；`data.mode=="eval"`；`timedOut==false`。
- 判定：result==2。
- 依据：§5.9、§6.4、§8.5-13「开启双开关后可执行并返回结果」。
- 【未执行】（高风险操作，仅在受控环境执行）

#### TOOL-33 PYTHON_ERROR 与审计红线 【P1】
- 前提：E2（同 TOOL-32）。
- 步骤：(a) `{"code":"raise ValueError('uemcp-test')","mode":"exec"}`；(b) 调用后检查当日审计文件 `~/.uemcp/audit/YYYY-MM-DD.jsonl` 中该调用记录。
- 预期：(a) `error.code=="PYTHON_ERROR"`，error.message 含 traceback（可含 `ValueError`）；(b) 审计记录含 `codeSha256`（64 位十六进制）与 `codeLength`，**不包含**源码文本 `ValueError('uemcp-test')` 原文，不含任何 token。
- 判定：(a) 错误码符合；(b) 审计字段符合红线。
- 依据：§5.9、§6.5（审计永不记录源码/token）。
- 【未执行】

### 4.3 L3 安全（SEC）

#### SEC-01 read-only 下纯写工具不可见、混合工具写 action 被拒 【P0】
- 前提：E0（read-only 策略，无需编辑器即可验证策略层）；E1 用于 (d)(e)(f) 副作用核验。
- 步骤：(a) tools/list 检查；(b) tools/call `ue_actor_edit`（合法参数）；(c) tools/call `ue_python_exec`；(d) tools/call `ue_level_control {action:"save_current"}`；(e) tools/call `ue_material_params {action:"set",...}`（合法参数形态）；(f) tools/call `ue_blueprint {action:"compile",...}`。
- 预期（裁决补充 §8.4，D12）：
  - (a) 列表恰为 read-only 7 工具集合（PROTO-03 ①）：不含 `ue_actor_edit`、`ue_console_command`、`ue_python_exec`；
  - (b) HTTP 200 + `isError==true`，`error.code=="TOOL_DISABLED"`，`details.gate=="server.policy"`；
  - (c) `error.code=="TOOL_DISABLED"`，`details.gate=="server.allowExec"`；错误 message **不包含**工具参数细节或存在性描述（§5.11「错误信息不透露工具细节」）；
  - (d) `error.code=="INVALID_ARGUMENT"`（Schema 收窄后 action 枚举不含 `save_current`），`details.issues` 非空；且 `list_dirty` 确认**未保存任何内容**（脏包计数不变）；
  - (e) `error.code=="INVALID_ARGUMENT"`；且读回材质参数确认**未改变**；
  - (f) `error.code=="INVALID_ARGUMENT"`；且蓝图 `compileState` 确认**未触发编译**。
- 判定：(a) 集合相等；(b)(c) 错误码 + gate 断言；(d)(e)(f) 错误码 + 无副作用三项核验全部成立。
- 依据：§1.4-3、§5.0.3、§5.11、裁决补充 §8.2/§8.4（D12）、§5.1（D6 gate 契约）。
- 【未执行】

#### SEC-02 默认策略为 read-only 【P0】
- 前提：E0；**不带** `--policy` 参数启动。
- 步骤：initialize → tools/list。
- 预期：列表 == read-only 集合（无 P1/P2 工具）；`ue_editor_status` 在 E1 下返回 `policies.mode=="read-only"`。
- 判定：默认即 read-only。
- 依据：§6.3「默认策略为 read-only」、§7.1（README）。
- 【未执行】

#### SEC-03 非回环地址不可达 【P0】
- 前提：E0 + 本机局域网 IP（如 192.168.x.x）。
- 步骤：从本机以局域网 IP 为目标 `curl http://<LAN_IP>:18777/health`（服务绑定回环时 TCP 连接将被拒绝）；如条件允许，另用第二台机器访问。
- 预期：连接被拒绝（curl 退出码 7，Connection refused）；桥接 18778 同理。
- 判定：两端口均连接拒绝。
- 依据：§6.2（强制 127.0.0.1，TCP peer 非回环直接断开）、§8.5-4。
- 【未执行】（需要局域网 IP 或第二台机器，环境受限时以本机双栈验证并在报告注明）

#### SEC-04 Host 头校验 → 421 【P0】
- 前提：E0。
- 步骤：`curl -H "Host: evil.example.com" http://127.0.0.1:18777/health`。
- 预期：HTTP 421；响应为 JSON-RPC error（`data.errorCode=="INVALID_REQUEST"`），不进入工具层（裁决补充 §1.6 补充）。
- 判定：状态码 == 421 且层位正确。
- 依据：§3.3（仅接受 127.0.0.1/localhost Host，其他 421）、裁决补充 §1.6。
- 【未执行】

#### SEC-05 恶意 Origin → 403 【P1】
- 前提：E0。
- 步骤：POST `/mcp` initialize，加 `-H "Origin: http://evil.example.com"`。
- 预期：HTTP 403；响应为 JSON-RPC error（`data.errorCode=="INVALID_REQUEST"`），不进入工具层（裁决补充 §1.6 补充）。
- 判定：状态码 == 403 且层位正确。
- 依据：§3.3（Origin 必须为回环同源或 null）、裁决补充 §1.6。
- 【未执行】

#### SEC-06 桥接 token 校验 【P0】
- 前提：E1；从 `~/.uemcp/bridges/<hash>.json` 读 token。
- 步骤：(a) `curl -X POST http://127.0.0.1:18778/rpc -d '{"jsonrpc":"2.0","id":1,"method":"bridge.ping"}'`（无 token 头）；(b) 带错误 `X-UEMCP-Token: wrong`；(c) 带正确 token。
- 预期：(a) HTTP 401；(b) HTTP 401，响应不区分「token 缺失/错误」；(c) HTTP 200，`result.ok==true`。
- 判定：401/401/200 三态正确。
- 依据：§2.4、§6.6、§8.5-3。
- 【未执行】

#### SEC-07 OPTIONS 预检 → 405 【P2】
- 前提：E0。
- 步骤：`curl -X OPTIONS http://127.0.0.1:18777/mcp`。
- 预期：HTTP 405；响应不含 `Access-Control-Allow-Origin: *`。
- 判定：405 且无通配 CORS 头。
- 依据：§6.2（不启用 CORS、OPTIONS 405）。
- 【未执行】

#### SEC-08 delete 无确认渠道 → CONFIRMATION_REQUIRED 【P1】
- 前提：E2：standard + **无** `--allow-destructive` + 客户端未声明 elicitation（curl 场景）；场景中有 1 个测试 Actor。
- 步骤：tools/call `ue_actor_edit`，operations=[{op:"delete",selector:{kind:"label",value:"UEMCP_T_Spawn1"}}]。
- 预期：`isError==true`，`error.code == "CONFIRMATION_REQUIRED"`；Actor 仍存在。
- 判定：错误码符合且 Actor 未被删除。
- 依据：§5.0.3、§6.3、§8.5-7「delete 在未开启 destructive 时被拒绝」。
- 【未执行】

#### SEC-09 `--allow-destructive` 生效并记录 confirmationMode 【P1】
- 前提：E2：standard + `--allow-destructive`。
- 步骤：重复 SEC-08 的 delete → 检查审计文件该条记录。
- 预期：delete 成功（`results[0].ok==true`，`deleted` 非空）；审计该条 `confirmationMode=="policy"` 且同时记录 `confirmationSwitch=="--allow-destructive"`（裁决补充 §7.2 补充：policy 模式必须记录所用开关）。
- 判定：删除成功且审计字段正确。
- 依据：§6.3-4。
- 【未执行】

#### SEC-10 elicitation 确认流（拒绝分支） 【P1】
- 前提：E2：standard 无 `--allow-destructive` + 测试客户端在 initialize 中声明 `capabilities.elicitation:{}` 且对 `elicitation/create` 回复 `approve:false`。
- 步骤：发起 delete。
- 预期：客户端收到 `elicitation/create` 请求（message 含删除描述）；最终工具结果 `error.code == "CONFIRMATION_DENIED"`；审计该条 `confirmationMode=="elicitation"`（裁决补充 §7.4）。
- 判定：确认请求发出且回拒后返回 CONFIRMATION_DENIED，审计模式字段正确。
- 依据：§6.3 确认流程。
- 【未执行】（需自制 elicitation 客户端，脚本纳入测试资产）

#### SEC-11 双重权限门：服务端开、桥接 exec 门关 【P1】
- 前提：E2：Server `--policy full --allow-exec` + 桥接 `allowExec=false`（默认）。
- 步骤：tools/call `ue_python_exec`，`{"code":"1+1","mode":"eval"}`。
- 预期（裁决补充 §5.1 固定，不再多选）：HTTP **200**；`isError==true`；`error.code == "EXEC_DISABLED"`；`error.details.gate == "bridge.allowExec"`；编辑器未执行代码。
- 判定：错误码 + gate 断言 + 无代码执行全部成立。
- 依据：§6.3 双重执行、裁决补充 §5.1/§5.5（D6）。
- 【未执行】

#### SEC-11b 双重权限门：桥接写门关 【P1】
- 前提：E2：Server `--policy standard`（`ue_actor_edit` 可见）+ 桥接 `allowWrite=false`（默认）。
- 步骤：tools/call `ue_actor_edit`，operations 为 1 个合法 spawn。
- 预期：HTTP 200；`isError==true`；`error.code == "PERMISSION_DENIED"`；`error.details.gate == "bridge.allowWrite"`；拒绝发生在游戏线程入队之前（`actor_query` 确认场景无变化）。
- 判定：错误码 + gate + 场景无变化全部成立。
- 依据：裁决补充 §5.1/§5.3（D6）。
- 【未执行】

#### SEC-11c 双重权限门：桥接控制台门关 【P1】
- 前提：E2：Server `--policy full --allow-console` + 桥接 `allowConsole=false`。
- 步骤：tools/call `ue_console_command`，`{"command":"stat fps"}`。
- 预期：HTTP 200；`isError==true`；`error.code == "PERMISSION_DENIED"`（**不是** `EXEC_DISABLED`——console 门不使用 exec 语义，裁决补充 §5.2）；`error.details.gate == "bridge.allowConsole"`。
- 判定：错误码 + gate 符合，且与 TOOL-31 (a) 的 `COMMAND_NOT_ALLOWED`（白名单拒绝）明确区分。
- 依据：裁决补充 §5.1/§5.2/§5.5（D6）。
- 【未执行】

#### SEC-12 审计日志内容与红线 【P0】
- 前提：E2：E1 + 若干 P1 调用（TOOL-07/08/14 已执行）。
- 步骤：读取 `~/.uemcp/audit/<当日>.jsonl`，逐行 JSON.parse。
- 预期：每个 P1 调用恰有一行；每行含 `ts`/`requestId`/`tool`/`policyMode`/`decision`/`durationMs`/`ok`；全文件不含 `bridge.json` 中的 token 值、不含截图 base64（`iVBORw0KGgo` 前缀）、不含 Python 源码原文。
- 判定：字段齐全 + 三项红线均不出现。
- 依据：§6.5、§1.4-5。
- 【未执行】

#### SEC-13 审计降级标记 【P2】
- 前提：E1；构造审计写入失败的方式（主管判定 D9：**允许以只读 ACL 锁定审计目录模拟写入失败**）。
- 步骤：锁定目录后连续调用 3 次 P1 工具 → `GET /health`。
- 预期：`/health` 响应含 `auditDegraded==true`；工具调用本身不因审计失败而阻塞（仍返回正常结果）。
- 判定：degraded 标记出现且调用不受阻。
- 依据：§6.5（审计写入失败不阻塞；连续失败 3 次标记）。
- 【未执行】

#### SEC-14 速率限制 【P2】
- 前提：E1；压测脚本（主管判定 D5：降为 P2 **选测**，CI 不阻塞）。
- 步骤：单会话以 >20 req/s 连续发送 50 个 `ue_editor_status`（1 秒内）。
- 预期：限流发生在 HTTP 中间件阶段（尚未进入工具）→ 协议层形态：HTTP **429** + 顶层 JSON-RPC `error.code == -32012`、`error.data.errorCode == "RATE_LIMITED"`、**无 `result`、无 `isError` 字段**（裁决补充 §1.6）；被限流请求之外的请求正常返回；服务不崩溃。
- 判定：层位断言正确（协议层 429 + 顶层 error；不得出现 200 + isError 的工具级形态）；降速后请求恢复正常。
- 依据：§6.7（每会话 20 req/s）、裁决补充 §1.1/§1.6（D1 分层）。
- 【未执行】（P2 选测）

#### SEC-15 `--allow-destructive` 不能让 exec 出现 【P1】
- 前提：E2：Server 仅 `--policy full --allow-destructive`（**无** `--allow-exec`）+ 桥接 `allowExec=true`。
- 步骤：(a) tools/list 检查；(b) tools/call `ue_python_exec`，`{"code":"1+1","mode":"eval"}`。
- 预期（裁决补充 §7.4，D11）：(a) `ue_python_exec` **不在** tools/list（P2 可见性只由 `--allow-exec` 决定，`--allow-destructive` 不参与）；(b) HTTP 200 + `isError==true`，`error.code=="TOOL_DISABLED"`，`details.gate=="server.allowExec"`；未执行任何代码。
- 判定：不可见 + 调用被拒 + 无代码执行全部成立。
- 依据：裁决补充 §7.1/§7.4（D11）。
- 【未执行】

#### SEC-16 `--allow-exec` 不豁免 P1 破坏性确认 【P1】
- 前提：E2：Server 仅 `--policy full --allow-exec`（**无** `--allow-destructive`）+ 桥接 `allowWrite=true` + 客户端未声明 elicitation（curl 场景）+ 场景中有 1 个测试 Actor。
- 步骤：(a) tools/call `ue_actor_edit` delete 该 Actor；(b) tools/call `ue_python_exec`，`{"code":"1+1","mode":"eval"}`。
- 预期：(a) HTTP 200 + `isError==true`，`error.code=="CONFIRMATION_REQUIRED"`；Actor 仍存在；(b) exec 成功（`data.result==2`）。
- 判定：`--allow-exec` 的作用域仅限 exec（兼作策略确认），不影响 delete 的确认路径——(a) 拒绝 + (b) 成功同时成立。
- 依据：裁决补充 §7.1/§7.4（D11）。
- 【未执行】

### 4.4 L4 故障恢复（RES）

#### RES-01 插件启用后生成发现文件 【P0】
- 前提：E0→E1 转换：UE 5.4.4 打开样例工程，插件已安装启用（§10.4-2/3）。
- 步骤：等待编辑器完全启动 → 检查 `<Project>/Saved/UEMCP/bridge-settings.json`、`~/.uemcp/bridge.json`、`~/.uemcp/bridges/<projectHash>.json`。
- 预期：三文件存在；`bridges/<hash>.json` 可 JSON.parse，`schemaVersion==1`、`pid` 为编辑器进程 PID（任务管理器可核）、`port==18778`、`ueVersion` 以 5.4 开头、`token` 为 base64url 长度 43 字符、`startedAt` 为合法 ISO 时间；文件权限 0600（Windows 上记录 ACL 实况，若无法精确对应 0600 则记录观察）。
- 判定：文件存在 + 结构字段全部符合。
- 依据：§2.4、§4.4、§8.4 A1、§10.4-4、§8.5-1、§9.1-1。
- 【未执行】

#### RES-02 桥接 /health 自检 【P0】
- 前提：E1。
- 步骤：`curl http://127.0.0.1:18778/health`。
- 预期：HTTP 200；JSON 含 `"app":"uemcp-bridge"`（或 §2.4 的 `{"app":"uemcp-bridge","ok":true}` 形态）；`pid`/`startedAt` 与发现文件一致。
- 判定：app 标识正确且与发现文件一致。
- 依据：§2.4 校验规则、§8.5-2。
- 【未执行】

#### RES-03 桥接不可达 → BRIDGE_UNAVAILABLE 且 Server 存活 【P0】
- 前提：E0（**不启动编辑器**）+ MCP Server 以默认发现路径启动。
- 步骤：tools/call `ue_editor_status` → `GET /health`（MCP Server 的）。
- 预期：工具结果为工具层形态（HTTP **200** + `isError==true`，不得使用 503/4xx），`error.code=="BRIDGE_UNAVAILABLE"`，`retryable==true`；MCP Server `/health` 仍返回 200 `ok==true`（进程未退出）；连续调用 3 次行为一致。
- 判定：错误码正确且 Server 存活。
- 依据：§1.4-4、§2.4（全部发现来源失败 → BRIDGE_UNAVAILABLE）、§3.2。
- 【未执行】

#### RES-04 编辑器正常退出后清理 【P1】
- 前提：E1。
- 步骤：正常关闭编辑器（文件→退出）→ 检查 `~/.uemcp/bridge.json` 与 `bridges/<hash>.json`。
- 预期：两文件已删除（或不再存在）；`netstat` 无 18778 监听。
- 判定：文件清理 + 端口释放。
- 依据：§4.4（退出时停止服务并删除发现文件）、§9.1-6。
- 【未执行】

#### RES-05 强杀编辑器后陈旧发现文件被忽略 【P0】
- 前提：E1；记录当前 `bridges/<hash>.json` 内容。
- 步骤：任务管理器强杀编辑器进程（文件残留）→ 重启 MCP Server（或复用）→ tools/call `ue_editor_status`。
- 预期：调用返回 `BRIDGE_UNAVAILABLE`（不挂起、不崩溃）；Server 日志（stderr）含跳过陈旧文件的记录；再正常启动编辑器后同一调用成功——验证自愈。
- 判定：三段行为均符合。
- 依据：§2.4 校验规则（PID 存活 + `/health` pid/startedAt 一致性）、R9、§8.5-16、§10.5。
- 【未执行】

#### RES-06 MCP Server 端口冲突 fail-fast 【P1】
- 前提：E0；18777 被占（用 python 起一个占位监听进程并保持）。
- 步骤：以默认端口启动 MCP Server，捕获退出码、stderr 全文与退出耗时（计时）。
- 预期（裁决补充 §6.1，D10）：进程**退出码 == 2**；stderr 含一行 JSON：`event=="http_bind_failed"`、`port==18777`、`code=="EADDRINUSE"`（格式见裁决补充 §6.1 示例）；**2 秒内**退出；不存在自动换端口分支——未打开任何其他端口、未进入重试循环、未写发现文件；占用进程保持监听 18777。
- 判定：退出码、stderr JSON 字段、退出时限、无换端口分支四项全部成立。
- 附加观察（P2）：`--port 0` 用于 CI/测试时成功启动，实际端口写入启动日志与 `/health`。
- 依据：裁决补充 §6.1/§6.5（D10）。
- 【未执行】

#### RES-07 桥接端口回退与全占降级 【P1】
- 前提：E1 前。(a) 占用 18778（占位监听）；(b) 变体：占用 18778–18788 全部 11 个端口。
- 步骤：(a) 启动编辑器 → 检查发现文件与 `/health` → 启动 MCP Server 并调用 `ue_editor_status`；(b) 同样启动编辑器并检查。
- 预期（裁决补充 §6.1，D10）：(a) 桥接成功绑定 **18779**（或 18778–18788 中第一个可用端口）；发现文件 `port`/`url` 指向**实际端口**；该端口 `/health` 返回 `app=="uemcp-bridge"`；MCP Server 通过发现文件完成 `ue_editor_status`（回退对客户端透明）；(b) 编辑器日志含 `[UEMCP] bridge_bind_failed`（`Saved/Logs/*.log`）；**不写**任何可用发现文件；MCP Server 侧 `ue_editor_status` 返回 `BRIDGE_UNAVAILABLE`。
- 判定：(a) 端口回退 + 发现文件正确 + 调用成功；(b) 无发现文件 + 明确失败。
- 依据：裁决补充 §6.1/§6.5（D10）、§10.5。
- 【未执行】

#### RES-08 连续 100 次调用稳定性 【P0】
- 前提：E1。
- 步骤：脚本循环 100 次 tools/call `ue_editor_status`，计时。
- 预期：100 次全部 `ok==true`，无失败；平均耗时 < 100ms（不含客户端开销，按 structuredContent.meta.durationMs 累计平均或端到端计时，以 meta.durationMs 为准）；MCP Server 与编辑器均无崩溃。
- 判定：成功率 100% 且平均 durationMs < 100。
- 依据：§9.1-5。
- 【未执行】

#### RES-09 token 轮换后自愈 【P1】
- 前提：E1，MCP Server 已连接。
- 步骤：重启编辑器（token 轮换、新发现文件）→ 不重启 MCP Server，直接 tools/call `ue_editor_status`。
- 预期：调用成功（Server 重新读取发现文件取到新 token）；`/health` 的 `bridge.startedAt` 更新。若首次调用短暂失败但随后恢复，记录恢复耗时。
- 判定：最终成功且无需重启 Server。
- 依据：§6.6（每次编辑器启动轮换；Server 每次调用前可重新读取）。
- 【未执行】

#### RES-10 请求体超限（协议层）与内联图像超限（工具级）不得混淆 【P2】
- 前提：E0（(a)）；E1（(b)）。
- 步骤：(a) POST `/mcp`，body 为 >8 MiB 的合法 JSON（填充长字符串参数）；(b) `ue_viewport_capture` `returnMode:"image"` 且输出图像 >8 MiB（构造方式同 TOOL-26 (b)，场景不足时标注【未测】）。
- 预期：(a) 协议层：HTTP **413** + 顶层 JSON-RPC `error.code == -32011`、`error.data.errorCode=="PAYLOAD_TOO_LARGE"`、无 `result`；(b) 工具级：HTTP **200** + 必有 `result`——若为警告形态则 `isError==false` + `warnings` 含 `IMAGE_TOO_LARGE_FOR_INLINE` 只返回路径，若为错误形态则 `isError==true` + `error.code=="PAYLOAD_TOO_LARGE"`（裁决补充 §2.4：同一字符串码两层均可能出现，**靠 HTTP 状态与「是否存在 result」区分层位**）。
- 判定：(a) 413 + 顶层 error；(b) 200 + result 存在；两分支的层位断言不得互换。
- 依据：§3.3（请求体上限 8 MiB）、裁决补充 §1.6/§2.4（D1）。
- 【未执行】

### 4.5 L5 客户端兼容性（CLIENT）

#### CLIENT-01 curl 最小序列全通 【P0】
- 前提：E1。
- 步骤：附录 A.1 完整四步（initialize → initialized → tools/list → tools/call `ue_editor_status`）。
- 预期：四步依次 200/202/200/200；tools/list 返回工具数组；tools/call 返回 `structuredContent.ok==true` 且 `ueVersion` 以 5.4 开头。
- 判定：四步状态码与内容均符合。
- 依据：§3.5.4、§8.5-14（curl 等价）。
- 【未执行】

#### CLIENT-02 Claude Code Streamable HTTP 接入 【P0】
- 前提：E3；`claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp`。
- 步骤：在 Claude Code 会话中请求列出可用 MCP 工具 → 让模型调用 `ue_editor_status`。
- 预期：工具列表出现 UEMCP 工具；调用返回真实编辑器状态（UE 版本/关卡名）。实测记录 Claude Code 版本号与是否支持 `--transport http`（A5 结论）。
- 判定：工具可见且调用结果含正确 ueVersion。
- 依据：§3.5.1、§8.4 A5、§9.2-1。
- 【未执行】

#### CLIENT-03 Claude Code stdio 接入 【P0】
- 前提：E3；按 §3.5.2 配置（Windows 下必要时用 `cmd /c npx` 变体）。
- 步骤：stdio 会话中列出并调用 `ue_editor_status`。
- 预期：同 CLIENT-02；无 stdout 污染导致的解析错误（客户端日志无 JSON parse failure）。
- 判定：工具可见、调用成功、客户端日志无解析错误。
- 依据：§3.5.2、§8.5-14、§9.1-4。
- 【未执行】

#### CLIENT-04 Cursor Streamable HTTP 接入 【P0】
- 前提：E3；`.cursor/mcp.json` 按 §3.5.3 配置 url 指向 `/mcp`。
- 步骤：Cursor 中刷新 MCP → 调用 `ue_editor_status`。
- 预期：工具可见且返回正确状态；记录 Cursor 版本号（A6 结论）。
- 判定：同 CLIENT-02。
- 依据：§3.5.3、§8.4 A6、§9.2-1。
- 【未执行】

#### CLIENT-05 旧版 SSE 双基线（脚本必测 + Cursor 0.45.11） 【P1】
- 前提：E3。双基线（裁决补充 §4.1，D2）：(i) **脚本基线**——仓库 `examples/generic/sse_client.py`，**必测横线，失败即 FAIL**；(ii) **客户端基线**——Cursor **0.45.11**（可安装时必须测；无法安装时允许以 0.45.x 系列最早可安装版本替代并记录实际版本号；**不得用 0.46+**——其 `url` 语义可能已转向 Streamable HTTP）。
- 步骤：(i) 执行脚本（命令见附录 A.4，退出码语义同 PROTO-14）；(ii) Cursor 0.45.11 配置 `url` 指向 `/sse`（§3.5.3），刷新 MCP 后调用 `ue_editor_status`。
- 预期与判定（裁决补充 §4.3 表）：

| 条件 | 判定 |
|---|---|
| 脚本 PASS 且 Cursor 基线 PASS | 通过 |
| 脚本 PASS，Cursor 无法安装/无法获取 | 通过（Cursor 部分 N/A） |
| 脚本 PASS，Cursor 可安装但客户端声明不支持 SSE | 通过（Cursor 部分 N/A，附版本与证据） |
| 脚本 FAIL | 失败 |
| 脚本 PASS，Cursor 可安装支持 SSE，因服务端响应错误（4xx/5xx、SSE 格式错误、endpoint 缺失）失败 | 失败 |
| 脚本 PASS，Cursor 失败原因是客户端 UI/配置限制，与服务端无关 | 通过（N/A，附截图与版本） |

- 证据要求：Cursor 实际版本号、配置截图、`/sse` 响应头、失败时的客户端日志。
- 依据：裁决补充 §4.1/§4.3/§4.5（D2）、§3.4、§8.5-15。
- 【未执行】

#### CLIENT-06 §1.4 闭环脚本 【P0】
- 前提：E4：standard + `--allow-destructive` + 桥接 `allowWrite=true`。
- 步骤：一条脚本（附录 A.2）顺序执行：spawn（StaticMeshActor）→ actor_query（确认存在）→ set_transform → viewport_capture（file 模式）→ delete → actor_query（确认消失）。
- 预期：六步全部成功；截图文件存在；delete 前后 query 的 total 分别 +1 与复原；全程无未捕获错误。
- 判定：六步全部达成即视为 §1.4-2 闭环判据满足。
- 依据：§1.4-2、§9.2-5。
- 【未执行】

### 4.6 PoC 清单（§8.5）覆盖映射

| §8.5 项 | 对应用例 |
|---|---|
| 1 发现文件生成 | RES-01 |
| 2 桥接 /health | RES-02 |
| 3 错误/正确 token | SEC-06 |
| 4 非回环拒绝 | SEC-03 |
| 5 editor.status | TOOL-01 |
| 6 actor.query 分页过滤 | TOOL-03/04/05 |
| 7 actor.edit dryRun/spawn/delete 拒绝 | TOOL-06/07、SEC-08 |
| 8 level get_current/list_dirty/save | TOOL-13/14 |
| 9 asset.search 依赖 | TOOL-17/19 |
| 10 material.params 读写 | TOOL-20/21 |
| 11 截图（视口/PIE） | TOOL-24/25 |
| 12 blueprint 查询/编译 | TOOL-27/28 |
| 13 python.exec 隐藏与开启 | SEC-01（隐藏）、TOOL-32（开启）、SEC-15/16（开关作用域） |
| 14 stdio Claude Code | CLIENT-03 |
| 15 HTTP Cursor / SSE 旧客户端 | CLIENT-04/05、PROTO-14（脚本基线） |
| 16 强杀编辑器陈旧文件 | RES-05 |

16 项全部被用例覆盖，无遗漏。

---

## 5. 验收标准

### 5.1 架构文档 §1.4 成功判据 → 可判定测试结论映射

| # | §1.4 成功判据 | 判定用例 | 通过标准 |
|---|---|---|---|
| 1 | 三类客户端均能完成 initialize→tools/list→tools/call | CLIENT-01/02/04（curl、Claude Code HTTP、Cursor）+ CLIENT-03/05（stdio、SSE 补充） | 三类主客户端 3 个用例全部通过；stdio/SSE 变体至少其一通过 |
| 2 | 一条脚本完成「创建→查询→改变换→截图→删除」闭环 | CLIENT-06 | 六步全部成功 |
| 3 | read-only 下纯写工具不在 tools/list；直接调用返回 TOOL_DISABLED；混合工具以收窄 Schema 出现、写 action 返回 INVALID_ARGUMENT | SEC-01、SEC-02、PROTO-03 | 7 工具集合相等 + (d)(e)(f) 错误码与无副作用均符合 |
| 4 | 桥接不可达时 Server 不崩溃，返回 BRIDGE_UNAVAILABLE | RES-03、RES-05 | 错误码正确且 /health 存活 |
| 5 | 审计含时间/工具/参数摘要/结果/耗时，且不含 token 与完整 Python 源码 | SEC-12、TOOL-33 | 字段齐全 + 红线不出现 |

### 5.2 阶段 1（MVP）验收映射（§9.2 验收清单 → 用例）

| §9.2 验收项 | 用例 |
|---|---|
| 三客户端 initialize→tools/list→tools/call | CLIENT-01/02/04 |
| read-only：7 个工具（含收窄混合工具）；纯写/隐藏调用 TOOL_DISABLED；混合写 action INVALID_ARGUMENT | SEC-01/02、PROTO-03 |
| standard：P0+P1 可用，P2 不可见 | PROTO-03 |
| full+exec 可见可执行；桥接 allowExec=false 时返回 EXEC_DISABLED | TOOL-32、SEC-11、SEC-15/16（开关作用域） |
| Actor 闭环（destructive 开启） | CLIENT-06 |
| 关卡 open/save/save_all/new；脏包未确认拒绝 open | TOOL-13/14/15/16 |
| 资产搜索/分页/依赖/引用；大工程超时部分结果 | TOOL-17/18/19；SEARCH_TIMEOUT 构造见 D7 |
| 材质 list/get/set/create_instance；非 MIC 拒绝 | TOOL-20/21/22/23 |
| 截图 PNG/JPEG 尺寸正确；>8MiB 只返回路径 | TOOL-24/26；>8MiB 构造见 D3 |
| 蓝图 query/compile；节点编辑请求 CAPABILITY_UNAVAILABLE | TOOL-27/28；节点编辑拒绝场景并入 TOOL-29 执行时验证（`ue_blueprint` 无编辑 action，Schema 层应拒） |
| HTTP 会话：session/缺头 400/未知 404/DELETE 204/TTL | PROTO-01/05/06/07/08 |
| SSE：/sse+/messages 完成一次调用（脚本基线必测） | PROTO-14 |
| 安全：Host/Origin/非回环/token 不入日志 | SEC-03/04/05/12 |
| 审计：P1/P2 一条 JSONL；无源码/token/base64 | SEC-12、TOOL-33 |
| 桥接断开 BRIDGE_UNAVAILABLE 且 Server 不退出 | RES-03 |
| 文档 docs/tools.md 与实现一致 | 执行期人工比对（不设独立用例；检查项：10 工具名与 inputSchema 同 tools/list） |
| 许可证与商标声明齐全 | 发布检查项（LICENSE/TRADEMARK.md 存在且含 README §9.2 文本），非测试用例 |

### 5.3 判定规则与缺陷分级

**用例结论**（三态）：

- **通过**：实际结果与用例「预期结果」逐条一致（状态码、错误码、字段值、文件/日志证据齐备）。
- **失败**：任一可观察条件不符且可复现；附复现步骤、实际与预期差异、日志摘录。
- **阻断**：前置条件不可用导致用例无法执行（如 npm 包不可运行、插件无法加载、A1 失败导致桥接不启动）。阻断必须注明缺失的具体前提与解除条件；**阻断不等于失败，也不得计为通过**。

**缺陷分级**：

| 级别 | 定义 | 示例（本项目语境） |
|---|---|---|
| Blocker | 阻断 MVP 核心验收，无变通 | `tools/call` 完全不可用；桥接 token 校验缺失；非回环可访问 |
| Critical | 核心功能错误、安全红线失守，有变通但不充分 | read-only 下 delete 可执行；审计泄漏 Python 源码；会话隔离失效 |
| Major | 主路径外的重要行为错误 | 分页 offset 不生效；错误码与 §2.9 不符；dryRun 实际写场景 |
| Minor | 边缘/文案/性能偏差，不影响验收 | warnings 文案缺失；meta.durationMs 缺失；非关键字段命名偏差 |

**验收通过门槛**：§5.1 五条判据映射用例全部通过；P0 用例 100% 通过；P1 用例无未处置的 Blocker/Critical 失败；P2 失败须逐条经主管裁决豁免或转下阶段。出现 Blocker/Critical 时，发布门槛（§9.2「发布把关」7 项）一并复核。

---

## 6. 回归策略

### 6.1 冒烟集（每次代码迭代后必跑，目标 < 10 分钟）

| 顺序 | 用例 | 覆盖点 |
|---|---|---|
| 1 | RES-01、RES-02 | 桥接启动与发现文件 |
| 2 | PROTO-01/02/03（standard 档） | 协议三方法与策略过滤 |
| 3 | CLIENT-01 | curl 全序列 |
| 4 | TOOL-01 | 编辑器状态 |
| 5 | TOOL-03/04 | 查询与分页 |
| 6 | TOOL-06/07 | dryRun 与 spawn |
| 7 | SEC-01 | 隐藏工具与 TOOL_DISABLED |
| 8 | SEC-06 | token 三态 |
| 9 | RES-03 | 桥接不可达降级 |

### 6.2 全量集

- 触发时机：发布候选、传输层/安全/错误模型改动、依赖（MCP SDK、Node 大版本）升级、策略门或桥接权限实现变更。
- 范围：§4 全部用例（含 P2），外加 §9.2 发布门槛复核与文档一致性比对。
- 节奏建议：P0+P1 随 CI 每日跑（代码实现后）；P2 与 CLIENT 客户端类用例人工按轮次执行。

### 6.3 变更敏感矩阵（局部回归）

| 改动区域 | 必须重跑 |
|---|---|
| 会话/TTL/传输 | PROTO-01~09、13~17 |
| 错误模型/错误码 | PROTO-10/11/12/12b/12c、SEC-08、RES-03/10、各 TOOL 异常路径 |
| 策略门/隐藏逻辑/开关作用域 | SEC-01/02/10/11/11b/11c/15/16、PROTO-03 |
| 桥接发现/token | RES-01/02/05/09、SEC-06 |
| 截图/能力探测 | TOOL-24/25/26、TOOL-29 |
| 审计 | SEC-12/13、TOOL-33 |

---

## 7. 未执行与受阻项

**当前状态：§4 全部 86 条用例均为【未执行】**（v0.1.0 为 80 条 + v0.1.1 新增 6 条），原因是同一根本阻塞：

- **B1（根阻塞）：项目代码尚未实现**（README V1：npm 包未发布、插件不存在、任何命令不可运行）。
- 解除条件：MVP 代码可运行（`npx -y @uemcp/server` 可启动且 `/health` 返回 `{"ok":true,...}`）+ 插件目录可安装启用（RES-01 可执行）。

由 B1 派生的次级受阻项与解除条件：

| 编号 | 受阻内容 | 解除条件 |
|---|---|---|
| B2 | A1（init_unreal.py 自动执行）未验证 → E1 全部用例悬置 | 插件骨架落地后执行 RES-01 |
| B3 | A5/A6（Claude Code/Cursor 传输支持）未验证 → CLIENT-02/04/05 判定标准无法最终化 | Server 可运行后按 CLIENT-02/04 实测 |
| B4 | 截图路径行为（A2）未验证 → TOOL-24 预期中的输出路径判定可能需按实测修正 | TOOL-24 首轮执行 |
| B5 | ~~工具级错误码 HTTP 映射未定义~~ **已解除（v0.1.1）**：裁决补充 §2.4/§1.6 已补全映射，相关用例判定标准已固定 | — |
| B6 | 无 elicitation 测试客户端 → SEC-10 需自制脚本 | 测试资产开发（纳入执行阶段准备项） |

**风险与适用范围声明**：

- 本计划全部预期行为引自架构文档 v0.2.0 的**设计目标**；实现与设计偏差时，以实测结果为准并回修计划，不反向「按计划改现实」。
- 未执行不得写成通过；后续任何执行报告必须附执行环境版本（Node/UE/客户端）、命令与日志证据。
- 偶发问题（如资源加载慢导致的 BRIDGE_TIMEOUT）首次出现记录环境与复现率，连续复现才升级为缺陷。

---

## 8. 裁决与判定问题状态（v0.1.1 更新）

v0.1.0 列出的 12 项问题已全部闭环：7 项由架构师裁决（裁决补充 v0.1.1 §0–§8），5 项由主管判定并写入对应用例，1 项转实现方。

| # | 问题 | 状态 | 落点 |
|---|---|---|---|
| D1 | 工具级错误码映射缺失 | **已裁决**（裁决补充 §1/§2）：工具失败一律 HTTP 200 + `isError:true`；24 个码入库；`TIMEOUT` 退役 | TOOL-10/11/15/19/22/23/25/31、RES-03/10 |
| D1b | `INVALID_ARGUMENT` 二义 | **已裁决**（§3）：协议层 `INVALID_PARAMS`（400/-32602），工具层 200+`isError` | PROTO-12、新增 PROTO-12b/12c |
| D2 | SSE 最低客户端基线 | **已裁决**（§4）：Cursor 0.45.11 + `sse_client.py` 双基线 | PROTO-14、CLIENT-05、附录 A.4 |
| D3 | 截图成功判定标准 | **主管判定**：文件存在 + PNG 头/尺寸即通过；像素校验为观察项 | TOOL-24/26 |
| D4 | TTL 测试参数 | **转实现方**：实现提供 TTL 覆盖参数则测，否则未测 | PROTO-08 |
| D5 | 压测类用例是否必测 | **主管判定**：降 P2 选测，CI 不阻塞 | PROTO-09、SEC-14 |
| D6 | 双重权限门错误码 | **已裁决**（§5）：`TOOL_DISABLED`/`PERMISSION_DENIED`/`EXEC_DISABLED` 按拒绝位置区分 | SEC-11/11b/11c、TOOL-31 |
| D7 | SEARCH_TIMEOUT 触发条件 | **主管判定**：环境受限可标【未测】 | TOOL-19 (b) |
| D8 | A8 事务降级是否接受 | **主管判定**：接受降级（通过+降级标注+A8 结论记录） | TOOL-10 |
| D9 | 审计失败模拟方式 | **主管判定**：允许 ACL 锁定审计目录 | SEC-13 |
| D10 | MCP Server 端口冲突行为 | **已裁决**（§6）：Server fail-fast exit 2；桥接 18778–18788 回退 | RES-06/07 |
| D11 | `--allow-destructive` 生效范围 | **已裁决**（§7）：只豁免 P1；P2 由各自开关兼作策略确认 | TOOL-30/32、SEC-09/10/15/16 |
| D12 | read-only 混合工具可见性 | **已裁决**（§8）：注册但收窄 Schema；read-only 共 7 个 | PROTO-03、SEC-01 |

> 另据架构文档 v0.2.0 对齐：类过滤失败错误码由 `INVALID_ARGUMENT` 修正为 `CLASS_NOT_FOUND`（工具层 200 + `isError`），见 TOOL-05 (c)。

---

## 附录 A：标准执行脚本

### A.1 curl 最小序列（Git Bash）

```bash
BASE=http://127.0.0.1:18777/mcp
H_CT='Content-Type: application/json'
H_ACC='Accept: application/json, text/event-stream'

# 1. initialize（记录响应头 Mcp-Session-Id）
curl -s -D headers.txt -X POST "$BASE" -H "$H_CT" -H "$H_ACC" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0.0.0"}}}'
SID=$(grep -i '^mcp-session-id:' headers.txt | tr -d '\r' | awk '{print $2}')

# 2. initialized（预期 202）
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE" -H "$H_CT" -H "$H_ACC" \
  -H "Mcp-Session-Id: $SID" -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# 3. tools/list
curl -s -X POST "$BASE" -H "$H_CT" -H "$H_ACC" -H "Mcp-Session-Id: $SID" \
  -H "MCP-Protocol-Version: 2025-06-18" -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# 4. tools/call
curl -s -X POST "$BASE" -H "$H_CT" -H "$H_ACC" -H "Mcp-Session-Id: $SID" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ue_editor_status","arguments":{}}}'
```

### A.2 §1.4 闭环脚本骨架（CLIENT-06）

```
1. tools/call ue_actor_edit {operations:[{op:"spawn",class:"StaticMeshActor",location:{x:0,y:0,z:100},label:"UEMCP_T_E2E"}]}
2. tools/call ue_actor_query {filter:{labelContains:"UEMCP_T_E2E"}}            → 恰 1 条
3. tools/call ue_actor_edit {operations:[{op:"set_transform",selector:{kind:"label",value:"UEMCP_T_E2E"},location:{x:200,y:300,z:400}}]}
4. tools/call ue_actor_query {filter:{labelContains:"UEMCP_T_E2E"},fields:["identity","transform"]} → z≈400
5. tools/call ue_viewport_capture {returnMode:"file",width:640,height:480}      → 文件存在
6. tools/call ue_actor_edit {operations:[{op:"delete",selector:{kind:"label",value:"UEMCP_T_E2E"}}]}
7. tools/call ue_actor_query {filter:{labelContains:"UEMCP_T_E2E"}}             → 0 条
```

### A.3 执行记录模板

```
用例ID：        执行日期：        执行人：
环境：Node __ / UE __ / 客户端 __ / Server 启动参数：
结论：通过 / 失败 / 阻断
证据（命令、HTTP 状态码、JSON 字段、日志摘录、文件路径）：
差异（实际 vs 预期）：
缺陷编号与级别：
```

### A.4 旧版 SSE 脚本调用（PROTO-14 / CLIENT-05 脚本基线）

```bash
python examples/generic/sse_client.py \
  --url http://127.0.0.1:18777/sse \
  --expect-tools 8 \
  --timeout 10
```

- `--expect-tools` 按当前策略取值：read-only=7、standard=8、full（无 P2 开关）=8、full+单开关=9、full+双开关=10（裁决补充 §8.1）。
- 退出码语义：0=通过；1=断言失败；2=传输失败；3=超时；4=SSE 解析失败（裁决补充 §4.2）。
- 脚本仅用 Python 标准库，不依赖 Cursor 与 Node；全部等待有超时。

---

*本文档 v0.1.1 由测试角色依据《UEMCP 架构设计与工具清单》v0.2.0、《UEMCP 架构裁决补充》v0.1.1 与 README 草稿 v0.1.0 更新（2026-10-20）；未自行发明产品行为；全部用例未执行。随实现迭代更新。*
