# 变更说明：修 D1（viewport activateWindow 透传）+ D4 预留（object.call captureLog）

日期：2026-11-03 ｜ 负责人：Server 工程（TypeScript / MCP 协议层）
任务：2e0e2aaf ｜ 基线：HEAD c505b66（15 工具，test 59 / smoke 84）

## 1. 改动清单

### D1（主）：`ue_viewport_capture` 透传 `activateWindow`
- `packages/shared/src/schemas/viewport.ts`：`ViewportCaptureInput` 新增
  `activateWindow: z.boolean().default(false)`——默认值与 Bridge 的
  `get_bool(params, "activateWindow", default=False)`（handlers/viewport.py:574）对齐。
- `packages/shared/src/schemas/outputs.ts`：`ViewportCaptureData` 增补 `activation`
  块（`requested/ok/alreadyForeground/hwnd/editorPid/foregroundPid/isIconic`，
  字段逐一取自 Bridge `_activation_payload`，未自创）。
- `packages/server/src/tools/viewportCapture.ts`：仅工具描述加一句可发现性说明
  （此前参数根本不存在，调用方无从得知）；透传路径本就整包转发，无需改逻辑。

**根因**：schema 是 `.strict()`，而 Server 侧从未声明 `activateWindow`，因此走正常
MCP 路径必现 `INVALID_ARGUMENT: Unrecognized key(s): 'activateWindow'`（只有直连
Bridge 端口才可用）。修复后 MCP 路径与直连行为一致。

### D4（预留）：`ue_call_function` 接受并透传 `captureLog`
- `packages/shared/src/schemas/primitives.ts`：`callFunctionInputSchema()` 新增
  **`captureLog: z.boolean().optional()`（刻意不设 default）**。
- `packages/shared/src/schemas/outputs.ts`：`CallFunctionData` 预留
  `logLines[{lineNo, level, text}]`（D4 的输出形态，passthrough 兼容）。

**为何必须"可选无默认"**：Bridge `object.call` 的 `check_keys` 白名单当前是
`{target, function, args, waitMs}`（objects.py:299），**不含 captureLog**。若给它设
`default(false)`，每次调用都会把该键下发 → 现桥接以 INVALID_ARGUMENT 拒绝 → 所有
`ue_call_function` 调用全挂。现在只有调用方显式传 `captureLog:true` 才透传；
不传时请求体与修复前完全一致（现网桥接零影响）。D4 桥接侧落地（0.1.5）后自动生效。

**标题歧义的处理**：任务标题只写"为 D4 预留 captureLog 透传"未点明工具；CHANGELOG
`[Unreleased]` 的 D4 条目明确"`object.call` accepts `captureLog:true`"，故落在
`ue_call_function`，viewport 只加 activateWindow（viewport 语义上也无"captureLog"）。

## 2. 谁受影响
- 用 `activateWindow` 的调用方：MCP 路径由必失败变为可用；不传时行为不变
  （默认 false 会显式下发，Bridge 语义等价）。
- `ue_call_function` 调用方：不传 captureLog → 请求体不变；显式传 true → 0.1.4 现桥接
  会以 INVALID_ARGUMENT 拒绝（预期，0.1.5 桥接落地后可用），Server 侧已就绪。
- 输出侧：两处新增块均为可选 + passthrough，旧客户端/旧响应零破坏。

## 3. 新增断言（3 条）
1. `viewport: defaults are …/activateWindow`（扩展既有默认值测试）——防默认值漂移。
2. `viewport: activateWindow accepted (D1) and strictly boolean`——防参数再被 strict
   schema 拒收（D1 回归）。
3. `object.call: captureLog is reserved passthrough but NOT defaulted (D4; current
   bridge whitelist rejects unknown keys)`——防有人给 captureLog 加 default 而
   一次性打死所有调用。
4. `D1/D4: ue_viewport_capture passes activateWindow through (activation returned);
   ue_call_function forwards reserved captureLog only when set`（blackbox，19168）——
   端到端防回归：`activateWindow:true` 到达 bridge（mock 回显 `received`）且返回
   `activation.requested/ok/editorPid`；默认 false 也下发；captureLog:true 透传并原样
   回传 `logLines`；不传时请求体**无该键**。
   （mock-bridge 相应补了 activation/received 回显与 D4 logLines 镜像。）

## 4. 四门与计数
| 门 | 结果 | 计数 |
|---|---|---|
| `pnpm -r build` | exit 0 | — |
| `pnpm -r typecheck` | exit 0 | — |
| `pnpm test` | exit 0 | **62/62**（基线 59 + 3） |
| `pnpm smoke` | exit 0 | **87/87**（基线 84 + 3；跑后 uemcp-smoke-* 计数 0） |

## 5. 边界
未改 UE 侧 Python；未改 docs/README；未 push；未碰 ue_p_text / dist-release。
