# UEMCP 服务端只读核查报告（server-verification.md）

## 0. 元信息

| 项 | 值 |
| --- | --- |
| 核查人 | TS服务端开发（员工会话） |
| 核查时间 | 2026-11-17（Asia/Shanghai）；更正范围证据补采 16:20 完成；打回定向补充自 19:02 起（证据：server-rework-meta.log / server-item1-editorstatus.log / server-item6-healthchain.log）；补遗任务 583badd5 项A/B/C 自 20:38 起（证据：server-itemA-editorstatus.log / server-583b-gen.log） |
| 对应任务 | **`034c6724-1a41-4352-89f0-92b1a0112437`（rework＝定向补充，非重写；本轮按打回理由 7 项补齐）**；权威范围＝打回理由重申的最终 6 项口径（前序 8ab8f2a9 更正包）；备份协议 dec1385e 已按规格执行；**补遗任务 `583badd5-1d43-4aa7-b457-0e06542d700d`**（项A/B/C 增量补齐：§3.4 暴露专节＋§0/§8.1/§13.1 勘误＋双路径同版复核） |
| 交付路径（打回项3） | **最终版：`feedback-review/server-verification.md`**；investigation 副本 `uemcp/logs/investigation-2026-11-17/server-verification.md` 与最终版**逐字节一致**；备份 `feedback-review/ts-backup/server-verification.md`；原件/备份 SHA256＋字节数见 `feedback-review/logs/server-deliverable-hash.log`（18:01 节＋20:16 打回节＋583badd5 节依次追加，互不覆盖）；**两处同版**（583badd5 项B 复核，逐字节一致） |
| 版本说明（透明披露） | 主管打回时审阅的是旧 355 行版快照；盘上版本在打回前已按 8ab8f2a9 重排为 299 行（结构即最终 6 项口径，旧章节全部保留于正文/附录）。本轮仅定向补充：⑥schemaVersion 原文摘录＋不匹配行为＋/health 消费链（§8）、①ue_editor_status 工具侧直接证据（§3.2(7)）、探针退出码补录（§1.2）、50 文件哈希复核（§1.5）、归属措辞（§2/§10）、双路径交付＋备份刷新。已认可内容未重写；另有一处事实更正（watchdog 状态字段枚举，§3.2(3)，以 live 文件为准）。**补遗版本披露（583badd5）**：该任务包引用 299 行旧快照（SHA256 67444D91…）与 44 行哈希日志（files=13）；接件时盘上已是 034c6724 返工后 323 行版（SHA256 5749C507…，20:16 交付，哈希日志 68 行）。本轮在现版上增量补齐 A/B/C，不回退、不重写已验收内容 |
| 核查范围（最终 6 项口径，打回权威） | ①CMD 3.1（P0）审计构建身份＋ue_editor_status 暴露面（CMD md :70-83）；②CMD 3.3 **TS 部分**（P0）audit.ts 写入方/保留/轮转/argsSummary＋根 README 与桥接 README §8 文档缺口（:100-113；**桥接请求级日志不在本任务范围**，仅作观察呈报）；③CMD 3.7 审计部分（P2）origin/stage/handler schema 提案（:162-175）；④CMD 3.9（P1）生效 policies/rateLimit 入审计＋发布配置快照（:192-206）；⑤CMD 3.11 **TS 文档**（P1）根 README＋packages/server＋README-DEV（:223-238）；⑥/health 消费链＋schemaVersion（主管附加）。章节号以磁盘 CMD 反馈原文逐条对号 |
| 解释声明（将在 report_task 重申） | ① **schemaVersion 为主管附加项**：CMD md 全文 grep `schema` **无 schemaVersion 相关命中（仅 CMD md :77 SCHEMA_KEYS 行，-SimpleMatch 大小写不敏感）**（证据：server-schemaversion.log:7-11 首块；583badd5 项C 勘误：原「零命中」表述不准确，该 grep 实有 1 处命中），故按「发现文件 schemaVersion 全链路」做综合只读核查（写入方→记录→TS 硬校验→失败路径→文档契约→缺口提案）。② 旧编号项（viewport=实际 CMD 3.5、argsSummary=实际 3.6、ZM P2-1）**不作为主项/验收项**，已核实内容保留于附录 A/B/C 作**额外观察**（打回理由：「已完成的3.5/3.6/ZM P2-1章节保留为额外观察，无需补做」）。③ 哈希基线 `feedback-review/logs/server-hash-before.txt` 已存在（他人 2026-11-17 10:12:54 生成，50 文件，范围恰为验收范围 `uemcp/packages/{server,shared}/src/**`，与本人 23 文件基线重叠项哈希一致）→ **复用不覆盖**，仅新建 after/compare。④ 双路径交付（打回项3；583badd5 项B 路径表述更正）：最终版 `feedback-review/server-verification.md` 与 investigation 副本 `uemcp/logs/investigation-2026-11-17/server-verification.md` **两处同版、逐字节一致**（SHA256＋字节数对照见 server-deliverable-hash.log 583badd5 节；另见「交付路径」行）。 |
| 性质 | **只读核查**：未修改任何源码/文档；只提案不实现；未运行 build/typecheck/smoke/test（不得声称其通过） |
| CMD 源文档 | `C:\Users\Administrator\Desktop\UEMCP遇到的问题\CMD构建发布组_UEMCP反馈\UEMCP插件使用问题与改进建议.md`（323 行）+ `raw/collect.log`、`raw/collect.py`（只读引用，未写入该目录） |
| 代码基线 | 工作区 `C:\UE5_P\5.4\UEMCP`（uemcp/ TS 服务端＋UEMCPBridge/ 桥接插件源码，桥接侧只读引用）；CMD 工程部署副本 `C:\UE5_P\5.7\CMD_SHUZINUANSHENG_J2\Plugins\UEMCPBridge\`（只读比对） |

## 1. 核查方法与只读证明

1. **静态逐字锚点**：TS 服务端（packages/server、packages/shared）与桥接插件相关文件全文/分段读取，行号锚点逐字核对；原始摘录存 `evidence.log`（1115 行/50 节）＋本轮新增 `feedback-review/logs/server-cmd*.log`、`server-schemaversion.log`（每块含命令与完整输出）。
2. **审计数据只读聚合探针**：`audit_probe.py`、`audit_probe2.py` 本轮重跑（`C:\Python314\python.exe`，均 EXIT 0，完整输出存 `feedback-review/logs/server-audit-probe.log` / `server-audit-probe2.log`），对 `~/.uemcp/audit/*.jsonl`（4 文件 1003 条）只做聚合，**不输出任何 argsSummary 值、代码原文或命令内容**（CMD §1 隐私口径、collect.py:135）。**打回项6补证**：investigation 目录 `audit_probe.log`/`audit_probe2.log` 已于 19:02 重跑并追加退出码行（现分别以 `PROBE_DONE`＋`EXIT=0`（:31-32）、`PROBE2_DONE|records=1003`＋`EXIT=0`（:11-12）结尾；重跑数据与 16:20 版一致：VIEWPORT n=30、records=1003）；重跑命令与退出码另录 `feedback-review/logs/server-rework-meta.log:23-33`；重跑前旧版快照存 `backup-20261117/audit_probe*.log`。
3. **发现文件安全探针**：`probe_discovery.py`（新增）只打印非敏感键（schemaVersion/pid/pluginVersion/bridgeProtocol/stale/staleReason/projectDir/startedAt/ueVersion＋hasTokenKey 布尔），**绝不输出 token 值**。结果：`DISCOVERY_FILES|count=0`——核查时桥接未运行、`~/.uemcp/bridge.json` 与 `bridges/*.json` 均不存在，故 schemaVersion 链路以**代码＋文档**证实，无现场文件样本（如实注明）。
4. **外部佐证（只读）**：CMD 工程 `Saved/UEMCP/bridge-settings.json` 与 `Saved/UEMCP` 目录 Test-Path 均 **False**；`Saved/Logs/CDM.log` grep `[UEMCP]` 恰 **2 行**；部署副本 settings.py 与仓库 **SHA256 完全一致**（C3207C7320E1794563B5132C5488D360E1DC9382A3ECED4505EC6F4F42342B8D）；`Config/DefaultWebAPI.ini:6 = DataChannelType=PixelStreaming`（附录 A 用）。
5. **只读证明（验收口径）**：`server-hash-before.txt`（50 文件，复用）→ 本轮 `server-hash-after.txt`（同 50 路径同格式）→ `server-hash-compare.log`：**targets=50 scopeOk=50 differences=0**（checkedAt=2026-11-17T16:20:25+08:00）。**打回项5复核**：19:02:12 按同一 before 基线（50 路径，范围 `uemcp/packages/{server,shared}/src/**`，排除 node_modules/dist）重算 after/compare（本人文件，覆盖更新；16:20 版已快照于 ts-backup/）：**targets=50 scopeOk=50 differences=0**（checkedAt=2026-11-17T19:02:12.3998332+08:00，server-hash-compare.log:51-52；命令与汇总见 server-rework-meta.log:35-38）。另：本人 23 文件证据基线三时点比对 differences=0（hash-before/after/final.log，补充证据）。feedback-review/ 有桥接侧与 QA 同事在写，本轮仅新建/更新 `server-*` 前缀本人文件（新日志名拒绝覆盖），未触碰任何他人文件。**备份协议（dec1385e＋打回项4）**：本报告最终写入后，副本连同本轮 server-* 证据存 `feedback-review/ts-backup/`（TS 独有目录），原件＋备份 SHA256＋**字节数**对照见 `feedback-review/logs/server-deliverable-hash.log`（18:01 节保留，打回节追加）；前序 `uemcp/logs/investigation-2026-11-17/backup-20261117/` 为历史快照，保留不动（本轮仅追加探针旧版快照）。自查结论：未误动他人文件（他人基线 server-hash-before.txt 只读复用，备份中仅存其副本）。**583badd5 复核**：按同一 before 基线再次重算，仅新建 `server-hash-after-583b.txt`/`server-hash-compare-583b.log`（19:02 版保留不动）：**targets=50 scopeOk=50 differences=0**（checkedAt=2026-11-17T20:50:05.7932470+08:00；命令与完整输出见 server-583b-gen.log）。
6. **未运行**：build、typecheck、smoke、test 均未执行；smoke 仅静态计数（static-counts.log：check( 88=1 定义+87 调用点，上限口径；运行时数量未验证）。

## 2. 结论速览（更正后范围）

| 项 | 优先级 | 状态 | 一句话结论 | 证据日志 |
| --- | --- | --- | --- | --- |
| CMD 3.1 审计无法归因到构建 | P0 | **属实** | 1003 条中 buildHash/buildTime/sourcePath/instanceId 全为 0；/health 已有四字段，TS watchdog 解析后丢弃；client 字段也从未填充；**ue_editor_status 返回不含四字段（工具侧直接证据，§3.2(7)）** | server-cmd31.log、server-item1-editorstatus.log |
| CMD 3.3（TS 部分）审计写入方/保留无文档 | P0 | **属实（写入方身份已核实）** | 写入方＝**TS 服务端 audit.ts**（非插件）；按天文件＋30 天硬编码保留＋启动清理；用户文档无保留/轮转/停写告警契约；桥接 rpc.py 零日志、CDM.log 仅 2 行生命周期（**观察项，桥接请求级日志不在本任务范围**） | server-cmd33.log |
| CMD 3.7 PYTHON_ERROR 混计两来源 | P2 | **属实** | 用户代码异常与 handler 异常同码，details 无 origin/stage；exceptionType 有无仅部分可区分；20 条全为 7–71ms 快速失败 | server-cmd37.log |
| CMD 3.9 生效权限/限流配置来源未记录 | P1 | **属实（机制证实，逐会话不可归因）** | 双层门：TS policy 默认 read-only（full=显式 CLI/env）×桥接 settings 默认全关（env>file>default）；工程无配置文件＋部署副本与仓库逐字节一致⇒当前代码下 env 是唯一开启路径；settings.source 永不反映 env；审计两层状态皆盲 | server-cmd39.log |
| CMD 3.11 Tests/README 计数与代码不符 | P1 | **属实（不一致处比 CMD 列举更多）** | 方法数：README:29 写 12、§5 表 13 行 vs rpc.py 实际 16；自检数：:170 写 14、:31/:209/:220 写 11 vs 实际 16 个 check_/test_；5 个脚本存在但未列表；ue_call_function 全文缺席 | server-cmd311.log |
| 附加项⑥ /health 消费链＋schemaVersion | 主管附加 | **核实完成（本轮补逐字原文＋分来源不匹配行为＋消费链汇总）** | 桥接写 schemaVersion=1 → TS `=== 1` 硬校验（discovery.ts:70），不符即 stale/换源/BRIDGE_UNAVAILABLE（§8.1 逐字＋分来源行为）；/health 17 键经 watchdog 单点丢弃、下游仅消费 7 字段状态（§8.2）；shared 类型为 number 而运行时只认字面量 1；无协商/迁移协议；**TS 忽略桥接 stale 标记**；/health 与审计均无 schemaVersion；现场发现文件 count=0 | server-schemaversion.log、server-item6-healthchain.log |

CMD §2 统计独立复现（server-audit-probe.log / server-audit-probe2.log，均 EXIT 0）：
RECORDS=1003；失败 31（PYTHON_ERROR 20 / CAPTURE_TIMEOUT 5 / BRIDGE_TIMEOUT 2 / EXEC_DISABLED 2 / PERMISSION_DENIED 1 / NOT_FOUND 1）；PLUGINVERSION_DIST {0.1.0:890, 0.1.4:113}（0.1.5=0）；UEVERSION_DIST {5.4.4:4, 5.7.4:999}；POLICYMODE_DIST {full:963, standard:40}；CONFIRMMODE_DIST {policy:952, None:51}；PER_DAY_COUNT {10-20:4, 10-29:886, 11-02:22, 11-09:91}；TOOL_DIST {python_exec:952, viewport_capture:30, call_function:12, pie_control:7, actor_edit:2}。与 CMD §2 及 collect.log 全部一致。

> 范围归属（打回项7）：上表按打回理由最终 6 项口径。CMD 3.5/3.6/ZM P2-1 **非验收项**，已核实内容保留于附录 A/B/C 作额外观察（§10，无需补做）；CMD 3.3 桥接请求级日志为观察/呈报项（§4.2(4)），实现归属见 §12。

---

## 3. 主项一：CMD 3.1（P0）审计记录无法归因到具体构建

### 3.1 CMD 主张（原文锚点，全文摘录见 server-cmd31.log 首块）

- :70 标题「P0 审计记录无法归因到具体构建，事后无法证明『谁在跑哪个包』」。
- :72 现象：审计 16 键，无 buildHash/sourcePath/instanceId。:74 影响：pluginVersion 是唯一线索，文档自认两个构建共用同一版本号，需 /health 的 buildHash/sourcePath 才能区分。
- :77-79 证据：collect.log SCHEMA_KEYS 行＋`Plugins/UEMCPBridge/README.md:169`、`README.md:264`＋server.py:567-570。
- :81 建议：审计增加 buildHash/sourcePath/instanceId（至少 instanceId），与 /health 同源取值；README §8 增加「审计字段 ↔ /health 字段」对照表。:83 优先级 P0（发布组主责）。

### 3.2 独立复核（状态：属实）

1. **审计侧**：`audit_probe.log` SCHEMA_KEYS 恰 16 键；KEY_PRESENCE：buildHash/buildTime/sourcePath/instanceId/client/origin/stage/queuedMs/details/errorResource **全部 0**（1003 条）。类型 `AuditRecord`（uemcp/packages/shared/src/types.ts:70-88）共 17 键，无任何构建身份字段；唯一写入点 auditCall（tools/common.ts:107-142，record :123）只落 ueVersion/pluginVersion（:139-140，取自 watchdog 状态）。
2. **桥接 /health 已有四字段**（server.py:558-577 health_payload，摘录 server-cmd31.log）：

   ```python
   "instanceId": server.instance_id,   # :567
   "buildHash": BUILD_HASH,            # :568
   "buildTime": BUILD_TIME,            # :569
   "sourcePath": PLUGIN_SOURCE_PATH,   # :570
   ```

3. **丢失点精确定位在 TS**：watchdog.ts `BridgeWatchState`（:8-16）只有 7 字段（**connected/url/ueVersion/pluginVersion/projectDir/startedAt/pid**，live 逐字核对；旧版本报告误枚举为 available/bridgeProtocol/port/failures，现以 live 文件为准更正，见 server-rework-meta.log:8-9），:49-65 从 /health JSON 只取 ueVersion/pluginVersion/projectDir/startedAt/pid（缺失时回落 cached.discovery）＋connected/url——instanceId/buildHash/buildTime/sourcePath/capabilities/rateLimit/policies/bridgeProtocol/port/projectFile **全部被丢弃**。即使审计想记也无数据可取。探针周期 5s（:75）、单次超时 1s（:42）、首次失败即 markDown（:79-86）。逐字摘录：server-item6-healthchain.log（watchdog 块）；消费链汇总见 §8.2。
4. **client 字段从未填充**：AuditRecord.client? 存在，但 common.ts:127 取 ctx.clientInfo，而 buildServer.ts:19-27 的 oninitialized 只记日志、无 setter 调用→恒缺失（KEY_PRESENCE client=0 印证）。
5. **版本号归因失效的数据印证**：PLUGINVERSION_DIST {0.1.0:890, 0.1.4:113}，0.1.5=0；与桥接 README:264「曾有两个不同构建共用 0.1.4」互证。
6. **CMD 引用核对**：:78 两处 README 引用均指**桥接 README**（:169 构建身份段 ✓、:264 版本纪律段 ✓ 逐字属实）；根 README.md:264 是「### 目录结构」（不同文件，非矛盾）。rpc.py 响应 meta（:219-224）只有 requestId/durationMs/ueVersion/pluginVersion，无构建身份→仅靠 RPC 响应无法补齐，必须经 /health（watchdog）通道。
7. **ue_editor_status 暴露面：工具侧直接证据（打回项2补齐）**——**MCP 返回不含 buildHash/buildTime/sourcePath/instanceId 中任何一个**，且该结论与 watchdog 丢弃无关（工具路径根本不经过 /health）。链路逐字：`tools/status.ts:16` 工具名 ue_editor_status、:17 rpcMethod="editor.status"、:21 timeoutMs=30000、:31 `ctx.bridge.call("editor.status", …, {retriable:true})`、:37 `const data = (res.data ?? {})` 原样透传桥接 payload、:38-43 **覆写** `data.policies` 为 TS 侧策略（注释 :36「§5.1：policies 段为 Server 侧信息（桥接不知道 MCP 策略）」；桥接若返回 policy_snapshot 会被替换）、:44-50 okResult。桥接侧 `handlers/status.py` 的 editor.status payload **本身就没有构建身份**：ALL_SECTIONS:23 {editor,level,selection,viewport,capabilities,policies}、DEFAULT_SECTIONS:24 [editor,level,selection,capabilities]；`_editor_section:80-95` 仅返回 8 键 {ueVersion:87, pluginVersion:88, bridgeProtocol:89, processId:90, isPieRunning:91, isSimulating:92, isCompiling:93, isAssetRegistryLoading:94}；level/selection/viewport（:109-189）同样无；capabilities:232-233、policies:234-235 仅显式请求时返回。四字段**只存在于桥接 /health**（server.py:567-570），工具路径从未触及。外层 meta 由 TS `common.ts makeMeta:33-41` 生成＝{requestId:36, durationMs:37, ueVersion:38, pluginVersion:39}；okResult:43-59 structuredContent={ok:true, data, warnings, meta}:56——同样无构建身份。grep 验证：status.ts 与 status.py 对四字段名 **MATCH_COUNT=0**（server-item1-editorstatus.log:134/:139；该日志含 status.ts 全文 52 行＋common.ts:33-59＋status.py:23-24/:80-95/:218-237 逐字摘录）。结论：ue_editor_status 暴露面＝桥接 editor.status payload（editor 段 8 键等）＋TS policies 覆写＋4 键 meta；欲暴露构建身份须桥接加字段或 TS 从 watchdog 状态注入（§3.3 提案，主管裁决）。

### 3.3 提案（只提案，不实现）

- TS 侧（本角色范围）：① watchdog 状态扩展 instanceId/buildHash/buildTime/sourcePath（顺带 capabilities/policies/rateLimit，见 §6/§8/附录 A）；② AuditRecord＋auditCall 增补同名字段（至少 instanceId），与 /health 同源；③ 顺手修复 client 从未填充。
- 文档侧：README §8「审计字段 ↔ /health 字段」对照表（CMD :81 原文建议；本轮禁止改文档，留待修复任务）。
- 归属：字段落地＝TS；/health 字段已存在＝桥接无需改；对照表文档＝发布组/主管裁决。
- **证据日志**：`feedback-review/logs/server-cmd31.log`（CMD 原文＋probe KEY_PRESENCE＋types.ts/common.ts/buildServer.ts/watchdog.ts/server.py/rpc.py/README 摘录）；`server-audit-probe.log`；`server-item1-editorstatus.log`（打回项2：ue_editor_status 全链路逐字＋四字段 grep MATCH_COUNT=0）。

### 3.4 ue_editor_status 暴露专节（补遗任务 583badd5 项A；live 复核，增量不重写 §3.2(7)）

**明确回答：ue_editor_status 的 MCP 返回不暴露 instanceId/buildHash/buildTime/sourcePath 中任何一个（四字段全无）。** 与 §3.2(7) 结论一致；本节为独立专节，原始证据＝本轮新建 `feedback-review/logs/server-itemA-editorstatus.log`（302 行，live 逐字摘录＋grep 计数，命令与完整输出均在）。

1. **实际数据流（live 核实，回答主管未决问题）**：`tools/status.ts:31` 直接 `ctx.bridge.call("editor.status", …, {retriable:true})`——**不读取 watchdog 状态**，故暴露与否与 watchdog 丢弃无关；watchdog（:8-16 状态 7 字段、:49-65 赋值）仅是 /health 消费链（§8.2），不在本工具路径上。
2. **工具实现锚点＋关键摘录**（status.ts 全文 52 行见 itemA 日志首块）：:16 name="ue_editor_status"、:17 rpcMethod="editor.status"、:21 timeoutMs=30000；:37 `const data = (res.data ?? {})` 原样透传桥接 payload；:38-43 **覆写** data.policies 为 TS 侧策略（:36 注释「§5.1：policies 段为 Server 侧信息（桥接不知道 MCP 策略）」）；:44-50 okResult。外层 meta＝common.ts makeMeta:33-41 {requestId/durationMs/ueVersion/pluginVersion}，okResult:43-59 structuredContent={ok,data,warnings,meta}——均无构建身份。
3. **桥接侧 payload（live 核实，澄清主管引用）**：任务包所指 `status.py:27-58` 实为 `detect_capabilities()`（返回 **9 个能力键**：python/screenshot/blueprintRead/blueprintNodeRead/blueprintCompile/animBlueprintEdit/assetRegistry/console/pieControl），**并非 editor.status 响应主体**；editor 段为 `_editor_section:80-95`，返回 **8 键** {ueVersion:87/pluginVersion:88/bridgeProtocol:89/processId:90/isPieRunning:91/isSimulating:92/isCompiling:93/isAssetRegistryLoading:94}。ALL_SECTIONS:23/DEFAULT_SECTIONS:24；capabilities:232-233、policies:234-235 仅显式请求时返回。**两处均无四字段**。
4. **四字段唯一存在处**：桥接 /health health_payload（server.py:567-570，17 键，摘录见 itemA 日志）；工具路径从未触及。
5. **grep 验证（本轮 live）**：status.ts、handlers/status.py、watchdog.ts 对四字段名（buildHash/buildTime/sourcePath/instanceId）均 **MATCH_COUNT=0**（itemA 日志 :280/:286/:292）。
6. **结论**：暴露面＝桥接 editor.status payload（editor 段 8 键＋默认 level/selection/capabilities）＋TS policies 覆写＋4 键 meta；欲暴露构建身份须桥接加字段或 TS 从 watchdog 状态注入（§3.3 提案，主管裁决）。

## 4. 主项二：CMD 3.3（TS 部分，P0）审计写入方/保留/轮转无文档（桥接请求级日志为观察项）

### 4.1 CMD 主张（:100-113，全文摘录见 server-cmd33.log 首块）

- :102 现象：`~/.uemcp/audit/` 只有 4 个按天文件（10-20/10-29/11-02/11-09），最后写入 2026-11-09 12:53；插件本体 57 文件 0 处提及 audit；CDM.log 里 `[UEMCP]` 只有 2 行（bridge_started/bridge_stopped），无请求级记录、无 requestId。
- :104 影响：引擎日志与审计无法按 requestId 对齐；审计写几天、谁轮转、磁盘满会怎样无书面约定；停写（11-09 后无新文件）没人会发现。
- :107-109 证据：collect.log AUDIT_FILE×4＋PLUGIN_SCAN 57/0/2；CDM.log:1661/:3472；server.py:132-142 仅生命周期；rpc.py 无 logging。
- :111 建议：桥接 /rpc 入口/出口各写一行结构化日志（requestId/method/tool/errorCode/durationMs/pluginVersion/instanceId），与审计共用 requestId；审计侧明确「按天文件＋保留天数＋轮转方式＋停写告警」。:113 P0。

### 4.2 独立复核（状态：属实；写入方身份已核实）

1. **写入方＝TS 服务端，不是插件**（CMD §5 #4 悬案就此关闭）：`uemcp/packages/server/src/audit.ts` 是唯一审计写入器——文件头注释 :5「按天轮转；启动时清理 30 天前的文件」；`RETENTION_DAYS = 30` **硬编码**（:15）；启动清理 :41-58（cutoff=now-30d，:43）；落盘 `~/.uemcp/audit/YYYY-MM-DD.jsonl`，`UEMCP_AUDIT_DIR` 可覆写，目录 0700/文件 0600。插件 57 文件 0 处 audit（本轮 grep 计数 **0**，server-cmd33.log）是**预期行为**而非缺陷；collect.py:4 文档字符串把审计误标为桥接侧产物，应更正（QA/发布组口径）。
2. **停写告警＝部分存在**：audit.ts 写失败不阻塞调用，连续 3 次失败置 auditDegraded（:27-29/:71-77），经 /health 暴露（transports/http.ts:274）——是**被动健康旗标**，无主动告警；「11-09 后无新文件」更可能是**此后无 MCP 会话**（审计由 TS 服务端进程写，桥接单独运行不产生审计），而非写入器故障（见 §9 #5）。
3. **文档缺口成立**：根 README grep `审计|audit` 7 处（:63/:238/:243/:270/:367/:547/:574）全是安全性概述；grep `保留|retention|轮转|rotat` 仅 :542（说的是**桥接 token** 每次启动轮换，与审计保留无关）→ **无任何「按天文件＋保留天数＋轮转方式＋停写告警」用户契约**。logger.ts（:37/:62-70）是另一条 stderr 日志通道，同样无保留策略。
4. **桥接无请求级日志成立（观察项；桥接请求级日志不在本任务验收范围，仅呈报）**：rpc.py grep `logging|_log\(|print\(` **零命中**（handle_request :139-230 全程无日志）；server.py 日志助手 `_log`（:132-139，unreal.log("[UEMCP] %s")，异常回退 print）/`_log_error`（:142-149）只被生命周期调用（bridge_started/bridge_stopped :554 等）。CDM.log 实测恰 2 行：

   ```text
   1661: [2026.11.15-10.06.07:620][  1]LogPython: [UEMCP] bridge_started port=18778 pid=37300 project=C:\UE5_P\5.7\CMD_SHUZINUANSHENG_J2
   3472: [2026.11.15-10.08.07:236][958]LogPython: [UEMCP] bridge_stopped pid=37300
   ```

   无 requestId→CMD「无法对齐」主张成立。审计目录实测 4 文件（1878B/…/50416B，mtime 至 2026-11-09 12:53:41），与 collect.log AUDIT_FILE 行一致。
5. **requestId 共享可行性**：TS 审计已有 requestId（common.ts:123 record），桥接响应 meta 也回传 requestId（rpc.py:219-224）→ 桥接补入口/出口日志即可对齐，无需改协议。

### 4.3 提案（只提案）

- 桥接侧（**报告项，非本角色改**）：按 CMD :111 在 /rpc 入口/出口写结构化日志（requestId/method/tool/errorCode/durationMs/pluginVersion/instanceId），复用 `_log` 通道。
- TS 侧（本角色范围，留待修复任务）：① 审计保留/轮转/停写告警契约写入用户文档（30 天硬编码是否可配置由主管裁决）；② auditDegraded 升级为可观测告警（如 /health 之外增加启动自检与显式警告日志）；③ sessionId 在 stdio 传输下缺失的口径一并文档化。
- QA/发布组：collect.py:4 写入方误标更正。
- **证据日志**：`feedback-review/logs/server-cmd33.log`（CMD 原文＋CDM grep＋插件 audit grep＋rpc.py logging grep＋audit.ts/logger.ts/http.ts 摘录＋README 双 grep＋审计目录清单＋collect.log AUDIT_FILE/PLUGIN_SCAN＋collect.py:1-14）。

## 5. 主项三：CMD 3.7（审计部分，P2）PYTHON_ERROR 把调用方代码错误与插件缺陷混在一起

### 5.1 CMD 主张（:162-175，全文摘录见 server-cmd37.log 首块）

:164 同码两来源（rpc.py:101-116 兜底所有非 RpcError 异常 vs python_exec.py:64-70 用户代码异常），审计无 stage/handler 字段；:169 证据 ERRORCODE_DIST PYTHON_ERROR 20＋FAIL_ROW（collect.log 工具名带 ue_ 前缀：ue_python_exec 13+7；原始审计 tool 字段为 python_exec，命名映射非矛盾）；:170 errors.py:40（-32014/500/不可重试）；:173 建议 **`origin: caller|bridge`**＋stage 进 errorResource/details，审计同步记录。

### 5.2 独立复核（状态：属实）

1. **双来源同码逐字属实**：用户代码路径 python_exec.py:64-70 `except Exception` → `RpcError("PYTHON_ERROR", ..., {"traceback": ...})`；handler/桥接路径 rpc.py:101-116 `_python_error` 把**所有非 RpcError 异常**统一 PYTHON_ERROR，details={"traceback"(≤8000 字符，_MAX_TRACEBACK_CHARS=8000 :98), "exceptionType"}。errors.py:40 = -32014/500/retryable False；TS errors.ts:120 镜像一致。
2. **部分可区分但无显式标记**：用户代码 details 只有 traceback；handler 路径多一个 exceptionType→**exceptionType 有无**可作启发式区分，但契约上无 origin/stage 字段；审计只落 errorCode（common.ts:138），details 整体不落（KEY_PRESENCE details=0）→ 事后无法归因。
3. **数据佐证「调用方代码错误」假设（CMD 3.2 :96）**：probe2 PYTHON_BY_CODE PYTHON_ERROR n=20，min 7 / p50 20 / p95 27 / max 71 ms——全部**即时异常**（非超时、非长执行），与用户代码语法/名字错误特征一致；但**逐条归因未证实**（审计无 details）。EXEC_DISABLED n=2（1/3ms）＝桥接门拒绝（rpc.py:90-95，见 §6）。
4. **TS 透传链路已通**：client.ts:164-177 把桥接 error.details 原样透传进 structuredContent.error→桥接若加 origin/stage，**MCP 客户端无需改 TS 即可看到**；但审计要记录则需 AuditRecord＋auditCall 增补（TS 侧改动）。另 TS 自身 BRIDGE_TIMEOUT 的 details.phase="game_thread"（client.ts:194-200）同样未落审计。

### 5.3 提案（只提案）

- 桥接侧（报告项）：PYTHON_ERROR details 增加 `origin: caller|bridge`（CMD :173 原文枚举）＋stage（handler 名/执行阶段）；用户代码路径与兜底路径分别打标。
- TS 侧（本角色范围）：AuditRecord＋auditCall 记录 origin/stage（连同 details 关键键），与 §3 构建身份字段同批落地最经济。
- **证据日志**：`feedback-review/logs/server-cmd37.log`（CMD 原文＋python_exec.py/rpc.py/errors.py/client.ts/common.ts/errors.ts 摘录＋probe ERRORCODE_DIST/PYTHON_BY_CODE＋collect.log FAIL_ROW）。

## 6. 主项四：CMD 3.9（P1）本轮生效的权限/限流配置来源未记录

### 6.1 CMD 主张（:192-206，全文摘录见 server-cmd39.log 首块）

:194-197 现象：policyMode full 963/1003、standard 40；confirmationMode=policy 952；工程内无 bridge-settings.json（README 默认全门关闭/只读）却有 952 次 python.exec 成功；疑似环境变量临时开启且无快照；PERMISSION_DENIED 仅 1、EXEC_DISABLED 2。:199-202 证据 collect.log POLICY_DIST/CONFIRM_DIST＋桥接 README:104/:68＋rpc.py:74-95。:204 建议：交付清单附生效权限/限流配置快照；/health `policies` 进审计。:206 P1。

### 6.2 独立复核（状态：属实——机制证实；逐会话来源不可归因；历史不可考）

**两层独立的门，审计对两层都盲：**

1. **TS 层（policyMode 的来源）**：config.ts:87-93 优先级 CLI `--policy`（standard/full/read-only）＞ env `UEMCP_POLICY`（仅 standard/full）＞ **默认 "read-only"（:93）**。故 full=963 **必为显式** `--policy full` 或 `UEMCP_POLICY=full`，绝非默认；但**CLI-vs-env 的来源未记录**。审计 policyMode 写入点 common.ts:131（ctx.policy.mode）；门判定 policy.ts:43（console 需 full＋allowConsole）/:45（exec 需 full＋allowExec）；allowDestructive/Console/Exec 开关 config.ts:94-96。
2. **桥接层（settings 门）**：settings.py 默认 allow_write/exec/console=**False**（:93-95，pick 默认 :144-152 同）；`pick(key, env_key, default)`（:137-140）＝**env＞file＞default**；env 键 UEMCP_BRIDGE_ALLOW_WRITE/EXEC/CONSOLE（:145/:148/:151）；配置文件＝`Saved/UEMCP/bridge-settings.json`（:124）。**`source` 字段（:87/:104/:118/:131/:234）只会是 "defaults" 或配置文件路径——env 覆写永不改变 source⇒env 使用在配置自身也不可见**。文件损坏静默回退 data={}（:132-135）。searchTimeoutMs/consoleAllowlist 无 env 入口（:171-176/:154-157）；rateLimit 有 env 钮（:178-208，perSecond=0 即禁用）。
3. **桥接门实现（rpc.py:74-95 enforce_gates，逐字摘录 server-cmd39.log）**：入队前硬门——写操作拒→`PERMISSION_DENIED` details.gate="bridge.allowWrite"（:78-83）；console.command 拒→`PERMISSION_DENIED` gate="bridge.allowConsole"（:84-89）；python.exec 拒→**`EXEC_DISABLED`** gate="bridge.allowExec"（:90-95）。审计里 EXEC_DISABLED n=2（1/3ms）即此层拒绝；PERMISSION_DENIED n=1 的层归属（TS 门 vs 桥接写/控制台门）**不可判**——details.gate 在响应里有、审计不落。
4. **现场佐证**：CMD 工程 `Saved/UEMCP/bridge-settings.json` Test-Path **False**，`Saved/UEMCP` 目录亦 **False**（独立复核，非仅转述 CMD）。桥接 README:104 逐字「默认全部权限门关闭（只读）。写操作、控制台、Python 执行必须分别显式开启。」:68 配置优先级段 ✓。
5. **部署副本比对（本轮新增）**：`C:\UE5_P\5.7\CMD_SHUZINUANSHENG_J2\Plugins\UEMCPBridge\` 当前为 **0.1.5**（.uplugin:4 VersionName；settings.py:12 PLUGIN_VERSION），settings.py 与仓库 **SHA256 逐字节一致**（C3207C73…，server-cmd39.log 两块 Get-FileHash），门默认 False（:93-95）、discovery.py:19 SCHEMA_VERSION=1 行号全同。⇒ **就当前代码而言**，文件缺席时开启 exec 的机械路径只剩 env `UEMCP_BRIDGE_ALLOW_EXEC`（＋TS 层显式 full）。**但审计记录属 0.1.0/0.1.4 时代（890+113 条），当时部署副本已被覆盖→历史默认值不可考**；952 次成功究竟经 env 还是旧副本默认开启，**逐会话不可归因**（审计既无桥接门状态也无 source）。
6. **/health 已暴露桥接门快照但被 TS 丢弃**：policy_snapshot（settings.py:237-248）返回 `{mode: "standard"|"read-only"（按 allow_write 推）, write: allow_write, exec: allow_exec, destructive: False}`——**含 write/exec 布尔，但无 console、无 source、无 "full"**；经 /health `policies`（server.py:576）与 `rateLimit`（:575，字段 enabled/perSecond/burst/available/accepted/rejected，README:101 ✓）暴露；watchdog.ts:8-16/:49-65 全部丢弃→审计永远看不到桥接层生效配置。

### 6.3 提案（只提案）

- TS 侧（本角色范围）：① watchdog 保留 /health policies/rateLimit 快照；② 审计增补 TS policy **来源**（cli/env/default）＋桥接门快照（write/exec/console＋settings.source）；③ confirmationMode/confirmationSwitch 已有，补 policy 来源即闭环。
- 桥接侧（报告项）：settings.source 扩展为可标记 env 覆写（如 "env:UEMCP_BRIDGE_ALLOW_EXEC"）；policy_snapshot 补 console 与 source。
- 发布组/QA：按 CMD :204 交付清单附「生效权限/限流配置快照」（含 env 清单）；历史会话来源不可考如实标注。
- **证据日志**：`feedback-review/logs/server-cmd39.log`（CMD 原文＋settings.py/rpc.py/server.py/config.ts/policy.ts/common.ts/watchdog.ts 摘录＋Test-Path×2＋部署/仓库双 Get-FileHash＋部署 grep＋.uplugin＋README:68/:86/:104＋probe2 POLICYMODE/CONFIRMMODE＋collect.log POLICY_DIST/CONFIRM_DIST）。

## 7. 主项五：CMD 3.11（P1）Tests/README 的方法数与自检数同代码不符（TS 文档为验收部分；桥接 README 为报告项）

### 7.1 CMD 主张（:223-238，全文摘录见 server-cmd311.log 首块）

:225-230 现象：README 目录树写「10 个工具对应的 12 个 RPC method」，§5 表与自检表数量对不上代码；:232-234 证据 桥接 README:29/:118-134/:170/:209/:220＋rpc.py:51-68＋collect.log TOOL_DIST/RPCMETHOD_DIST（ue_call_function/object.call 真实存在）；:236 建议（逐字）「§5 表与自检表改为『从代码/目录生成』，文档里给出生成命令；数量不复述，改成指向生成结果。」:238 P1。

### 7.2 独立复核（状态：属实；不一致处比 CMD 列举更多）

1. **方法数三处口径 vs 代码**：桥接 README:29 逐字「└─ handlers/ # 10 个工具对应的 12 个 RPC method」；§5 表（:120-134）**13 行**（bridge.ping/bridge.capabilities/editor.status/actor.query/actor.edit/level.control/asset.search/material.params/viewport.capture/console.command/python.exec/blueprint.query/pie.control）；rpc.py:51-68 HANDLERS 实际 **16 方法**（多出 object.reflect/object.call/log.query）。工具数也不符：TS 实际 15 工具（toolNames.ts:1-17；14 桥接 RPC＋policy_explain 本地）。
2. **ue_call_function 全文缺席**：桥接 README grep `ue_call_function|object\.call|object\.reflect|log\.query` 零命中（server-cmd311.log）；而审计 TOOL_DIST call_function=12（MCP 名 ue_call_function→object.call，toolNames.ts:15/:40）真实流量存在。
3. **自检数四处口径 vs 目录**：README:170 逐字「跑 §10.2 的 14 个无编辑器自检，全部 exit 0」；:31「Tests/ # 11 个无编辑器自检＋引擎冒烟/探针」；:209「### 10.2 无需编辑器的 11 个自检」；:220「预期 11 个脚本全部 exit=0」——**14/11/11/11 互相矛盾**；Tests/ 实测 28 个 .py＝**16 个 check_/test_**＋11 probe_＋1 其他（static-counts.log＋server-cmd311.log 双证）。§10.2 表（:222 起）缺 5 个**确实存在**的脚本：check_plugin_version.py / test_log_query.py / test_object_call.py / test_pie_control.py / test_viewport_capture.py（Test-Path 全 True，server-cmd311.log）。
4. **发布包口径**：README:34 ✓「Tools/ 与 Tests/*.ps1 仅源码仓库有」（test_uplugin_metadata.py 依赖 Tools/，发布包内必失败——与 CMD 3.10 关联，附录 D）；README:30 Tools/stamp_uplugin.py 源码仓库存在。
5. **TS 侧文档同病（本角色范围内的提案对象）**：根 README:262（CN）/:566（EN）写 11 工具、:270/:282 写 10 工具（实际 15）；README-DEV.md 过时锚点 :15/:104/:106/:115/:130/:132/:133/:141/:182（工具数/冒烟数/outputSchema 未挂载等，详见 §11.2）。另核实（打回项5口径补充）：`packages/server` 与 `packages/shared` **均无任何 .md 文件**（Get-ChildItem -Recurse -Filter *.md COUNT=0×2，server-rework-meta.log:12-16）→3.11 TS 文档的实际对象＝根 README.md＋README-DEV.md 两份。
6. **生成命令已有先例**：README:213-218 已给出 Tests 的 Get-ChildItem `^(check_|test_)` 生成命令→CMD :236「从代码/目录生成」可直接推广到 §5 方法表（从 rpc.py HANDLERS 生成）与自检表。

### 7.3 提案（只提案）

- 桥接 README（**报告项**）：按 CMD :236 方法表/自检表改为生成式，数量不复述；补 ue_call_function/object.reflect/object.call/log.query 四方法行；统一 :29/:31/:170/:209/:220 计数口径。
- TS 侧文档（本角色范围，留待修复任务）：根 README 与 README-DEV 的工具数/冒烟数/outputSchema 描述更正（§11.2 清单）。
- **证据日志**：`feedback-review/logs/server-cmd311.log`（CMD 原文＋README 五处计数＋§5 表＋§10.2 表＋rpc.py HANDLERS＋Tests 计数与 16 脚本名单＋5 脚本 Test-Path＋ue_call_function grep＋根 README/README-DEV 过时行＋collect.log TOOL_DIST/RPCMETHOD_DIST）。

## 8. 主项六（主管附加）：/health 消费链＋发现文件 schemaVersion 全链路

> CMD md 全文 grep `schema` **无 schemaVersion 相关命中（仅 CMD md :77 SCHEMA_KEYS 行，-SimpleMatch 大小写不敏感）**（server-schemaversion.log:7-11 首块；583badd5 项C 勘误，原「零命中」表述更正）→本项为主管附加，按全链路综合核查。

### 8.1 链路逐段核实（状态：核实完成）

1. **写入方（桥接）**：discovery.py:19 `SCHEMA_VERSION = 1`；server.py:469-484 `_record` 首键即 `"schemaVersion": SCHEMA_VERSION`（:470），其余 pid/projectDir/projectFile/host/port/url/token/ueVersion/pluginVersion/bridgeProtocol/capabilities/startedAt（:471-483；token 值永不回显，源码摘录安全）；publish（:495）经 discovery.py:167-169 **同时原子写** `~/.uemcp/bridges/<sha1-16>.json` 与 `~/.uemcp/bridge.json`（write_json_atomic :52-65：.tmp＋os.replace＋fsync，chmod 0600 尽力）；写失败→discovery_write_failed（:497）；关机回调 :499-504＋atexit RES-05 :506-509。
2. **TS 硬校验（逐字原文＋逐来源不符行为；打回项1补充）**：文件 `uemcp/packages/server/src/bridge/discovery.ts`（在 src/bridge/ 下，非 src/ 根）。头注释逐字（:5-6）：「校验：结构合法 + schemaVersion===1 + pid 存活 + GET /health 校验 app/pid/startedAt；」「任一失败视为陈旧，转向下一来源；全部失败 → null（调用侧 BRIDGE_UNAVAILABLE）。」门逐字（:70，validStructure :66-78 内）：`o.schemaVersion === 1 &&`（另查 pid:number/url:string/startedAt:string/token:string/host:string/port:number；projectDir 不在结构校验内，仅用于匹配 :139/:147）。**不符时的实际行为＝validStructure 返回 false→该条目视为陈旧/跳过；不抛错、不协商、不迁移、无版本兼容窗口**，逐来源：① **project 源（:133-172）**：:137/:139 门跳过无效条目→:143-155 目录扫描回退（validStructure(cand)&&equalProjectDir）→无匹配则**硬失败** :157-162 `log.warn("bridge_discovery_project_failed",{file,reason:"no-matching-project-bridge"})`→return null（Critical-2：不回退 bridge.json/默认端口）；pid 失败 :164-167 `bridge_discovery_stale_pid`；health 失败 :168-171 `bridge_discovery_health_failed`。② **bridge.json（:176-190）**：:179 门，否则 :188 `log.warn("bridge_discovery_invalid",{file:bridgeJsonFile})`→继续走默认端口。③ **bridge-url（:124-130）与默认端口（:193-196，env UEMCP_BRIDGE_PORT 否则 DEFAULT_BRIDGE_PORT）**：不读发现文件，仅 healthCheck。④ 全失败→:198 return null→调用侧工具调用时 **BRIDGE_UNAVAILABLE**。解析顺序（:1-9）：bridge-url→project-hash→bridge-json→default-port。逐字摘录＋grep（schemaVersion MATCH_COUNT=2）：server-item6-healthchain.log。
3. **类型 vs 运行时**：shared types.ts:44-67 `BridgeDiscoveryFile.schemaVersion: number`（:45，宽类型）而运行时只认字面量 1；capabilities 为 8 布尔（:56-65）。**接口无 stale/staleReason/staleAt 字段**。
4. **桥接 stale 标记被 TS 忽略（缺口）**：discovery.py mark_stale_file（:115-127）会写 `stale/staleReason/staleAt`；cleanup_stale（:146-164）按 `data.get("stale")` 或 pid 死亡删除（:157）。但 TS validStructure 不检查 stale、接口无该字段→**桥接主动标记的 stale 文件 TS 照常尝试**（仅靠 pid 存活 :55-64＋healthCheck :89-109 兜底，2s 超时 :95，只查 app/ok/pid/startedAt）。
5. **文档契约**：架构 §2.4（docs/UEMCP-架构设计.md:200-244）——projectHash sha1-16（:203）、样例 schemaVersion:1（:207）、capabilities 样例（:218-227）、解析顺序（:232-237）、校验规则逐字「文件结构合法，`schemaVersion === 1`」（:241）、pid process.kill（:242）、/health app/ok（:243）、pid/startedAt 匹配（:244）→**===1 规则有文档**；但**无任何版本升级/迁移协议文档**。桥接 README grep schemaVersion **零命中**。
6. **相邻字段口径**：/health（server.py:558-577，17 键）有 bridgeProtocol:1（:564）**无 schemaVersion**、无 settings.source；AuditRecord（types.ts:70-88）**无 schemaVersion**→审计无法归因发现协议版本。跨语言 pid 存活判定双方均保守（TS process.kill+EPERM=alive vs Python OpenProcess+异常=alive，discovery.py:82-112）；projectHash 双方保大小写（discovery.py:37-38 注释「Do not change case」；TS equalProjectDirOn win32 比较时不敏感 :36-44）。
7. **现场样本**：probe_discovery.py 实测 `DISCOVERY_FILES|count=0`（核查时桥接未运行）→无现场文件可验，链路结论全部来自代码＋文档（如实注明）。

### 8.2 /health 消费链（打回项1补充；逐字摘录见 server-item6-healthchain.log）

**桥接输出（17 键）**：server.py health_payload:558-577——app/ok/ueVersion/pluginVersion/bridgeProtocol/port/pid/**instanceId:567/buildHash:568/buildTime:569/sourcePath:570**/projectDir/projectFile/startedAt/capabilities:574/rateLimit:575/policies:576。

**TS 侧仅两个消费者，均选择性丢弃**：

1. **discovery.ts healthCheck（:89-109）**：fetch url+"/health"（AbortSignal.timeout(2000):95），只校验 app==="uemcp-bridge"&&ok===true（:99）、pid（:101）、startedAt（:102-103）；catch→false。用于 :126/:168/:182/:194。**不读取其余任何字段**。
2. **watchdog.ts probe（:40-75）**：fetch（AbortSignal.timeout(1000):42），门 body.app==="uemcp-bridge"&&body.ok===true（:47）；赋值（:49-65）只保留 **5 个 body 字段** ueVersion/pluginVersion/projectDir/startedAt/pid（typeof 守卫＋cached.discovery 回退）＋connected/url→**BridgeWatchState（:8-16）＝7 字段 {connected, url?, ueVersion?, pluginVersion?, projectDir?, startedAt?, pid?}**。**丢弃 instanceId/buildHash/buildTime/sourcePath/capabilities/rateLimit/policies/bridgeProtocol/port/projectFile**（app/ok 仅校验用）。setInterval(probe,5000):75＋unref:76；markDown（:79-86）：warn bridge_watchdog_down:81、client.invalidate():83、state={connected:false}:85（首次失败即 down）；未缓存→{connected:false}:37。

**下游消费**：makeMeta（common.ts:38-39）与审计（common.ts:139-140）只取 ueVersion/pluginVersion；**TS http.ts /health（:255-276）**输出 ok/name/version/protocolVersions/transports/sessions/uptimeSec/pid/logPath?＋`bridge:{connected,url?,ueVersion?,pluginVersion?,projectDir?}`（:267-273，**连 watchdog 已持有的 startedAt/pid 也未输出**）＋auditDegraded:true（:274）；ue_editor_status 的 policies 为 TS ctx.policy（status.ts:38-43），与桥接 /health policies 无关。

**结论**：构建身份（instanceId/buildHash/buildTime/sourcePath）、capabilities、rateLimit、policies **不达任何 TS 侧输出**（MCP 返回/审计/TS /health）；唯一丢弃点＝watchdog.ts:49-65 赋值。此为 3.1/3.9/附录 A 缺口的机制根因（§11.1）。

### 8.3 提案（只提案）

- TS 侧（本角色范围）：① BridgeDiscoveryFile 增补 stale/staleReason/staleAt 并在 validStructure/解析中尊重桥接 stale 标记；② 审计增补 schemaVersion（与 §3 字段同批）；③ schemaVersion 不符时的告警日志带期望/实际值，便于升级排障。
- 桥接侧（报告项）：/health 增补 schemaVersion；升级 schemaVersion 时提供双写/兼容窗口或明确迁移协议。
- 文档侧：架构 §2.4 补「版本升级与迁移」小节；桥接 README 补发现文件契约引用。
- **证据日志**：`feedback-review/logs/server-schemaversion.log`（CMD schema grep＋discovery.py/server.py/discovery.ts/types.ts 摘录＋TS stale grep＋架构 :200-244＋桥接 README grep＋/health＋AuditRecord＋probe_discovery 完整输出）＋**server-item6-healthchain.log（打回项1/6：discovery.ts 逐字＋schemaVersion grep＋watchdog/http.ts/common.ts/server.py 消费链）**。

---

## 9. CMD §5「未验证事项」#1–#8 处置（:288-297 逐字已核）

> 范围归属（打回项7，仅措辞）：下列处置对应最终 6 项口径——#4→§4（3.3 TS 部分）；#8→§6（3.9）；#2→§5（3.7 审计部分）＋附录 D；#1/#3→附录 A（3.5 额外观察）；#7→附录 B（3.6 额外观察）；#5→§4/本表；#6→附录 D（3.12 存档）。表内容不变。

| # | CMD 原文要点 | 处置 |
| --- | --- | --- |
| 1 | 两条 45s 请求实际 timeoutMs（审计不记请求参数） | **不可恢复精确值**（argsSummary 不含 timeoutMs，audit.ts:131-136）；但 45s 已被机制解释：ToolDef 固定 45000→dispatcher 上限（附录 A）；probe2 实测 45002/45009ms |
| 2 | 0.1.4 失败率 15.04% 根因 | **部分解决**：17 失败＝PYTHON_ERROR 13＋EXEC_DISABLED 2＋CAPTURE_TIMEOUT 2（CMD :94 自列）；PYTHON_ERROR 全为 7–71ms 即时异常（§5），逐条根因不可考 |
| 3 | 2 次 BRIDGE_TIMEOUT 触发层（排队 vs 执行） | **部分解决**：45s＝dispatcher 等待上限；同步截图阻塞 game thread 路径更吻合（附录 A）；逐条不可判（审计无 stage/queuedMs） |
| 4 | 审计实际写入进程与保留策略 | **已解决**：写入方＝TS 服务端 audit.ts（非插件）；按天文件＋RETENTION_DAYS=30 硬编码＋启动清理；插件 0 audit 为预期（§4.2） |
| 5 | 11-15 10:06 桥接会话是否发生请求、为何没落审计 | **部分解决（机制）**：审计由 TS 服务端进程写，桥接单独运行不产生审计；CDM.log 该会话仅 2 行（10:06:07 start→10:08:07 stop，2 分钟），**是否发生过请求不可判**（桥接无请求级日志，§4） |
| 6 | 5.4.4 那 4 条请求所属工程与环境 | **计数复现**（UEVERSION_DIST 5.4.4:4）；归属开放（审计无 projectDir/instanceId） |
| 7 | 952 次 python.exec 用途分布 | **定性解决**：argsSummary 仅 codeSha256/codeLength（隐私设计），102＝哈希摘要自然长度，无截断（附录 B）；用途聚类不可行属设计使然 |
| 8 | 本轮生效权限/限流配置来源 | **机制证实＋现场佐证**（§6）：双层门、env>file>default、文件缺席、部署副本与仓库一致⇒当前代码下 env 唯一路径；settings.source 不反映 env；历史副本被覆盖不可考；逐会话来源未记录 |

## 10. 附录（额外观察：CMD 3.5/3.6/ZM P2-1 及其余存档项；**非验收项**）

> 范围归属（打回项7）：以最终 6 项口径为准（§0/§2）。CMD 3.5/3.6/ZM P2-1 **非验收项**；前序任务已完成的核实内容保留为**额外观察**（打回理由原文：「已完成的3.5/3.6/ZM P2-1章节保留为额外观察，无需补做」）；旧编号（3.5 schemaVersion/3.6 retention/3.7 docs）不沿用。viewport/argsSummary 在 CMD 原文中的真实编号为 3.5/3.6。

### 附录 A：viewport 23.3% 失败＋PixelStreaming（CMD 真实编号 3.5，P1；**额外观察，非验收项**）

- **状态：属实（修复面比 CMD 设想小）**。检测正则已存在（viewport.py:63 `_PIXEL_STREAMING_RE`，:67/:90-95/:101-103/:608）；CMD 工程 ini:6=DataChannelType=PixelStreaming 实读 ✓；offscreen 快速失败先例（:609-620 CAPABILITY_UNAVAILABLE+suggestion）、截图预检（:601-606）、失败后 hint（:752-758）均在。
- **超时解耦**：TS ToolDef.timeoutMs=45000 固定（viewportCapture.ts:36，:47 传固定值非 args.timeoutMs）→rpc.py:119-136 `_request_timeout_seconds` MAX(meta, params+5000)（:132）→dispatcher 恒 45s；TS HTTP AbortSignal.timeout(50000)（client.ts:138）永不及。args.timeoutMs（schemas/viewport.ts:39，1000–30000 默认 15000）**内部有效**：viewport.py:575→:686 deadline=started+max(1.0, timeout_ms/1000-1.0)→默认 14s/上限 29s/下限 1s。
- **数据分离**（probe2）：BRIDGE_TIMEOUT n=2 **45002/45009ms**（dispatcher 上限；同步 take_high_res_screenshot :693-694 阻塞 _on_tick→dispatcher.py:87-91 等待超时更吻合；排队过期 :113-116 次之；逐条不可判）；CAPTURE_TIMEOUT n=5 **7040–29645ms** 全<30s（异步 pending 轮询；精确 timeoutMs 不可恢复）；OK n=23 p50 399/max 7473。
- **缺口**：无 pixelStreaming 前置快速失败；/health 无能力位（status.py:27-58，9 键）；TS 无预检；watchdog 丢弃 capabilities；45s 硬上限（CMD ~20s 设想＝设计决策）；失败后释放 pending（桥接侧；dispatcher.py:1-84 未读，不妄断）。
- 证据：evidence.log＋audit_probe2.log＋server-audit-probe2.log；DefaultWebAPI.ini 实读。

### 附录 B：argsSummary「102 字符上限」与 94.9% 流量（CMD 真实编号 3.6，P2；**额外观察，非验收项**）

- **「102 上限」假设证伪**（CMD :158 自标未验证）：audit.ts 全 146 行无 slice/truncate；102＝Python-repr({codeSha256(64hex), codeLength(4位)}) 自然长度 16+64+17+4+1=102（json_compact=99；collect.py:136 repr 口径）；CODELENGTH_DIGITS {2:2, 3:920, 4:30}。隐私设计只落哈希（arch:2593-2594、README-DEV:127、pythonExec.ts:21/:72 §6.5）。
- **mode 缺失 952/952**：auditCall 收 rawArgs（pythonExec.ts:83），zod default（schemas/python.ts:7）只作用于 parsed.data→审计永远看不到默认 mode。
- **94.9%＝已审计调用占比**：唯一记录点 common.ts:123；6 个纯读工具不写审计（editor_status/actor_query/asset_search/policy_explain/ue_reflect/log_query）；4 个已审计但零流量（level_control/material_params/blueprint/console_command）确为 0；full 可见 15 工具（policy.ts:20-47）。
- 证据：audit_probe.log（ARGSSUMMARY/MODE_KEY_PRESENT/CODELENGTH_DIGITS）＋evidence.log。

### 附录 C：ZM P2-1 BFS 预算硬编码（**额外观察，非验收项**；旧报告主项存档）

- 属实＋加重：assets.py:19-20 `_MAX_BFS_NODES=1000`/`_MAX_SEEDS=50` 写死无配置；预算耗尽**静默截断无 warning**（:205-209）vs 超时路径有 partial（:180-192）；_MAX_WARNINGS=20（:43/:353）未用；TS AssetSearchInput **.strict()**（schemas/assets.ts:31）使请求级 maxNodes 必被拒；assetSearch.ts:30 透传、:20 timeoutMs 30000、无 auditCall；根 README:132/:436 searchTimeoutMs 建议不可达。
- 证据：evidence.log＋ZM 反馈 md:123-127（只读）。**保留为额外观察：本轮不主张、不提案，仅存档（无需补做）。**

### 附录 D：其余章节简核（非本轮范围，仅存档）

- **3.2**（0.1.4 失败率）：17 失败构成见 §9 #2；PYTHON_ERROR 即时异常特征支持调用方代码假设（:96），逐条未证实。
- **3.4**（python 超时）：python_exec.py:37 timeoutMs 被丢弃、:93 timedOut:False 硬编码、同步执行无 deadline；README:116 自认 ✓；rpc.py:135 clamp 120000 vs README:78/settings.py:19 默认 30000 ✓；**CMD :119 误归因**：>30s＋BRIDGE_TIMEOUT 记录属 viewport（python max_ms=2382）非 python.exec；pythonExec.ts:22 timeoutMs=120000 仅声明、:70 实传 args.timeoutMs、schemas/python.ts:13 默认 10000→桥接等待 15s。
- **3.8**（读工具零流量）：5 个未审计方法的「零」是覆盖伪影；冒烟脚本口径——仅 *.ps1 不随包（README:247），README:34 已澄清 Tools//*.ps1 源码仓库专有；:181「冒烟脚本不随包」表述不精确。
- **3.10**（发布包缺 Tools//*.ps1）：README:34 ✓ 自认；test_uplugin_metadata.py 依赖 Tools/→发布包内必失败；与 3.11 生成式文档提案联动。
- **3.12**（5.4.4 流量，附录性质）：UEVERSION_DIST {5.4.4:4, 5.7.4:999} 复现 ✓；归属开放（§9 #6）。
- **3.13/优先级表**（:279-286）：P0=3.1/3.3（发布组主责）、P1=3.9/3.11 等，与本轮主项优先级一致。
- **限流/错误模型交叉核实**（供 3.9 快照提案用）：HTTP 每会话 20 req/s burst 40；桥接全局 30/30 先于门/入队（rpc.py:176-190，README:98 ✓）；429+retryAfterMs details（README:99 ✓）；禁用三法（README:100 ✓）；/health+/events 豁免（README:102 ✓）；TS 429 仅在 32 会话槽全满的流式 POST tools/call（smoke:275-291）；根 README:248 准确、README-DEV:132 不精确。错误模型：工具失败＝HTTP 200+isError:true+structuredContent.error（common.ts:61-71）；envelope 400 -32602/未知方法 404 -32601/坏 JSON 400 -32700（http.ts:248）/内部 500 -32603（:251）/会话 404 -32001/限流 429 -32012；errors.ts 45 码表（:79-125）与 errors.py:20-49 一致；client 仅 BRIDGE_UNAVAILABLE 自动重试一次（client.ts:84-94），CAPTURE/BRIDGE/SEARCH_TIMEOUT retryable:true 但不自动重试；401→BRIDGE_UNAVAILABLE details.bridgeHttpStatus:401（:141-149）。

## 11. 跨切面发现

### 11.1 watchdog 是单点丢弃器（解锁多项修复的钥匙）

watchdog.ts:8-16（7 字段状态）＋:49-65（选择性赋值）把 /health 的 instanceId/buildHash/buildTime/sourcePath（3.1）、policies/rateLimit（3.9）、capabilities（附录 A）全部丢弃。**扩展此一处状态＋赋值，即可同时解锁 3.1/3.9 的审计字段与附录 A 的能力位预检**——建议作为修复任务的第一刀（主管裁决）。

### 11.2 过时文档清单（提案对象，本轮不改）

- 根 README：:262/:566 工具数 11、:270/:282 工具数 10（实际 15）；:132/:436 searchTimeoutMs 建议不可达（附录 C）；审计保留契约缺失（§4.2）。
- README-DEV.md：:15/:104/:106/:115/:130/:132/:133/:141/:182（工具数/冒烟数/限流口径/outputSchema 未挂载——实际已注册+挂载+双形状，registerTools.ts:32/:33/:68，smoke:236-239/:252-253/:269-271）；:3 Docs/ 大小写笔误；准确项 :127/:145/:146/:181 不动。
- 桥接 README（报告项）：:29/:31/:170/:209/:220 计数（§7）；:169/:264 构建身份/版本纪律段**准确**，3.1 对照表提案的落点。
- 架构文档：:5 v0.2.0、:51/:53 过时；§2.4 发现契约准确但缺迁移协议（§8）；:2189 console「可关闭hash」未实现；:2566-2589 样例 16 键与实测一致。
- collect.py:4 审计写入方误标（§4.2，QA/发布组）。

## 12. 修复归属与提案汇总（只提案，不实现；主管裁决后才动源码）

| 提案 | 归属 | 依据 |
| --- | --- | --- |
| watchdog 状态扩展（构建身份＋policies/rateLimit＋capabilities） | **TS（本角色）** | §3.2/§6.2/§11.1 |
| AuditRecord＋auditCall 增补：instanceId/buildHash/buildTime/sourcePath、origin/stage、policy 来源＋桥接门快照、schemaVersion；修复 client 恒缺失 | **TS（本角色）** | §3.3/§5.3/§6.3/§8.3 |
| BridgeDiscoveryFile 增补 stale 三字段并尊重桥接 stale 标记；schemaVersion 不符告警带期望/实际值 | **TS（本角色）** | §8.1(4)/§8.3 |
| 审计保留/轮转/停写告警用户契约；auditDegraded 主动告警；stdio sessionId 口径 | **TS（本角色）＋文档裁决** | §4.3 |
| 根 README/README-DEV 过时计数与 outputSchema 描述更正 | **TS（本角色）** | §7.2(5)/§11.2 |
| 读工具审计覆盖（6 个纯读工具是否落审计）＝隐私/流量裁决 | **主管裁决** | 附录 B |
| /rpc 入口/出口结构化日志（requestId 对齐）；PYTHON_ERROR origin/stage；settings.source 标记 env；policy_snapshot 补 console/source；/health 补 schemaVersion；pixelStreaming 快速失败＋能力位；BFS 预算可配（附录 C 为额外观察，仅存档） | **桥接侧（报告项，非本角色改）** | §4.3/§5.3/§6.3/§8.3/附录 A |
| 桥接 README §5/自检表生成式＋计数统一；README §8 审计↔/health 对照表；架构 §2.4 迁移协议小节 | **发布组/文档（报告项）** | §7.3/§3.3/§8.3 |
| 交付清单附生效权限/限流快照（含 env）；collect.py:4 误标更正；历史来源不可考如实标注 | **发布组/QA** | §6.3/§4.3/§9 |
| 三版本协商回显 ["2025-06-18","2025-03-26","2024-11-05"]、unknown→2025-06-18（arch:923、README-DEV:181；2025-11-25 门控 buildServer.ts:13-16 TODO）；confirm:true 注入；P2 门值；base64Data 前向兼容（viewportCapture.ts:26）；m-3 python 下限移除（pythonExec.ts:65-69）；D1 activateWindow（viewport.ts:35-38） | **主管既有裁决，保持不动** | 前序会话 |

## 13. 证据日志索引（全部保留原始输出，不用总结代替）

### 13.1 本轮新增（feedback-review/logs/，验收口径）

| 文件 | 内容 |
| --- | --- |
| server-cmd31.log | CMD 3.1 原文＋probe SCHEMA_KEYS/KEY_PRESENCE/PLUGINVERSION_DIST＋types/common/buildServer/watchdog/server.py/rpc.py/README/arch 摘录（命令＋完整输出） |
| server-cmd33.log | CMD 3.3 原文＋CDM.log grep（2 行）＋插件 audit grep（0）＋rpc.py logging grep（0）＋server.py:125-149＋audit.ts/logger.ts/http.ts＋README 双 grep＋审计目录清单＋collect.log AUDIT_FILE/PLUGIN_SCAN＋collect.py:1-14 |
| server-cmd37.log | CMD 3.7 原文＋python_exec.py/rpc.py/errors.py/client.ts/common.ts/errors.ts＋probe ERRORCODE_DIST/PYTHON_BY_CODE＋collect.log FAIL_ROW |
| server-cmd39.log | CMD 3.9 原文＋settings.py/rpc.py:74-95/server.py/config.ts/policy.ts/common.ts/watchdog.ts＋Test-Path×2（False）＋部署/仓库 settings.py 双 SHA256（一致）＋部署 grep＋.uplugin＋README:68/:86/:104＋probe2 POLICYMODE/CONFIRMMODE＋collect.log POLICY_DIST/CONFIRM_DIST |
| server-cmd311.log | CMD 3.11 原文＋README:29/:31/:170/:209/:220＋§5 表＋§10.2 表＋rpc.py HANDLERS＋Tests 28/16 计数与名单＋5 脚本 Test-Path（True）＋ue_call_function grep（0）＋根 README/README-DEV 过时行＋collect.log TOOL_DIST/RPCMETHOD_DIST |
| server-schemaversion.log | CMD schema grep（**仅 :77 SCHEMA_KEYS 1 命中，无 schemaVersion 相关命中；583badd5 项C 勘误**）＋discovery.py/server.py/discovery.ts/types.ts 摘录＋TS stale grep＋arch:200-244＋桥接 README schemaVersion grep（0）＋/health＋AuditRecord＋probe_discovery 完整输出（count=0） |
| server-item1-editorstatus.log | **打回项2**：ue_editor_status 全链路——status.ts 全 52 行＋common.ts makeMeta/okResult＋status.py ALL_SECTIONS/_editor_section/handle＋policy.ts/annotations.ts 摘录＋四字段 grep MATCH_COUNT=0×2＋CONCLUSION |
| server-item6-healthchain.log | **打回项1/6**：discovery.ts:1-9/:66-78/:88-109/:133-198 逐字＋schemaVersion grep（MATCH_COUNT=2）＋watchdog.ts 全＋http.ts:254-276＋common.ts＋server.py health_payload:558-577＋CONCLUSION 消费链 |
| server-rework-meta.log | 打回元证据：packages 无 .md COUNT=0×2、最终路径 EXISTS_BEFORE_WRITE=False、两探针重跑 CMD/EXIT=0、50 文件哈希复核尾行（targets=50 scopeOk=50 differences=0 checkedAt=19:02:12） |
| server-rework-gen.log | 打回证据生成器控制台完整输出（REWORK_GEN_EXIT|0） |
| server-audit-probe.log / server-audit-probe2.log | 两探针本轮重跑完整输出（均 exit=0，RECORDS=1003） |
| server-hash-after.txt | 50 文件 SHA256（与 before 同范围同格式；16:20:25 首轮，**打回复核 19:02:12 重生成**，旧版存档 ts-backup/） |
| server-hash-compare.log | 逐文件 SAME×50＋`# targets=50 scopeOk=50 differences=0 checkedAt=2026-11-17T19:02:12.3998332+08:00`＋RESULT 行（打回复核；16:20 版存档 ts-backup/） |
| server-loggen.log | 生成器控制台完整输出（GEN_EXIT|0） |
| server-deliverable-hash.log | dec1385e 备份协议：本报告＋全部 server-* 证据的原件与 ts-backup/ 备份副本 SHA256 对照（含命令与逐项 MATCH 判定）；18:01 节＋20:16 打回节＋**583badd5 节**依次追加（含字节数与 hash_match，互不覆盖） |
| server-itemA-editorstatus.log | **583badd5 项A**：ue_editor_status 暴露面 live 复核——status.ts 全 52 行＋common.ts:25-60＋status.py:23-24/:27-58（detect_capabilities 9 能力键）/:80-95（editor 段 8 键）/:215-237＋watchdog.ts:8-16/:40-75＋server.py:558-577＋四字段 grep MATCH_COUNT=0×3（:280/:286/:292）＋CONCLUSION |
| server-hash-after-583b.txt | 583badd5 复核：50 文件 SHA256（与 before 同范围同格式；19:02 版保留不动） |
| server-hash-compare-583b.log | 583badd5 复核：逐文件 IDENTICAL×50＋`# targets=50 scopeOk=50 differences=0 checkedAt=2026-11-17T20:50:05.7932470+08:00`＋RESULT 行 |
| server-583b-gen.log | 583badd5 证据生成器控制台完整输出（GEN_583B_DONE；哈希复核汇总行） |

备份目录：`feedback-review/ts-backup/`（TS 独有；含本报告副本＋19 个 server-* 证据副本（11 首轮＋4 打回新增＋4 补遗新增：itemA/after-583b/compare-583b/583b-gen；hash-after/compare 为 19:02 复核版，16:20 首轮版同目录存档）＋复用的他人基线 server-hash-before.txt 之副本，原件均未移动/修改；583badd5 交付后共 23 文件）。

### 13.2 前序证据（uemcp/logs/investigation-2026-11-17/，保留）

| 文件 | 内容 |
| --- | --- |
| evidence.log | 1115 行/50 节逐字锚点（policy.ts 节描述行有误记，以 live 锚点为准） |
| hash-before.log / hash-after.log / hash-final.log | 23 目标三时点 SHA256，differences=0 |
| static-counts.log | smoke check( 88/1/87；HANDLERS 16；Tests 28/16/11/1 |
| audit_probe.py / audit_probe.log / audit_probe2.py / audit_probe2.log | 前序探针原件与输出（**打回项6重跑：audit_probe.log:32 / audit_probe2.log:12 追加 EXIT=0**；重跑前版本存档 backup-20261117/） |
| gen_server_logs.ps1 / gen_rework_logs.ps1 / gen_583b.ps1 / probe_discovery.py | 本轮生成器、打回证据生成器、补遗证据生成器与安全探针脚本（原件保留，可复跑） |
| （外部只读引用） | CMD md＋raw/collect.log/collect.py；ZM md:123-127；DefaultWebAPI.ini:6；CDM.log；部署副本 settings.py/discovery.py/.uplugin；feedback-review/logs/server-hash-before.txt（复用基线，未覆盖） |

—— 报告完 ——
