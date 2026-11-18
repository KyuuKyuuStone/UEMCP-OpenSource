# UEMCP 0.1.5 反馈证据核验报告（evidence-check）

- 任务包：`8cbd15e8-b867-4dc9-b9bd-eb124ecd35cf`（反馈证据核验 + 测试覆盖盘点 + 0.1.5 真机冒烟计划）；补充核查任务包：`0faacf99-e3c5-4c44-b33b-33a52501b10e`（CMD 3.8/3.10/3.12 并入，本文 §3A/§8.1 与 smoke-plan §4.1/§4.2 为该任务包交付）
- 作者：测试工程师（QA）；RUN 日期：2026-11-17；主机：ZH-XUXUANWEI
- 纪律：反馈原件、ZMCPP_54_NEW、UEMCP 源码全程只读；未启动 UE 编辑器；未执行真机冒烟；未改任何产品/测试代码。
- 原始日志：`feedback-review/logs/qa-*.log`（本文所有数字均可在对应日志行复核，不凭记忆）。

## 0. 一页结论

1. **CMD 构建发布组反馈：证据可信。** 其统计唯一来源 `raw/collect.log` 复算 **62/62 行逐行一致**（`logs/qa-collect-diff-20261117.log`），交付包 6 文件 SHA256+大小 **6/6 MATCH**（`logs/qa-hash-check-20261117.log`）。13 项问题：**10 属实、3 部分属实、0 证伪**；"部分属实"仅因个别子断言属对方工程运行时、本机不可复核（明细见 §8）。
2. **ZM 项目组反馈：核心属实，但"原始证据环境"已消失。** 反馈包 5 文件内部一致性 82 行/28 条 **0 失配**（`logs/qa-zm-layer1-20261117.log`）；对插件 README/源码引文在本仓库 HEAD（0.1.5）核对 **36 MATCH / 5 行号漂移**（漂移处 token 均在，判"版本漂移"，`logs/qa-zm-layer23-20261117.log`）；业务源码在迁移后目录抽查 3 文件，崩溃模式实锤在位（`FloodCmdHandler.cpp:48` 无判空解引用）。28 条：**21 属实、3 部分属实、4 无法核验、0 证伪**（§9）。
3. **工程侧运行时证据（`Saved/UEMCP/*` 10 个文件）已全部不可复核**——原目录 `ZMCPP_54` 在核验期间被迁移为 `ZMCPP_54_NEW`，运行时目录未随迁（§7 缺失清单）。按主管裁决记"无法核验：原目录迁移、运行时证据未随迁"，不记"反馈不实"。
4. **0.1.5 审计记录仍为 0 条**（VERSION_DIST 只有 0.1.0/0.1.4，`logs/qa-collect-recompute-20261117.log:18`），且 HEAD 的审计 schema（`types.ts:70-88`）依然没有 buildHash/sourcePath/instanceId——**CMD 3.1 的 P0 在 0.1.5 未修**，发布前必须按冒烟计划（另一交付物）补一条真实 0.1.5 审计证据。
5. 本文件与 `smoke-plan-0.1.5.md` 曾于 ~10:50 后从磁盘消失（原因未决），本报告为**依据 logs/ 留档数据的重建版**，事件记录见 §1.2。
6. **补充核查（任务包 0faacf99，12:35）**：CMD 3.10 已由静态推断升级为**动态实测**——按 README:34 口径在 `feedback-review/pkg-sim/` 构造发行包并实跑 16 自检，**15 可跑 EXIT 0 / 1 不可跑（`test_uplugin_metadata.py` EXIT 1，缺 `Tools/stamp_uplugin.py`）**（§8.1，日志 `logs/qa-cmd310-pkg-sim-20261117.log`）；CMD 3.8/3.12 的三列覆盖矩阵与引擎×策略×method 矩阵并入 smoke-plan §4.1/§4.2。反馈原件（两份桌面目录全 16 文件）经哈希清单证明**零写入**、8 个有基线者 0 失配（§3A，日志 `logs/qa-cmd38-coverage-and-zero-write-20261117.log`）。
7. **口径更正（任务包 1f9b9ac3，12:47-12:52）**：smoke-plan §4.2 初版对 CMD 3.12 的引述"5.7 上从未系统跑过"有误——**原件 §3.12 缺真实流量的是 5.4.4**（标题逐字"999 条来自 5.7.4，5.4.4 只有 4 条"，正文 L244"0.1.4/0.1.5 的改动从未在 5.4.4 上跑过"），已按原件校正并勘误留痕；5.4.4 的 0.1.5 真机会话证据被显式排入矩阵（smoke-plan §4.2 run 映射/G-008 + 新闸门 A-2b）；原件 §3.13 的 queuedMs/stage 字段建议以观测点提案 O-QUEUE/O-STAGE 落入 smoke-plan §4.3；同时把"审计真实流量 vs `Tests/smoke-runs/` 历史产物"两类证据的区分写死（禁混用）。依据：原件 L240-L268 逐字读取 + 既有日志，无新断言（日志 `logs/qa-cmd312-verbatim-and-correction-20261117.log`）。

## 0.5 本文怎么读

- **状态口径**：`属实`＝证据在只读复核中复现/复算一致；`部分属实`＝主体属实、个别子断言在本环境无法复核或存在版本漂移；`无法核验`＝所需证据（多为运行时文件）已不存在，既不能证实也不证伪；`证伪`＝复核与断言矛盾（本轮无此类项）。
- **版本差**：ZM/CMD 反馈基于 0.1.4 包，本仓库 HEAD 为 0.1.5（`qa-repo-facts`：uplugin VersionName=0.1.5）；行号不一致而 token 存在时记"版本漂移"，不记"不属实"。
- **ZM 28 条分布**：problem 13 / improvement 8 / positive 7（`logs/qa-zm-layer1-20261117.log:6`），逐条状态见 §9。
- NEW 目录（`C:\UE5_P\5.4\ZMCPP_54_NEW`）归属待用户确认，本次仅按主管批准对 3 个文件做只读抽查；见 §6 免责条。

## 1. 证据环境变更与交付物丢失事件记录

### 1.1 磁盘事实（`logs/qa-env-probe-20261117.log`，RUN 10:51）

| 路径 | 状态 | mtime |
| --- | --- | --- |
| `C:\UE5_P\5.4\ZMCPP_54`（ZM 反馈原始工程根） | **ABSENT**（os error 2） | — |
| `C:\UE5_P\5.4\ZMCPP_54_NEW` | EXISTS（DIR） | 2026-11-17 10:38:16 |
| `ZMCPP_54_NEW\Saved\UEMCP` | **ABSENT** | — |
| `ZMCPP_54_NEW\Saved\Logs` | EXISTS | 2026-11-17 10:30:07 |
| `ZMCPP_54_NEW\Saved\AutoScreenshot.png` | EXISTS | **2026-11-17 10:46:12** |
| `ZMCPP_54_NEW\ak.uproject` | EXISTS | 2026-11-16 23:51:06 |
| 桌面两份反馈原件目录 | EXISTS，未被动过 | 11-16 |

- 首跑抽查（09:24）即报全部 `path not found`（`logs/qa-zm-spotcheck-20261117.log`，EXIT 2，样本 10 条 ≥3）——当时 `ZMCPP_54` 已消失。主管复核确认为**并发迁移**（08:48 前后），非 QA 改动。
- **NEW 目录在核验期间仍被活跃写入**（DefaultGame.ini mtime 10:38:29、AutoScreenshot.png 10:46:12）——存在不明的进行中会话；按主管禁令：零写入、不扩大访问面。
- 我方已抽查 3 文件在 10:51:34 复算哈希 **UNCHANGED**（`logs/qa-new-rehash-20261117.log`），§6 结论不因活跃写入失效；但 NEW 其余内容状态以行为准。

### 1.2 交付物丢失事件记录（主管指示新增）

- 原版 `evidence-check.md`、`smoke-plan-0.1.5.md` 最后确认存在并成功 present 于 **~10:50 前**（最后一次成功编辑为两文档追加 §0.5）。
- 10:52 发现两 .md 从磁盘消失；同目录留存非 QA 创建的**合法变更前哈希基线**（主管已证实：`bridge-hash-before.txt` 09:23、`logs/bridge-hash-before.txt` 09:45、`logs/server-hash.log` 10:12，均为派单配套产物，不是可疑文件）。
- 主管 **11:18 与 12:07** 两次全仓 basename 搜索证实无任何副本；QA 日志与脚本完好。
- 删除行为人/原因**未决**（不排除与 08:48 ZM 目录迁移的未知行为人相关或环境故障），主管已报用户。
- 本版为 12:2x 依据 `logs/` 留档**重建**：逐条引用日志路径，无日志支撑的结论一律不写。重建后已按要求：备份至 `feedback-review/qa-backup/`，原件+备份 SHA256 记入 `logs/qa-deliverable-hash-20261117.log`。

## 2. CMD 组：`raw/collect.log` 统计复算对照

- 复算方式：先审读 `raw/collect.py`（10049B，与 sha256.txt 记录一致）确认**只读**（读 `~/.uemcp/audit/*.jsonl` 与插件包目录，仅 print），再以 `C:\Python314\python.exe` 在 cmd 字节级重定向下重跑（`PYTHONIOENCODING=utf-8`；首次经 PowerShell 管道出现 GBK 重编码乱码，已弃用该通道——伪影记录见 `logs/qa-collect-recompute-20261117.log` 头注）。
- 结论：**`DIFF original-body=62 recomputed-body=62` / `RESULT: IDENTICAL`**（`logs/qa-collect-diff-20261117.log`）。即反馈引用的全部统计行在本机此刻仍可从原始审计数据复现。
- 关键行对照（复算输出 ←→ 反馈引用，行号指 `logs/qa-collect-recompute-20261117.log`）：

| 统计 | 复算值 | 反馈引用处 | 判定 |
| --- | --- | --- | --- |
| 审计文件 | 4 个，最后 mtime 2026-11-09 12:53:41（:9-12） | 3.3 | 一致 |
| 总量 | requests=1003 failed=31 fail_rate=3.09%（:15） | 3.2 | 一致 |
| 版本分布 | {"0.1.0":890, "0.1.4":113}，**无 0.1.5**（:18） | 3.2 | 一致 |
| 版本失败率 | 0.1.0=1.57%，0.1.4=15.04%（:66-67） | 3.2 | 一致 |
| 工具分布 | python.exec 952 / capture 30 / call 12 / pie 7 / actor_edit 2（:17） | 3.6 | 一致（94.9%） |
| method 分布 | 仅 5 个 method（:19） | 3.8 | 一致 |
| capture 失败 | 30 次 7 败 23.3%，max 45009ms（:33,:37） | 3.5 | 一致 |
| 引擎分布 | 5.7.4=999，5.4.4=4（:24） | 3.12 | 一致 |
| 策略分布 | full 963 / standard 40；confirm policy 952（:21,:23） | 3.9 | 一致 |
| 插件扫描 | files_scanned=57, mentioning_audit=0（:68） | 3.3 | 一致（扫描对象为对方 5.7 包） |
| 审计 schema | SCHEMA_KEYS 17 键，无 buildHash/sourcePath/instanceId/stage/queuedMs（:14） | 3.1/3.7/3.13 | 一致 |

## 3. CMD 组：md/docx 与交付包哈希核对

数据源 `raw/sha256.txt` 六行；复算 `Get-FileHash SHA256`＋字节大小，输出 `logs/qa-hash-check-20261117.log`：**6/6 `HASH_MATCH_SIZE_MATCH`**。

| 文件 | 大小(记录=实测) | SHA256（前 16） |
| --- | --- | --- |
| `UEMCP插件使用问题与改进建议.md` | 24386 ✓ | cce3bbb9518cd01c ✓ |
| `UEMCP插件使用问题与改进建议.docx` | 49305 ✓ | 2850d049d8d7ea95 ✓ |
| `raw\collect.log` | 4957 ✓ | b8924276f1c6048d ✓ |
| `raw\collect.py` | 10049 ✓ | 8783199da140dc0b ✓ |
| `make_docx.py` | 6010 ✓ | f78f447badd7f0dd ✓ |
| `verify_docx.py` | 2721 ✓ | d89431a7b0880c98 ✓ |

sha256.txt 自引用行按规则豁免（其自身哈希 ecfaac36… 已记录于日志尾行）。md 与 docx 内容一致性：本次仅核**哈希与大小**（原件声明"逐段生成，内容一致"，未做全文 diff——记入未决 U-6）。

## 3A. 反馈原件零写入证明（任务包 0faacf99 验收项）

方法：`qa_cmd38_manifest.py` PART2 对桌面两份反馈目录**递归只读**列清单（16 文件全量），每文件记 size/mtime/SHA256；与先前留档基线比对（CMD 6 文件←`logs/qa-hash-check-20261117.log` 的 recorded_sha 字段动态解析；ZM 两 .md←`logs/qa-zm-layer1-20261117.log` 的 1c9bf345…/e1d0e489…）。完整输出：`logs/qa-cmd38-coverage-and-zero-write-20261117.log`（PART2 段，RUN 12:35:55）。

结论：`PART2_SUMMARY files=16 baseline_mismatch=0`；**16/16 文件 mtime 均标注 `PRE_QA_READ`**（最晚 2026-11-16 16:57:36，早于 QA 首次读取 09:24）。

| 组 | 文件数 | 基线比对 | 无基线文件（本次清单即首次基线） |
| --- | --- | --- | --- |
| CMD `UEMCP插件使用问题与改进建议.md/.docx` + `raw/` 5 件 | 7 | md/docx/collect.py/collect.log/make_docx.py/verify_docx.py **6/6 BASELINE_MATCH**；sha256.txt 自引用豁免（ecfaac36… 已记录） | — |
| ZM `UEMCP使用反馈.md`/`证据索引.md` | 2 | **2/2 BASELINE_MATCH** | — |
| ZM `00_checks.txt` + `UEMCP_AI_REVIEW/` 6 件 | 7 | 首建基线（mtime 11-12/11-16 全部早于 QA 接触） | 7 文件 SHA256 全串已入日志 |

- 佐证：QA 全程对 `C:\Users\Administrator\Desktop\UEMCP遇到的问题\` 仅执行读与哈希（本任务包禁止项之一）；父目录 "UEMCP遇到的问题" mtime 2026-11-17 09:14:56 为**放置/搬移事件**（早于派单，主管侧），非文件级修改。

## 4. ZM 层①：反馈包内部一致性（桌面包 5 文件互核）

日志 `logs/qa-zm-layer1-20261117.log`（脚本 `qa_zm_layer1_consistency.py`，只读），EXIT 0：

| 检查 | 结果 | 状态 |
| --- | --- | --- |
| `证据索引.md` 行数 | rows=82 = 期望 82 | 属实 |
| 索引 ↔ `00_checks.txt` | 82 行逐指针比对 mismatch=0 | 属实 |
| `findings.json` 计数 | total=28 {problem:13, improvement:8, positive:7} | 属实 |
| findings ↔ `05_evidence_check.txt` | rows=28 mismatch=0 | 属实 |
| 正文 ID 覆盖 | PROB/IMP 正文引用 missing=NONE；POS 7/7（【POS-00x】标题制） | 属实 |
| 桌面包 SHA256 双份（工作区==桌面） | `UEMCP使用反馈.md` 1C9BF345…、`证据索引.md` E1D0E489… 双 MATCH | 属实 |
| 运行时证据路径 | 索引引用 `Saved/UEMCP/*` distinct=10，桌面包内无留档 | 见 §7（无法核验） |

## 5. ZM 层②：README/插件源码引文对照本仓库 HEAD（0.1.5）

日志 `logs/qa-zm-layer23-20261117.log`（41 条 L2 行），汇总 **MATCH 36 / TOKEN_DRIFT 5**；`REPO_HEAD_PLUGINVERSION|0.1.5`；本仓库 README sha256=8dbec1cb…（267 行）。

5 条漂移明细（**token 在 HEAD 存在、行号位移＝版本漂移，不判不属实**）：

| 证据 ID | 对方引文 | HEAD 实际 |
| --- | --- | --- |
| E-036 | viewport.py:598 `headless` | [610, 614] |
| E-037 | objects.py:245 `except TypeError` | [479, 493] |
| E-045 | objects.py:213 `_to_snake` | [39, 55, 425] |
| E-061 | objects.py:251 `expectedParamCount` | [485, 510] |
| E-062 | objects.py:218 `blacklisted_name` | [434] |

其余 36 条（README 的端口/回环/权限门/限流/429/不能中断/工具表，及 rpc.py try_acquire:178、retryAfterMs:188、assets/actors/materials/levels/errors/viewport 各行）**行号+token 双匹配**——ZM 对插件源码的引用纪律良好。

## 6. ZM 层③：ZMCPP_54_NEW 业务源码抽查（迁移后环境，≤3 文件，只读）

**免责条**：以下为**迁移后目录** `ZMCPP_54_NEW`（ak.uproject），非反馈时点原始证据环境；引文不符记"迁移后内容已变更"，不记"反馈不实"（主管 Q1 裁决）。

| # | 文件（sha256 / 行数 / 读取时间） | 抽查点 | 判定 |
| --- | --- | --- | --- |
| 1 | `Plugins/ZS_WebAPI/.../FloodCmdHandler.cpp`（d4f58853… / 201 / 10:40:46） | `:48 FloodReturnInfo.PeakModelId = FloodController.Value->GetPeakModelId();` **无判空解引用实锤在位**（=PROB-001/E-025）；`AddUniqueDynamic` 引 :86→实际 :87、`SendMessage(ResponseMsg)` 引 :96→实际 :97（±1 行位移）；上下文（`logs/qa-zm-layer3-getlist-context-20261117.log`）：Contains 门在 :66，:93-95 else 置 error 后 **:97 无条件 SendMessage**（=PROB-009"不检查 Open 结果"结构成立） | 属实（迁移后仍复现；10:51:34 复算 UNCHANGED） |
| 2 | `Plugins/ZS_Flood/.../FloodPeak.cpp`（b5dc7ecf… / 46 / 10:40:46） | `:34 SetCameraFollow_Implementation` 签名行 MATCH，但**函数体非空**：`:36 CurCameraControl.State = IsFollow;`（`logs/qa-zm-layer3-floodpeak-body-20261117.log`）——PROB-011"空实现"与当前内容矛盾 | **无法核验（迁移后内容已变更）**：反馈时点的空实现无法在当前文件证实 |
| 3 | `Config/DefaultGame.ini`（c5b56128… / 109 / 10:40:46） | `:98 +DirectoriesToAlwaysCook=(Path="/Game/Sequence")` 行号+内容双 MATCH（=PROB-012/E-047 的"cook 条目已存在"半句） | 属实（打包是否真丢序列仍属对方"未验证"自注） |

## 7. ZM 工程运行时证据：不可复核 + 缺失清单

原工程根 `ZMCPP_54` 已消失、`ZMCPP_54_NEW\Saved\UEMCP` 不存在（§1.1），且桌面包未内嵌这 10 个运行时文件 → **统一判"无法核验：原目录迁移、运行时证据未随迁"**（清单源 `logs/qa-zm-layer1-20261117.log:13-22`）：

`Saved/UEMCP/bridge-health.json`、`Saved/UEMCP/floodpeak/bugs.md`、`Saved/UEMCP/floodpeak/session.log`、`Saved/UEMCP/spillwayfix/args.json`、`Saved/UEMCP/spillwayfix/evidence/snapshot_composition.json`、`Saved/UEMCP/spillwayfix/pixel_diff_cross.json`、`Saved/UEMCP/spillwayfix/py/apply_clean_params.py`、`Saved/UEMCP/spillwayfix/py/play_seq_direct.py`、`Saved/UEMCP/spillwayfix/py/snapshot.py`、`Saved/UEMCP/svn/06_notes.txt`

影响面：仅依赖这类证据的断言（如 E-007 实测端口 18790、E-015 像素差 8.004、E-023 崩溃日志行、E-034 探针 valueIsNone、E-078/E-081 svn 状态、PROB-008/013 的运行时支撑）不能证实也不能证伪；其中崩溃**代码路径**已被 §6 层③ 独立证实。

## 8. CMD 13 项逐条核验状态

（每项"依据"栏 = 复算行/固化日志行；运行时侧引文一律单列）

| # | 主题 | 状态 | 关键依据 |
| --- | --- | --- | --- |
| 3.1 P0 | 审计缺 buildHash/sourcePath/instanceId | **属实（HEAD 0.1.5 仍未修）** | SCHEMA_KEYS 17 键无此三字段（recompute:14）；`types.ts:70-88` AuditRecord 字段集（`qa-repo-facts`）；/health 已有三字段（`server.py:567-570`）→ 数据源在、未入审计 |
| 3.2 P0 | 0.1.5 真实审计 0 条；0.1.4 失败率 15.04% | **属实** | PLUGINVERSION_DIST 无 0.1.5（recompute:18）；VERSION_FAIL_ROW 两行（:66-67）逐值一致 |
| 3.3 P0 | 审计写入方/轮转无文档；桥接无请求级日志 | **部分属实** | 统计面：AUDIT_FILES=4、最后 mtime（:9-12）、PLUGIN_SCAN mentioning_audit=0（:68）一致；代码面：桥接仅 `_log/_log_error` 生命周期/错误打印、rpc.py 无请求级日志（`qa-repo-facts2` SERVER 区）；轮转**有码内约定**（audit.ts:5「启动时清理 30 天前」）但文档未写→"无文档"属实；`CDM.log:1661/3472` 属对方工程（不可复核） |
| 3.4 P1 | timeoutMs 不生效、timedOut 恒 false | **属实** | HEAD：python_exec.py:37 `get_int(...timeoutMs...)` 返回值丢弃、:93 `"timedOut": False` 硬编码（`qa-repo-facts2`）；rpc.py:132 `timeoutMs+5000`、:135 clamp 120000；README:78 `requestTimeoutMs: 30000`（本文件 §8 前 read 复核）——与 rpc.py 上限 120s 的落差表述成立；collect 侧 DURATION/FAIL_ROW 复算一致 |
| 3.5 P1 | capture 失败率 23.3% + PixelStreaming 路径 | **部分属实** | 统计面一致（PER_TOOL_ROW 30/7/23.3%/45009，recompute:33）；代码面 HEAD viewport.py 有 headless fail-fast [610-614]、PixelStreaming 注释/提示 [688,690,754,757]、force_game_view [691,694,748]（`qa-repo-facts2`）——与对方引 688-695/752-758 基本吻合（±2 行）；`Config/DefaultWebAPI.ini:6` 属对方工程（不可复核） |
| 3.6 P2 | 94.9% 流量压 python.exec | **属实** | TOOL_DIST 952+51=1003（recompute:17,:64）；HEAD 仅校验 code/mode/resultExpression/timeoutMs/captureOutput（python_exec.py:30-38） |
| 3.7 P2 | PYTHON_ERROR 混吞调用方/插件错误 | **属实** | ERRORCODE_DIST PYTHON_ERROR=20 一致（:16）；HEAD rpc.py:101-116 统一映射无 origin/stage（`qa-repo-facts2`）；SCHEMA_KEYS 无 stage 字段 |
| 3.8 P2 | 真实流量仅覆盖 16 method 中 5 个 | **属实** | RPCMETHOD_DIST 5 个（:19）；HEAD rpc.py HANDLERS 注册 16 个（`qa-repo-facts` 45-70）；README §5 表 13 行（L122-134，本文件 §8 前复核）缺 object.reflect/call、log.query。**补查（0faacf99）**：静态扫描证"审计=0 且离线自检未引用且不在历史 8 只读"的方法为 console.command、blueprint.query 两个（`logs/qa-cmd38-coverage-and-zero-write-20261117.log` PART1）；三列矩阵成品见 smoke-plan §4.1 |
| 3.9 P1 | 生效权限配置不可复现 | **部分属实** | POLICY_DIST/CONFIRM_DIST 复算一致（:21,:23）；/health 有 `policies` 快照字段（server.py:576）；`bridge-settings.json 缺失` 属对方工程（不可复核）；"环境变量开启未验证"对方已自注 |
| 3.10 P1 | 发行包不含 Tools/ 与 *.ps1 | **属实（已动态实测强化）** | README:30（Tools 仅源码仓库）、README:34（包内容清单）、README:245-247（ps1 不随包）（`qa-repo-facts2`/`qa-repo-facts`）；**补查（0faacf99）**：按 README:34 口径构造发行包模拟 `feedback-review/pkg-sim/` 实跑 16 自检＝**15 EXIT 0 / 1 EXIT 1**（唯 `test_uplugin_metadata.py`，失败体 `FAIL: missing …\pkg-sim\UEMCPBridge\Tools\stamp_uplugin.py`；同脚本回源仓复跑 EXIT 0 排除环境因素）→ 逐脚本清单见 §8.1，日志 `logs/qa-cmd310-pkg-sim-20261117.log` + `logs/qa-cmd310-crosscheck-20261117.log` |
| 3.11 P1 | 文档数字互相矛盾 | **属实** | README L29"12 个 RPC method"、§5 表 13 行 vs rpc.py 实际 16；L170"14 个自检"、L209/L220/L31"11 个"vs Tests 目录 `^(check_|test_)` 实际 **16** 个（`qa-repo-facts` TESTS_DIR + 本文件 §8 前复核）——四处口径 11/11/14/16 全中 |
| 3.12 P2 | 5.4.4 真实流量仅 4 条（0.1.0 期） | **属实** | 标题逐字："UE 5.4.4 的兼容性缺真实流量：999 条来自 5.7.4，5.4.4 只有 4 条"（原件 L240）；缺流量方=**5.4.4**，5.7.4 恰是流量大户；正文 L244"0.1.4/0.1.5 的改动从未在 5.4.4 上跑过"。UEVERSION_DIST 999/4（:24）；PER_DAY_DETAIL 2026-10-20 = 3 capture + 1 actor_edit（:27）。**补查（0faacf99）**：所要求的 5.4/5.7 × readonly/standard/full × 16 method 冒烟矩阵已补入 smoke-plan §4.2。**勘误（1f9b9ac3）**：该节初版曾误引"5.7 上从未系统跑过"（方向相反、非原件表述），已按原件 L240/L244/L251 重写并加 A-2b 闸门；5.4.4 真实会话证据被显式排入矩阵 |
| 3.13 P2 | 单队列单 pending 静默队头阻塞 | **属实** | HEAD dispatcher.py:98-103 pending 早返回、errors.py:28 BRIDGE_BUSY 存在（`qa-repo-facts2`）；ERRORCODE_DIST 无 BRIDGE_BUSY（:16）；DURATION 45009ms、审计无 queuedMs（:14,:37）。原件建议"审计补 `queuedMs`/`stage` 字段"（L266，属开发）；**冒烟侧旁证观测点提案 O-QUEUE/O-STAGE 已入 smoke-plan §4.3（1f9b9ac3）** |

**分布（按上表逐行数）：属实 10（3.1/3.2/3.4/3.6/3.7/3.8/3.10/3.11/3.12/3.13）/ 部分属实 3（3.3/3.5/3.9，个别子断言属对方工程运行时不可复核）/ 证伪 0。**

## 8.1 CMD 3.10 补充：发行包内自检"可跑/不可跑"清单（实测，任务包 0faacf99）

- **场地**：`feedback-review/pkg-sim/UEMCPBridge/`——严格按 README:34 的发行包（zip）口径构造：`UEMCPBridge.uplugin` + `Content/`（含 `Content/Python/uemcp_bridge/**`）+ `README.md` + `COMPAT-UE57.md` + `Tests/*.py`（16 自检 + probe/smoke 等 28 py）+ `Tests/SMOKE-REAL-ENGINE.md`；**不含** `Tools/`、`Tests/*.ps1`、`smoke-runs/`。抽样哈希证明副本与源仓逐字节一致（uplugin、rpc.py same=True，见 pkg-sim 构造命令输出留档）。
- **执行**：与源仓基线同一解释器（`C:\Program Files\Epic Games\UE_5.4\...\python.exe`，3.11.8），逐脚本跑，完整输出 `logs/qa-cmd310-pkg-sim-20261117.log`。

| # | 自检脚本 | pkg-sim EXIT | 源仓 EXIT（基线 `logs/qa-offline-regression-…`） | 包内判定 | 依赖说明 |
| --- | --- | --- | --- | --- | --- |
| 1 | check_error_codes.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 2 | check_handler_names.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 3 | check_plugin_version.py | 0 | 0 | ✅ 可跑 | .uplugin+Content/ |
| 4 | test_bridge_timeout_http.py | 0 | 0 | ✅ 可跑 | 本地起服务，仅 Content/ |
| 5 | test_class_path_resolution.py | 0 | 0 | ✅ 可跑 | stub，仅 Content/ |
| 6 | test_dependency_options.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 7 | test_discovery_lifecycle.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 8 | test_log_query.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 9 | test_object_call.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 10 | test_pie_control.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 11 | test_port_fallback.py | 0 | 0 | ✅ 可跑 | 本地端口，仅 Content/ |
| 12 | test_python_error_mapping.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 13 | test_rate_limit.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 14 | test_serialization.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |
| 15 | **test_uplugin_metadata.py** | **1** | 0 | ❌ **包内不可跑** | 读 `../Tools/stamp_uplugin.py`（README:34 自认："第 10 项…请在源码检出中运行"）；失败体逐字：`FAIL: missing …pkg-sim\UEMCPBridge\Tools\stamp_uplugin.py`；同脚本源仓复跑 EXIT 0（`logs/qa-cmd310-crosscheck-20261117.log`）→ 差异因素=Tools/ 缺失，非环境 |
| 16 | test_viewport_capture.py | 0 | 0 | ✅ 可跑 | 仅 Content/ |

**汇总：包内可跑 15/16；不可跑 1（test_uplugin_metadata.py，属"预期不可跑"——README 已自我声明该依赖，CMD 3.10 的"至少 1 个必然失败"实测坐实且仅 1 个）。** 附带发现：README:34 声明包内含 `LICENSE`，但 `UEMCPBridge/` 目录树下无 LICENSE 文件（仅仓库根 `C:\UE5_P\5.4\UEMCP\LICENSE` 存在）→ zip 是否真含 LICENSE 取决于不在仓内的打包脚本，包内侧无法核验（新增未决 U-9；见 crosscheck 日志 LICENSE 段）。

**替代证据建议（仅提案，不改打包/发布流程）**：
1. **两态清单固化**：发布说明把自检拆为"包内 15/15（解包即可跑，README:34 末句口径）+ 源码检出 16/16"两态，各自附 exit 记录——替代当前"11/11 实跑"单口径（其不可复核性见 U-3）。
2. **打包产物清单留档**：每次出 zip 附 `sha256manifest`（含 LICENSE 有无），QA 冒烟前的包内自检以该清单为验收输入（对应 §5 冒烟证据清单第 4 项同款做法）。
3. **自检脚本自带场地探测**：提案 test_uplugin_metadata.py 在检测不到 `Tools/` 时输出 `SKIP(需源码检出)` 且 exit 0 或 3，使"包内跑 16 个"不再出现红叉——属开发侧改动提案，本 QA 不动代码。

## 9. ZM 28 条逐条核验状态

（id 与断言文本源 `UEMCP_AI_REVIEW/findings.json` 原文；证据类型：层②=插件源码/README 对照本仓 HEAD，层③=NEW 业务源码，运行时=`Saved/UEMCP/*` 已失）

| ID | 断言（摘要） | 判定 | 依据 |
| --- | --- | --- | --- |
| PROB-001 P0 | getList 空指针解引用崩溃 | **属实** | 层③ FloodCmdHandler.cpp:48 实锤（layer23:51；上下文 getlist-context.log） |
| PROB-002 P0 | record 在未验证控制器指针上绑委托 | **属实** | 层③ `AddUniqueDynamic` 在 :87（引 :86，±1 位移；layer23:52） |
| PROB-003 P0 | offset/offsetReset/cameraFollow/close 重复同一未判空模式 | **属实** | 层③ `SendMessage` 五处 [97,119,141,163,185] 与 :110/:132/:154/:176 模式对应（layer23:53） |
| PROB-004 P1 | headless 编辑器 capture 直接失败无回退 | **部分属实** | 层② headless fail-fast 存在（token 598→HEAD 610-614，版本漂移）；"无回退"代码可见，但属设计选择（layer23:20 + facts2） |
| PROB-005 P2 | BFS 预算硬编码 | **属实** | 层② assets.py:19 `_MAX_BFS_NODES` MATCH（layer23:24） |
| PROB-006 P1 | 体内 TypeError 被改判 INVALID_ARGUMENT | **部分属实** | 层② `except TypeError` 存在但行号漂移（245→479/493）；0.1.5 行为需按 HEAD 代码细读，反馈基于 0.1.4（layer23:21） |
| PROB-007 P2 | 黑名单只按 snake 名匹配 | **部分属实** | 层② `_to_snake` 漂移（213→39/55/425）；blacklist token 在 434（layer23:25,39） |
| PROB-008 P0 | 场景 FloodControllers 键到空控制器 | **无法核验** | 运行时证据 session.log 缺失（§7）；代码侧崩溃模式已由 PROB-001 独立证实 |
| PROB-009 P1 | record 无条件回包不查 Open 结果 | **属实** | 层③ :66 Contains 门内、:93-95 else 后 :97 无条件 SendMessage（getlist-context.log） |
| PROB-010 P1 | spillway 缺序列无回退 | **无法核验** | 属 `Source/ak/` 主工程源码，超出批准访问面（3 文件上限，主管 Q2） |
| PROB-011 P2 | SetCameraFollow_Implementation 空实现 | **无法核验（迁移后内容已变更）** | 现体 `:36 CurCameraControl.State = IsFollow;` 非空（floodpeak-body.log）；不能证实也不能证伪反馈时点 |
| PROB-012 P2 | cook 已含 /Game/Sequence，丢包待实测 | **属实**（其"已存在"半句） | 层③ DefaultGame.ini:98 双 MATCH（layer23:57）；打包实测对方自注未验证 |
| PROB-013 P2 | getList 只回 name+modelId | **无法核验** | 运行时 bugs.md 缺失（§7）；代码侧 :47-49 确仅填 PeakModelName/PeakModelId/Duration（getlist-context.log:8-10，作旁证） |
| IMP-001 | 全局限流→建议 per-client 桶 | **属实** | 层② rpc.py:178 `try_acquire` MATCH；HEAD test_rate_limit 实跑绿（offline:109-116） |
| IMP-002 | truncated→建议 nextOffset | **属实** | 层② assets.py:321 MATCH |
| IMP-003 | 依赖选项引擎矩阵需文档 | **属实** | 层② assets.py:111 MATCH；offline test_dependency_options 3 种降级路径绿（offline:30-35） |
| IMP-004 | 相机模式固定集→建议 transform | **属实** | 层② viewport.py:36 `_CAMERA_MODES` MATCH |
| IMP-005 | dryRun→建议 diff 摘要 | **属实** | 层② actors.py:746 MATCH |
| IMP-006 | create_instance 路径唯一性 | **属实** | 层② materials.py:16 MATCH |
| IMP-007 | save_all 进度上报 | **属实** | 层② levels.py:19 MATCH |
| IMP-008 | retryable 外露 | **属实** | 层② errors.py:15 ERROR_TABLE MATCH |
| POS-001 | 错误码单表映射 | **属实** | errors.py:15/19 MATCH（layer23:35-36）；offline check_error_codes PASS |
| POS-002 | RATE_LIMITED 带 retryAfterMs | **属实** | rpc.py:188 MATCH（:37）；offline HTTP_LIMIT 429 序列绿 |
| POS-003 | call TypeError 带期望/实际参数数 | **属实（行号漂移）** | expectedParamCount 在 HEAD [485,510]（:38） |
| POS-004 | 黑名单拒绝回显 name/blocked/reason | **属实（行号漂移）** | blacklisted_name 在 HEAD [434]（:39） |
| POS-005 | actor.edit 按动作白名单 | **属实** | actors.py:369 OP_ALLOWED_KEYS MATCH（:40） |
| POS-006 | level.control 读写动作分离 | **属实** | levels.py:18 READ_ACTIONS MATCH（:41）；rpc.py:31-40 WRITE_METHODS/WRITE_ACTIONS 结构旁证（facts2） |
| POS-007 | 依赖选项逐旗降级+告警 | **属实** | assets.py:95 MATCH（:42） |

**分布：属实 21 / 部分属实 3（PROB-004/006/007）/ 无法核验 4（PROB-008/010/011/013）/ 证伪 0。**

## 10. 未决清单

| # | 事项 | 状态 |
| --- | --- | --- |
| U-1 | ZMCPP_54_NEW 归属与用途（08:48 迁移、10:30-10:46 活跃写入、08:46 编辑器会话行为人不明） | 待用户确认；已禁止扩大访问面 |
| U-2 | 两份 .md 交付物 10:50-10:52 间被删除的行为人/原因 | 未决，主管已报用户（§1.2） |
| U-3 | README §10.2"已实跑 11/11 exit 0"的当时环境证据（桌面 CMD 包无留档） | 无法核验（不记证伪，主管裁决） |
| U-4 | ZM 运行时 10 文件与 `CDM.log` 行号引用 | 无法核验（§7） |
| U-5 | `source/ak/CustomDomainCmdHandler.cpp:255`（PROB-010） | 超出批准访问面 |
| U-6 | md↔docx 全文一致性（仅核了双哈希+对方自述） | 未做（可补 python-docx 抽段比对，非验收必需） |
| U-7 | auditDegraded（连续 3 次失败）与 30 天清理的**运行时**行为 | 仅码内证据（audit.ts:4-5,15,27-29），无真机证据 |
| U-8 | 主管 glob 曾报 NEW 内未见 `Plugins\UEMCPBridge` 等——QA 实测 `README.md` 存在（env-probe） | 差异未解释，仅记录 |
| U-9 | README:34 称发行包含 `LICENSE`，但 `UEMCPBridge/` 下无 LICENSE 文件（仅仓库根存在）；zip 实际是否含之取决于不在仓内的打包脚本 | 包内侧无法核验（`logs/qa-cmd310-crosscheck-20261117.log` + `qa-cmd310-pkgsim-build-20261117.log`）；已给替代证据建议（§8.1-2） |

## 11. 日志索引（`feedback-review/logs/`，全部保留原始输出）

| 日志 | 内容 |
| --- | --- |
| `qa-collect-recompute-20261117.log`（+`-rawstdout-…bin`） | collect.py 复算全文 71 行（EXIT 0） |
| `qa-collect-diff-20261117.log` | 62/62 IDENTICAL 结论 |
| `qa-hash-check-20261117.log` | 6 文件哈希+大小 6/6 MATCH |
| `qa-zm-spotcheck-20261117.log`（+raw.bin） | 首跑 10 样本全 path-not-found（EXIT 2，环境变更发现记录） |
| `qa-zm-layer1-20261117.log`（+raw.bin） | 层① 一致性全 CONSISTENT + 运行时 10 缺失清单 |
| `qa-zm-layer23-20261117.log`（+raw.bin） | 层② 41 条（36M/5D）+ 层③ 3 文件（SHA+时间戳） |
| `qa-zm-layer3-floodpeak-body-20261117.log` / `-getlist-context-…` | 层③ 补充上下文段 |
| `qa-offline-regression-20261117.log`（+raw.bin） | 16 个离线自检于 UE5.4 Py3.11.8 实跑 **16/16 EXIT 0** |
| `qa-env-probe-20261117.log` | 环境变更磁盘事实（§1.1 表源） |
| `qa-new-rehash-20261117.log` | NEW 3 文件 10:51 复算 UNCHANGED |
| `qa-repo-facts-20261117.log` / `qa-repo-facts2-20261117.log` | 仓内代码/README 事实固化（rpc 注册 16、/health 字段、AuditRecord、audit.ts 约定、python_exec timeoutMs、dispatcher pending、README 各口径行） |
| `qa-deliverable-hash-20261117.log` | 重建交付物原件+备份 SHA256（12:26 首轮；后续追加见同文件后段） |
| `qa-cmd310-pkgsim-build-20261117.log` | pkg-sim 发行包模拟构造清单+复制一致性抽样（0faacf99） |
| `qa-cmd310-pkg-sim-20261117.log` | 16 自检在 pkg-sim 内实跑全文：**15×EXIT 0 / 1×EXIT 1**（0faacf99） |
| `qa-cmd310-crosscheck-20261117.log` | 失败体逐字 + 同脚本源仓复跑 EXIT 0 对拍 + LICENSE 探测（0faacf99） |
| `qa-cmd38-coverage-and-zero-write-20261117.log` | PART1 三列覆盖静态扫描（all3_empty=console.command/blueprint.query）；PART2 反馈原件 16 文件零写入清单（mismatch=0）（0faacf99） |
| `qa-cmd312-verbatim-and-correction-20261117.log` | 1f9b9ac3：桌面原件 §3.12/§3.13 逐字读取（L240-268，只读）+ smoke-plan 勘误后 grep 复核（旧口径仅存于勘误引文；A-2b/§4.3 在位） |

（`bridge-hash-before.txt`、`logs/bridge-hash-before.txt`、`logs/server-hash.log` 为**他人合法**变更前基线，非 QA 产物，见 §1.2。）
