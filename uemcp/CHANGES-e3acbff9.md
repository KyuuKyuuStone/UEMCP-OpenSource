# 变更说明：会话池加固——满仓 LRU 逐出、429 可读化、失效可预期（任务 e3acbff9 / P1-5）

日期：2026-10-30 ｜ 负责人：Server 工程（TypeScript / MCP 协议层）
基线：主管收尾后的 HEAD 969d02c（test 56 / smoke 84 全绿，12 工具目录）。
范围：`packages/server/src/transports/http.ts`、`packages/server/src/config.ts`、`CHANGELOG.md`（[Unreleased] 一行）、`tests/server.blackbox.test.mjs`（+3 测试）。不改 UE 侧 Python、不改 README、不 push、未碰 ue_p_text 与 dist-release。

## 1. 改了什么 / 为什么这样设计

### A. 满仓 LRU 逐出（http.ts）
- 原行为：`sessions.size >= 32` → initialize 一律 429 -32012，直到 30 分钟 TTL 到期（测试岗 RECON §A 复现）。
- 新行为：满仓时先按「最近活动时间」选**最老的空闲 streamable 会话**逐出（`session_evicted` 日志含 idleMs），腾位后正常 initialize；仅当**全部会话都持有活跃 SSE 流**（无可逐出对象）才 429。
- 不参与逐出的两类（设计理由）：
  1. `legacy`（旧版 /sse）——其 SSE 连接是长活流，只有断连（onclose）才会出 map，在 map 中即活跃；
  2. `streamable` 且 `sseOpen=true`——有未关闭的 standalone GET /mcp 流。
- **为何优先逐出「裸 POST 会话」**：这类会话没有任何在途响应/流，`transport.close()` 不会打断客户端正在读取的数据；逐出 SSE 活流会立刻表现为客户端读到半截事件流，比「新建会话被拒」伤害更大。`sseOpen` 通过 GET /mcp 路由在响应 `close` 事件上标记/解除（`res.on("close")`），连接粒度准确。
- 逐出动作：`sessions.delete` + `rateBuckets.delete` + `transport.close()`（触发 SDK onclose，幂等）。
- 429 升级：无可逐出对象时的 429 响应 data 携带 `retryAfterMs`（取 `--session-sweep-ms`，默认 60000）、`sessions`（现值）、`maxSessions`。

### B. 失效可预期
- **头名选择：`Mcp-Session-Expires-In-Ms`**（initialize 响应头，值=配置的空闲 TTL，默认 1800000）。理由：① 单位写在头名里，杜绝秒/毫秒歧义（FastMCP 的 `Mcp-Session-Id-Expires-In` 用秒，易混）；② 不绑定单一厂商惯例；③ 语义与本服务器的「空闲 TTL（lastSeen+TTL）」精确对应——注意它传达的是**授予时的默认空闲 TTL**，实际剩余随活动滑动，头值即配置值。
- `404 -32001`（SESSION_NOT_FOUND，POST/GET/DELETE 三处）的 error.data 新增 `hint: "reinitialize"` 与 `ttlMs`（= 配置 TTL），客户端可程序化自愈。实现：`sendRpcError` 增加可选 `extraData` 参数（其余调用点不变）。
- 注入方式：initialize 分支在响应写出前包裹 `res.writeHead`（与 charset 中间件同机制、链式叠加），仅在含 Content-Type 的那次 writeHead 上补头。

### C. 上限与 TTL 可配
- `MAX_SESSIONS` 常量 32 → `opts.maxSessions`：`--max-sessions N`（CLI）或 `UEMCP_MAX_SESSIONS`（env），默认 32、下限 1，**仅供测试与运维调小**。/sse 与 /mcp 两条路径共用。
- 既有项：`--session-ttl-ms`（默认 30min）/ `--session-sweep-ms`（默认 60s）不变，已随 404 data.ttlMs 与过期头暴露语义。
- CHANGELOG `[Unreleased]` 加一行（英文，与现有条目风格一致）。

## 2. 谁受影响
- 长跑客户端：32 个旧会话不再把池锁死 30 分钟；被逐出方收到 404 + `hint=reinitialize`，可静默重建。
- 使用 standalone SSE 的客户端：活跃流会话不会被逐出；极端情况（全部被 SSE 占满）得到带 `retryAfterMs` 的 429，可退避重试。
- 运维/测试：可用 `--max-sessions`/`UEMCP_MAX_SESSIONS` 缩池做容量演练；`session_evicted` 日志（reason=pool_full_lru）可观测逐出行为。
- 兼容性：不改变任何既有成功/失败形态；smoke 既有 429/404 断言全部原样通过。

## 3. 新增断言（blackbox，防回退）
1. `sessions: maxSessions=2 LRU-evicts the oldest idle session — 3 initializes all succeed, first sid 404s with hint+ttlMs and expires header` —— 防「满仓直接 429」回退；同时锁 expiry 头（=1800000）、404 data.hint/ttlMs、幸存者可用。
2. `sessions: eviction prefers bare-POST sessions over live SSE sessions; a pool of live SSE streams returns 429 with retryAfterMs` —— 防「逐出误伤 SSE 活流」与「429 缺可读数据」：上限 2 时 A(SSE)+B(裸) → initC 逐出 B、A 存活；A+C 双 SSE → initD 429 且 data.sessions=2 / maxSessions=2 / retryAfterMs>0。
3. `sessions: UEMCP_MAX_SESSIONS env is honored like --max-sessions (C. configurability)` —— 防 env 通道回退。

## 4. 四门与计数
| 门 | 结果 | 计数 |
|---|---|---|
| `pnpm -r build` | exit 0 | — |
| `pnpm -r typecheck` | exit 0 | — |
| `pnpm test` | exit 0 | **59/59**（基线 56 + 3） |
| `pnpm smoke` | exit 0 | **84/84**（与基线持平，跑后 uemcp-smoke-* 计数 0） |

## 5. 其他说明
- **上一任务遗留观察（按嘱列出，未动）**：`tools/common.ts` 的 `summarizeOut` 无 `ue_pie_control` / `ue_policy_explain` 专用 case，两者摘要走 default 分支（key=value 预览），功能无损，仅文案不如其他工具精炼。
- **并行干扰说明（非本任务引入）**：本轮 smoke 后 TEMP 曾出现 1 个 `uemcp-smoke-*` 残留（创建时间 13:07:45，为测试岗/主管并行跑 smoke 所留，当时我未在跑 smoke）；删除后复跑 smoke 84/84 且计数 0，证明本改动无泄漏。
- RECON §A 的自证：上限=2 时 3 次 initialize 全成功（测试 1 即该场景，无 429）。
