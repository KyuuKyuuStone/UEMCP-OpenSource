# 0.1.5 第二批修复 · TS 侧（接管补完）报告

- 任务：`74a0246e-daae-4f14-8902-29708b6aa618`（接管前任 `f72451d4`），执行角色：运维脚本（员工）。
- 基线：`feedback-review/logs/tsfix-hash-before.txt`（63 文件，git HEAD `bacbe1c048f590020592528241fda93b04f5ce99`，checkedAt 2026-11-18T11:23）。
- 版本保持 **0.1.5**（未动任何 package.json 版本号）。
- 依据：`feedback-review/server-verification.md` §12 表 TS 侧五行 + §11.2 过时文档清单。

## 1. 前任工作盘点（接管时状态）

- 盘点日志：`feedback-review/logs/tsfix2-inventory.log`（2163 行，生成脚本 `gen-tsfix2-inventory.ps1`）。
- 结论（log :154 / :219 / :2129）：63 文件中 **32 个已被前任修改**（vs HEAD `+1000/−31`，git diff 全文在 log :381–2065）；`CROSSCHECK: OK`（与 `git status --porcelain` 一致，无范围外 TS 侧改动）。
- 前任已落地的 TS 侧代码改动覆盖 §12 行 1–4 的代码部分（watchdog / auditCall / discovery-stale / 审计保留+auditDegraded / viewport 能力门 / outputSchema 注册等），并新增两测试文件增量（blackbox +192 行、internal +387 行）。
- **前任未完成**：① 单测从未运行（仅 typecheck EXIT=0 @12:29，`tsfix-typecheck2.log`）——两项断言与实现不符；② README / README-DEV / 架构文档修正完全未动；③ 其 audit.ts 注释宣称「架构文档『(可配置)』表述已同步修正」为**虚假陈述**（架构文档哈希与基线一致，未改）——本次通过实际修正文档兑现。

## 2. §12 TS 侧逐项对照（fix → anchor → evidence → 归属）

| # | §12 条目 | 代码/文档锚点 | 证据 | 归属 |
|---|---|---|---|---|
| 1 | watchdog 状态扩展 | `bridge/watchdog.ts`（保留 instanceId/buildHash/buildTime/sourcePath/capabilities/rateLimit/policies/bridgeProtocol/schemaVersion；markDown 全清不冒用旧缓存） | `tsfix2-inventory.log` diff；`tsfix2-typecheck.log` EXIT=0；`server.internal.test.mjs` watchdog 用例（`tsfix2-test.log` 82/82） | 前任 |
| 2 | AuditRecord + auditCall 增补 | `tools/common.ts:106-186`（origin/stage、policySnapshot{ts,bridge}、schemaVersion、连接态构建身份 4 字段、client/transport/ueVersion）；`mcp/buildServer.ts:27-30` oninitialized 回填 clientInfo（修复「client 恒缺失」）；`shared/src/types.ts` AuditRecord 新字段 | 同上；blackbox `tsfix B7/client` 用例（修复后绿） | 前任 |
| 3 | BridgeDiscoveryFile stale 三字段 + schemaVersion 告警 | `shared/src/types.ts`（stale/staleReason/staleAt）；`bridge/discovery.ts` `acceptDiscovery`（schemaVersion 不符 → `discovery_schema_version_mismatch` warn；pid 存活但 stale → STALE_DISCOVERY_WARN）；`transports/http.ts` /health 透传扩展字段 | 同上；internal 用例覆盖 | 前任 |
| 4 | 审计保留/轮转/auditDegraded/stdio sessionId + **文档** | 代码：`audit.ts`（RETENTION_DAYS=30 常量、连续 3 次失败 stderr 跃迁告警、/health auditDegraded）——前任；文档：根 README CN「可追溯与会话行为」+ EN 镜像新增**审计日志契约**条目（按天轮转、固定 30 天不可配置、启动清理、全工具含只读、origin/stage/policySnapshot/schemaVersion/构建身份、stdio 无 sessionId、红线不变）+ 架构文档 §6.5 两行同步（详见 §3.4） | `tsfix2-inventory.log` diff（audit.ts）；README/arch-doc 哈希变更见 `tsfix2-hash-after.txt` | 代码=前任；**文档=本次** |
| 5 | README / README-DEV 过时计数与 outputSchema 描述更正 | 见 §3.2 / §3.3 逐行清单 | `tsfix2-hash-after.txt`（README.md、README-DEV.md 哈希变更） | **本次** |

「保持不动」项复核（§12 末行）：三版本协商回显（`buildServer.ts` PROTOCOL_VERSIONS + TODO）、confirm:true、P2 门值、base64Data 前向兼容分支（`viewportCapture.ts`）、pythonExec 下限（:65-69）、activateWindow（`viewport.ts:35-38`）——全部未动，inventory diff 中无这些锚点的语义变更。

## 3. 本次补完明细

### 3.1 单测断言修复（前任写了没跑的测试，首轮 2 失败）

首轮 `pnpm test`：`ℹ tests 82 / pass 80 / fail 2`（失败现场完整保留：`feedback-review/logs/tsfix2-test-failrun-1.log`）。两处均为**测试侧断言与既有实现不符**，生产代码未改：

1. `tests/server.blackbox.test.mjs:1109`：`j.transport` 期望 `"http"` → 改为 `"streamable-http"`（`index.ts:78` 为 HEAD 既有实现：HTTP 进程恒记 streamable-http，stdio 记 stdio；HEAD 基线测试从未断言过该值）。
2. `tests/server.blackbox.test.mjs:1216`：`startBridge(home, ["--fail-python"])` → 追加 `"--allow-exec"`（mock 桥与真实桥接一致默认 deny exec——`mock-bridge.mjs:351` 门先拒 EXEC_DISABLED，永远到不了 PYTHON_ERROR 分支）。

修复后 `pnpm test`：**82/82 pass，EXIT=0**（`tsfix2-test.log`）。

### 3.2 根 README.md（CN + EN 双语对称修正）

- 测试计数：`84/84`→`87/87`（smoke）、`59 项/cases`→`82 项/cases`（node --test）、UE 侧「无需引擎 14/11 个脚本」→「20 个（另 4 个需引擎）」（与 `UEMCPBridge/README.md` §7 现文对齐）。
- 目录树与文档索引：server 包 `10 工具`→`15 工具`（:270/:574）；架构文档索引行改为「MVP 10 工具 Schema（现共 15 工具，新增 5 个以 `shared/src/toolNames.ts` 为准）」（:282/:586）。
- 新增**审计日志契约**用户可见条目（CN「可追溯与会话行为」+ EN「Traceability and session behaviour」各一条，内容同 §2 行 4）。

### 3.3 uemcp/README-DEV.md（§11.2 清单全覆盖 + 实施后新过时项）

- :3 `Docs/`→`docs/`；:35 本机 Node `24.18`→`26.13`（实测 `v26.13.0`）。
- :15/:104 断言数 `61`→`87`；:106 实测行改 `SMOKE RESULT: 87/87 passed` + `node --test 82/82`，注明日志路径与日期/Node 版本。
- :115 策略矩阵 `7/8/10`→`11/13/15`（smoke.mjs:303/226/324 断言实据）；:130 stdio `tools/list=8`→`13（standard）`（smoke.mjs:574）；:132 「第 33 个 initialize 429」→满仓逐出空闲/全推流才 429（实现语义）；:133 `read-only=7`→`11`。
- :141 `10 个工具`→`15`、`3 个混合工具`→`4 个（blueprint/level/material/pie）`（`narrowedActions` 调用点实据）；:145 审计条目重写（全部 15 工具含只读、origin/stage、policySnapshot、schemaVersion、构建身份、第 3 次 stderr 跃迁告警、RETENTION_DAYS=30 固定、stdio 无 sessionId）。
- :148 viewport.capture `45s`→`20s` + pixelStreaming 预检门（前任代码改动的文档同步）；:19-21 schemas 树 10→13 文件（补 pie/primitives/outputs）；:161 `（11 个）`→`（13 个）`；:167 `common + 10 工具`→`+ 15 工具`。
- :182 outputSchema 条目：「MVP 未注册/延后」→「已注册：registerTools 挂载 success|failure 双形态 + smoke 矩阵断言 + 单测回归（`tsfix2-test.log` 中 `✔ outputSchema: every visible tool publishes a dual-shape` 项）」。

### 3.4 docs/UEMCP-架构设计.md §6.5（兑现前任虚假注释）

- `:2595`「完整命令（可配置为 hash）」→「（hash 选项未实现，无配置开关）」；`:2597`「保留 30 天…（可配置）」→「固定 `RETENTION_DAYS=30`，不可配置（0.1.5 第二批按主管裁决落地为常量）」。
- 修正后 `audit.ts:6/:16` 的「已同步修正」注释成为事实；代码未动。

## 4. 验证证据（最终代码状态，全部 EXIT=0）

| 命令（在 `uemcp/`，`pnpm --config.verifyDepsBeforerun=false <cmd>`） | 日志 | 结果 |
|---|---|---|
| `pnpm build` | `feedback-review/logs/tsfix2-build.log` | EXIT=0 |
| `pnpm typecheck`（build 后） | `feedback-review/logs/tsfix2-typecheck.log` | EXIT=0 |
| `pnpm test` | `feedback-review/logs/tsfix2-test.log` | 82 pass / 0 fail，EXIT=0 |
| `pnpm test`（修复前首轮，留证） | `feedback-review/logs/tsfix2-test-failrun-1.log` | 80/82，EXIT=1（2 失败=§3.1） |
| `pnpm smoke` | `feedback-review/logs/tsfix2-smoke.log` | 87/87，EXIT=0 |

文档编辑发生在第二轮验证之后；已证实 `tests/*.test.mjs` 与 `scripts/smoke.mjs` 均不读取 README/架构文档内容（grep 无命中），故验证结论对最终树成立。运行器 `run-tsfix2-verify.ps1` 每步记录 COMMAND/START/EXIT_CODE/END 原始输出。

## 5. 哈希与备份

- `feedback-review/logs/tsfix2-hash-after.txt`：63 文件重算 SHA256，**35 个相对基线变更 = 前任 32 + 本次 3 文档（README.md / README-DEV.md / 架构文档）**（server.blackbox.test.mjs 本次也改但其哈希在前任清单内已变更）；missing=0。
- 备份：`feedback-review/tsfix2-backup/`（镜像相对路径，含证据日志与本报告）。
- `feedback-review/logs/tsfix2-deliverable-hash.log`：Phase A 63 源文件「工作树=备份=hash-after 记录」三方对比 **match=63 mismatch=0**；Phase B 追加报告+10 个证据文件原/备对比。

## 6. 发现与未决（不擅自改动，报主管）

1. **maxNodes 上限不一致**：TS 侧 `shared/src/schemas/assets.ts` 透传 `.max(1000)`，桥接 `assets.py:277` 实为 `maximum=10000`——TS 更严则功能被提前拒绝；接口口径以桥接现行代码为准是否放宽到 10000，需主管/桥接同事裁决。
2. **架构文档主体工具清单仍是 v0.2.0 MVP 十工具口径**（:37「MVP 固定 10 个工具」、§5、:3223 验收项等）——0.1.1–0.1.5 新增 5 工具未入表。本次仅按任务包改 §6.5 两行 + README 索引行加注；全量刷新属发布/文档组范围。
3. §11.2 未列的历史行（README-DEV :189/:190「61→65→71」修复轮记录、:50「实测输出（2026-10-20）」）按历史事实保留未改。
4. `UEMCPBridge/` 工作树含同事在途未跟踪测试（test_bridge_fixes.py 等 3 个）与 §7「20 脚本」现文——根 README 计数按该现文对齐，若其后续变动需再同步。
5. 前任首轮 typecheck 绿而测试红：建议后续批次把 `pnpm test` 纳入交付前强制门禁（本次 `run-tsfix2-verify.ps1` 已含四步全跑）。

## 7. 边界遵守

未动 `UEMCPBridge/**`、QA smoke 脚本、任何 ZM 目录、§12「保持不动」清单、`feedback-review/` 已验收历史证据（tsfix-*.log 只读保留）；未 git add/commit；版本保持 0.1.5。本次改动文件全集：`README.md`、`uemcp/README-DEV.md`、`docs/UEMCP-架构设计.md`、`uemcp/tests/server.blackbox.test.mjs`（2 断言）+ 新增证据文件 `feedback-review/logs/tsfix2-*`、`feedback-review/logs/gen-tsfix2-*.ps1`、`feedback-review/tsfix2-backup/`、本报告。
