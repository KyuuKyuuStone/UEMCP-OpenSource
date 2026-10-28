# 变更说明：Server 侧质量优化（任务 4248c955）

日期：2026-10-28 ｜ 负责人：Server 工程（TypeScript / MCP 协议层）
范围：`uemcp/packages/server` + `uemcp/packages/shared` + 测试/脚本；**不改** UE 侧 Python、不改既有文档结论、不做发布。

## 1. 改了什么 / 为什么 / 谁受影响

### A. 为 10 个工具补 outputSchema（附录 A / HANDOFF §10-1）
- **改**：新增 `shared/src/schemas/outputs.ts`（`ToolMetaOutput`/`ToolErrorOutput`/`TOOL_OUTPUT_DATA_SCHEMAS`/`TOOL_OUTPUT_SCHEMAS`）与 `server/src/mcp/outputSchema.ts`（`toolOutputJsonSchema`）；`registerTools.ts` 在 tools/list 为每个可见工具发布 outputSchema。
- **形态**（关键约束）：MCP 规范与 SDK `ToolSchema` 要求 outputSchema **根层级 `type:"object"`**（实测：裸 anyOf union 会被 SDK `ListToolsResultSchema` 打回）。发布形态＝根 object（声明 ok/data/warnings/error/meta，`additionalProperties:false`）+ `anyOf` 判别分支：成功 `{ok:true,data,warnings,meta}`、失败 `{ok:false,error,meta}`（`not` 互相排他）。SDK 客户端对**存在的 structuredContent 一律校验（含 isError=true）**，故双形态必须同 schema 兼容。
- **data 策略**：按架构 §5.x 声明字段但 passthrough、除 `status.policies`（Server 恒注入）外不强制必填——桥接侧字段演进不会被客户端校验打回；封套是强约束部分。
- **谁受影响**：使用会做 outputSchema 校验的客户端（SDK 1.32+ `callTool` 自带 Ajv）的用户。**实测**：真 SDK Client 走 mock bridge，10 工具成功路径 + 3 错误路径（INVALID_ARGUMENT/CLASS_NOT_FOUND/COMMAND_NOT_ALLOWED）全部通过校验（`packages/server/scripts/verify-client-validation.mjs`，`pnpm --filter @uemcp/server verify:sdk`）。不校验的老客户端无感。

### B. 消除 toolAnnotations 重复（任务 B）
- **改**：删除 `policy.ts` 中无人引用的 `toolAnnotations(tool, PolicyState)`（死代码，grep 验证零引用）；删除 `mcp/annotations.ts` 的 `PolicyState` 再导出。`narrowedActions` 改为直接引用 shared 的 `READ_ONLY_LEVEL/MATERIAL/BLUEPRINT_ACTIONS`（单一来源，与 §5.11 收窄枚举及 Major-5 白名单口径同源）。`isToolVisible`/`toolDisabledGate` 复核一致（P1 gate=server.policy，P2 gate=对应开关，SEC-01(c)）。
- **谁受影响**：无运行时行为变化（死代码删除 + 等值重构）。

### C. 五个遗留 Minor
| 项 | 裁决 | 谁在什么条件下受影响 |
|---|---|---|
| m-3 | **移除 Server 端下限**：`pythonExec.ts` 不再 `Math.max(args.timeoutMs, 30000)`，直传 `args.timeoutMs`（zod 默认 10000，client clamp 1000..120000）。选此项因架构 §5.9 明确 default 10000；改 schema 默认 30000 会与文档结论冲突（本次禁改文档）。`ue_python_exec` 的 ToolDef.timeoutMs=120000 降级为上限参考注释 | 调用 `ue_python_exec` 的用户：缺省超时 30s→10s；显式传 <30s（如 5s）不再被抬高。长任务需显式传大 timeoutMs；写方法不自动重试语义不变 |
| m-2 | **删除死分支**：`bridge/client.ts` 的 `CONNECT_WINDOW_MS`（`elapsed<3s→UNAVAILABLE`）不可达（abort 时 elapsed 恒 ≥ timeoutMs+5s ≥ 6s），按审查建议删除；分类改为纯按异常类型（TimeoutError→BRIDGE_TIMEOUT，其他→BRIDGE_UNAVAILABLE） | 无运行时行为变化（分支本就不可达） |
| m-13 | **isWrite 计入 save**：`blueprint.ts` `isWrite = BLUEPRINT_WRITE_ACTIONS.has(action) || (action==="query" && save===true)`。action 维度与 Bridge 端 `WRITE_ACTIONS={compile}` 口径不变 | read-only 下 `query+save:true` 由静默写盘改为 `PERMISSION_DENIED`（gate=server.policy）；standard/full 下该调用新增审计记录且失败不自动重试 |
| N-2 | **复验已修复**（audit.ts 两处 mkdir 已传 `mode:0o700`），本轮补 POSIX 断言（目录 0700/文件 0600；Windows 按 §6.5 ACL 近似跳过 mode 断言） | 无行为变化（回归加固） |
| N-3 | **复验已修复**（win32 不敏感/POSIX 敏感），重构为纯函数 `equalProjectDirOn(platform,…)` 注入平台以便测试，行为等值 | 无行为变化（等值重构）；POSIX 保守方向＝宁可发现失败报 BRIDGE_UNAVAILABLE，不连错编辑器 |

### D. 版本无关化（任务 D）
- **改**：`packages/server/package.json` 与根 `uemcp/package.json` 的 description 去掉写死的 "5.4"（改为 engine version reported by the bridge）。源码/运行时本无写死引擎版本（ueVersion 一律来自 bridge /health → watchdog → `meta.ueVersion` 与 `/health bridge.ueVersion`）。
- **说明**：smoke 断言 `meta.ueVersion==="5.4.4"` 来自 mock bridge fixture 的运行时上报值（正是"由 bridge 上报"机制的验证），非硬编码，保留；shared `levels.ts` 注释 "§5.4" 是文档章节号，不动。

## 2. 测试断言清单（断言名 → 防的回归）
- `shared.schemas.test.mjs`：`python: timeoutMs defaults to 10000 per §5.9 (m-3…)`→Server 重新抬高默认值；`outputs: TOOL_OUTPUT_SCHEMAS covers exactly the 10-tool catalog`→新增工具漏 outputSchema；`outputs: every schema accepts success and failure…`→outputSchema 退化成单形态（错误路径被客户端打回）；`outputs: schema rejects extra envelope keys…`→封套约束松动；`outputs: READ_ONLY_* …`→收窄常量漂移。
- `server.blackbox.test.mjs`：`outputSchema: every visible tool publishes a dual-shape…`→tools/list 漏发布/根形态不符 MCP 规范；`outputSchema: success AND error … for all 10 tools`→发布 schema 与实现漂移（任一工具成功/错误形态不匹配）；`m-13: read-only …→PERMISSION_DENIED` 与 `m-13: standard …→audited`→写盘绕过门/审计缺口回归；`m-3: timeoutMs semantics flow to the bridge (default 10000, explicit 5000)`→30s 下限复活；`bridge: hung /rpc with timeoutMs=1000→BRIDGE_TIMEOUT`→abort 分类被改坏（此用例靠 m-3 的 1s 可调下限才可测，顺带覆盖 HANDOFF 待办 5 的 BRIDGE_TIMEOUT 路径）。
- `server.internal.test.mjs`（新）：`audit N-2…`→mkdir mode 回退；`discovery N-3: …`→平台语义回退成无条件 toLowerCase；`policy B: …`→narrowedActions 与 shared 常量脱钩、gate 口径漂移。
- `engine-agnostic.test.mjs`（新）：package description 再次写死引擎版本。
- `smoke.mjs` 新增 6 条：工具/只读目录 outputSchema 存在性 + status 成功、INVALID_ARGUMENT、TOOL_DISABLED 场景、python 成功、COMMAND_NOT_ALLOWED、BRIDGE_UNAVAILABLE 的 structuredContent 全部通过发布 schema 校验 + `python exec: timeoutMsReceived=10000`。
- `scripts/verify-client-validation.mjs`（新，`verify:sdk`）：真 SDK 客户端端到端校验（非本仓库近似器）。

## 3. 风险
- 真实 UE 桥接若在成功路径返回**非 object** 的 data（违反 §5.x），客户端校验将打回——已用 passthrough+可选字段把风险压到最小；QA 复跑（mock bridge）全绿。
- m-3 的行为变化对依赖隐式 30s 的长任务用户是显性变化（错误信息含 timeoutMs，可自行调大）。

## 4. 未做项及原因
- **协议版本 2025-11-25 未放开**：按 HANDOFF §10-6 / README-DEV §8-1 裁决，放开前需先更新架构 §3.6 三版本表（文档归文档岗；本次不改文档结论）。已留 `TODO` 于 `buildServer.ts` 的 `PROTOCOL_VERSIONS` 处（含操作指引）。
- HANDOFF/架构/审查报告等文档中对应条目的"已修复"状态更新：归文档岗，本次不代改。

## 5. 验证（2026-10-28，本机 node v24.18.0，cmd /c pnpm）
- `pnpm -r typecheck` → exit 0
- `pnpm -r build` → exit 0（shared tsc；server tsup：dist/index.js + dist/internal.js）
- `pnpm test` → **54/54 pass, 0 fail**（exit 0）
- `pnpm smoke` → **80/80 PASS**（exit 0）
- `pnpm --filter @uemcp/server verify:sdk` → 真机 SDK 客户端 10 成功 + 3 错误全部通过 outputSchema 校验（exit 0）
