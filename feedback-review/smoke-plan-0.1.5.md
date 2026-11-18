# UEMCP 0.1.5 发布前真机冒烟计划（smoke-plan-0.1.5）

- 任务包：`8cbd15e8-b867-4dc9-b9bd-eb124ecd35cf`；补充核查任务包：`0faacf99-e3c5-4c44-b33b-33a52501b10e`（CMD 3.8/3.12 → 本文 §4.1/§4.2 并入）；**口径更正任务包：`1f9b9ac3-54b1-470d-b0bd-5c817c902f0d`（CMD 3.12 缺流量方=5.4.4，非 5.7；§4.2 勘误 + §4.3 queuedMs/stage 观测点 + §6 A-2b 闸门）**；作者：测试工程师（QA）；日期：2026-11-17
- 配套：证据核验见 `evidence-check.md`；本文件所有仓内事实引用均有 `feedback-review/logs/qa-repo-facts*.log`、`qa-offline-regression-20261117.log` 留档。
- **本任务只产出计划：不执行冒烟、不启动编辑器、不改代码。** 执行由主管派单给持有 5.4/5.7 smoke 技能的运行者。

## 0. 目的、范围与怎么读

- **目的**：闭环 CMD 反馈的 P0/P1 使用侧证据缺口——0.1.5 至今 **0 条真实审计**（recompute:18）、真实流量仅覆盖 16 个 RPC method 中的 5 个（recompute:19）、5.4.4 上 0.1.4/0.1.5 从未跑过（原件 §3.12 标题："999 条来自 5.7.4，5.4.4 只有 4 条"；recompute:24 UEVERSION_DIST 999/4 一致）。
- **范围**：引擎 UE 5.4.4 / UE 5.7.4 × 策略（policyMode standard/full × 权限门 allowWrite/allowConsole/allowExec × confirmationMode elicitation/policy/none）× 16 个 RPC method；每 run 固定证据集；pluginVersion=0.1.5 审计验证项（§6）。策略层的 CMD 3.12 命名视图（readonly/standard/full）见 §4.2；现状三列覆盖对照（CMD 3.8：自检/冒烟/审计）见 §4.1。
- **不在范围**：修复类问题（CMD 3.1 审计字段、3.4 timeoutMs 生效、3.13 分队列等）属开发；本计划只保证 0.1.5 发布时"每个 method 有真机证据、每条证据能溯源到版本"。
- 状态口径同 `evidence-check.md` §0.5；ZM 28 条中 4 条无法核验、3 条部分属实，均**不阻塞**本计划，但 §3 映射表逐条给出冒烟侧处理。

## 1. 既有工具链基线（衔接，不重造）

| 资产 | 事实（固化处） | 计划中的角色 |
| --- | --- | --- |
| `Tests/ue_smoke_run.ps1` / `ue_probe_run.ps1` / `ue_common.ps1` | 仅源码仓库，**不随发行包**（README:245-247，qa-repo-facts） | 每 run 的执行器 |
| 现有 smoke 的 8 个只读 RPC | `bridge.ping`、`bridge.capabilities`、`editor.status`、`actor.query`、`asset.search`、`level.control(get_current)`、`material.params(list)`、`viewport.capture(640x360)`（SMOKE-REAL-ENGINE.md:73，qa-repo-facts 固化） | 矩阵的"只读基线列" |
| 证据目录结构 `Tests/smoke-runs/<kind>-<engine>-<stamp>/` | plan/health/discovery/editor-log/rpc-01..08/cleanup/summary（SMOKE-REAL-ENGINE.md:75-99） | §5 证据清单的地基 |
| preflight | 拒绝残留 `UnrealEditor*` 进程、18778–18788 占用（ue_common.ps1:172-175；SMOKE §6） | 每 run 第一步，硬约束 |
| 退出码语义 | 0 通过/1 preflight/2 启动超时/3 采集/4 清理（SMOKE §6 表） | 判定语言 |
| 已知不可自动化 | UI 弹窗、截图内容、许可/首启、DPI、完整 MCP 链路、PIE 截图与事务回滚（SMOKE §5 表；后者指向 COMPAT-UE57 §5 V2/V3/V6 手动项） | §7 手动观察项 |
| 探针 | `probe_ue57.py` 13 必检 API（SMOKE §4 两版全过）；**无 PixelStreaming 检查**（PROBE_PS_LINES=[]，qa-repo-facts2） | §3 G-005 补观测 |
| 引擎自带 Python | 5.4/5.7 均 3.11.8（offline-regression 头行） | 一致性前提 |

**一次只跑一个引擎**（技能硬规则）；除 `ue_p_text` / `ue54_text` 测试工程外**不装插件进任何用户工程**；`ZMCPP_54_NEW` 在用户确认前不得作为冒烟场地。

## 2. 现有测试 ↔ 反馈问题覆盖映射

### 2.1 离线自检 16 个（README 只列 11 个——本身即 CMD 3.11 实锤）

全部于 2026-11-17 10:44 在 UE5.4 自带 Python 3.11.8 实跑 **16/16 EXIT 0**（`logs/qa-offline-regression-20261117.log`）。

| 自检 | 关联反馈项 | 覆盖判定 |
| --- | --- | --- |
| check_error_codes | ZM POS-001/IMP-008；CMD 3.7 码表侧 | 覆盖（含 INVALID_ARGUMENT -32602 契约） |
| check_handler_names | 静态完整性 | 覆盖 |
| check_plugin_version | **CMD 3.2/3.1 版本一致性**；uplugin=0.1.5==runtime==health（offline:13） | 覆盖（离线）；真机侧待 §6 |
| test_bridge_timeout_http | CMD 3.4 | **仅部分**：测的是 504 路径；timeoutMs 被丢弃/`timedOut` 恒 false 无用例（HEAD python_exec.py:37,93 已固化） |
| test_class_path_resolution | ZM E-045 族 | 覆盖 |
| test_dependency_options | ZM IMP-003/POS-007 | 覆盖（3 种降级路径） |
| test_discovery_lifecycle | 发现文件 | 覆盖；**不含**配置快照（CMD 3.9 → §5 补） |
| test_log_query | README 未列方法 log.query | 覆盖（离线）；真机 0 证据→矩阵补 |
| test_object_call | ZM PROB-006/007、POS-003/004；CMD 3.11 缺表方法 | 覆盖（离线，21 子项）；真机补 |
| test_pie_control | CMD 3.8 pie 7 次流量 | 覆盖（离线）；真机 PIE 截图属手动项 |
| test_port_fallback | ZM E-007（18790 说法）旁证 | 覆盖 |
| test_python_error_mapping | CMD 3.4/3.7 | 覆盖映射行为；**origin/stage 无**（功能未实现，属开发） |
| test_rate_limit | ZM IMP-001/POS-002、E-021/022/049/050/051/052 | 覆盖（含 429 序列与 retryAfterMs 通道） |
| test_serialization | FQuat 序列化 | 覆盖 |
| test_uplugin_metadata | **CMD 3.10** | 部分：依赖 `Tools/stamp_uplugin.py`（仓库有、发行包无）→ **包内实测 exit 1**（pkg-sim 模拟发行包 15 可跑/1 不可跑，逐脚本清单见 evidence-check §8.1）；替代证据见 G-010 |
| test_viewport_capture | CMD 3.5；ZM PROB-004 | 部分：activateWindow/timeout_partial 15 子项绿；headless/PixelStreaming 场景无 |

TS 侧（uemcp/tests）：`server.internal.test.mjs` audit N-2（jsonl 落盘+0700/0600）、`server.blackbox.test.mjs` m-13（save:true 才入审计）、`--audit-python-source` fatal——审计**行为**有测试，**schema 字段**无（G-001）。

### 2.2 缺口清单（现有测试给不出证据、必须由冒烟/开发补的）

| G | 缺口 | 来源 | 0.1.5 冒烟侧处置 |
| --- | --- | --- | --- |
| G-001 | AuditRecord 无 buildHash/sourcePath/instanceId（types.ts:70-88 固化） | CMD 3.1 P0 | 冒烟不掩盖：run.json 固化 /health 三字段（server.py:567-570）替代溯源；向发布组声明残余风险 |
| G-002 | 0.1.5 真实审计 0 条 | CMD 3.2 P0 | **每 run ≥1 条 MCP 链路调用**产生 0.1.5 审计行（§6-A2；5.4.4 侧专项见 §6-A2b） |
| G-003 | 审计轮转/停写无文档约定、桥接无请求级 requestId 日志 | CMD 3.3 P0 | 每 run 采集 audit 当日文件 mtime+行数增量，验证"写了就有行"；发现停写即 fail run |
| G-004 | timeoutMs 不生效、timedOut 恒 false 无行为用例 | CMD 3.4 P1 | S2/S4 记录 python.exec 实际 durationMs vs 传入 timeoutMs 的偏差证据（不修，取数） |
| G-005 | PixelStreaming 工程 capture 前置检查缺失、probe 无 PS 检查（PROBE_PS_LINES=[]） | CMD 3.5 P1 | 观察项 O-PS：若冒烟工程启用 DataChannelType=PixelStreaming，capture 计时入 run.json；默认测试工程未启用则记 N/A |
| G-006 | 单队列 pending 静默队头阻塞，无 queuedMs | CMD 3.13 P2 | O-HOL 并发观察项（S4）：1 个慢 capture + 并行 ping 的耗时对照，留 rpc-*.json 时间戳；**5.4 侧扩为一等观测点 O-QUEUE + 负例 O-STAGE，提案见 §4.3（1f9b9ac3）** |
| G-007 | 真机仅 8 只读 RPC 有 `Tests/smoke-runs/` 历史产物证据（**run 产物类，非审计真实流量**——审计 5 method 全在 0.1.0/0.1.4 期，recompute:19）；actor.edit/console.command/python.exec/blueprint.query/pie.control/object.reflect/object.call/log.query 共 8 个方法**连历史产物也没有** | CMD 3.8/3.11 | 矩阵 §4 全 16 方法 × 双引擎铺满；两类证据区分口径见 §4.2 尾注 |
| G-008 | 5.4.4 上 0.1.4/0.1.5 从未有真实会话（历史上仅 0.1.0 期 4 条：2026-10-20 的 3×capture+1×actor.edit，原件 L242） | CMD 3.12 P2 | **S1/S2b/S2 = 5.4.4 闭环 run（三档）**；按原件 L251 要求把"5.4.4 真实会话证据"作显式产出物：任一 5.4 run 内 ≥1 次 MCP 链路调用（5–10 次即可，哪怕单会话），产出 `pluginVersion=0.1.5` 且 `ueVersion=5.4.*` 的审计行——**§6 A-2b 专项闸门**；该 4 条属哪个工程/环境原件自记未验证，本计划不断言 |
| G-009 | 生效权限/限流配置无快照 | CMD 3.9 P1 | run.json 固化 /health `policies`+`rateLimit` 快照（server.py:575-576） |
| G-010 | 发行包缺 Tools//*.ps1 → 包内自检断链（**0faacf99 实测坐实：15/16 可跑，唯一断链=test_uplugin_metadata**，`logs/qa-cmd310-pkg-sim-20261117.log`） | CMD 3.10 P1 | 发布验收改用"维护者本机 16/16 绿印 + 本矩阵 run 编号"作替代证据链；三条具体替代证据提案见 evidence-check §8.1 末（含打包产物 sha256manifest 留档、LICENSE 在包与否核验 U-9） |

ZM 侧 28 条处理：业务崩溃类（PROB-001/002/003/008/009/013、IMP 全 8、POS 全 7）已在 evidence-check §9 定性，**冒烟不背修复**；插件侧 PROB-004/005/006/007/011/012 → 分别落 S2/S4 的 capture、asset.search、object.call 用例（结果按 HEAD 0.1.5 行为记录，漂移单列）；PROB-010（ak 主工程）与运行时 10 文件 → 不进入 0.1.5 冒烟范围（场地与访问面纪律）。

## 3. 冒烟 run 定义（引擎 × 策略）

| Run | 引擎 | policyMode | 权限门 allowWrite/Console/Exec | confirmationMode | 目的（闭环项） |
| --- | --- | --- | --- | --- | --- |
| S1 | 5.4.4 | standard | off/off/off | policy | 8 只读基线 + **关闭态拒绝路径**（actor.edit/python.exec → EXEC_DISABLED/权限拒绝），CMD 3.12、G-008 |
| S2 | 5.4.4 | full | on/on/on | none | 全 16 方法正向铺满（含 object.reflect/call、log.query、blueprint.query compile、pie start/stop、material set、level save）+ §4.3 O-QUEUE/O-STAGE |
| S2b（0faacf99 新增） | 5.4.4 | **standard** | on/on/on | policy | 与 S2 同脚本集，仅 policyMode=standard（bridge-settings.json/环境变量，settings 优先级见 README:27）——CMD 3.12 之 standard 层；独立 run 目录 |
| S3 | 5.7.4 | standard | off/off/off | policy | 同 S1 的 5.7 对照 |
| S4 | 5.7.4 | full | on/on/on | none | 同 S2 + O-HOL/O-PS 观察项（G-004/005/006）+ §4.3 O-QUEUE/O-STAGE |
| S4b（0faacf99 新增） | 5.7.4 | **standard** | on/on/on | policy | S2b 的 5.7 对照；独立 run 目录 |
| S5 | 5.7.4 | full | on/on/on | **elicitation**（MCP 客户端全链路） | **审计验证 run**：elicitation 批/拒各 ≥1 次 + python.exec 成功 ≥1 → 产生 pluginVersion=0.1.5、confirmationMode=elicitation/policy、decision=allowed/denied 的审计行（G-002/G-003，§6） |
| S6（可选） | 5.4.4 | full | on/off/off | elicitation | elicitation 路径 5.4 侧最小覆盖（ping + 1 次写） |

顺序：S1→S2（5.4 完）→ S3→S4→S5（5.7）；一次一引擎；S5 需 MCP 客户端在线（TS server 由运行者按 uemcp 发布包启动）。

## 4. 引擎 × 策略 × RPC 矩阵（16 method 铺满验收）

图例：`R`=只读通过；`W`=写路径通过；`D`=期望被拒（默认门）；`M`=手动/观察项；`—`=不适用。每格结果须落 `rpc-<n>-<method>.json`。

| RPC method（rpc.py:51-68 注册 16 个） | S1 5.4 std | S2 5.4 full | S3 5.7 std | S4 5.7 full | S5 5.7 elicitation | 关联反馈项 |
| --- | --- | --- | --- | --- | --- | --- |
| bridge.ping | R | R | R | R | R（心跳+确认旁） | SMOKE 基线 |
| bridge.capabilities | R | R | R | R | R | — |
| editor.status | R | R | R | R | R | SMOKE 基线 |
| actor.query | R | R | R | R | R | SMOKE 基线 |
| actor.edit | **D**(allowWrite off) | W(dryRun+实写+回滚记录) | **D** | W | W（批准后）+ 1 次 declined | ZM IMP-005/POS-005；CMD 3.8 |
| level.control | R(get_current) | W(new/open/save_current/save_all) | R | W | R | ZM E-064；CMD 3.8 |
| asset.search | R | R | R | R | R | SMOKE 基线；ZM IMP-002/003 |
| material.params | R(list) | W(set/create_instance) | R | W | R | ZM IMP-006；create 重路径负例 1 |
| viewport.capture | R | R | R | R+O-PS/O-HOL | R | CMD 3.5/3.13；ZM PROB-004（headless 场景另记 N/A：冒烟非 headless） |
| console.command | **D**(allowConsole off) | W(白名单内 1 条) | **D** | W | W | README:76 consoleAllowlist；CMD 3.8 |
| python.exec | **D**(EXEC_DISABLED) | W(+G-004 计时对照) | **D** | W | W + declined 各 1 | CMD 3.4/3.6/3.7；pythonExec.ts:43-64 elicitation/audit 流 |
| blueprint.query | R | W(query+compile 一次性测试资产) | R | W | R | SMOKE §5 手动项衔接（V2） |
| pie.control | **D**(start；status 可 R) | W(start/stop + PIE 内 capture→M) | **D** | W | W | COMPAT V3（PIE 截图需人工看内容）；ZM E-017 |
| object.reflect | R(只读；0faacf99 起纳入 readonly 档，与 §4.2 一致) | R | R | R | R | CMD 3.11 缺表方法真机首证 |
| object.call | **D**(allowWrite off) | W(黑名单负例 1 + 参数错负例 1 + 正例 1) | **D** | W | W | ZM PROB-006/007、POS-003/004；CMD 3.8 ue_call_function 12 次流量 |
| log.query | R | R | R | R | R | CMD 3.11 缺表方法真机首证 |

**矩阵完成判据**：每格有证据文件或标 `M/N/A+原因`；三列（S2/S4/S5）内 16/16 方法全有 PASS 记录；D 格必须收到预期拒绝码（非超时）才算过。

### 4.1 三列覆盖矩阵（显式引用 CMD 3.8）

CMD 3.8 主张"真实流量仅覆盖 16 method 中 5 个"，并建议一张"哪些被自检覆盖 / 哪些被引擎冒烟覆盖 / 哪些有真实审计记录"的三列矩阵。下表即该三列矩阵，作为 §4/§4.2 冒烟要补齐的**现状基线**（扫描脚本 `feedback-review/qa_cmd38_manifest.py`，静态引用证据 `logs/qa-cmd38-coverage-and-zero-write-20261117.log` PART1，RUN 12:35:55）：

- ① 离线自检＝16 个 `check_/test_` 脚本中是否引用该 method（字面量或其 handler 模块 import，模块归属按 `rpc.py:51-68`）；
- ② 引擎冒烟（现状）＝是否落在现有 `SMOKE-REAL-ENGINE.md:73` 的 8 只读基线内（8 个方法有 `Tests/smoke-runs/` 历史真机产物——版本以产物 run.json 为准；该产物**不是审计真实流量**，两类证据不得混用，见 §4.2 尾注）；
- ③ 真实审计记录＝`RPCMETHOD_DIST` 计数（CMD 环境 0.1.0/0.1.4 历史流量）。

| RPC method | ① 离线自检 | ② 冒烟设计 | ③ 真实审计条数 | 三列皆空? |
| --- | --- | --- | --- | --- |
| bridge.ping | ✅(test_rate_limit) | ✅ | 0 | 否 |
| bridge.capabilities | ❌ | ✅ | 0 | 否 |
| editor.status | ✅(test_python_error_mapping;test_pie_control 模块) | ✅ | 0 | 否 |
| actor.query | ✅(test_python_error_mapping;test_serialization) | ✅ | 0 | 否 |
| actor.edit | ❌ | ❌ | 2 | 否 |
| level.control | ❌ | ✅ | 0 | 否 |
| asset.search | ✅(check_handler_names;test_dependency_options 模块) | ✅ | 0 | 否 |
| material.params | ❌ | ✅ | 0 | 否 |
| viewport.capture | ✅(test_viewport_capture) | ✅ | 30 | 否 |
| **console.command** | ❌ | ❌ | 0 | **★三列皆空** |
| python.exec | ❌ | ❌ | 952 | 否（仅③高） |
| **blueprint.query** | ❌ | ❌ | 0 | **★三列皆空** |
| pie.control | ✅(test_pie_control) | ❌ | 7 | 否 |
| object.reflect | ✅(test_object_call) | ❌ | 0 | 否 |
| object.call | ✅(test_object_call) | ❌ | 12 | 否 |
| log.query | ✅(test_log_query) | ❌ | 0 | 否 |

**读法**：`PART1_SUMMARY all3_empty=['console.command','blueprint.query']`——这两个 method **无离线自检、无冒烟设计覆盖、无真实审计**，是 CMD 3.8 覆盖缺口里最硬的两个（§4.2 已把它们在 full 档全部铺为 W 格补测）。次级缺口：`python.exec` 虽有 952 条历史审计，但①②两列皆空（自检不引用、不在 8 只读冒烟内），且 0.1.5 真实审计仍 **0 条**——正是 §6 A-2 闸门要反驳的 CMD 3.2/3.8。

### 4.2 引擎 × 策略档 × 16 method 矩阵（显式引用 CMD 3.12）

CMD 3.12 原文主张（标题逐字）："**UE 5.4.4 的兼容性缺真实流量：999 条来自 5.7.4，5.4.4 只有 4 条**"；正文补"0.1.4/0.1.5 的改动（限流、截图格式、`list_dirty` 语义）**从未在 5.4.4 上跑过**"，建议"对 5.4.4 发布**单独给一条「真实会话证据」**（哪怕 1 个会话 5–10 次调用）"（原件 §3.12 L240/L244/L251；数据面 UEVERSION_DIST 999/4 = `logs/qa-collect-recompute-20261117.log:24`）。**缺真实流量的一侧是 5.4.4，5.7.4 恰是流量大户（999 条）**。〔勘误：本节初版（12:38）曾误写"5.7 上从未系统跑过"——与原件相反，任务包 `1f9b9ac3` 按原件 §3.12 校正，旧口径作废〕故冒烟必须按 **引擎（5.4/5.7）× 策略档（readonly/standard/full）× 16 method** 铺满，其中 **5.4.4 三列（S1/S2b/S2）承担"5.4.4 首条 0.1.5 真实会话证据"的闭环目标**（§6 A-2b）。策略档定义（`rpc.py:31-40` WRITE_METHODS/WRITE_ACTIONS；`/health` policies 快照 `server.py:576`）：

- **readonly**：`policyMode=standard` + `allowWrite/allowConsole/allowExec` **全关**（出厂默认门，写/执行类必被拒）
- **standard**：`policyMode=standard` + 三门按需开（写类需确认）
- **full**：`policyMode=full` + 三门全开、confirmation none（写/执行直接放行）

图例：`R`=只读通过；`W`=写/执行路径通过；`D`=期望被拒；`M`=手动/观察；`—`=不适用。

| RPC method | 5.4 readonly | 5.4 standard | 5.4 full | 5.7 readonly | 5.7 standard | 5.7 full |
| --- | --- | --- | --- | --- | --- | --- |
| bridge.ping | R | R | R | R | R | R |
| bridge.capabilities | R | R | R | R | R | R |
| editor.status | R | R | R | R | R | R |
| actor.query | R | R | R | R | R | R |
| actor.edit | **D**(WRITE门关) | W(dryRun→实写→回滚) | W | **D** | W | W |
| level.control | R(get_current)/D(write) | W(open/save/new) | W | R/D | W | W |
| asset.search | R | R | R | R | R | R |
| material.params | R(list)/D(set) | W(set/create_instance) | W | R/D | W | W |
| viewport.capture | R | R | R+O-PS/O-HOL | R | R | R+O-PS/O-HOL |
| console.command | **D**(EXEC关) | W(白名单内) | W | **D** | W | W |
| python.exec | **D**(EXEC_DISABLED) | W(+G-004计时) | W+declined×1 | **D** | W | W |
| blueprint.query | R/D(compile) | W(query+compile) | W | R/D | W | W |
| pie.control | **D**(start；status R) | W(start/stop) | W+PIE内capture→M | **D** | W | W |
| object.reflect | R | R | R | R | R | R |
| object.call | **D**(WRITE门关) | W(黑名单/参数错/正例) | W | **D** | W | W |
| log.query | R | R | R | R | R | R |

**run 映射**：5.4 readonly=S1；5.4 standard=S2b；5.4 full=S2；5.7 readonly=S3；5.7 standard=S4b；5.7 full=S4（elicitation 审计子跑 S5/S6 挂在 full 列内，见 §3/§6）。**验收**：6 个策略×引擎组合下 16 方法每格有 `rpc-<n>-<method>.json` 证据或标 `M/—+原因`；readonly 列所有 D 格必须收到**预期拒绝码**（非超时/非误放行）才算 CMD 3.8/3.12 缺口闭合，**且 §6 A-2b（5.4.4 的 0.1.5 真实会话审计行）必须单独过闸**。**注意：本表是计划，非已跑结果**。历史证据分两类，**不得混用**（任务包 1f9b9ac3 禁止项）：①**审计真实流量**（collect 复算）＝5 个 method、全部发生在 0.1.0/0.1.4 时代且以 5.7.4 为主（999/4）；②**真机冒烟历史产物**（`Tests/smoke-runs/`，8 只读 RPC）是维护者执行器时代的 run 目录证据——**它不是审计流量**，版本与环境以产物内 run.json 为准，不得当作 0.1.5 或"5.4.4 真实会话"证据。0.1.5 在两类证据中均为 **0 条**（recompute:18），故执行者不得把任一空格或旧产物当作"已证实"。

### 4.3 queuedMs / stage 观测点提案（CMD 3.13/3.7 旁证，任务包 1f9b9ac3 新增；只提案、不改产品代码）

原件 §3.13 建议"审计补 `queuedMs`/`stage` 字段，让「排队慢」与「执行慢」可分"，并自记"45s 那两笔到底是排队还是执行 **未验证**"（原件 L266）。字段修复属开发（本计划 §0 不在范围）；冒烟侧以两个**观测点**采集旁证——HEAD 审计 schema 17 键无 queuedMs（`logs/qa-collect-recompute-20261117.log` SCHEMA_KEYS 行固化），桥接侧亦无请求级日志（facts 复核），故一切结论只能来自 run 端计时。

- **O-QUEUE（queuedMs 旁证）**——落在 S2/S2b（5.4）与 S4/S4b（5.7）各一次：①先做一次 capture 预热（避开冷启动 15s 干扰，§7）；②发 1 个慢请求（viewport.capture，或 exec 时限内 python.exec `time.sleep`），期间并行发 `bridge.ping` ×5（客户端并行，零服务端改动）；③每请求的发起/返回时间戳与 durationMs 记入 run.json `observations.queuedMsProxy[]`；④若复现 45s 量级阻塞，按 SMOKE §6 REPRO 纪律留 `hol-timeline.txt`。判读口径：ping 的 durationMs ≈ 慢请求剩余时长 ⇒ 与"单队列队头阻塞"特征一致——**run 报告只写观测签名一致，不得断言成因**。
- **O-STAGE（stage/origin 旁证）**——落在 S2/S4（exec 开）：两类 PYTHON_ERROR 负例各 ≥1：(a) 调用方代码体自身错误（如 NameError）；(b) handler/插件侧内部错误路径（构造缺参或不存在资源引用）。各留 `rpc-*.json` 原始错误 payload。HEAD `rpc.py:101-116` 统一映射、payload 无 origin/stage 字段（evidence-check §8 行 3.7 属实口径）→ 本观测点为开发按 CMD 3.7/3.13 补字段提供用例素材，**不新增 0.1.5 行为断言**。
- 产出物形态：两观测点结果均写入对应 run 目录 `run.json.observations`，发布说明引用时须带 run 编号与时间戳，禁止脱离上下文转述为"已证实排队/成因"。

## 5. 每 run 证据清单（run 目录 = `Tests/smoke-runs/smoke-<eng>-<stamp>/`，扩展现有结构）

**沿用**（SMOKE-REAL-ENGINE.md:75-99）：`plan.json`、`uproject.before.json`、`run.json`、`summary.txt`、`discovery.json`、`health.json`、`editor-log-path.txt`、`editor-log-uemcp.txt`、`rpc-<n>-*.json`、`viewport-capture.png`、`cleanup.json`、失败时 `failure.json`。

**0.1.5 新增（每 run 必含）**：

1. `run.json` 扩展字段：`engine`（5.4.4-35576357…/5.7.4-51494982… 全串）、`uplugin.VersionName`、`pluginVersion`、**`buildHash`/`sourcePath`/`instanceId`（原样取自 /health，server.py:566-570）**、`policyMode`、`confirmationMode`、三权限门状态、`policies`+`rateLimit` 快照（server.py:575-576，G-009）。
2. `rpc-*` 编号扩展到 16+ 方法行（含负例 D 与 declined 各一），每文件含请求参数、HTTP 状态、响应、耗时、`meta.requestId`。
3. `audit-window.jsonl`：从 `~/.uemcp/audit/YYYY-MM-DD.jsonl` 截取本 run sessionId 对应行（采集只读）+ `audit-window.stat.txt`（run 前后文件行数与 mtime 差，证明确有写入，G-003）。
4. `sha256manifest.txt`：run 目录全部证据文件哈希清单（防事后篡改/丢失——本轮交付物丢件事件的直接教训）。
5. `preflight.json`：无残留编辑器进程、18778–18788 空闲、插件副本装载前后（cleanup 按字节还原 .uproject+SHA256 比对，SMOKE §2/§3）。

## 6. pluginVersion=0.1.5 审计验证项（发布闸门，A-1..A-6）

前提：审计由 **MCP server 侧**写入 `~/.uemcp/audit/`（audit.ts:2；tools/common.ts auditCall——pythonExec.ts:48,73 两处调用已固化），故**纯 bridge 直连不产生审计行**，S5（或任一 run 内嵌 ≥1 次 MCP 链路调用）为审计项的必要条件。

- **A-1** run 前记录当日审计文件行数/mtime；run 后必须严格增长（停写=0.1.5 发布阻断，CMD 3.3"停写没人发现"的机制化）。
- **A-2** `audit-window.jsonl` 内 `pluginVersion=="0.1.5"` 行数 ≥ 本 run MCP 链路工具调用数（直接反驳 CMD 3.2"0 条"；0.1.4 的 15.04% 失败率叙事由此获得 0.1.5 对照基线）。
- **A-2b（5.4.4 真实会话专项，原件 §3.12 L251 要求，任务包 1f9b9ac3）**：任一 5.4 侧 run（S1/S2b/S2/S6）的 audit-window.jsonl 中，**≥1 行同时满足 `pluginVersion=="0.1.5"` 且 `ueVersion` 以 `5.4.` 开头**（审计 schema 含 ueVersion 字段，recompute SCHEMA_KEYS 行）——该行即原件要求的"5.4.4 真实会话证据"，**不得**用 `Tests/smoke-runs/` 历史产物或 0.1.0 期审计行替代。不满足 ⇒ CMD 3.12 未闭环，发布闸门阻断并在发布说明保留"5.4.4 仅单测/历史验证，0.1.5 真机会话待补"的降级表述（原件 L251 的第二选项）。
- **A-3** 审计行 `rpcMethod`/`tool` 与 rpc-*.json 一一对应；`requestId` 双侧相等（types.ts:71-77 字段存在性复核）。
- **A-4** S5 内出现 `confirmationMode=elicitation`（approved）与 `decision=denied`+`errorCode=CONFIRMATION_DENIED`（declined，pythonExec.ts:54-56 路径）各 ≥1 行；S2/S4 出现 `confirmationMode=policy|none` 与设置一致（policyMode 字段同步核对）；**S2b/S4b 审计行 `policyMode==standard` 且与同法 S2/S4 的 full 行构成 3.9 两策略层对照对**（0faacf99）。
- **A-5** `buildHash` 溯源：run.json 的 /health `buildHash` == 发布包构建记录（README §9 步骤 2 口径，README:169-171 已固化）；**审计 schema 本身无 buildHash（G-001 未修）**，此不一致须写入发布说明的残余风险。
- **A-6** schema 回归断言：审计行键集 == types.ts:70-88 字段集（多记/漏记都算异常）；若开发后续补 G-001 字段，本项升级为"审计行直接可溯源三字段"。

**通过判据**：A-1..A-6（含 A-2b）全绿 + §4 矩阵无未解释空格 + 各 run 退出码 0。任一失败：按 SMOKE §6 出 `failure.json` + `REPRO:` 命令，run 作废重跑（重跑证据目录并存，不覆盖）。

## 7. 衔接手动项与风险注意

- COMPAT-UE57 §5 **V2/V3/V6**（蓝图编译产物、PIE 截图内容、事务回滚）为**人工**项：随 S2/S4 做，结论记入 run 目录 `manual-checks.md`；不与自动判据混算。
- 首启 5.7 着色器编译 → `-TimeoutSeconds 600`（SMOKE §6 常见原因）；冷启动首次 capture 可达 15s（SMOKE §4 补充观测：14902ms），O-HOL 计时取"预热后"基线。
- PixelStreaming：当前测试工程是否启用 `DataChannelType=PixelStreaming` 未定——O-PS 先探测 `Config/DefaultWebAPI.ini`（只读），无该配置记 N/A；**不**为冒烟改任何工程配置。
- `ue_common.ps1:265/:480` 与 COMPAT-UE57.md V6 表述存在矛盾（本会话早前发现，**未固化为日志**——列为执行者第一步复核项，发现矛盾先报主管，不改脚本）。
- 场地红线：`ZMCPP_54_NEW` 归属未确认（其 10:30-10:46 有活跃写入）——**不得**作为冒烟工程；只用 ue_p_text/ue54_text。
- 时间：本任务包不执行冒烟；建议 S1-S5 排在 0.1.5 封版后、发布前，串行预留 1 个工作日。

## 8. 交付物丢失事件记录（同 evidence-check.md §1.2，简述）

两份 .md 于 ~10:50 后从磁盘消失（原因未决、主管 11:18/12:07 复核无副本）；本版 12:2x 依 logs/ 重建并立即备份至 `qa-backup/` + 哈希留档 `logs/qa-deliverable-hash-20261117.log`。计划正文所有事实均引自留档日志，未凭记忆新增断言。**12:38-12:41 依补充任务包 0faacf99 增补 §4.1/§4.2 与 S2b/S4b**（新增事实全部引自本轮 `logs/qa-cmd310-*`、`logs/qa-cmd38-*` 日志）；修订后重新备份+追加哈希（同日志文件第二段）。**12:47-12:52 依口径更正任务包 1f9b9ac3 校正 §4.2（勘误：初版把 3.12 缺流量方误写为"5.7 从未系统跑过"，原件实为"缺真实流量的是 5.4.4，999 条来自 5.7.4"，旧口径作废）、§4.1 ②列尾注与 §4.2 尾注（区分审计真实流量 vs `Tests/smoke-runs/` 历史产物，禁混用）、新增 §4.3 O-QUEUE/O-STAGE 观测点提案与 §6 A-2b 闸门、G-002/006/007/008 联动**；依据=桌面反馈原件 §3.12/§3.13 逐字读取（原件 L240-L268）+ qa-collect-recompute 日志既有数字；修订后再备份+哈希 RUN3。

## 9. 执行前复核勘误节（append-only，2026-11-18 任务 d9fa8820，主管批准；原文一字未改）

- **§7 第 4 条（ue_common.ps1:265/:480 与 COMPAT V6 矛盾）执行前复核结论：锚点失效、矛盾在 HEAD（0.1.5, bacbe1c）不可复现，脚本零改动**（git status Tests=clean）。真实拒绝逻辑锚点＝`ue_common.ps1:71-80`（Assert-PortsFree）/`:96-103`（Assert-NoEditorProcess）与 `ue_smoke_run.ps1:161-181`（引擎 exe/uplugin/repoSample 守卫/项目缺失 throw）；`ue_common.ps1:265` 逐字＝`Get-NewestEditorLog`（ZIP-2 日志选择），`:480` 在 ue_common.ps1 任何版本（337/386 行）不存在。证据：`logs/qasmoke-prep-ps1-history-20261118.log`、`logs/qasmoke-prep-anchor-history-20261118.log`、`logs/qasmoke-prep-checklist-20261118.log` PART1/PART5。执行日检查单已改用真实锚点。
- **§7 场地红线现状更新**：5.4 默认工程 `ue_p_text/ue54_text` 曾被工作树删除（272 个跟踪文件 ` D`，未提交；stash 空；删除时间无法由 git 判定）。2026-11-18 经主管授权执行 `git checkout -- ue_p_text/ue54_text` 恢复并验证：status clean、磁盘 272=HEAD 272、`git diff --stat HEAD` 空、uproject 解析 EngineAssociation=5.4、抽查 5 文件与 HEAD 一致（`logs/qasmoke-prep-restore-verify-20261118.log`；恢复前现场取证 `logs/qasmoke-prep-scene-preserve-20261118.log`）。**这是继交付物丢失后第二起未解释消失事件，现场已固化；行为人仍未决。**
- **执行前复核附带观察（未处置，仅记录）**：`UEMCPBridge/COMPAT-UE57.md` 存在未提交工作树修改（diff 61 行＝§4.3.1 资产依赖矩阵文档追加，来源 IMP-003 2026-11-13，不触及 V6 行 :233，故本计划引用的 V6 逐字原文仍为现行口径）。QA 未触碰该文件，diff 全文在 scene-preserve 日志 COMMAND8，待维护方自行处置。
- 本节追加时间 2026-11-18 07:48:19（d9fa8820，只读任务包内主管 q1/q2 授权动作之记录部分）；三档映射/§4/§6 A-2b 闸门等其余内容不变。
