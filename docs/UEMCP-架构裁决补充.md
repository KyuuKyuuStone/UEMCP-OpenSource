# UEMCP 架构裁决补充（v0.1.1）

| 项 | 值 |
|---|---|
| 文档版本 | 0.1.1 |
| 日期 | 2026-10-20 |
| 状态 | 已合并（决策记录） |
| 裁决人 | 架构师 |
| 基线文档 | `Docs/UEMCP-架构设计.md` v0.1.0（已合并入 v0.2.0） |
| 输入 | `Docs/UEMCP-测试计划.md` §8 D1、D1b、D2、D6、D10、D11、D12 |
| 适用范围 | UEMCP MVP（UE 5.4.x） |

> **本补充内容已全部合并进《UEMCP 架构设计》v0.2.0，保留作决策记录。实现与验收以 v0.2.0 为准。**

本文是 v0.1.0 的增量裁决记录。自 v0.2.0 起，**实现与验收以《UEMCP 架构设计》v0.2.0 为准**；本文仅用于追溯决策依据，不再作为冲突时的首选依据。

---

## 0. 裁决总览

| # | 裁决 | 一句话结论 | 主要影响用例 |
|---|---|---|---|
| D1 | 工具级错误码统一映射 | `tools/call` 的工具执行失败一律 **HTTP 200 + `isError:true` + `structuredContent.error`**；桥接内部使用稳定数字码，对外只认字符串码；新增/明确 24 个工具级错误码；`TIMEOUT` 退役，统一用 `BRIDGE_TIMEOUT` | TOOL-11/15/22/23/25/31、RES-10 |
| D1b | `INVALID_ARGUMENT` 二义 | 协议层参数错误改名 `INVALID_PARAMS`（400/-32602）；工具层参数校验失败固定为 **200 + `isError:true` + `INVALID_ARGUMENT`** | PROTO-12 |
| D2 | SSE 最低客户端基线 | 必测基线 = **Cursor 0.45.11** + 仓库内自研脚本 `examples/generic/sse_client.py`；脚本失败即 FAIL；Cursor 不可安装为 N/A；Cursor 可安装但因服务端缺陷失败为 FAIL | CLIENT-05、PROTO-14 |
| D6 | 双重权限门错误码 | 服务端未注册 → `TOOL_DISABLED`；桥接 `allowWrite=false` / `allowConsole=false` → `PERMISSION_DENIED`；桥接 `allowExec=false` → `EXEC_DISABLED` | SEC-11、TOOL-31 变体 |
| D10 | MCP Server 端口冲突 | **MCP Server 失败退出（exit code 2），不换端口**；桥接端继续按发现文件回退（18778–18788，再临时端口） | RES-06、RES-07 |
| D11 | `--allow-destructive` 范围 | 只豁免 P1 破坏性操作；**不豁免** console/exec。P2 由 `--allow-console` / `--allow-exec` 各自作为策略级确认 | TOOL-30/32、SEC-09、SEC-11 |
| D12 | read-only 下混合工具 | **注册，但 inputSchema 按只读动作收窄**：level_control 2 个 action、material_params 2 个、blueprint 1 个；read-only 共 **7** 个工具 | PROTO-03、SEC-01 |

---

## 1. 统一原则（D1/D1b 的基础）

### 1.1 三层分离

| 层 | 失败类型 | 对外形态 | HTTP | 顶层 JSON-RPC |
|---|---|---|---|---|
| MCP 协议层 | JSON 解析失败、JSON-RPC 信封错误、未知 method、会话缺失/过期、鉴权失败、请求体超限、HTTP 层限流 | JSON-RPC `error` | 非 200 | 有 `error` |
| MCP 工具层 | 已知工具的参数校验失败、对象不存在、策略拒绝、桥接不可达/超时/忙、编辑器执行异常 | `CallToolResult` | **200** | **无 `error`**，有 `result` |
| 桥接内部层 | 编辑器执行异常 | JSON-RPC `error`（仅 Server↔Bridge） | 按 §1.5 | 有 `error`，**不直接暴露给客户端** |

### 1.2 对外 HTTP 状态固定规则

1. **只要请求已经成功路由到一个已知工具的 `tools/call`，任何执行失败都是 HTTP 200。**
2. `isError` 必须为 `true`，`structuredContent.ok` 必须为 `false`，`structuredContent.error` 必须存在。
3. 禁止出现“HTTP 4xx/5xx + 工具错误对象”或“HTTP 200 + 顶层 JSON-RPC error”的混合形态。
4. 只有 §1.1 的协议层失败才使用非 200。
5. 这条规则同时适用于 Streamable HTTP、旧版 SSE（结果通过 SSE message 下发）与 stdio。

### 1.3 `isError` 语义

| 场景 | `isError` | `structuredContent.ok` | `error` 字段 |
|---|---|---|---|
| 成功 | `false`（或缺省） | `true` | 不存在 |
| 工具执行失败 | `true` | `false` | 必须存在 |
| 成功但有警告（`rolledBack:false`、`outputAvailable:false`、截图过大只返回路径） | `false` | `true` | 不存在；写 `warnings[]` |
| 策略拒绝（隐藏工具、桥接权限门） | `true` | `false` | 必须存在 |
| 协议层失败 | 无 `result` | — | 顶层 JSON-RPC error |

补充：

- `content[0].text` 固定以 `"<CODE>: <message>"` 开头，便于不支持结构化内容的客户端。
- `error.retryable` 为布尔值；客户端只能据此决定是否自动重试，不能根据 HTTP 状态猜。
- `error.details` 必须是 JSON 对象；大小上限 16 KiB（超出截断并附 `detailsTruncated:true`）。

### 1.4 数字码使用规则

- 对外契约只认 **字符串 `code`**；数字码只存在于桥接内部与文档映射表。
- 桥接数字码固定、不可复用；新增错误只能追加新码，不得改变既有码的含义。
- `-32700` ~ `-32603` 只用于协议/JSON-RPC 标准错误。
- `-32000` ~ `-32099` 为应用错误。
- **`-32001` 专用于 `SESSION_NOT_FOUND`**（架构 v0.1.0 同时把它用于 `BRIDGE_TIMEOUT`，属于冲突；本次将 `BRIDGE_TIMEOUT` 迁移到 `-32020`）。

### 1.5 桥接内部 HTTP 状态（仅 Server↔Bridge 可见）

| 桥接错误类别 | 桥接 HTTP |
|---|---|
| 参数/选择器/对象不存在 | 400 或 404 |
| 权限/开关拒绝 | 403 |
| 状态冲突（PIE、脏包、已存在、事务失败） | 409 |
| 请求/结果过大 | 413 |
| 队列满/限流 | 429 |
| 超时 | 504 |
| 桥接未启动/不可达 | 503（由 MCP Server 在连接阶段合成） |
| 未分类执行异常 | 500 |
| 能力不支持 | 501 |

MCP Server 转换规则：

- 连接拒绝、DNS/端口不可达、连接超时 → `BRIDGE_UNAVAILABLE`。
- 收到合法 JSON-RPC error → 按其 `data.errorCode` 映射；未知 errorCode → `INTERNAL`。
- 收到非 JSON 响应或 HTTP 5xx 且无合法 JSON-RPC body → `INTERNAL`（`details.bridgeHttpStatus`），**不要**误报为 `BRIDGE_UNAVAILABLE`。
- 桥接返回 429/504 且带 JSON-RPC error → 使用 `BRIDGE_BUSY` / `BRIDGE_TIMEOUT`。

### 1.6 协议层错误码表（对外非 200）

| code | HTTP | JSON-RPC | 说明 |
|---|---|---|---|
| `PARSE_ERROR` | 400 | -32700 | JSON 解析失败 |
| `INVALID_REQUEST` | 400 | -32600 | JSON-RPC 信封结构错误 |
| `METHOD_NOT_FOUND` | 404 | -32601 | 未知 JSON-RPC method |
| `INVALID_PARAMS` | 400 | -32602 | `tools/call` 信封/未知工具名错误（见 §3） |
| `SESSION_NOT_FOUND` | 404 | -32001 | 会话缺失、未知或过期 |
| `UNAUTHORIZED` | 401 | -32019 | MCP 入口 Bearer token 错误/缺失（启用鉴权时） |
| `PAYLOAD_TOO_LARGE` | 413 | -32011 | HTTP 请求体超过 8 MiB |
| `RATE_LIMITED` | 429 | -32012 | HTTP 中间件限流，尚未进入工具 |
| `INTERNAL` | 500 | -32603 | 协议层未捕获异常 |

补充：

- 这些响应没有 `CallToolResult`，因此不存在 `isError` 字段；客户端按 JSON-RPC `error` 处理。
- Host/Origin 拒绝使用 HTTP 421/403 + `INVALID_REQUEST`，不进入工具层。
- 同一字符串码（如 `PAYLOAD_TOO_LARGE`、`RATE_LIMITED`）在两层都可能出现，靠 HTTP 状态与“是否存在 `result`”区分；测试必须同时断言层位。

---

## 2. D1：工具级错误码统一映射

### 2.1 裁决

1. 所有工具级错误对外 **HTTP 200 + `isError:true` + `structuredContent.error`**；顶层 JSON-RPC 不出现 `error`。
2. 补全错误码表（§2.4）：测试计划列出的 24 个码中，`TIMEOUT` 退役，其余 23 个入库；另补 v0.1.0 遗漏的 `ACTOR_NOT_FOUND`，合计新增/明确 24 个工具级错误码。
3. `TIMEOUT` **退役**，不新增该字符串码；Python/截图/搜索的所有超时分别使用 `BRIDGE_TIMEOUT`、`CAPTURE_TIMEOUT`、`SEARCH_TIMEOUT`。
4. 具体错误优先于通用错误：能用 `MATERIAL_NOT_FOUND` 就不返回 `NOT_FOUND`。
5. `details` 必须承载可判定的上下文（见 §2.5），测试据此断言，不能只断言字符串码。

### 2.2 为什么不把工具错误映射成 4xx/5xx

- MCP 的工具执行错误语义是 in-band（`isError`），不是传输失败。
- 4xx/5xx 会让部分客户端在解析 `CallToolResult` 之前就按传输错误处理，模型拿不到错误码，也无法纠正参数。
- 统一 200 后，测试判定唯一：看 `result.isError` 与 `result.structuredContent.error.code`。
- HTTP 状态码仍保留给“请求本身不成立”的协议层错误。

### 2.3 错误码命名规则

| 规则 | 示例 |
|---|---|
| 资源域前缀 + `_NOT_FOUND` | `ACTOR_NOT_FOUND`、`LEVEL_NOT_FOUND`、`MATERIAL_NOT_FOUND`、`BLUEPRINT_NOT_FOUND` |
| 能力/类型不匹配 | `NOT_A_MATERIAL`、`NOT_AN_INSTANCE`、`NOT_A_BLUEPRINT`、`TYPE_MISMATCH` |
| 状态冲突 | `UNSAVED_CHANGES`、`ALREADY_EXISTS`、`EDITOR_UNSAFE_STATE`、`PIE_NOT_RUNNING` |
| 超时带域 | `SEARCH_TIMEOUT`、`CAPTURE_TIMEOUT`；通用执行超时 `BRIDGE_TIMEOUT` |
| 禁止同义码 | 不新增 `TIMEOUT`、`MATERIAL_INSTANCE_NOT_FOUND`、`BP_NOT_FOUND` 等别名 |

### 2.4 补全后的工具级错误码表

> 完整表包含 v0.1.0 已有码与新增码。`MCP HTTP` 对外恒为 200；`Bridge HTTP` 仅内部可见。

| code | Bridge JSON-RPC | Bridge HTTP | MCP HTTP | isError | retryable | 含义 |
|---|---|---|---|---|---|---|
| `INVALID_ARGUMENT` | -32602 | 400 | 200 | true | false | 工具参数未通过 Schema 或业务校验 |
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
| `BRIDGE_TIMEOUT` | **-32020** | 504 | 200 | true | true | 游戏线程任务超时 |
| `BRIDGE_BUSY` | -32002 | 429 | 200 | true | true | 队列满/编辑器忙 |
| `PERMISSION_DENIED` | -32003 | 403 | 200 | true | false | 策略或桥接权限门拒绝（非 exec） |
| `TOOL_DISABLED` | -32004 | 403 | 200 | true | false | 工具未在当前策略/开关组合中注册 |
| `CONFIRMATION_REQUIRED` | -32005 | 428 | 200 | true | false | 需要确认但未满足 |
| `NOT_FOUND` | -32006 | 404 | 200 | true | false | 通用资源不存在（优先使用具体码） |
| `CONFLICT` | -32007 | 409 | 200 | true | false | 通用冲突（优先使用具体码） |
| `UNSUPPORTED` | -32008 | 501 | 200 | true | false | 当前引擎/平台不支持 |
| `EXECUTION_ERROR` | -32009 | 500 | 200 | true | false | 编辑器执行异常（未分类） |
| `EDITOR_UNSAFE_STATE` | -32010 | 409 | 200 | true | true | PIE/编译/加载中，重试可能成功 |
| `PAYLOAD_TOO_LARGE` | -32011 | 413 | 200 | true | false | **工具级**结果/图像超限（协议级见 §3） |
| `RATE_LIMITED` | -32012 | 429 | 200 | true | true | **工具级**限流（HTTP 层见 §3） |
| `SAVE_FAILED` | -32013 | 500 | 200 | true | false | 保存资产/关卡失败 |
| `PYTHON_ERROR` | -32014 | 500 | 200 | true | false | Python 异常，含 traceback |
| `RESULT_NOT_SERIALIZABLE` | -32015 | 500 | 200 | true | false | 返回值无法 JSON 化 |
| `CAPABILITY_UNAVAILABLE` | -32016 | 501 | 200 | true | false | 能力探测为 false |
| `COMMAND_NOT_ALLOWED` | -32017 | 403 | 200 | true | false | 控制台命令被白名单/拒绝表拦住 |
| `CONFIRMATION_DENIED` | -32018 | 403 | 200 | true | false | 用户在 elicitation 中拒绝 |

说明：

- `INVALID_ARGUMENT` 的 Bridge HTTP 写 400，但它仍然走 JSON-RPC error，由 MCP Server 转成 200 + `isError`。
- `PAYLOAD_TOO_LARGE` / `RATE_LIMITED` 只有在请求已被工具接收后才算工具级；HTTP 中间件阶段触发的走 §3 协议层。
- `NOT_FOUND` / `CONFLICT` 保留但不再新增使用；新代码必须用具体码。

### 2.5 `details` 必填契约

| code | 必填 `details` 字段 |
|---|---|
| `INVALID_ARGUMENT` | `issues: [{path, code, message}]` |
| `ACTOR_NOT_FOUND` | `selector: {kind, value}`，`matches: []` |
| `AMBIGUOUS_SELECTOR` | `selector: {kind, value}`，`matches: [{actorPath, name, label, class}]`（≥2） |
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

### 2.6 特殊裁决：`UNSAVED_CHANGES` 与 `CONFIRMATION_REQUIRED`

`ue_level_control {action:"open"}` 的判定固定为：

| 条件 | 返回 |
|---|---|
| 有脏包且 `allowDiscardUnsaved=false` | `UNSAVED_CHANGES`（不管 `confirm` 是什么） |
| 有脏包、`allowDiscardUnsaved=true`、`confirm=false`，且未满足破坏性确认 | `CONFIRMATION_REQUIRED` |
| 有脏包、`allowDiscardUnsaved=true`、`confirm=true`，或 elicitation 已批准，或 `--allow-destructive` | 执行打开 |
| 无脏包 | 执行打开 |

同理，`save_all` 在 `confirm=false` 时返回 `CONFIRMATION_REQUIRED`，而不是 `UNSAVED_CHANGES`。

### 2.7 对工具 Schema / 错误码表 / 策略矩阵的影响

- **工具 Schema**：无入参/出参结构变更；`error` 对象新增 `details` 必填契约（§2.5），`error.code` 必须是本文表中的字符串码。
- **错误码表**：以 §2.4 替换 v0.1.0 §2.9 的工具级部分；`BRIDGE_TIMEOUT` 改为 `-32020`；新增 §1.6 协议层表。
- **策略矩阵**：无变化。工具可见性、确认规则、开关范围均不受 D1 影响；只改变失败时的返回形态与错误码。

---

## 3. D1b：`INVALID_ARGUMENT` 的唯一返回形态

### 3.1 裁决

**协议层与工具层彻底分名：**

| 场景 | 对外 code | HTTP | JSON-RPC 顶层 |
|---|---|---|---|
| `tools/call` 信封不合法：`params` 非对象、缺少 `name`、`name` 非字符串、`arguments` 非对象、`arguments` 为数组、未知工具名 | `INVALID_PARAMS` | 400 | `error.code = -32602` |
| 已知工具，`arguments` 未通过该工具的 inputSchema（类型、enum、required、additionalProperties、范围） | `INVALID_ARGUMENT` | **200** | 无 error；`result.isError=true` |

**边界判定规则**：只要 `name` 是字符串且能在当前注册表中找到该工具，后续一切参数问题都归工具层；否则归协议层。

### 3.2 两个形态的示例

协议层：

```json
{
  "jsonrpc": "2.0",
  "id": 12,
  "error": {
    "code": -32602,
    "message": "Invalid params: arguments must be an object",
    "data": { "errorCode": "INVALID_PARAMS" }
  }
}
```

工具层：

```json
{
  "jsonrpc": "2.0",
  "id": 13,
  "result": {
    "content": [
      { "type": "text", "text": "INVALID_ARGUMENT: sections[0] must be one of ..." }
    ],
    "structuredContent": {
      "ok": false,
      "error": {
        "code": "INVALID_ARGUMENT",
        "message": "sections[0] must be one of ...",
        "retryable": false,
        "details": {
          "issues": [
            { "path": ["sections", 0], "code": "invalid_enum_value", "message": "..." }
          ]
        }
      },
      "meta": { "requestId": "req_...", "durationMs": 1 }
    },
    "isError": true
  }
}
```

### 3.3 实施要求

- zod 校验只针对 `arguments` 内容；信封校验在路由层单独做。
- 未知工具名返回协议层 `INVALID_PARAMS`，不返回 `TOOL_DISABLED`（后者只用于“已注册但因策略/开关被隐藏”的工具）。
- **工具存在性按完整工具目录（10 个）判断，不按当前可见集合判断。** 只有完整目录里也没有的名字才是 `INVALID_PARAMS`；在完整目录里但未注册的，进入策略层并返回 `TOOL_DISABLED`。
- 不在 `arguments` 校验失败时返回 400；否则客户端会把它当传输错误。
- `tools/call` 的参数校验顺序：信封 → 完整目录存在性 → 策略/开关 → zod → 业务校验。

### 3.4 对工具 Schema / 错误码表 / 策略矩阵的影响

- **工具 Schema**：不变；只是把“信封校验”和“arguments 校验”放在不同层。
- **错误码表**：协议层新增 `INVALID_PARAMS`；工具层 `INVALID_ARGUMENT` 只保留 in-band 形态。
- **策略矩阵**：无变化；策略/开关判断发生在 zod 之前，被隐藏工具仍返回 `TOOL_DISABLED`。

### 3.5 测试计划更新

- **PROTO-12**：删除“满足其一即通过”，固定判定为 (b)：
  - HTTP 200；
  - `result.isError == true`；
  - `result.structuredContent.ok == false`；
  - `result.structuredContent.error.code == "INVALID_ARGUMENT"`；
  - `details.issues` 为数组且非空；
  - 响应中不存在顶层 `error`。
- 新增 **PROTO-12b**：`tools/call` 的 `arguments` 传数组 → HTTP 400 + 顶层 `error.code == -32602` + `data.errorCode == "INVALID_PARAMS"`。
- 新增 **PROTO-12c**：`tools/call` 未知工具名 → HTTP 400 + `-32602` + `INVALID_PARAMS`。

---

## 4. D2：旧版 SSE 兼容的最低客户端基线

### 4.1 裁决

**双基线，脚本为必测，Cursor 版本为兼容性证据。**

| 基线 | 具体对象 | 性质 |
|---|---|---|
| 客户端基线 | **Cursor 0.45.11**（0.45 系列是 MCP 引入期、远程配置以 SSE 为主的版本线） | 兼容性证据；可安装时必须测 |
| 脚本基线 | 仓库内 `examples/generic/sse_client.py`（仅标准库） | **必测横线，失败即 FAIL** |

版本说明：

- 若测试环境无法安装 0.45.11，允许用 **0.45.x 系列中最早可安装的版本**替代，必须记录实际版本号；不得跨到 0.46+ 作为 SSE 基线。
- 0.46+ 的 `url` 语义可能已转向 Streamable HTTP，不能用于“旧版 SSE”判定。

### 4.2 自研脚本规格（可直接实现）

路径：`examples/generic/sse_client.py`

CLI：

```bash
python examples/generic/sse_client.py \
  --url http://127.0.0.1:18777/sse \
  --expect-tools 7 \
  --timeout 10
```

流程：

1. `GET /sse`，`Accept: text/event-stream`。
2. 逐行解析 SSE；等待 `event: endpoint`，取 `data:` 得到 `/messages?sessionId=...`，解析为绝对 URL。
3. 向该 URL `POST` `initialize`（`protocolVersion: "2024-11-05"`），在 SSE 流中按 `id` 匹配响应。
4. `POST` `notifications/initialized`，断言 HTTP 202。
5. `POST` `tools/list`，断言工具数与 `--expect-tools` 一致。
6. `POST` `tools/call` `ue_editor_status`，断言 `result.structuredContent.ok == true`。
7. 输出 JSON 摘要并按退出码退出。

退出码：

| 退出码 | 含义 |
|---|---|
| 0 | 全部通过 |
| 1 | 断言失败（结构/字段/数量不符） |
| 2 | 传输失败（连接拒绝、HTTP 非预期） |
| 3 | 超时 |
| 4 | SSE 解析失败（无 endpoint 事件/无匹配响应） |

约束：

- 仅用 Python 标准库（`http.client`/`urllib`/`threading`），不引入 `requests`。
- 所有等待有超时，禁止无限阻塞。
- 脚本本身不依赖 Cursor、不依赖 Node。

### 4.3 通过/不适用/失败判定

**CLIENT-05 总判定：**

| 条件 | 判定 |
|---|---|
| 自研脚本 PASS，且 Cursor 基线 PASS | **通过** |
| 自研脚本 PASS，Cursor 基线无法安装/无法获取 | **通过（Cursor 部分 N/A）** |
| 自研脚本 PASS，Cursor 基线可安装但客户端本身声明不支持 SSE | **通过（Cursor 部分 N/A，需附版本与证据）** |
| 自研脚本 FAIL | **失败** |
| 自研脚本 PASS，Cursor 基线可安装、支持 SSE，但因服务端响应错误（4xx/5xx、SSE 格式错误、endpoint 缺失）失败 | **失败** |
| 自研脚本 PASS，Cursor 基线可安装，但失败原因是客户端 UI/配置限制（如无法填写本地 URL、强制 OAuth），与服务端无关 | **通过（N/A，需附截图与版本）** |

**为什么脚本是必测**：SSE 兼容性是我们对协议端点的承诺，不能依赖某个第三方客户端的安装可用性。Cursor 只作为真实客户端证据。

### 4.4 对工具 Schema / 错误码表 / 策略矩阵的影响

- **工具 Schema**：不变。
- **错误码表**：不新增错误码；SSE 端点失败仍按协议层/传输层处理。
- **策略矩阵**：无变化；SSE 与 Streamable HTTP 共享同一策略与工具注册。

### 4.5 测试计划更新

- **CLIENT-05**：
  - 前提写明 Cursor **0.45.11**（或 0.45.x 替代并记录）。
  - 判定改为上述 4.3 的表。
  - 证据必须包含：Cursor 版本、配置截图、`/sse` 响应头、失败时的客户端日志。
- **PROTO-14**：明确使用 `examples/generic/sse_client.py`，退出码 0 即通过；补充断言：`/messages` 返回 202、SSE 流中出现与请求 `id` 匹配的响应。
- **附录 A**：增加 “A.4 旧版 SSE 脚本调用” 小节，给出上面的命令。

---

## 5. D6：双重权限门被拒时的错误码

### 5.1 裁决

**按“哪一道门拒绝”区分，不再使用多选。**

| 拒绝位置 | 条件 | 返回 code | `details.gate` |
|---|---|---|---|
| MCP Server 未注册 | 策略为 read-only / standard；或 P2 开关未开 | `TOOL_DISABLED` | `server.policy` / `server.allowConsole` / `server.allowExec` |
| 桥接写权限门 | Server 已放行，桥接 `allowWrite=false` | `PERMISSION_DENIED` | `bridge.allowWrite` |
| 桥接控制台门 | Server 已放行，桥接 `allowConsole=false` | `PERMISSION_DENIED` | `bridge.allowConsole` |
| 桥接执行门 | Server 已放行，桥接 `allowExec=false` | `EXEC_DISABLED` | `bridge.allowExec` |
| 命令白名单/拒绝表 | 命令本身不允许 | `COMMAND_NOT_ALLOWED` | — |

### 5.2 理由

- `TOOL_DISABLED` 表达“这个工具不在你当前可见的工具集里”，属于服务端注册层。
- `PERMISSION_DENIED` 表达“工具存在，但当前编辑器配置不允许这个操作”，适合写/控制台。
- `EXEC_DISABLED` 专门表达“任意代码执行被禁用”。把它用于 console 会模糊风险语义；console 的拒绝用 `PERMISSION_DENIED`。
- 三者都对外 200 + `isError`，测试通过字符串码唯一判定。

### 5.3 补充规则

- 桥接拒绝时 **不得** 执行任何编辑器操作；拒绝发生在游戏线程入队之前。
- `details.gate` 必须出现，便于测试和排障。
- 桥接的 `PERMISSION_DENIED` 与 MCP Server 的 `PERMISSION_DENIED` 共用字符串码，但 `details.gate` 区分来源。
- 如果 Server 与桥接同时关闭，以 Server 为准，返回 `TOOL_DISABLED`（工具根本不出现；直接调用也是该码）。
- `EXEC_DISABLED` 加入错误码表（Bridge `-32043`，MCP HTTP 200）。

### 5.4 对工具 Schema / 错误码表 / 策略矩阵的影响

- **工具 Schema**：不变。
- **错误码表**：新增 `EXEC_DISABLED`（-32043）；`PERMISSION_DENIED` 增加 `details.gate`；`TOOL_DISABLED` 明确只表示服务端未注册。
- **策略矩阵**：可见性判定不变；新增“拒绝来源”维度（Server 注册层 / 桥接能力层），不新增开关。

### 5.5 测试计划更新

- **SEC-11**：固定预期为 `EXEC_DISABLED`，`details.gate=="bridge.allowExec"`；去掉多选。
- 新增 **SEC-11b**：Server `standard`、桥接 `allowWrite=false`，调用 `ue_actor_edit` → `PERMISSION_DENIED` + `details.gate=="bridge.allowWrite"`，场景无变化。
- 新增 **SEC-11c**：Server `full --allow-console`、桥接 `allowConsole=false`，调用 `ue_console_command` → `PERMISSION_DENIED` + `details.gate=="bridge.allowConsole"`。
- **TOOL-31**：保持 `COMMAND_NOT_ALLOWED`；另加一条变体（桥接 `allowConsole=false`）断言 `PERMISSION_DENIED`，避免与白名单拒绝混淆。
- **TOOL-30/32**：前提保留双开关；这是能力门，不是确认门。

---

## 6. D10：MCP Server 端口被占的行为

### 6.1 裁决（定死）

**MCP Server：失败退出，不自动换端口。**

具体语义：

- 默认绑定 `127.0.0.1:18777`。
- `EADDRINUSE` 或其他 bind 失败 → **2 秒内退出**，退出码 **2**。
- stderr 输出一行 JSON：

```json
{"level":"error","event":"http_bind_failed","host":"127.0.0.1","port":18777,"code":"EADDRINUSE","message":"listen EADDRINUSE: address already in use 127.0.0.1:18777"}
```

- 不启动会话清理器、不打开任何其他端口、不写发现文件、不进入重试循环。
- 用户换端口必须显式：`--port 18790`（或 `UEMCP_HTTP_PORT`），并同步修改客户端 URL。
- `--port 0` 允许用于 CI/测试，实际端口写入启动日志与 `/health`；不推荐给普通客户端。

**桥接端：保留自动回退，但把语义写死。**

- 启动时先删除本项目对应的陈旧发现文件。
- 端口尝试顺序：配置端口（默认 18778）→ 18779 → … → 18788（共 11 个）→ 系统临时端口（bind port 0）。
- 第一个成功绑定的端口即实际端口，写入 `~/.uemcp/bridges/<hash>.json` 与 `~/.uemcp/bridge.json` 的 `port`/`url`。
- 全部失败 → 写编辑器日志 `[UEMCP] bridge_bind_failed`，**不写**任何可用发现文件，MCP Server 侧表现为 `BRIDGE_UNAVAILABLE`。
- 桥接的回退对客户端透明：MCP Server 通过发现文件拿实际端口。

### 6.2 为什么两端策略不同

- MCP 客户端（Claude Code/Cursor）配置的是固定 URL，MCP Server 静默换端口会导致“服务启动了但客户端连不上”，且用户很难发现。
- 桥接的 URL 由发现文件动态发布，换端口不影响 MCP Server；编辑器不应因为默认端口被占就无法提供自动化。
- 因此：**面向固定客户端的一端 fail-fast；面向发现文件的一端可回退。**

### 6.3 客户端如何发现

| 端 | 发现方式 |
|---|---|
| MCP Server | 客户端配置 `http://127.0.0.1:<显式端口>/mcp`；默认 18777；换端口必须改配置 |
| 桥接 | MCP Server 读取 `~/.uemcp/bridges/<projectHash>.json` / `~/.uemcp/bridge.json` 的 `url`；无需客户端介入 |
| 排障 | `GET /health` 返回实际端口（MCP Server 为自身 `port`；桥接 `/health` 返回 `port`） |

### 6.4 对工具 Schema / 错误码表 / 策略矩阵的影响

- **工具 Schema**：不变。
- **错误码表**：不新增错误码；`BRIDGE_UNAVAILABLE` 仍是桥接不可达时的唯一工具级码。
- **策略矩阵**：无变化；仅明确 MCP Server 的启动失败语义与桥接的端口发现语义。

### 6.5 测试计划更新

- **RES-06**：固定为：
  - 进程退出码 == 2；
  - stderr 含 `http_bind_failed` 与 `EADDRINUSE`；
  - 2 秒内退出；
  - 无 18777 监听（占用进程保持）；
  - 不存在“自动换端口成功”分支。
- **RES-07**：改为：
  - 占用 18778 后启动编辑器；
  - 桥接成功绑定 18779（或其他 18778–18788 端口）；
  - 项目发现文件的 `port`/`url` 指向实际端口；
  - 该端口 `/health` 返回 `app=uemcp-bridge`；
  - MCP Server 能通过发现文件完成 `ue_editor_status`；
  - 再补一条“18778–18788 全占”用例：无可用发现文件，MCP 返回 `BRIDGE_UNAVAILABLE`。
- 架构文档 **R4**、**§10.5** 的“换端口/端口回退”表述按上述拆分修正。

---

## 7. D11：`--allow-destructive` 的生效范围

### 7.1 裁决

**`--allow-destructive` 只作用于 P1 破坏性操作，不豁免 P2 的每次调用确认。**

| 开关 | 作用域 | 不作用域 |
|---|---|---|
| `--allow-destructive` | `ue_actor_edit` 的 `delete`；`ue_level_control` 的 `open`（丢弃未保存）；`save_all` 的批量保存确认 | console、python、任何 P2 工具 |
| `--allow-console` | 使 `ue_console_command` 可见；无 elicitation 时作为该工具的**策略级确认** | python、P1 破坏性操作 |
| `--allow-exec` | 使 `ue_python_exec` 可见；无 elicitation 时作为该工具的**策略级确认** | console、P1 破坏性操作 |

### 7.2 确认模式（固定）

| 工具/操作 | 客户端支持 elicitation | 客户端不支持 elicitation |
|---|---|---|
| P1 delete / open 丢弃 / save_all | 每次调用弹 `elicitation/create`；拒绝 → `CONFIRMATION_DENIED` | 需 `--allow-destructive`；否则 `CONFIRMATION_REQUIRED` |
| `ue_console_command` | 每次调用弹 elicitation；拒绝 → `CONFIRMATION_DENIED` | 需 `--allow-console`；开关本身视为策略级确认，审计记 `confirmationMode:"policy"` |
| `ue_python_exec` | 每次调用弹 elicitation；拒绝 → `CONFIRMATION_DENIED` | 需 `--allow-exec`；开关本身视为策略级确认，审计记 `confirmationMode:"policy"` |

补充：

- 即使 `--allow-console`/`--allow-exec` 已开，只要客户端声明支持 elicitation，**仍然每次询问**（最安全，且行为可预测）。
- 桥接端的 `allowConsole`/`allowExec` 只是能力门，不承担确认语义。
- `--allow-destructive` 不能单独让 P2 工具出现；P2 的可见性只由对应的 `--allow-console`/`--allow-exec` 决定。
- 审计字段：`confirmationMode ∈ {"elicitation","policy","none"}`；`policy` 时必须同时记录 `confirmationSwitch`（`--allow-destructive` / `--allow-console` / `--allow-exec`）。

### 7.3 对工具 Schema / 错误码表 / 策略矩阵的影响

- **工具 Schema**：不变。
- **错误码表**：不新增错误码；`CONFIRMATION_REQUIRED` / `CONFIRMATION_DENIED` 的触发条件更明确。
- **策略矩阵**：**确认列**更新：P1 破坏性操作由 `--allow-destructive` 兜底；console/exec 由各自能力开关兼作策略确认；`--allow-destructive` 不再出现在 P2 的确认路径。

### 7.4 测试计划更新

- **TOOL-30**：前提改为 `--policy full --allow-console`（去掉“另加 `--allow-destructive`”的括号说明）。
- **TOOL-32**：前提改为 `--policy full --allow-exec`（不再依赖 `--allow-destructive`）。
- **SEC-09**：保持 standard + `--allow-destructive` 删除成功。
- 新增 **SEC-15**：`--allow-destructive` 单独开启（无 `--allow-exec`）时，`ue_python_exec` 不在 `tools/list`；直接调用 → `TOOL_DISABLED`，不得执行。
- 新增 **SEC-16**：`--allow-exec` 单独开启（无 `--allow-destructive`）时，delete 无 elicitation → `CONFIRMATION_REQUIRED`；exec 可执行。
- **SEC-10**：保持 elicitation 拒绝分支；补记 `confirmationMode`。

---

## 8. D12：read-only 下 P0/P1 混合工具是否出现在 `tools/list`

### 8.1 裁决

**出现在 `tools/list`，但 inputSchema 按只读动作收窄。**

| 工具 | read-only 下注册的 action | read-only 下不注册的 action |
|---|---|---|
| `ue_level_control` | `get_current`, `list_dirty` | `open`, `save_current`, `save_all`, `new` |
| `ue_material_params` | `list`, `get` | `set`, `create_instance` |
| `ue_blueprint` | `query` | `compile` |

因此 read-only 的工具集合为 **7 个**：

1. `ue_editor_status`
2. `ue_actor_query`
3. `ue_asset_search`
4. `ue_viewport_capture`
5. `ue_level_control`（收窄）
6. `ue_material_params`（收窄）
7. `ue_blueprint`（收窄）

standard = 上述 7 个 + `ue_actor_edit` = **8 个**。
full（未开 P2 开关）= **8 个**。
full + 仅 `--allow-console` = **9 个**。
full + 仅 `--allow-exec` = **9 个**。
full + 两者 = **10 个**。

### 8.2 调用语义

- 客户端按 `tools/list` 的收窄 Schema 调用：写 action 会先被 zod 拒绝 → 工具层 `INVALID_ARGUMENT` + `details.issues`。
- 若绕过 Schema 直达 handler（例如内部调用）：handler 必须再次检查策略，返回 `PERMISSION_DENIED` + `details.gate="server.policy"`。
- 不允许返回 `TOOL_DISABLED` 来表示“混合工具存在但该 action 被禁”——工具本身是可见的，用参数校验/策略拒绝更准确。
- 工具描述与 `annotations` 随策略变化：
  - read-only 下这三个工具 `readOnlyHint=true`；
  - standard/full 下 `readOnlyHint=false`；
  - `destructiveHint=false`（它们的写操作不是删除类）。
- `inputSchema` 的 `action.enum` 在注册时生成，不在调用时临时过滤。

### 8.3 为什么不是“整体隐藏”

- 三个工具的只读动作有独立价值（看关卡、读材质参数、看蓝图结构）。
- 收窄 Schema 让模型在工具列表阶段就知道不能写，比运行时报错更可预测。
- 也避免“read-only 下工具数过少”导致客户端体验下降。

### 8.4 测试计划更新

- **PROTO-03**：
  - 修正计数：read-only 不是 6，而是 **7**（原文列出 7 项却写 6，属笔误）。
  - 断言 read-only 下 7 个工具名集合完全相等。
  - 断言三个混合工具的 `inputSchema.properties.action.enum` 分别为：
    - level_control = `["get_current","list_dirty"]`
    - material_params = `["list","get"]`
    - blueprint = `["query"]`
  - standard 8、full 8、full+console 9、full+exec 9、full+both 10。
  - 断言 read-only 下混合工具 `annotations.readOnlyHint == true`。
- **SEC-01**：
  - (a) 列表不含 `ue_actor_edit`、`ue_console_command`、`ue_python_exec`；
  - (b) 直接调用 `ue_actor_edit` → `TOOL_DISABLED`；
  - (c) 直接调用 `ue_python_exec` → `TOOL_DISABLED`，message 不透露工具细节；
  - 新增 (d) 调用 `ue_level_control {action:"save_current"}` → `INVALID_ARGUMENT`（Schema 收窄），且未保存任何内容；
  - 新增 (e) 调用 `ue_material_params {action:"set",...}` → `INVALID_ARGUMENT`，材质未改变；
  - 新增 (f) 调用 `ue_blueprint {action:"compile",...}` → `INVALID_ARGUMENT`，蓝图未编译。
- **PROTO-03** 的判定依赖“集合相等”，不得用“包含”代替。

---

## 9. 架构文档需同步的章节

| 章节 | 需要修改的内容 | 关联裁决 |
|---|---|---|
| §1.4 成功判据 | “read-only 下写工具不在 tools/list”改为“纯写工具不在；混合工具以收窄 Schema 出现” | D12 |
| §2.3 端口与进程规划 | MCP Server 端口失败 = 失败退出（exit 2）；桥接 = 18778–18788 回退 + 临时端口 | D10 |
| §2.9 错误模型 | 拆分协议层/工具层；工具错误统一 200；`INVALID_PARAMS` 新增；`BRIDGE_TIMEOUT` 改为 -32020；`SESSION_NOT_FOUND` 固定 -32001；补全 §2.4 表；`TIMEOUT` 退役 | D1、D1b |
| §3.3 Streamable HTTP | 增加一句：已路由工具的执行失败一律 200 + `isError`，不得用 4xx/5xx；修正会话错误码引用 | D1、D1b |
| §3.4 旧版 SSE | 写明基线 Cursor 0.45.11 + `sse_client.py`；说明通过/不适用规则 | D2 |
| §3.5.3 Cursor 配置 | 注明 0.45.x 基线用于 SSE，0.46+ 行为需另测 | D2 |
| §5.0.1 返回封装 | `isError` 与 `ok` 的镜像关系；错误 `content` 前缀；禁止混合形态 | D1 |
| §5.0.3 权限级别 | read-only 注册规则改为“P0 + 混合工具只读子集（收窄 Schema）”；确认开关作用域 | D12、D11 |
| §5.0.4 工具注解 | 混合工具的 `readOnlyHint` 随策略模式变化 | D12 |
| §5.3 `ue_actor_edit` | 错误码补 `ACTOR_NOT_FOUND` 等；delete 确认只受 `--allow-destructive` 影响 | D1、D11 |
| §5.4 `ue_level_control` | `UNSAVED_CHANGES` 与 `CONFIRMATION_REQUIRED` 的固定顺序 | D1 |
| §5.5 `ue_asset_search` | `SEARCH_TIMEOUT` / `ASSET_REGISTRY_UNAVAILABLE` 的 details | D1 |
| §5.6 `ue_material_params` | `MATERIAL_NOT_FOUND` / `NOT_A_MATERIAL` / `NOT_AN_INSTANCE` / `PARAM_NOT_FOUND` / `TYPE_MISMATCH` / `ALREADY_EXISTS` 的 details | D1 |
| §5.7 `ue_viewport_capture` | `CAPTURE_FAILED` / `CAPTURE_TIMEOUT` / `PIE_NOT_RUNNING` 的 details | D1 |
| §5.8 `ue_console_command` | 确认规则改为“elicitation 优先，否则 `--allow-console` 作为策略确认”；不使用 `--allow-destructive`；错误码移除 `EXEC_DISABLED`，桥接 `allowConsole=false` 改为 `PERMISSION_DENIED` | D6、D11 |
| §5.9 `ue_python_exec` | 删除 `TIMEOUT`；确认规则改为“elicitation 优先，否则 `--allow-exec`”；`EXEC_DISABLED` 语义 | D1、D11 |
| §5.10 `ue_blueprint` | 补齐蓝图类错误码 details | D1 |
| §5.11 工具与策略矩阵 | read-only 列改为“收窄”；read-only 计数 7；混合工具注解随模式变化 | D12 |
| §6.3 权限门 | 双重门错误码映射；`--allow-destructive` 作用域；`--allow-console`/`--allow-exec` 兼作策略确认 | D6、D11 |
| §6.4 默认隐藏策略 | 写明 P2 的确认模式与开关边界 | D11 |
| §8.3 R4 | 端口冲突改为“MCP Server fail-fast；桥接回退” | D10 |
| §8.4 A6 | Cursor 基线改为 0.45.11 + 脚本基线 | D2 |
| §9.2 MVP 验收 | read-only 7 个工具；端口行为；错误码唯一判定 | D1、D10、D12 |
| §10.5 故障排查 | “端口占用”拆成 MCP Server/桥接两种处理；错误码排查补 `EXEC_DISABLED` | D6、D10 |
| 附录 A 架构门槛 | 增加“工具错误不得用 4xx/5xx”“MCP Server 端口失败必须 exit 2” | D1、D10 |

---

## 10. 测试计划需更新的判定点

| 用例 | 更新内容 | 关联 |
|---|---|---|
| PROTO-03 | read-only 集合 7 个；五个启动组合计数 7/8/8/9/10；断言混合工具 action enum 收窄与 `readOnlyHint` | D12 |
| PROTO-12 | 固定为 200 + `isError` + `INVALID_ARGUMENT` + `details.issues`；禁止 400 分支 | D1b |
| PROTO-12b（新增） | `arguments` 为数组 → 400 + `-32602` + `INVALID_PARAMS` | D1b |
| PROTO-12c（新增） | 未知工具名 → 400 + `-32602` + `INVALID_PARAMS` | D1b |
| PROTO-14 | 使用 `examples/generic/sse_client.py`；退出码 0；断言 `/messages` 202 与 id 匹配 | D2 |
| TOOL-10 | `TRANSACTION_FAILED` 的 `details.rolledBack` 断言；不改变 A8 降级规则 | D1 |
| TOOL-11 | 断言 `AMBIGUOUS_SELECTOR` + `details.matches` 长度 ≥2；HTTP 200 | D1 |
| TOOL-15 | 脏包 + 未允许丢弃 → `UNSAVED_CHANGES`；已允许但未确认 → `CONFIRMATION_REQUIRED` | D1 |
| TOOL-19 | `SEARCH_TIMEOUT` / `ASSET_REGISTRY_UNAVAILABLE` 的触发条件与 details | D1 |
| TOOL-22 | `NOT_AN_INSTANCE` + `details.actualClass` | D1 |
| TOOL-23 | `ALREADY_EXISTS` + `details.path` | D1 |
| TOOL-25 | `PIE_NOT_RUNNING` + `details.target=="pie"` | D1 |
| TOOL-30 | 前提去掉 `--allow-destructive`；仅 `--allow-console` 即可，前提含双开关 | D11 |
| TOOL-31 | 保持 `COMMAND_NOT_ALLOWED`；新增桥接 `allowConsole=false` 变体 → `PERMISSION_DENIED` | D6 |
| TOOL-32 | 前提去掉 `--allow-destructive`；仅 `--allow-exec` | D11 |
| SEC-01 | 增加 (d)(e)(f)：混合工具写 action → `INVALID_ARGUMENT`，且无副作用 | D12 |
| SEC-09 | 保持 `--allow-destructive` 删除成功；审计 `confirmationMode=="policy"` | D11 |
| SEC-11 | 固定 `EXEC_DISABLED` + `details.gate=="bridge.allowExec"` | D6 |
| SEC-11b（新增） | 桥接 `allowWrite=false` → `PERMISSION_DENIED` + `gate=="bridge.allowWrite"` | D6 |
| SEC-11c（新增） | 桥接 `allowConsole=false` → `PERMISSION_DENIED` + `gate=="bridge.allowConsole"` | D6 |
| SEC-15（新增） | 仅 `--allow-destructive`，exec 不可见/调用 `TOOL_DISABLED`，无代码执行 | D11 |
| SEC-16（新增） | 仅 `--allow-exec`，delete 未确认 → `CONFIRMATION_REQUIRED`；exec 可执行 | D11 |
| RES-06 | MCP Server 端口占用 → exit code 2 + `http_bind_failed` + 2 秒内退出；无换端口分支 | D10 |
| RES-07 | 桥接 18778 占用 → 回退到 18779 且发现文件端口正确；全占 → 无发现文件 + `BRIDGE_UNAVAILABLE` | D10 |
| RES-10 | 协议层请求体 >8 MiB → 413 + `-32011`；工具级内联图像超限 → 200 + warning/`PAYLOAD_TOO_LARGE`，两者不得混淆 | D1 |
| CLIENT-05 | Cursor 0.45.11 + `sse_client.py` 双基线；按 §4.3 判定 PASS/N/A/FAIL | D2 |

---

## 11. 实施注意事项（避免回归）

1. **单一错误构造器**：MCP Server 侧所有工具失败必须经同一个 `toToolError(code, message, details, retryable)` 构造，禁止 handler 各自拼 JSON。
2. **数字码集中定义**：`packages/shared/src/errors.ts` 维护 `code ↔ bridgeRpc ↔ bridgeHttp ↔ retryable` 的唯一映射表；Schema 快照测试锁定。
3. **协议层不得使用 `INVALID_ARGUMENT`**：路由层只用 `INVALID_PARAMS` / `INVALID_REQUEST` / `METHOD_NOT_FOUND` / `SESSION_NOT_FOUND` / `PARSE_ERROR`。
4. **工具层不得返回 4xx/5xx**：包括桥接不可达、超时、忙、权限拒绝。
5. **桥接必须返回 `data.errorCode`**：MCP Server 不靠 `message` 文本推断错误。
6. **只读 Schema 收窄在注册时完成**：不要在 handler 里“先接受后拒绝”作为唯一防线；handler 仍需二次校验。
7. **端口错误必须可观测**：MCP Server 启动失败只写 stderr JSON；桥接失败写 `Saved/Logs` 的 `[UEMCP]` 前缀日志。
8. **测试断言以字符串码 + details 为准**：不要断言 HTTP 4xx/5xx（工具层）。
9. **文档生成**：`docs/tools.md` 从同一 Schema 生成；read-only 收窄版本需要单独的生成快照或在测试中动态读取。
10. **向后兼容**：`TIMEOUT` 字符串不再产生；若旧文档/旧脚本断言它，需同步更新。

---

## 12. 裁决记录摘要（供后续变更评审）

| 日期 | 版本 | 裁决 | 依据 |
|---|---|---|---|
| 2026-10-20 | 0.1.1 | 工具错误统一 200 + `isError`；协议/工具错误分名 | MCP `CallToolResult` 语义；测试判定唯一性 |
| 2026-10-20 | 0.1.1 | SSE 双基线：Cursor 0.45.11 + 自研脚本 | 可重复性；第三方客户端不可控 |
| 2026-10-20 | 0.1.1 | 双重门错误码：TOOL_DISABLED / PERMISSION_DENIED / EXEC_DISABLED | 语义分层；审计可区分 |
| 2026-10-20 | 0.1.1 | MCP Server 端口 fail-fast（exit 2）；桥接回退 | 固定客户端 URL vs 发现文件 |
| 2026-10-20 | 0.1.1 | `--allow-destructive` 只管 P1；P2 用各自开关兼作策略确认 | 最小权限；避免一个开关放大风险 |
| 2026-10-20 | 0.1.1 | read-only 注册混合工具并收窄 Schema | 保留只读价值；模型可预测 |
