# 桥接侧反馈逐条只读核查报告（ZM/CMD 两组反馈 vs 0.1.5 源码）

- 任务：主管任务 `a5707824-ee76-4bce-a95d-c6ce4e36daa4`「桥接侧反馈逐条只读核查（ZM/CMD 两组反馈 vs 0.1.5 源码）」
- 执行角色：UE桥接开发（本任务**严格只读**：零代码修改、不启动 UE 编辑器、反馈原始目录只读、未执行任何黑名单绕过脚本）
- 核查日期：2026-11-17（哈希基线 09:23/09:45，核查完成于当日 18:00 截止时间之前）
- 判定口径：以**当前 0.1.5 源码**为准（`settings.py:12 PLUGIN_VERSION="0.1.5"`、`UEMCPBridge.uplugin:4 VersionName "0.1.5"`）。反馈文档的行号锚点多来自 0.1.4/其他检出，本报告一律给出 0.1.5 实际 file:line，偏移见附录 F。
- 条目口径：按主管裁定，权威清单为 **12 项 + IMP 速查附录**；原任务包第 1–4 项（objectPath/setLocation/“300字符20行截断”/PIE errorCode）系派单编号错误，已撤回，不在本报告范围。实际截断上限为 1 MiB（`python_exec.py:17`），非 300/20。
- 裁决更正（任务 `49fb81d6-88d7-4fca-934c-1322d16e6389`，2026-11-17）：按主管裁决更正要求，以**原件与 HEAD 代码**为准复核两处——①第 7 组限流默认值：HEAD `settings.py:23 DEFAULT_RATE_LIMIT_ENABLED = True`（默认开启）；`rateLimitEnabled=false`/`rateLimitPerSecond=0` 是**配置关闭开关，不是代码默认值**（项 7 含 :23-25 逐字摘录与 false/0 指向核实）；②第 5 组锚点：改用 **CMD §3.13 原件锚点**（CMD-md:257/:262-264），逐一对照 HEAD 命中（项 5 含锚点对照表）。其余 12 项、附录与范围化哈希对要求不变；更正后重跑 scoped 哈希对仍 74/74 diff=0（`logs\bridge-hash-compare-correction.log`）。取证日志：`logs\bridge-correction-ratelimit.log`、`logs\bridge-correction-item05-anchors.log`。

## 0. 方法、路径缩写与只读纪律

**核查方法**：逐条阅读反馈原文 → 定位 0.1.5 源码对应实现 → 每项以 pwsh `Select-String` 取证，命令与完整输出重定向至 `feedback-review/logs/bridge-*.log`（原始日志全部保留，未用总结替代）→ 辅证用 read/grep/glob → 第 12 项另做离线 Python 空值序列化测试（不触碰 unreal、不启动编辑器）。

**路径缩写**（根目录 `C:\UE5_P\5.4\UEMCP`）：
| 缩写 | 实际路径 |
|---|---|
| PY | `UEMCPBridge\Content\Python\uemcp_bridge\`（0.1.5 插件源码，23 个 .py） |
| README | `UEMCPBridge\README.md`（267 行） |
| uplugin | `UEMCPBridge\UEMCPBridge.uplugin` |
| Tests | `UEMCPBridge\Tests\`（32 个文件，其中 16 个 `^(check_|test_)` 自检） |
| TS-server / TS-shared | `uemcp\packages\server\src\` / `uemcp\packages\shared\src\`（MCP 服务端，非桥接插件） |
| ZM-md | `C:\Users\Administrator\Desktop\UEMCP遇到的问题\ZM项目组——UEMCP_使用反馈\UEMCP使用反馈.md`（295 行，只读） |
| CMD-md | `C:\Users\Administrator\Desktop\UEMCP遇到的问题\CMD构建发布组_UEMCP反馈\UEMCP插件使用问题与改进建议.md`（323 行，只读） |
| logs | `feedback-review\logs\`（本报告全部原始日志） |

**只读纪律证明（哈希对）**：
- 验收对（scoped）：`logs\bridge-hash-before.txt` vs `logs\bridge-hash-after.txt`，范围 = `UEMCPBridge\Content\Python` + `uemcp\packages\{server,shared}\src`（排除 `__pycache__|node_modules|\logs\|\Saved\|\Binaries\|\Intermediate\|\.git\|feedback-review`），前后各 **74 文件，Compare-Object diff=0，完全一致**。裁决更正（任务 49fb81d6）后重跑：`logs\bridge-hash-after-correction.txt` vs 同一基线，仍 **74/74 diff=0**（`logs\bridge-hash-compare-correction.log`）。
- 补充对（全树）：`feedback-review\bridge-hash-before.txt`（5431）vs `bridge-hash-after.txt`（5435）：**基线 5431 个文件全部字节级不变（无 <= 项）**；新增 4 个文件全部位于 `uemcp\logs\investigation-2026-11-17\`（QA 同事另一任务的调查日志，基线之后创建；本核查只写 `feedback-review\`）。详见 `logs\bridge-hash-compare.log`（含新增文件创建/修改时间戳）。
- 离线测试用 `C:\Python314\python.exe -B` + `PYTHONDONTWRITEBYTECODE=1`，源码树未产生 `__pycache__`（由 after 哈希证实）。
- 注：`feedback-review\` 为与 QA 共用的交付目录，其中 `qa-*`、`evidence-check.md`、`smoke-plan-0.1.5.md` 等系 QA 产物，非本核查产物；本核查产物为 `bridge-*` 与 `null_serialization_test.py`、本报告。
- 交付物备份协议（风险告知任务 `141088e3-3939-40f6-9b1d-e4e91bd45fe5`）：本报告最终版备份至本角色独有目录 `bridge-backup\bridge-verification.md`；原件＋备份 SHA256 见 `logs\bridge-deliverable-hash.log`（两者哈希一致）。误动自查：本角色写入仅限 `bridge-*`、`null_serialization_test.py`、本报告、根目录 `bridge-hash-before/after.txt` 与 `bridge-backup\`；全树哈希对无任何 `<=` 项（基线 5431 文件字节级不变），新增 4 文件均为 QA 同事产物——**未曾触碰/移动/删除任何他人文件**。

**状态图例**：属实＝反馈描述与 0.1.5 源码一致；部分属实＝部分一致/部分不准确或已修复但有残留；不属实＝反馈描述与源码不符（含“缺口已实现”）；无法核验＝需运行时/真机/他方源码证据，静态核查不能判定（列为未决）。

## 1. 十二项状态总览

| # | 条目（反馈来源） | 状态 | 关键证据 | 原始日志 |
|---|---|---|---|---|
| 1 | 端口回退区间/18790 成因（ZM P1-5、§1.2） | 部分属实 | settings.py:15-16；server.py:437-457；README:46 | bridge-item01-port.log |
| 2 | python.exec 超时语义（ZM P1-6＋CMD 3.4） | 部分属实 | python_exec.py:37/:93；rpc.py:119-136；README:116/:146 | bridge-item02-timeout.log |
| 3 | 体内 TypeError 误分类/origin-stage（ZM P1-2＋CMD 3.7） | 部分属实 | objects.py:467-515；rpc.py:101-116 | bridge-item03-errorclass.log |
| 4 | headless 截图无回退/PixelStreaming（ZM P1-1＋CMD 3.5＋缺口4） | 属实 | viewport.py:608-620/:691/:752-758；status.py:47-48 | bridge-item04-screenshot.log |
| 5 | 单队列单 pending 顶队列头（CMD 3.13） | 属实 | CMD-md:257/:262-264 原件锚点→dispatcher.py:62-95/:98-132/:101-103、errors.py:28、server.py:278-286；rpc.py:214-230 | bridge-item05-queue.log、bridge-correction-item05-anchors.log |
| 6 | 请求级日志缺失/审计归因（CMD 3.3＋3.1） | 部分属实 | server.py:182-183/:292；audit.ts:17/:23/:60；types.ts:70-88 | bridge-item06-logging.log、bridge-audit-scan.log、bridge-item06-auditrecord.log |
| 7 | 限流默认开启/全局桶（ZM P2-6＋IMP-001） | 属实 | settings.py:23-25（默认 True/30/30）；ratelimit.py:24-25/:47/:54/:110-120；rpc.py:176-190；server.py:575 | bridge-item07-ratelimit.log、bridge-correction-ratelimit.log |
| 8 | BFS 预算硬编码/无 nextOffset（ZM P2-1＋IMP-002） | 属实 | assets.py:19-20/:245-246/:315-323 | bridge-item08-assets.log |
| 9 | 黑名单仅 snake 名、无类限定（ZM P2-2/PROB-007） | 属实 | objects.py:33-34/:39-63/:425-437 | bridge-item09-blacklist.log |
| 10 | retryable 客户端不可读（IMP-008） | 不属实（插件侧已透出） | errors.py:105/:113；server.py:275/:349；callers=1 | bridge-item10-retryable.log、bridge-item10-callers.log |
| 11 | README 与实现不一致（CMD 3.11＋3.10＋3.12） | 属实 | README:1/:29/:170/:209/:220；rpc.py:51-68；Tests=16 | bridge-item11-readme.log、bridge-tests-count.log |
| 12 | TMap 空值序列化（ZM P0-4/PROB-008） | 部分属实（桥接保留 None 已证实；场景根因无法核验） | serialization.py:104-105/:119-122；离线测试 PASS | bridge-item12-serialization.log、bridge-serialization-null.log |

## 2. 逐项详核

### 项 1｜端口回退（ZM P1-5 md:108-113；ZM §1.2 md:20-24）——部分属实

**反馈主张**：README 回退区间与实现可能不一致；实际运行端口 18790 不在默认链上，原因未证实（md:24/:113 自认）；建议 README 对齐或 /health 增加 `portFallbackHistory`。

**0.1.5 证据**：
- `PY\settings.py:15` `DEFAULT_PORT = 18778`；`:16` `FALLBACK_PORTS = tuple(range(18779, 18789))` → 回退区间 **18779–18788**，其后 bind 0（OS 临时端口）。
- `PY\server.py:437` `ports = [self.settings.port]`；`:438` `for candidate in FALLBACK_PORTS:`；`:444-450` 逐个 bind；全部失败才 `:452-457` `_log_error("bridge_bind_failed host=127.0.0.1 ports=%s error=%s")`（:454）。
- `README:46` 描述的链条（18778→18779–18788→临时端口）**与代码一致**。
- 端口可被显式配置覆盖：env `UEMCP_BRIDGE_PORT`（settings.py:142）或 JSON `<Project>/Saved/UEMCP/bridge-settings.json`（settings.py:124，pick() env 优先 :137-140）。
- 发现文件记录（server.py:469-484）与 `health_payload`（server.py:558-577）均只有最终 `port`，**无 portFallbackHistory**；启动日志仅 `bridge_started port=…`（:515-518），无逐次尝试历史。

**判定**：
- “README 回退区间与实现不一致”这一前提**不属实**（两者一致；若 CMD 侧曾称区间到 18798，亦不属实，实际上界 18788）。
- **18790 ∉ 回退区间** → 只能来自显式配置（env/JSON）或 OS 临时端口；具体成因**未决**（需 ZM 工程启动时的 env/配置文件与端口占用证据，反馈自认未证实）。
- `portFallbackHistory` 建议**未实现**（作为改进缺口属实）。

**日志**：`logs\bridge-item01-port.log`（30 行）。

### 项 2｜python.exec 超时（ZM P1-6 md:115-119；CMD 3.4 md:115-129）——部分属实

**反馈主张**：handler 解析 timeoutMs 后丢弃（CMD :117 指 python_exec.py:37）、`timedOut` 恒 False（:93）、HTTP 504 后游戏线程继续跑；CMD 称“与 README:78 默认 30000 不一致”；ZM 要求长任务心跳/可取消标记。

**0.1.5 证据**：
- `PY\handlers\python_exec.py:37`：`get_int("timeoutMs", default=10000, min=1000, max=120000)` 校验后**返回值未被 handler 使用**；`:93` `"timedOut": False` 硬编码；docstring :4-5 明示运行中代码不可中断。
- **但** `PY\rpc.py:119-136` `_request_timeout_seconds` 仍读取 `meta.timeoutMs`/`params.timeoutMs`（+5000ms 宽限 :132，钳制 [1000,120000] :135，缺省 `settings.request_timeout_ms` :134）用于 **HTTP 等待**。即 timeoutMs 并非完全无效，只是不在 handler 内生效。
- `README:116`：“Python 执行的超时只限制 HTTP 等待，不能中断已在游戏线程运行的代码”；`README:146`：“Python 沙箱/中断 不支持；超时仅停止等待”。**README 诚实警示，不构成误导**。
- 超时后 `dispatcher.py:88` 置 `cancelled=True`，pending 在下一 tick 释放（:137-141）；无心跳/取消令牌 API。
- CMD :117 的“默认 30000 不一致”论据弱：README:78 的 30000 是 HTTP 等待缺省值，handler 的 10000 是被丢弃参数的缺省值，二者语义不同，且存在请求级覆盖。

**判定**：部分属实——`timedOut` 恒 False、不可中断、handler 丢弃参数**属实**；“timeoutMs 完全无效/README 误导”**不属实**；心跳/可取消标记建议未实现。ZM 未实测（md:118）、CMD 45s 实例的 timeoutMs 取值未验证（:127）→ 运行时细节**未决**。

**日志**：`logs\bridge-item02-timeout.log`（48 行）。

### 项 3｜错误分类（ZM P1-2/PROB-006 md:89-94；CMD 3.7 md:162-175）——部分属实

**反馈主张**：函数体内 TypeError 被归为 INVALID_ARGUMENT（应区分调用方错/插件错）；建议先 `inspect.signature().bind()` 再调用；CMD 要求 PYTHON_ERROR 带 `origin:caller|bridge` 与 stage。

**0.1.5 证据**（`PY\handlers\objects.py`，handle_call）：
- `:467-475` 先取 `inspect.signature`（失败→None）；`:476-489` `signature.bind` 的 TypeError → `INVALID_ARGUMENT {expectedParamCount,gotParamCount,error}`（**仅绑定错误**）。
- `:491-504` 签名可知时，**体内** TypeError → `EXECUTION_ERROR {phase:"in-body"}`（ZM 建议归 PYTHON_ERROR，实际归 EXECUTION_ERROR——码不同但已正确区分调用方/体内）。
- **残留**：`:505-515` 签名不可知（signature=None）时体内 TypeError 仍 → `INVALID_ARGUMENT {unverifiedSignature:True}`。UE C++ 绑定方法常使 `inspect.signature` 失败，该残留可能是常见路径；实际频率需运行时证据→**未决**。
- CMD 3.7 的 origin/stage：全源码无 `origin` 字段；`rpc.py:101-116` `_python_error` 提供 exceptionType＋8000 字符 traceback（部分有助归因）；`python_exec.py:64-70` 仅末行 traceback、无 exceptionType。**origin/stage 建议未实现**（缺口属实）。
- 截断限额实测：捕获 1 MiB（python_exec.py:17）、traceback 8000（rpc.py:98）、details 16 KiB（errors.py:79）、message 1024（errors.py:80）、repr 2000（serialization.py:22）。

**判定**：部分属实——可 introspect 签名的误分类**已修复**（bind 前置＋phase:in-body）；signature=None 残留仍存在；origin/stage 字段缺失属实。

**日志**：`logs\bridge-item03-errorclass.log`（53 行）。

### 项 4｜截图（ZM P1-1/PROB-004 md:82-87；CMD 3.5 md:131-145；ZM 缺口4 md:259-262）——属实

**反馈主张**：headless/offscreen 下截图直接失败、无离屏回退；/health 的 screenshot 能力位未标 requires_window；PixelStreaming 环境截图长时间超时（30 次 7 失败、p95 45s）。

**0.1.5 证据**（`PY\handlers\viewport.py`）：
- `:67-98` `_render_environment` 检测 `-renderoffscreen`/`-nullrhi`（:88）与 PixelStreaming（`Config/DefaultWebAPI.ini` `DataChannelType=PixelStreaming`，:90-97）。
- `:608-620` headless → **fail-fast** `CAPABILITY_UNAVAILABLE`，消息（:614）“Viewport capture is unavailable in a headless/offscreen editor”，details 含 renderer 与 suggestion；**无离屏渲染回退**。反馈锚点 :598 已偏移（现 :596-599 为 PIE_NOT_RUNNING 检查）。
- 能力位：`PY\handlers\status.py:47-48` `screenshot` = `AutomationLibrary.take_high_res_screenshot` 存在与否，**无 requires_window/pixelStreaming 区分** → ZM md:87 建议未实现。
- CMD 3.5 的代码描述**全部核实**：`:688-690` PixelStreaming 卡帧注释（引用 2026-10-29 缺陷报告）；`:691` `force_game_view = target == "pie"`；`:752-758` 超时提示含 PixelStreaming 专段；`:686` 内部 deadline=timeout−1s；`:43`/`:776-790` 0.5s 部分宽限与文件回收；`:696-701` TypeError→旧版 3 参重试（5.4 兼容）；`README:180` 回退到 Saved/Screenshots 最新 PNG＋SCREENSHOT_FALLBACK_PATH 已文档化。
- timeoutMs 缺省 15000、[1000,30000]（:575）。PixelStreaming 检测**只出现在超时提示**：无 /health pixelStreaming 能力位、无前置检查、无 20s 硬上限（CMD :143 三项建议均未实现→改进缺口属实）。

**判定**：PROB-004/缺口4 **属实**（headless 无回退、能力位不细分）；CMD 3.5 代码层描述属实；23.3% 失败率与 p95 45s 属运行时审计数据，源码不可核验→**未决**。

**日志**：`logs\bridge-item04-screenshot.log`（52 行）。

### 项 5｜单队列单 pending（CMD 3.13 md:255-268）——属实

**CMD §3.13 原件锚点对照（裁决更正：本项一律采用原件锚点，CMD-md:255-268）**：

| CMD 原件锚点 | 原件位置 | HEAD 0.1.5 核对（逐字） |
|---|---|---|
| `dispatcher.py:101-103`（有 pending 不取新 job） | CMD-md:257 | **精确命中**：`:101 if self._pending is not None:`、`:102 self._continue_pending()`、`:103 return` |
| `dispatcher.py:62-95`（队列与 call） | CMD-md:262 | 命中：`:62 def __init__(self, max_queue=64)`、`:65 queue.Queue(maxsize=max_queue)`、`:84 self._queue.put(job, timeout=0.5)`、`:85-86 except queue.Full → DispatcherBusy` |
| `dispatcher.py:98-132`（_on_tick 的 pending 早返回） | CMD-md:262 | 命中：`:98 def _on_tick`、`:101-103` 早返回、`:125-129` Pending 挂起 |
| `errors.py:28`（BRIDGE_BUSY 已定义） | CMD-md:263 | **精确命中**：`"BRIDGE_BUSY": (-32002, 429, True),` |
| `server.py:278-286`（Busy/Timeout 映射） | CMD-md:263 | 命中：`:278-283` DispatcherBusy→BRIDGE_BUSY -32002/429 retryable=True；`:284-290` DispatcherTimeout→BRIDGE_TIMEOUT -32020/504（原件区间 :278-286 覆盖 Busy 块与 Timeout 块起始） |
| `raw/collect.log` ERRORCODE_DIST（无 BRIDGE_BUSY）/DURATION 45009ms | CMD-md:264 | 运行时数据→**无法核验（未决）** |

**0.1.5 证据**（`PY\dispatcher.py`）：
- `:59-74` 单队列 `maxsize=64`（:62），Slate post-tick 每 tick 取一个作业（:70）；`:101-103` **pending 优先且阻塞队列头**（CMD 锚点精确命中）。
- `BRIDGE_BUSY` 仅在队列满、put 0.5s 超时触发（:84；server.py:278-283 → -32002/429）；**“队列不满但被 pending 顶住”无任何信号**（静默排队属实）。
- 无批量 API（rpc.py:51-68 共 16 个 method，无 batch）；响应 meta 仅 `{requestId,durationMs,ueVersion,pluginVersion}`（rpc.py:214-230），**无 queuedMs/stage**。
- 已取消作业仍占位至下一 tick（:88/:109-111/:137-141）。
- `BRIDGE_TIMEOUT` → -32020/504（server.py:284-290），details.timeoutMs 取 settings 缺省值而非该请求实际值（额外观察，见附录 E）。

**判定**：属实（代码层）。分队列/pending 期间放行非 pending 作业/queuedMs 建议均未实现。45s 究竟排队还是执行、BRIDGE_BUSY 审计 0 次等运行时问题→**未决**。

**日志**：`logs\bridge-item05-queue.log`（69 行）、`logs\bridge-correction-item05-anchors.log`（53 行，原件锚点＋HEAD 对照取证）。

### 项 6｜请求级日志与审计归因（CMD 3.3 md:100-113；CMD 3.1 md:70-83）——部分属实

**反馈主张**：桥接无请求级日志（“没有任何请求级记录，也没有 requestId”，:102）；审计写入方/保留/轮转无文档；审计记录缺 buildHash/sourcePath/instanceId，无法归因到构建（P0）。

**0.1.5 证据**：
- **无常规请求级日志**：rpc.py 全文无 logging；`server.py:182-183` HTTP `log_message` 被抑制；requestId 只出现在响应 meta（rpc.py:214-230）。
- **但存在崩溃级请求日志**：`server.py:292` `_log_error("rpc handler crashed: %s\n%s")`（do_POST 兜底异常）→ CMD :102 “没有任何请求级记录”**表述过头**。
- CMD :109 锚点 server.py:132-142 即 `_log`/`_log_error` 定义。全部调用点：_log → :490（stale_discovery_removed）、:515-518（bridge_started）、:554（bridge_stopped）；_log_error → :292（crashed）、:453-456（bridge_bind_failed）、:492/:497（discovery 清理/写入失败）、:539（discovery_cleanup_failed）。“只用于生命周期与发现文件清理”**基本准确**（另含 bind 失败与崩溃）。
- **审计写入方＝TS 服务端，已证实**：`TS-server\audit.ts`（:2 docstring“~/.uemcp/audit/YYYY-MM-DD.jsonl”、:17 `export class Audit`、:23 目录、:60 `record()`、:74 audit_write_failed）；`index.ts:58` `new Audit(...)`；tools/*.ts 多处 auditCall。**插件 23 个 .py 中 audit 匹配=0**（bridge-audit-scan.log）。CMD “插件本体 57 个文件 0 处 audit”：audit=0 属实；“57”与实际包内 .py=23 口径不同（23 包内＋32 Tests＋1 Tools=56≈57，疑为全插件口径）→ 口径差异，非虚假主张。
- **CMD 3.1 审计字段**：`TS-shared\types.ts:70-88` `AuditRecord` 字段止于 pluginVersion，**无 buildHash/sourcePath/instanceId/buildTime**（bridge-item06-auditrecord.log：attribution_fields=0）。而插件 `/health` **早已提供**这四者：`server.py:567-570` `"instanceId": _INSTANCE_ID, "buildHash": _build_hash(), "buildTime": _build_time(), "sourcePath": _PLUGIN_ROOT`（CMD :79 自己也承认）。buildHash=插件 Python 全量 sha256（server.py:66-90），instanceId=uuid4（:54），buildTime 取 uplugin mtime（:103-125）。

**判定**：部分属实——无常规请求级日志属实（仅崩溃日志，CMD 表述夸大）；审计归 TS、插件 0 处 audit 属实；**审计缺构建归因字段是 TS 侧缺口（属实），插件侧不属实（/health 已具备全部所需值）**。修复落点：TS audit.ts 写入侧补字段（取 /health 同源值）＋README §8 对照表——均超出本角色（桥接 Python）编辑范围。/rpc 结构化日志建议未实现。

**日志**：`logs\bridge-item06-logging.log`（37 行）、`logs\bridge-audit-scan.log`（46 行）、`logs\bridge-item06-auditrecord.log`（18 行）。

### 项 7｜限流（ZM P2-6 md:151-155；IMP-001 md:163-166）——属实（代码层）

**反馈主张**：限流默认开启、超限 429/RATE_LIMITED、可经 rateLimitEnabled=false 或 rateLimitPerSecond=0 关闭；/health 已有 rejected 计数；建议按远端地址分桶。ZM 自认无一次被 429 的实测（md:154）。

**HEAD 默认值逐字摘录（`PY\settings.py:21-25`；裁决更正：代码默认＝开启，不是 false）**：

```python
# Bridge-wide request limit (architecture section 6.7: 30 req/s globally).
# Set rateLimitPerSecond to 0 (or rateLimitEnabled to false) to turn it off.
DEFAULT_RATE_LIMIT_ENABLED = True
DEFAULT_RATE_LIMIT_PER_SECOND = 30
DEFAULT_RATE_LIMIT_BURST = 30
```

**false/0 指向核实（二者是“关闭开关”，绝非代码默认值）**：
- `settings.py:22` 注释原文：`Set rateLimitPerSecond to 0 (or rateLimitEnabled to false) to turn it off.`——false/0 的语义是 *turn it off*。
- `settings.py:178-180` 注释：`A value of 0 disables the limiter (equivalent to rateLimitEnabled false) so either knob can turn it off from the settings file or the environment.`
- `settings.py:181-190`：`rateLimitPerSecond` 经 `_as_int(pick(...), DEFAULT_RATE_LIMIT_PER_SECOND, 0, 10000)`，缺省回落到 **30**，仅当显式配置 0 才关闭；`:201-208`：`rateLimitEnabled` 经 `_as_bool(pick("rateLimitEnabled","UEMCP_BRIDGE_RATE_LIMIT_ENABLED", DEFAULT_RATE_LIMIT_ENABLED), DEFAULT_RATE_LIMIT_ENABLED)`，缺省回落到 **True**。
- `ratelimit.py:47` 构造器缺省 `enabled=True`；`:52-54` 注释＋`self.enabled = bool(enabled) and self.per_second > 0.0`（perSecond≤0 等价关闭）。
- `README:94-95` 默认值列：`rateLimitEnabled`＝`true`、`rateLimitPerSecond`＝`30`（设为 `0` 等价于关闭）；`README:100`：「关闭方式（二选一）：`"rateLimitEnabled": false`，或 `"rateLimitPerSecond": 0`」——文档同样把 false/0 定位为**配置关闭方式**。
- **结论（更正主管裁决断言）**：把 `rateLimitEnabled=false` 写成代码默认值是**错误**的；HEAD 代码默认为 `True`（开启）、30/s、burst 30。本项判定维持「属实」，以本摘录与指向核实为准。

**0.1.5 证据**：
- `PY\settings.py:23-25` 默认 `True`/30/30（load :201-208）；`PY\ratelimit.py:24-25` 同值、`:47` 构造器 `enabled=True`；`server.py:430` 创建 RateLimiter。
- `PY\rpc.py:176-190`：**权限门之前、入队之前**判定（README:98/:111-112）；拒绝 → `RATE_LIMITED` -32012/429，details `{gate:"bridge.rateLimit",limitPerSecond,burst,retryAfterMs}`，retryable=true、无 result（errors.py:38；README:99）。
- `GET /health`、`GET /events` 不受限流（server.py:190-203 do_GET 无限流判定；README:102）。
- 关闭方式与反馈一致：rateLimitEnabled=false 或 rateLimitPerSecond=0（settings.py:181-190/:201-208；ratelimit.py:54 `enabled and per_second>0`；README:100）。
- **全局单桶、无 per-client key**（ratelimit.py:73-100 try_acquire 无客户端参数）→ IMP-001 缺口属实；每会话 20/s 属 MCP 服务端（ratelimit.py docstring），非插件。
- **/health rejected 计数已实现**：`server.py:575` `"rateLimit": self.rate_limiter.snapshot() if self.rate_limiter else None`；`ratelimit.py:110-120` snapshot 字段 enabled/perSecond/burst/available/accepted/rejected，与 README:101 完全一致 → **ZM md:155 的建议已被满足**。

**判定**：属实（默认开启/全局桶/429 语义/豁免/关闭方式均与代码一致）；per-client 分桶未实现（IMP-001 属实）；批量场景被 429 的实测→**未决**（反馈自认）。

**日志**：`logs\bridge-item07-ratelimit.log`（134 行）、`logs\bridge-correction-ratelimit.log`（76 行，默认值与 false/0 指向取证）。

### 项 8｜资产搜索预算与分页（ZM P2-1/PROB-005 md:123-127；IMP-002 md:168-171）——属实

**0.1.5 证据**（`PY\handlers\assets.py`）：
- `:19` `_MAX_BFS_NODES=1000`（:206 节点上限）、`:20` `_MAX_SEEDS=50`（:170 seeds[:50]）；settings.py 无对应配置键；check_keys（:214-231）无 maxNodes → **硬编码属实**，ZM :127 “挪进设置/请求级 maxNodes”未实现。
- 分页参数：`:245` limit 缺省 100、[1,**500**]；`:246` offset 缺省 0、min 0、**无上界**；`:239` dependencyDepth 缺省 1、[1,3]。
- 响应 `:315-323` `{total, returned, truncated: offset+len(window)<total, assets}` —— **只有 truncated 布尔，无 nextOffset**（IMP-002 属实，锚点 :321 精确）。
- SEARCH_TIMEOUT 两条路径：_bfs 内 :180-192（过期后 timeoutMs 为**负值**，带 partial）；过滤循环 :270-282（每 256 项检查 deadline，timeoutMs 为**正的** settings.search_timeout_ms，partial{total,returned,assets[:limit]}）。符号不一致见附录 E。

**判定**：属实（预算硬编码＋无 nextOffset）；两项建议均未实现。

**日志**：`logs\bridge-item08-assets.log`（56 行）。

### 项 9｜函数名黑名单（ZM P2-2/PROB-007 md:129-132）——属实

**0.1.5 证据**（`PY\handlers\objects.py`）：
- `:33` `_BLOCKED_EXACT=("exec","eval","execfile","compile","__import__","python","py")`；`:34` `_BLOCKED_PREFIXES=("python_","py_","subprocess","exec_","runpython","execpython")`；:35-36 camel 正则；`:39-45` `_to_snake`；`:48-63` `_blocked_rule`：`lowered=_to_snake(function).lower()` 后做 exact（:56-57）/prefix（:58-60）/leading_underscore（:61-62）匹配。
- **只用裸 snake 函数名，无类限定** → 不同类中同名异义函数一并被拦（ZM md:131 主张成立）。命中 → `:425-437` `PERMISSION_DENIED {blocked:True, reason:"blacklisted_name", matchedRule}`。
- docstring（:49-53）表明这是**有意的非子串设计**（使 `execute_console_command` 等普通名可调用）。
- ZM :132 “class-qualified 名匹配”未实现。
- 代码阅读层面的绕过面（**仅理论分析，未执行任何绕过脚本**）：camel 名如 `RunPythonScript` → snake `run_python_script`，与前缀 `runpython`（无下划线）不匹配，可滑过黑名单；但仍受 allowWrite 门控（:418-423）且必须是真实可调用对象。是否构成实际风险需真机验证→未决。

**判定**：属实（snake-only、无类限定、过度拦截结构性成立）；class-qualified 建议未实现。

**日志**：`logs\bridge-item09-blacklist.log`（21 行）。

### 项 10｜retryable 可读性（IMP-008 md:198-201）——不属实（插件侧已透出）

**反馈主张**：错误表之外客户端还要背错误码；期望“客户端能直接读 retryable”。

**0.1.5 证据**：
- `PY\errors.py:14-70` ERROR_TABLE 三元组 (jsonrpc_code, http_status, retryable)；`:105` `self.retryable=meta[2]`；`:107-116` `to_jsonrpc_error` 的 data 含 `{errorCode, retryable, details}`（:113）。
- **活路径透传**：`server.py:275` `_send_rpc_error(..., retryable=exc.retryable)`；`:349` data `retryable: bool(retryable)`；DispatcherBusy→True（:281）、DispatcherTimeout→True（:288）；RATE_LIMITED retryAfterMs（rpc.py:184-189）；actor.edit 逐操作错误也带 retryable（actors.py:790）。
- 唯一硬编码 `retryable: False` 的 `rpc_error_response`（errors.py:175-186，:183）经全包扫描**仅 1 处匹配＝定义本身，0 调用者**（bridge-item10-callers.log）→ 死代码，不影响线上行为。

**判定**：不属实（作为插件缺口）——每个 JSON-RPC 错误的 `error.data.retryable` 已可直接读取。MCP 工具返回侧是否同样透传属 TS 服务端职责→**未决/归 TS**。

**日志**：`logs\bridge-item10-retryable.log`（47 行）、`logs\bridge-item10-callers.log`（6 行）。

### 项 11｜README 一致性（CMD 3.11 md:223-238；兼 3.10 打包 md:208-221、3.12 兼容 md:240-253）——属实

**0.1.5 证据（多处不一致，CMD 列举精确）**：
- `README:29` “10 个工具对应的 12 个 RPC method” vs `rpc.py:51-68` **16 个 HANDLERS**；§5 表实为 **13 行**（L122-134），缺 `object.reflect`/`object.call`/`log.query`；审计中出现 12 次的 `ue_call_function` 工具↔`object.call` 映射无表行。
- `README:1` 标题仍 “v0.1.0” vs `settings.py:12`/`uplugin:4` 0.1.5。
- **自检数三处口径互相矛盾**：README:170 “14 个”、:209/:220/:31 “11 个”；Tests 实际 `^(check_|test_)` = **16**（bridge-tests-count.log，与 CMD 一致）；未进 README 表的 5 个恰为 CMD 所列：check_plugin_version、test_log_query、test_object_call、test_pie_control、test_viewport_capture。README:236 “11/11 exit 0” 与实际 16 个脚本不符。
- **CMD 3.10（发行包不带 Tools/ 与 *.ps1）**：源码仓库中 Tools/stamp_uplugin.py 与 Tests/*.ps1 存在（glob 证实），zip 不含——但 `README:30/:34/:247` **已明示**，且 :34 专门披露 test_uplugin_metadata 依赖 Tools/。代码证实该依赖：`Tests\test_uplugin_metadata.py:30` `TOOL_PATH=os.path.join(PLUGIN_DIR,"Tools","stamp_uplugin.py")`、`:36` importlib 硬加载 → 缺 Tools/ 时该自检必然失败（CMD :212 “至少 1 个必然失败”成立）。**事实属实、文档诚实**；建议 (a) 包内最小校验脚本 /(b) 随包维护者自检结果＋环境指纹均未实现。
- **CMD 3.12（5.4.4 只有 4 条流量且全 0.1.0）**：运行时审计数据，源码不可核验→**无法核验**。源码侧兼容措施存在：viewport 旧版 3 参重试（:696-701）、assets 旧版 include_management_references 降级（:108-112）；README:162 “不需要版本分支代码”（83 处调用点/46 符号核查）、:164 COMPAT-UE57.md、:236 自认 4 个需引擎脚本待与 QA 5.7 联跑。

**判定**：属实（method 数/表行/标题版本/自检数不一致均确证）；打包缺项属实但 README 已如实披露；5.4.4 流量归属无法核验。

**日志**：`logs\bridge-item11-readme.log`（62 行）、`logs\bridge-tests-count.log`（28 行）。

### 项 12｜TMap 空值序列化（ZM P0-4/PROB-008 md:73-78）——部分属实（桥接侧已证实；场景根因无法核验）

**反馈主张**：FloodControllers 键 “ZM库区洪水推演01” 值为 None（bugs.md:98；probe_env2.py controllerActorNames=[null]、mapDetail.valueIsNone=true，session.log:52/:50）；要求 (a) getList 返回显式 `nullController:true`＋原始键名，(b) “确认 TMap<FString,TWeakObjectPtr<...>> 序列化对空对象的处理，避免‘键留着、值没了’”。

**核查拆分**：
1. **场景侧根因**（控制器弱指针为空）＝ZM 项目资产/蓝图问题，桥接源码无从判定→**无法核验/归 ZM 项目**。
2. **(a) nullController:true 标记**：getList 属 ZS_WebAPI（项目 C++/蓝图侧），非桥接 method；serialization.py 无此类标记逻辑→**范围外**。
3. **(b) 桥接序列化对 None 的处理——已证实保留**：
   - `PY\serialization.py:104-105` `if value is None or isinstance(value, (bool, int, float, str)): return value`（None 原样透传）；`:110-125` dict 分支逐键递归，**键保留、None 值保留**（:119-122）。
   - **离线测试 PASS**（`feedback-review\null_serialization_test.py`，`C:\Python314\python.exe -B`，PYTHONDONTWRITEBYTECODE=1，standalone importlib 加载、unreal=None、无编辑器）：exit=0、ALL_ASSERTIONS_PASS；`{"ZM库区洪水推演01": None}` → to_jsonable 不变 → `json.dumps` 输出 `{"ZM库区洪水推演01": null}`（**键未被丢弃**）；嵌套 dict/list 中 None 同样保留。原始输出：`logs\bridge-serialization-null.log`（16 行）。
   - 说明：测试解释器为 Python 3.14.5（UE 自带 3.11.8）；被测逻辑纯标准库、None 处理与版本无关。**UE 侧 TMap 空弱指针迭代究竟产出 None 还是丢键，需真机验证→未决**（若 UE Python 迭代本身丢键，桥接无从保留——这正是反馈担心的“键留着、值没了”的反向情形，静态不可判）。

**判定**：部分属实——桥接序列化保留 None/键**已证实**（离线测试）；场景 null 根因归 ZM 项目（无法核验）；nullController 标记归 ZS_WebAPI（范围外）；UE TMap 迭代行为未决。

**日志**：`logs\bridge-item12-serialization.log`（42 行）、`logs\bridge-serialization-null.log`（16 行）。

## 附录 A｜IMP-001…008 速查（ZM 02_improvements.md / ZM-md §4）

| IMP | 主张（锚点） | 状态 | 0.1.5 证据 |
|---|---|---|---|
| IMP-001 | 全局桶→按远端地址分桶（rpc.py:178） | 属实（缺口） | rpc.py:176-190 全局判定；ratelimit.py:73-100 无 client key |
| IMP-002 | truncated 布尔→nextOffset（assets.py:321） | 属实（缺口） | assets.py:315-323 仅 truncated，无 nextOffset |
| IMP-003 | include_management_references 降级需 5.4/5.7 标志矩阵文档（assets.py:111） | 属实—需文档 | assets.py:108-112 旧标志降级；:70-82 hasattr 跳过→DEPENDENCY_OPTION_UNAVAILABLE/失败→DEPENDENCY_OPTION_FAILED；:102-107 5.4 hard/soft；README 无标志矩阵 |
| IMP-004 | explicit 模式接受 loc/rot/fov（viewport.py:36） | 部分属实 | loc/rot **已实现**：viewport.py:589-591 explicit 必填 camera.location(vec3)+camera.rotation(rotator)，:663-665 set_level_viewport_camera_info 应用；**fov 缺失**：全文件 grep `fov|FOV|field_of_view` 零匹配 |
| IMP-005 | dryRun 返回逐操作 before/after（actors.py:746） | 部分属实 | dryRun 存在（:746/:749/:756-769）；_dry_run_operation :689-742 仅 wouldCreate/wouldDelete/wouldModify 标志，**无 before/after 属性差值** |
| IMP-006 | create_instance 目标路径已存在时直接拒绝（materials.py:16；ZM-md:190） | **不属实（0.1.5 已实现）** | materials.py:414-419 `if asset_exists(instance_path): raise RpcError("ALREADY_EXISTS", "Asset already exists: %s" % instance_path, {"path": instance_path})`。ZM 在 0.1.4 踩坑（md:191）；0.1.4 是否缺该校验**未决**（ZMCPP_54 预期路径无 0.1.4 源码，glob 零命中） |
| IMP-007 | save_all 按包给进度（levels.py:19） | 属实（缺口） | levels.py:194-213：confirm=true 门槛（:195-200 CONFIRMATION_REQUIRED＋dirtyPackages）；单次 `saved=bool(subsystem.save_all_dirty_levels())`（:202）；失败 SAVE_FAILED（:203-212）；**无逐包进度** |
| IMP-008 | 客户端直接读 retryable（errors.py:15） | 不属实（插件侧已透出） | 见项 10：error.data.retryable 活路径透传；硬编码 False 的 helper 0 调用者 |

日志：`logs\bridge-imp.log`（111 行）及各对应项日志。

## 附录 B｜ZM「缺口」1–6（ZM-md §5）

| 缺口 | 状态 | 依据 |
|---|---|---|
| 缺口1 LevelSequence 播放/停止/快照回滚（md:241-245） | 属实 | rpc.py:51-68 十六个 method 无序列类；README §5 表亦无；“停止与回滚没有对应接口…播放进度也拿不到”（md:244）成立 |
| 缺口2 MID 批量写回与回读校验（md:247-251） | 部分属实 | **已有**：单实例批量 set（parameters 数组 ≤50，materials.py:173-177/:358-397）＋get/list 逐参数回读（:346-356）。**确缺**（md:250 三项全中）：set 结果 `value:None` 硬编码占位（:390-395，无内联回读值）；无跨实例（11 个 MID）批量语义；_apply_parameters :252-302 中途抛错留下已应用参数，**无事务/回滚/失败项汇总**。“没有批量写回”的笼统表述不准确 |
| 缺口3 cook 目录检查（md:253-257） | 范围外（项目配置侧） | DefaultGame.ini:98 +DirectoriesToAlwaysCook 已存在（ZM md:140 自纠）；桥接无 cook 检查功能；禁打包未证实 |
| 缺口4 headless 渲染管线（md:259-262） | 属实（＝项 4） | viewport.py:608-620 fail-fast，无离屏回退 |
| 缺口5 跨 actor 原子批事务（md:265-269） | 部分属实 | “事务作用域是单次调用”（md:266）对**跨 RPC** 成立；但**单次 actor.edit 内跨 actor 原子提交＋整体回滚已存在**：operations[] 每操作独立 selector、atomic 缺省 True（actors.py:748）、ScopedEditorTransaction（:777）、失败 cancel（:795-799，cancel 失败 ROLLBACK_FAILED :800-801）、TRANSACTION_FAILED {rolledBack,reason,failedIndex,succeeded,failed}（:808-818）。ZM 逐 actor 变通（snapshot.py:36）对纯 actor 批量并非必需；跨工具（actor+material+level）事务确无 |
| 缺口6 序列播放进度回执（md:271-275） | 范围外（ZS_WebAPI/ZS_Flood 侧） | handler_progress 恒 0.0 是 ZM 项目自身 handler（md:272）；桥接 /events SSE 仅 15s ping（server.py:368-384），本就无进度事件可收 |

## 附录 C｜CMD 其他条目（不在权威 12 项内，顺带核查）

- **§3.1 审计归因（P0）**：见项 6。插件 /health 四字段齐备（server.py:567-570，CMD :79 锚点精确）；TS AuditRecord 缺字段（types.ts:70-88，attribution_fields=0）→ **插件侧不属实、TS 侧属实**；修复归 TS 写入侧＋README 对照表。
- **§3.2 0.1.5 零审计记录/0.1.4 失败率 9.6×**：运行时数据→**无法核验**。版本锚点 settings.py:12＋uplugin:4 确证 0.1.5；buildHash 比对可行（/health:568 已提供）。
- **§3.6 python.exec 占 94.9%（952/1003）**：运行时数据→无法核验；README:132/:142 与 python_exec.py:26-38 锚点属实；“收敛 3–5 个专用工具＋替代清单”建议未实现；argsSummary 102 字符上限属 TS summarizeArgs（未验证）。
- **§3.8 仅 5/16 method 被使用**：运行时数据→无法核验；CMD :181 自称“16 个自检脚本”与 Tests 实际 16 一致（反而 README 的 11/14 不一致）；覆盖矩阵建议未实现。
- **§3.9 policyMode=full 963/1003、无 bridge-settings.json**：运行时数据→无法核验；env-vs-JSON 来源未验证（CMD :202 自认）；“配置快照/policies 进审计”——插件侧 `settings.policy_snapshot`（settings.py:237-248）与 /health `policies`（server.py:576）**已存在**，审计侧补字段归 TS。

## 附录 D｜范围外条目（C++/项目资产/配置侧，非 UEMCPBridge/Content/Python）

以下反馈指向 ZM 项目 C++（ZS_Flood/ZS_WebAPI/FloodCmdHandler）、蓝图资产或工程配置，**不属桥接插件源码范围，本报告不判定其代码状态**，仅登记归属：
- ZM P0-1（EXCEPTION_ACCESS_VIOLATION，FloodCmdHandler.cpp:48 GetPeakModelId 无空检查）、P0-2（AddUniqueDynamic，cpp:86，建议 FLOOD_CONTROLLER_NULL）、P0-3（offset/offsetReset/cameraFollow/close 崩溃，未逐一实测）；
- ZM P1-3/PROB-009、P1-4/PROB-010、P2-3/PROB-011（ZS_Flood C++）、P2-4/PROB-012（DefaultGame.ini cook）、P2-5/PROB-013（FFloodReturnInfo C++）；
- 01_problems.md 之 PROB-001/002/003/009/010/011/012/013；PROB-008 的场景根因部分（桥接相关部分已在项 12 核查）；
- ZM §5.7 第 5 项（offset 等崩溃）与缺口6（ZS_WebAPI/ZS_Flood 进度）。

## 附录 E｜额外观察（核查中发现、反馈未列）

1. `objects.py:415` handle_call 的 `waitMs` get_int(default=5000,[0,60000]) 校验后同样被丢弃（与 python_exec timeoutMs 同模式）。
2. `assets.py:180-192` _bfs 路径 SEARCH_TIMEOUT 的 details.timeoutMs 为**负值**（过期后剩余时间），过滤循环路径（:271-282）为正值——同一错误码两处符号不一致。
3. `server.py:287` BRIDGE_TIMEOUT details.timeoutMs 取 settings.request_timeout_ms **缺省值**，非该请求实际超时值，排障易误导。
4. `materials.py:390-395` set 成功结果 `value: None` 为硬编码占位（并非回读失败），客户端可能误读为“值被清空”。
5. `materials.py:252-302` _apply_parameters 无事务：中途 PARAM_NOT_FOUND/TYPE_MISMATCH/EXECUTION_ERROR 抛出时，先前参数已应用且不回滚。
6. `errors.py:175-186` rpc_error_response 为 0 调用者的死代码且硬编码 retryable:False——若未来被启用将造成回归，建议删除或修正（本次只读，未改）。
7. CMD §3.3 “插件本体 57 个文件”与实际包内 .py=23 口径不符（23+32 Tests+1 Tools=56≈57）；audit=0 的结论本身成立。
8. `levels.py:45-51` is_map 探针恒抛错→改报 True 的修复与 README:156（list_dirty isMap false→true）互证。
9. `actors.py:790` 逐操作错误已含 retryable（正面发现）。

## 附录 F｜反馈锚点偏移说明（0.1.4/其他检出 → 0.1.5）

- objects.py：_to_snake :213→**:39**；_blocked_rule :218→**:48**；PROB-006/POS-003 :245/:251→**:467-515**。
- viewport.py：PROB-004/P1-1/缺口4 :598→**:608-620**（:598 现为 PIE_NOT_RUNNING）；_finalize_file :538-547→**:537-548**。
- assets.py：POS-007 :95→**:70-82**。
- settings.py：CMD 所称回退上界 18798→实际 **18788**（:16）。
- **精确命中 0.1.5 的 CMD/ZM 锚点**（抽样复核无误）：server.py:567-570/:132-142/:278-286；settings.py:12；uplugin:4；python_exec.py:37/:93；rpc.py:132/:135/:178/:188；README:78/:116/:180/:30/:34/:233/:247/:29/:170/:209/:220/:162/:236；viewport.py:688-695/:752-758/:686/:43/:36；actors.py:746/:369；materials.py:16；levels.py:18/:19；errors.py:15/:19/:28/:40；objects.py:218（0.1.4 语义对应 :48-63）；assets.py:321。

## 日志清单（全部原始留存于 feedback-review\logs\）

| 日志 | 行数 | 内容 |
|---|---|---|
| bridge-item01-port.log | 30 | 项1 端口链/配置/日志点 Select-String 全输出 |
| bridge-item02-timeout.log | 48 | 项2 超时链 |
| bridge-item03-errorclass.log | 53 | 项3 错误分类 |
| bridge-item04-screenshot.log | 52 | 项4 截图/headless/PixelStreaming |
| bridge-item05-queue.log | 69 | 项5 队列/pending/meta |
| bridge-item06-logging.log | 37 | 项6 日志点全集 |
| bridge-item06-auditrecord.log | 18 | 项6 AuditRecord 字段缺失证明（attribution_fields=0） |
| bridge-item07-ratelimit.log | 134 | 项7 限流全链 |
| bridge-item08-assets.log | 56 | 项8 预算/分页 |
| bridge-item09-blacklist.log | 21 | 项9 黑名单 |
| bridge-item10-retryable.log | 47 | 项10 retryable 透传 |
| bridge-item10-callers.log | 6 | 项10 rpc_error_response 调用者扫描（1 匹配=定义，0 调用） |
| bridge-item11-readme.log | 62 | 项11 README/method/uplugin |
| bridge-item12-serialization.log | 42 | 项12 序列化 None 路径 |
| bridge-imp.log | 111 | IMP-001…008 锚点 |
| bridge-tests-count.log | 28 | Tests 计数（自检 16/总 32/Tools 1） |
| bridge-audit-scan.log | 46 | 插件 audit=0；TS audit.ts/types.ts 定位 |
| bridge-serialization-null.log | 16 | 离线空值测试全输出（exit=0，ALL_ASSERTIONS_PASS） |
| bridge-hash-before.txt / bridge-hash-after.txt | 74/74 | 验收哈希对（diff=0） |
| bridge-hash-compare.log | 27 | 两对哈希比较命令、结果与解释 |
| bridge-correction-ratelimit.log | 76 | 裁决更正：项7 默认值（True/30/30）与 false/0 关闭开关指向取证 |
| bridge-correction-item05-anchors.log | 53 | 裁决更正：项5 CMD §3.13 原件锚点（md:257/:262-264）＋HEAD 对照取证 |
| bridge-hash-after-correction.txt | 74 | 更正后重采 scoped 哈希（vs 基线 diff=0） |
| bridge-hash-compare-correction.log | 9 | 更正轮哈希比较命令与结果（74/74 diff=0） |
| bridge-deliverable-hash.log | 12 | 交付物备份协议：原件＋bridge-backup 备份 SHA256（一致）与误动自查 |
| bridge-hash-scoped-baseline.log / bridge-hash-baseline.log | 1/1 | 基线时间戳（09:45:14 / 09:23:21） |
| （根目录）bridge-hash-before.txt / bridge-hash-after.txt | 5431/5435 | 补充全树对（基线文件零变更；+4 为 QA 调查日志） |

测试脚本：`feedback-review\null_serialization_test.py`（离线、standalone 加载 serialization.py，无 unreal/编辑器依赖）。

## 未决汇总（需运行时/真机/他方证据，静态核查不能判定）

1. ZM 实际端口 18790 的成因（env/JSON 显式配置 or 临时端口；需启动时配置与端口占用证据）。
2. python.exec 超时后线程继续执行的实测、CMD 45s 案例的 timeoutMs 取值（ZM/CMD 均自认未实测）。
3. inspect.signature 对 UE 5.4/5.7 C++ 绑定方法的成功率（决定项 3 残留路径 :505-515 的实际频率）。
4. 截图 23.3% 失败率、p95 45s、PixelStreaming 现场复现（运行时审计数据）。
5. 45s 延迟中排队 vs 执行占比、BRIDGE_BUSY 触发层（运行时）。
6. 批量场景被 429 的实测（ZM 自认无）。
7. UE TMap<FString,TWeakObjectPtr> 空弱指针的 Python 迭代行为（None vs 丢键；需真机）。
8. 0.1.4 是否缺 create_instance ALREADY_EXISTS 校验（0.1.4 源码不可得，ZMCPP_54 预期路径 glob 零命中）。
9. CMD §3.2 0.1.5 零审计记录、§3.12 5.4.4 四条流量归属、§3.9 full 模式配置来源（env vs JSON）——均为运行时数据。
10. MCP 工具返回侧 retryable/policies 透传（TS 服务端职责，超出桥接范围）。
11. 黑名单理论绕过面（RunPythonScript 类前缀失配）是否构成实际风险（未执行任何绕过脚本；allowWrite 门控下需真机评估）。

—— 完 ——
