# 0.1.5 真引擎冒烟执行报告（smoke-exec-report-0.1.5）

- 任务包：`cc433d95-33b1-4864-8806-512e71a374c9`（截止 2026-11-18T22:00+08:00）；作者：测试工程师（QA）；执行窗口 2026-11-18 14:35–15:27（本机时间，UTC+8）。
- 口径：**代码冻结，只执行与记录**。全程零产品代码/文档/测试/脚本改动、零 git add/commit、零版本变更；QA 自有工具位于 `feedback-review/qa-tools/`（非产品）。
- **单引擎口径声明（裁定⑥）**：本证据包全部来自 **UE 5.7.4（51494982）单引擎**；5.4 侧三项（S1/S2/S2b）因环境缺失 BLOCKED。**本报告不给出发布结论**，闸门判定交主管/架构。

---

## 0. 结论总表（逐项 PASS / FAIL / BLOCKED）

| 项 | 内容 | 结论 | 关键证据 |
|---|---|---|---|
| S1 | 5.4.4 readonly 冒烟 | **BLOCKED——未执行（环境缺失）** | [qasmoke-exec-S1-run.log](logs/qasmoke-exec-S1-run.log)、[qasmoke-exec-S1-blocked-engine54-missing-20261118.log](logs/qasmoke-exec-S1-blocked-engine54-missing-20261118.log) |
| S2 | 5.4.4 full 全方法铺满 | **BLOCKED——未执行（同因）** | 同上 + [qasmoke-exec-e4-scene-supplement-20261118.log](logs/qasmoke-exec-e4-scene-supplement-20261118.log) |
| S2b | 5.4.4 standard 档 | **BLOCKED——未执行（同因）** | 同上 |
| S3 | 5.7.4 官方脚本冒烟 | **PASS**（EXIT=0，8/8） | [qasmoke-exec-run-S3.log](logs/qasmoke-exec-run-S3.log)；run=`UEMCPBridge\Tests\smoke-runs\smoke-5.7-20261118-144533` |
| S3 矩阵补测 | 5.7 readonly 矩阵 + 契约（QA 直连） | **PASS**（全格绿） | [qasmoke-exec-S3-matrix-20261118.log](logs/qasmoke-exec-S3-matrix-20261118.log)、[qasmoke-exec-S3-contracts.log](logs/qasmoke-exec-S3-contracts.log)、`logs/qasmoke-exec-S3-matrix/`（37 文件） |
| S4 | 5.7 full 桥直连矩阵（含 O-QUEUE/O-HOL/回滚/V2/白名单） | **PASS**（附 2 项观察，见 §5） | [qasmoke-exec-run-S4-driver.log](logs/qasmoke-exec-run-S4-driver.log)、[qasmoke-exec-run-S4-fix.log](logs/qasmoke-exec-run-S4-fix.log)、[qasmoke-exec-S4-case-summary.log](logs/qasmoke-exec-S4-case-summary.log)（78 行）、`logs/qasmoke-exec-S4/`（155 文件） |
| S4 补测（窗口 4） | full+allow-gates tools/list、A-4 负例、O-STAGE 两类负例 | **PASS**（=15；CONFIRMATION_REQUIRED 实证；O-STAGE 材料齐） | [qasmoke-exec-run-W4.log](logs/qasmoke-exec-run-W4.log)、`logs/qasmoke-exec-W4/`（33 文件）、[qasmoke-exec-S4-contracts.log](logs/qasmoke-exec-S4-contracts.log) |
| S4b | 5.7 standard MCP 链 | **PASS**（tools/list=13；audit delta=5） | [qasmoke-exec-run-S4b.log](logs/qasmoke-exec-run-S4b.log)、`logs/qasmoke-exec-S4b/` |
| S5 / S5b / S5c | 5.7 full MCP 链（policy 确认 / 开关短路 / destructive） | **PASS（执行面）**；**A-4 elicitation 分支活体未达成**（负例决定性，见 §3 A-4） | [qasmoke-exec-run-S5.log](logs/qasmoke-exec-run-S5.log)、`logs/qasmoke-exec-S5/`（15 文件，含桥侧审计 115 行） |
| S-PS-headless | PS 快速失败附加验证（裁定④，5.7 -NullRHI） | **PASS**（-32016/501/retryable=false，16ms） | `logs/qasmoke-exec-S4/resp-ps-headless-capture.json` |
| S6 | 5.4 附加组合 | **不执行**（主管 q2 裁定：随 5.4 环境消亡） | 裁定沿档 |
| V2（PIE 生命周期） | COMPAT §5 手动项顺带 | **PASS**（start/status/stop 全 ok，净还原） | `logs/qasmoke-exec-S4/resp-v2-pie-*.json` |
| V3（PIE 内截图内容） | 人工目检项 | **N/A**（冒烟非交互，未做 PIE 内 capture 目检；计划 §7 允许记 N/A） | 声明于 §4.1 |
| V6（full 档执行面） | console+python full 下可用 | **PASS** | S4/S5 证据同上 |

执行后恢复与冻结复核（验收⑤⑥）全部通过：[qasmoke-exec-99-post-verify-20261118.log](logs/qasmoke-exec-99-post-verify-20261118.log)。

---

## 1. 执行前检查（验收①②③）

1. **代码冻结校验**：bridgefix2 基线 61/61、tsfix2 基线 63/63 重算 **diff=0**——[qasmoke-exec-00-freeze-verify-20261118.log](logs/qasmoke-exec-00-freeze-verify-20261118.log)。
2. **P-3/P-4 与桌面复核**：沿档通过（prep 检查单，锚点复核见 smoke-plan §8 记录）。
3. **5.4 环境缺失与 E4 现场保全（裁定①②）**：14:38:43 S1 官方脚本在 preflight 失败：`UnrealEditor.exe not found: C:\Program Files\Epic Games\UE_5.4\...`（原文见 S1-run.log）。`UE_5.4` 安装目录已从磁盘消失，与当日早前两份反馈文档消失同象场；按裁定不重装、不修复，五项现场保全已入 [qasmoke-exec-e4-scene-supplement-20261118.log](logs/qasmoke-exec-e4-scene-supplement-20261118.log) 并哈希留档。消失原因**未决**（沿档）。
4. **5.7 开跑前复核（裁定③）**：`C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe` 存在；S3 前置检查 [qasmoke-exec-S3-precheck-20261118.log](logs/qasmoke-exec-S3-precheck-20261118.log)。
5. **附带发现（KeepPrepared）**：S1 失败路径仍触发仓库样例工程清理输出（`plugin copy removed: False / .uproject restored: False`），属执行器语义观察，已录 S1-run.log 原文，不定性。

## 2. 逐项执行记录

### S1/S2/S2b（5.4.4 三档）——BLOCKED
- 全部标记「未执行——环境缺失」。A-2b（5.4.4 真实会话证据）**无法满足**：不存在任何 `ueVersion=5.4.*` 的 0.1.5 审计行；不得以 `Tests/smoke-runs/` 历史产物或 0.1.0 期审计行替代（计划 §4.2 禁混用条款）。按计划 §6 A-2b 的第二选项，发布说明须保留降级表述「5.4.4 仅单测/历史验证，0.1.5 真机会话待补」——是否阻断发布由主管/架构裁定，QA 不下发布结论。

### S3（5.7 官方冒烟脚本）——PASS
- 命令：`pwsh -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.7`，EXIT=0，8/8 只读 RPC 通过；run 目录 `smoke-5.7-20261118-144533` 完整（run.json/health/capture/日志）。
- 其中 viewport.capture 在脚本通道 **1984ms PASS**（与窗口通道超时对照，见 §5 OBS-2）。

### S3 矩阵补测（readonly 负例全格 + 契约）——PASS
- 证据：[qasmoke-exec-S3-matrix-20261118.log](logs/qasmoke-exec-S3-matrix-20261118.log) + `logs/qasmoke-exec-S3-matrix/`（每格 params/resp 原始信封）+ [qasmoke-exec-S3-contracts.log](logs/qasmoke-exec-S3-contracts.log)。
- 要点：readonly 下全部写方法收到**预期拒绝码**（非超时非误放行）；分页 nextOffset 末页 null；BFS truncated 语义；/health 18 键；policies 7 键；审计 JSONL 10 键且 requestId 为字符串；错误载荷 origin/stage 在场。MCP 内嵌子跑（standard 档 dryRun）见 `logs/qasmoke-exec-S3-mcp/`：7 次 tools/call 产 4 审计行（缺的 3 行 = asset_search 参数校验拒绝 1 + python_exec TOOL_DISABLED 2，归入 OBS-1c/1b）。

### S4（5.7 full 桥直连矩阵）——PASS（附观察）
- 驱动：`qa-run-s4.ps1` + `qa-run-s4-fix.ps1`（r2/r3 修正重跑，见 §6 工具缺陷声明）；索引 [qasmoke-exec-S4-case-summary.log](logs/qasmoke-exec-S4-case-summary.log)（78 用例行，均含原始 resp 信封路径）。
- actor 链闭环：spawn→set_transform→set_props→duplicate→select→dryRun→delete；dryRun 零泄漏；**净还原 actor.query total=0**（resp-r2-find-final.json）。
- 事务回滚实证：无效 selector → `-32024` "Transaction rolled back after ACTOR_NOT_FOUND …"（resp-w-actor-set-transform/duplicate 原文）。
- 参数门实证：`resultExpression` 必须字符串、material `tags` 必须数组——原始错误信封在场。
- console：`stat fps` dispatched；非白名单 `Stat.DoesNotExist_QA` 亦 dispatched=true（OBS-3）；python.exec/material/blueprint compile/object.reflect/call 全 ok。
- **V2 PIE**：start→status(isPieRunning=true)→stop(=false) 全 ok，无残留。
- **O-QUEUE**：并发 16 全 ok；queuedMs>0 ×5（max 16ms）；桥侧 115 行审计中 queuedMs>0 共 48、**max 1812ms**——观测签名：存在队列等待、未见 45s 量级阻塞（按纪律不断言成因）。
- **O-HOL**：慢 capture（-32037，20239ms）阻塞期间并行 ping 全程 8–11ms；窗口 4 复验变体（python.sleep(5) 5010ms + ping×5 = 8/8/8/9/8ms，且 ping 的 `meta.queuedMs=null` 计量旁路——OBS-4）。
- **full+allow-gates tools/list = 15**（较 13 多出 ue_console_command/ue_python_exec，名称全列于 contracts 日志）。
- O-STAGE（计划 §4.3 两类负例，窗口 4 补齐）：(a) NameError → `-32014 PYTHON_ERROR`，**details 含 `origin="caller"`、`stage="python.exec"`**；(b) 缺参 → `-32602 INVALID_ARGUMENT` 同带 origin/stage；(c) 不存在资产 `rename_asset` → ok、stdout "False"（无异常，用例素材照录）。**注**：计划 §4.3 转述的旧口径「payload 无 origin/stage」在 0.1.5 实测**不成立**（字段已实现，与 types.ts B-3.7 声明一致），以原始信封为准。

### S4b（5.7 standard MCP 链）——PASS
- tools/list=13；8 次工具调用；audit delta=5 行（缺口 3 行 = level.control 读 1 + TOOL_DISABLED 的 console/python 2，见 OBS-1/1b/1c）。actor_edit dryRun 在 standard 直接 allowed、无确认、无 elicitation。
- 证据：`logs/qasmoke-exec-S4b/transcript-s4b-standard.jsonl(+.summary)`、`audit-delta-s4b.jsonl`。

### S5/S5b/S5c（5.7 full MCP 链）——执行面 PASS；elicitation 分支未达成
- S5（full+allow-gates）：python.accept / python.decline / console 均 `confirmationMode=policy` 过审——**注意**：decline 案例仍执行，非缺陷：未发生 elicitation 交互时 policy 模式自动批准（计划 §3 语义），原始 transcript 与审计行在场。
- S5b（full 无开关）：python/console 均 TOOL_DISABLED isError，audit delta=0 行 → 短路在审计之前（OBS-1b）。
- S5c（full 无 destructive）：`delete confirm:true` 直接 allowed（参数满足确认语义，无 confirmationMode）。
- **A-4 补充负例（窗口 4，决定性）**：`delete confirm:false` → **isError=True**，原文 `CONFIRMATION_REQUIRED: Destructive operation requires confirmation: client elicitation not available and --allow-destructive is off`；随后 actor_query total=1 证实未执行；清理后 **total=0**（resp-find-final.json `data.total=0`）。审计行 `denied | CONFIRMATION_REQUIRED` 在场。
- **elicitation 活体未达成**：本会话 6 份 transcript（s4b/s5/s5b/s5c/w4-a4/w4-gates15）中 `elicitation/create` 出现次数全部为 **0**（逐文件计数见 [qasmoke-exec-S4-contracts.log](logs/qasmoke-exec-S4-contracts.log)），QA 客户端已声明 `capabilities.elicitation={}`；服务端消息自证「client elicitation not available」；代码锚 `confirm.ts:18`（无 elicitation 能力协商则判 unsupported）。**结论口径：0.1.5 在实测配置下 elicitation 交互路径不可达（未观测≠不可能，但本证据包内未发生）**——交架构判定是否为设计内行为。

## 3. 发布闸门 A-1..A-6（本证据包内判定，不做发布结论）

| 闸门 | 判定 | 依据 |
|---|---|---|
| A-1 审计严格增长 | ✓ | 当日 TS 审计 4→9→14→15→18，与 run 对应（run-S4b/S5/W4.log + post-close tally） |
| A-2 0.1.5 行数≥MCP 工具调用数 | **✗（严格口径未达，缺行 100% 已被三类门行为解释）** | 全部 MCP tools/call=28（W1 7 + s4b 8 + s5 5 + s5b 4 + s5c 1 + w4 3），当日 TS 审计=18 行；缺 10 行 = level.control 读×1（OBS-1）+ TOOL_DISABLED×8（OBS-1b）+ 参数校验拒绝×1（OBS-1c）。均为**审计前短路**、码锚在场（README:250「全部工具调用均记录」不符点交架构定性；非落盘失败——auditDegraded 全程未触发，已写行与调用一一对应） |
| A-2b 5.4.4 真实会话证据 | **✗（无 5.4 环境，物理无法满足）** | §2 S1；触发计划 §6 降级表述条款 |
| A-3 policy/none 回声一致 | ✓ | s4b 行 confirmationMode 缺省(none)、s5 行 `policy`×3、S5c 无 confirmationMode（参数确认路径） |
| A-4 elicitation 双分支（approved+denied 各≥1 行） | **✗ 未达成** | 6/6 transcript 零 elicitation/create；负例 CONFIRMATION_REQUIRED 决定性（§2 S5） |
| A-5 buildHash 溯源 | ✓ | run/health/审计行三处同为 `5f965b17f93c…`，与 2026-11-17 构建记录（qa-collect-recompute:68 等 4 处、全 logs 唯一值）一致；计划「审计无 buildHash（G-001）」前提在 0.1.5 已过时——四字段实测在场 |
| A-6 审计键集==types.ts 声明集 | ✓ | 20 键观测集 ⊆ AuditRecord（types.ts:79-122），必填 10 字段全存在；stdio 无 sessionId=README 契约；可选字段按条件出现 |

## 4. 执行后验证（验收⑤⑥）

- **恢复验证**：编辑器进程 0、端口无占用、插件目录已摘、discovery 清空；uproject sha=`91344BCB…E777` 与基线一致、`DefaultEngine.ini` sha=`225B2BA9…C1B2` 与基线一致（未为 PS 改任何工程配置，真 pixelStreaming 分支维持 **N/A**）；SmokeBlank `Content/` 触盘扫描（≥14:00 本地）**0 文件**——全部 actor 编辑止于未保存 transient 关卡并净删。详见 [qasmoke-exec-99-post-verify-20261118.log](logs/qasmoke-exec-99-post-verify-20261118.log)。
- **冻结复核**：bridgefix2 61/61 + tsfix2 63/63 重算 **mismatch=0 missing=0**；git status 63 行 / 0 删除（与冻结时点同构）；**UE_5.7 仍存在（True）**；UE_5.4 维持缺失（False，非新增消失，裁定⑤复核点）。
- 五个窗口目录（145322/145803/151324/151559/152415）全部关闭还原；关闭记录 [qasmoke-exec-S4-window-close.log](logs/qasmoke-exec-S4-window-close.log)（窗口 4 首次为强杀 forced=True，二次为优雅关闭 forced=False）。

### 4.1 偏离登记
1. S4/S4b/S5/S5b/S5c 合并为窗口 2 一个编辑器会话、W4 补测单开窗口 4——偏离原「每格独立 run」；理由：环境二次事故（UE_5.4 消失）后时间盒保全证据，每格原始信封独立在场，矩阵可逐格追溯。
2. V3（PIE 截图内容目检）N/A：非交互执行无法目检截图内容（计划 §7 人工项）；level save/material save 全部 `save:false`，避免 Content 污染。
3. S6 未执行（主管 q2 裁定随 5.4 消亡）。
4. O-HOL 慢请求原口径 capture 在窗口通道超时后，追加了计划允许的 `python.exec time.sleep` 变体复验（§4.3 原文「或 exec 时限内 python.exec time.sleep」）。

## 5. 观察清单（保留现场、报主管、QA 零修复）

| # | 观察 | 证据锚 | 口径 |
|---|---|---|---|
| OBS-1 | **level.control 读动作不写审计**（get_current/list_dirty 成功但 0 行），与 README「全部工具调用均记录（含只读工具）」不符；其余只读工具均有行 | 码锚 `levelControl.ts:83` `if (isWrite)`；`audit-delta-s4b.jsonl`（6 调用 5 行）；README.md:250 | 文档-代码不一致候选缺陷，交架构定性 |
| OBS-1b | **TOOL_DISABLED 短路调用不写审计**（S5b 4 次全拒 0 行；W1×2、s4b×2 同型） | `pythonExec.ts:28-35` 门在 auditCall 之前；`audit-delta-s5b.jsonl`=0 行 | 同上；与 README「全部工具调用均记录」对照呈报 |
| OBS-1c | **参数校验拒绝（INVALID_ARGUMENT）调用不写审计**（W1 asset_search 缺 query → isError=True 且 0 行） | `audit-delta`/当日文件比对：06:55 批 4 行 vs 7 调用；校验失败信封见 `transcript-w1-dryrun.jsonl.summary.json` | 同族审计前短路第三型；呈报口径同上 |
| OBS-2 | 窗口通道 viewport.capture **-32037 超时 ×2**（20239ms），而官方脚本通道同参 **1984ms PASS** | `resp-ohol-capture2.json`、run-S4-fix.log vs S3 run.json | **未定性**（焦点/渲染节流假设未证，未再复测）；不影响 S3/O-HOL 结论（变体已复验） |
| OBS-3 | console 白名单未拦 `Stat.DoesNotExist_QA`（dispatched=true） | `resp-w-console-nonwhitelisted.json` | 观察：白名单语义是否应拦截未定义 cvar 待架构确认 |
| OBS-4 | bridge.ping 的 `meta.queuedMs=null`（计量旁路），而其它方法有值 | `resp-w4-ping-*.json` | 观察记录，与 O-QUEUE 判读口径（只写观测签名）一致 |
| OBS-5 | capabilities.screenshot 在 -NullRHI 下仍报 true，capture 实际快速失败 -32016 | `resp-ps-headless-capture.json` + `viewport.py:609/:88` | 能力位与环境判定独立的注记（裁定④附加验证的副产物） |

## 6. QA 驱动侧缺陷声明（不影响产品结论）

本次执行中 QA 自有工具暴露并已修正重跑覆盖：窗口关闭脚本 `param()` 位置错误；PS 单元素数组解包致首轮 actor 链 selector 损坏（反而产出 -32024 回滚证据，r2 重跑全绿）；O-QUEUE 首轮信封解析路径错误（重解析既有原始文件修正）；ISO 时间戳 `ConvertFrom-Json` 类型陷阱；W4 首轮 `params/ping-empty.json` 缺失致 ping 未跑（W4b 从**原始 resp 文件**重抽补齐，见 contracts 日志）；final-query 提取路径（值以 `data.total=0` 原始信封为准）。所有原始信封保留，汇总日志均为对原始文件的重解析而非记忆转写。

## 7. §7 手动项 → 可自动化升级建议（主管 q3 授权口径）

- `qa-exec-mcp.mjs` 已实现最小 MCP stdio 客户端（initialize/tools/list/tools/call、server→client ping 应答、elicitation accept/decline 分支、逐消息 transcript）；`qa-exec-bridge.mjs` 实现桥直连 RPC + 原始信封落盘。二者可作为把 **MCP 链、O-QUEUE/O-HOL、回滚负例、tools/list 计数** 固化为回归脚本的种子。
- 仍未自动化且需人工：PIE 内截图内容目检（V3）、崩溃恢复对话框处置（本次实证：强杀后首启可能卡「恢复包」对话框约 6 分钟，`-unattended` 可消解——工具链注记）、截图视觉质量、许可/首启、DPI。

## 8. 证据索引

- 门禁与现场：`qasmoke-exec-00-freeze-verify`、`qasmoke-exec-S1-blocked-engine54-missing`、`qasmoke-exec-e4-scene-supplement`、`qasmoke-exec-99-post-verify`（均在 `feedback-review/logs/`）。
- 运行日志：`qasmoke-exec-run-{S3,S4-driver,S4-fix,S4b,S5,W4}.log`、`qasmoke-exec-S3-{precheck,matrix-20261118,contracts}.log`、`qasmoke-exec-S4-{case-summary,contracts,window-close}.log`。
- 原始信封目录：`qasmoke-exec-S3-matrix/`(37)、`qasmoke-exec-S3-mcp/`(3)、`qasmoke-exec-S4/`(155)、`qasmoke-exec-S4b/`(4)、`qasmoke-exec-S5/`(15)、`qasmoke-exec-W4/`(33)；窗口目录 `qasmoke-window/{145322,145803,151324,151559,152415}`；官方 run 目录 `UEMCPBridge\Tests\smoke-runs\smoke-5.7-20261118-144533`。
- 桥侧审计切片：`qasmoke-exec-S5/bridge-audit-window2.jsonl`（115 行，10 键，requestId 字符串 115/115）。
- TS 审计：`~/.uemcp/audit/2026-11-18.jsonl`（终态 18 行，未改写历史行）。
