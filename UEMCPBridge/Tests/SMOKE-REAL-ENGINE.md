# 真机验证执行脚本（UE 5.4 / 5.7）

> 本文件描述的是源码仓库中的维护者工具链；发行包内只含 Python 自检脚本。文中引用的 `ue_smoke_run.ps1` / `ue_probe_run.ps1` / `ue_common.ps1` 执行器与 `smoke-runs/` 运行证据不随发行包分发，请到源码仓库运行与查看。

本目录下三个文件构成可重放的真机验证工具链：

| 文件 | 作用 |
| --- | --- |
| `ue_smoke_run.ps1` | 端到端冒烟：预检 → 装插件 → 启动编辑器 → 等 Bridge → 8 个 RPC → 优雅关闭 → 还原工程 |
| `ue_probe_run.ps1` | 在 5.4 与 5.7 各跑一次 `probe_ue57.py`，产出逐 API 的 5.4/5.7 对照表 |
| `ue_common.ps1` | 两个脚本共用的函数（端口探测、发现文件、RPC、进程关闭、清理） |

约束：**一次只开一个引擎实例**；脚本 preflight 会拒绝在有残留 `UnrealEditor*` 进程或 18778–18788 被占用时继续。除仓库自带的 `ue_p_text/ue54_text` 外，不得把插件装进任何用户工程。

## 1. 本轮实测结论（2026-10-28）

两个引擎版本均**实跑通过**，无阻断：

| 引擎 | 工程 | 结果 | 退出码 | Bridge 就绪 | 证据目录（相对本目录） |
| --- | --- | --- | --- | --- | --- |
| UE 5.4.4 | `<RepoRoot>/ue_p_text/ue54_text`（仓库样例，跑完已还原） | **PASS** | `0` | 16.4 s | `smoke-runs/smoke-5.4-20261028-175716/` |
| UE 5.7.4 | `%USERPROFILE%\Documents\Unreal Projects\UEMCP_Smoke_Blank`（`TP_BlankBP` 新建） | **PASS** | `0` | 22.4 s | `smoke-runs/smoke-5.7-20261028-175743/` |
| 5.4 + 5.7 探针 | 同上两工程 | **PASS**（各 13/13 必检项） | `0` | — | `smoke-runs/probe-both-20261028-175544/` |

另有一次 `-SkipLaunch` 干跑通过（不启动编辑器，验证创建/安装/还原）：`smoke-runs/smoke-5.4-20261028-175814/`，退出码 `0`。

## 2. 用法

在仓库根目录执行（PowerShell 5.1 或 pwsh 7 均可）：

```powershell
# 5.4：使用仓库样例工程
powershell -NoProfile -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.4

# 5.7：首次运行会自动从 TP_BlankBP 建空白工程，然后跑完整流程
powershell -NoProfile -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.7

# 干跑：只做预检/建工程/装插件/改 .uproject，不启动编辑器，结束自动还原
powershell -NoProfile -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.7 -SkipLaunch

# 干跑并保留现场（供人工启动）
powershell -NoProfile -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.7 -SkipLaunch -KeepPrepared

# 5.4 / 5.7 探针对照（默认 both）
powershell -NoProfile -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_probe_run.ps1
```

参数：

| 参数 | 适用 | 默认 | 说明 |
| --- | --- | --- | --- |
| `-EngineVersion` | smoke | `5.4` | `5.4` / `5.7`；决定编辑器二进制与默认工程 |
| `-ProjectDir` | smoke | 见上表 | 目标工程目录；5.7 不存在时自动创建 |
| `-PluginSource` | smoke | `UEMCPBridge/` | 要安装的插件目录 |
| `-SkipLaunch` | smoke | 关 | 只准备、不启动；结束自动清理（除非 `-KeepPrepared`） |
| `-KeepPrepared` | smoke | 关 | 与 `-SkipLaunch` 连用：保留装好的工程供人工启动 |
| `-TimeoutSeconds` | smoke | `420` | 等待 `/health` 的超时 |
| `-EngineRoot` | smoke | `%ProgramFiles%\Epic Games\UE_<ver>` | 引擎安装根目录 |
| `-EngineVersion` | probe | `both` | `5.4` / `5.7` / `both` |
| `-ProjectDir54` / `-ProjectDir57` | probe | 同 smoke 默认 | 探针使用的工程 |
| `-TimeoutSeconds` | probe | `900` | 单个 commandlet 超时 |

## 3. 每一步做什么、产出什么证据

| 步骤 | 动作 | 证据文件 | 通过判据 |
| --- | --- | --- | --- |
| preflight | 校验引擎/插件源/工程；拒绝残留编辑器进程；独占探测 18778–18788；5.7 缺失时从 `TP_BlankBP` 复制并改 `EngineAssociation=5.7`、启用 3 个插件（保留原条目，幂等） | `plan.json`、`uproject.before.json` | 无可执行文件缺失、端口全空闲、`.uproject` 可解析 |
| prepare | 安装插件副本（跳过 `__pycache__`/`*.pyc`/历史证据），备份同名目标 | `run.json`（`pluginTarget`） | 约 48 个文件就位（含 `Tests/` 脚本） |
| launch | `UnrealEditor.exe <uproject> -log -nop4 -nosplash`，后台轮询发现文件与 `GET /health` | `discovery.json`、`health.json`、`editor-log-uemcp.txt`、`editor-log-path.txt` | 日志含 `[UEMCP] bridge_started`；`/health` 返回 200 且 `app=uemcp-bridge` |
| collect | 依次发送 8 个**只读** RPC（默认权限门下即可通过） | `rpc-01..08-*.json`、`viewport-capture.png` | 每条 `httpStatus=200`、`result.ok=true`、无 `error`；截图是合法 PNG 且 >1 KiB |
| cleanup | WM_CLOSE 优雅关闭（90 s），必要时强杀并清理孤儿发现文件；等待端口释放；删除插件副本；按字节还原 `.uproject` 并比对 SHA-256 | `cleanup.json`、`summary.txt` | `portsFree=true`、`pluginRemoved=true`、`uprojectRestored=true` |

8 个 RPC：`bridge.ping`、`bridge.capabilities`、`editor.status`、`actor.query`、`asset.search`、`level.control(get_current)`、`material.params(list, /Engine/BasicShapes/BasicShapeMaterial)`、`viewport.capture(640x360, png)`。全部只读，**不修改** `allowWrite/allowConsole/allowExec`。

证据目录结构（`<RepoRoot>/UEMCPBridge/Tests/smoke-runs/<kind>-<engine>-<stamp>/`）：

```text
smoke-5.4-20261028-175716/
├─ plan.json                  # 本次参数与将要执行的命令行
├─ uproject.before.json       # 修改前的字节（清理时按此还原）
├─ run.json                   # 汇总：时间/端口/pid/每条 RPC/清理状态
├─ summary.txt                # 人读摘要（含 RESULT 行）
├─ discovery.json             # ~/.uemcp/bridges/<sha1-16>.json 原文
├─ health.json                # /health 原文 JSON
├─ editor-log-path.txt        # 本次打开的日志绝对路径
├─ editor-log-uemcp.txt       # 日志中所有 [UEMCP] 行
├─ rpc-01-bridge-ping.json    # 请求 + HTTP 状态 + 响应 + 耗时
├─ ...
├─ rpc-08-viewport-capture.json
├─ viewport-capture.png       # 截图副本（仅当 <20 MB）
└─ cleanup.json               # 关闭方式/端口/还原校验结果

probe-both-20261028-175544/
├─ probe-5.4.json / probe-5.7.json     # 探针原始报告（逐 API）
├─ probe-5.4.stdout.log / .stderr.log  # commandlet 输出
├─ result-5.4.json / result-5.7.json   # 退出码/超时/必检失败数
├─ compare.md                          # 5.4 vs 5.7 逐项对照表
└─ summary.txt
```

## 4. 实跑摘录

关键日志行（路径按占位符替换）：

```text
[UEMCP] bridge_started port=18778 pid=<pid> project=<ProjectDir>
```

`/health` 摘要：

| 引擎 | ueVersion | capabilities.screenshot | capabilities.blueprintCompile | rateLimit |
| --- | --- | --- | --- | --- |
| 5.4.4 | `5.4.4-35576357+++UE5+Release-5.4` | true | true | enabled 30/30 |
| 5.7.4 | `5.7.4-51494982+++UE5+Release-5.7` | true | true | enabled 30/30 |

8 个 RPC（耗时 ms）：

| RPC | 5.4 | 5.7 |
| --- | --- | --- |
| bridge.ping | 11 | 12 |
| bridge.capabilities | 0 | 0 |
| editor.status | 9 | 5 |
| actor.query（limit 5） | 5 | 5 |
| asset.search（/Game） | 102 | 7 |
| level.control get_current | 2 | 3 |
| material.params list | 5 | 5 |
| viewport.capture | 464 | 399 |

补充观测：

- `actor.query` 两版都返回 `total=138`，首个对象是 `DirectionalLight`；`level.control` 均为 `/Temp/Untitled_1`（引擎默认启动关卡，含 `WorldPartitionHLOD` actor）。
- `asset.search`：5.4 为 267（样例工程含 StarterContent），5.7 为 0（空白工程），符合预期。
- 截图均为合法 PNG：5.4 `326060` 字节、5.7 `339438` 字节；人工查看为真实地形视口，非黑屏。冷启动首次截图可能到 15 s（首次运行实测 14902 ms，预热后 0.4–0.5 s），脚本按 90 s HTTP 超时兜底。
- 清理：两版均 `forced=false`（WM_CLOSE 优雅退出）、`portsFree=true`、`pluginRemoved=true`、`uprojectRestored=true`（SHA-256 与运行前一致）。
- 探针：两版 13/13 必检项通过，退出码 0；差异只有 `asset_registry.gameAssets`（267 vs 0）和版本号，其余 API 形状一致。`worldPartitionProperty` 两版均为 `unavailable (Exception)`，与 README「已知限制」一致。

## 5. 未自动化 / 需人工确认的项

| 项 | 原因 | 人工怎么做 |
| --- | --- | --- |
| 编辑器界面是否正常（弹窗、报错对话框、欢迎页） | 脚本只等 `/health`，无法判断 UI 是否被模态框挡住 | 启动后看屏幕；异常时看 `editor-log-tail.txt` 与 `Saved/Logs/*.log` |
| 截图画面是否符合预期 | 只校验 PNG 头、尺寸与体积 | 打开证据目录里的 `viewport-capture.png` |
| 首次运行/升级后的许可、崩溃上报、模板提示 | 一次性交互，无法稳定脚本化 | 首次跑时人工点掉；后续运行不再出现 |
| 高 DPI / 多显示器下的取景差异 | 与机器显示配置相关 | 需要时人工对比不同机器截图 |
| MCP 客户端 → TS Server → Bridge 的完整链路 | 本脚本只覆盖 Bridge HTTP 层（TS 侧不在本岗位边界） | 由 Server 侧 smoke/联调用例覆盖 |
| PIE 内截图、真实事务回滚等破坏性用例 | 需要 allowWrite/allowExec 与场景准备 | 按 `COMPAT-UE57.md` §5 的 V2/V3/V6 手动执行 |

## 6. 失败处理与退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 全部通过（清理也通过） |
| `1` | preflight / prepare 失败（引擎/工程/端口/进程/插件源） |
| `2` | 启动失败或等待 `/health` 超时 |
| `3` | 采集阶段失败（RPC 非 200、`result.ok!=true`、截图无效、日志缺 `bridge_started`） |
| `4` | 清理不完整（端口未释放、`.uproject` 还原失败等） |

失败时脚本会打印失败步骤、`REPRO:` 复现命令和证据目录，并在证据目录写 `failure.json`。常见原因：

- **端口被占**：上一次编辑器没关干净 → `Get-Process UnrealEditor*` 后关闭；
- **等待超时**：5.7 首次打开要编译着色器 → 加 `-TimeoutSeconds 600` 重试；
- **工程打不开**：看 `Saved/Logs/*.log` 末尾；确认 `.uproject` 的 `EngineAssociation` 与 `-EngineVersion` 一致；
- **RPC 失败**：看对应 `rpc-*.json` 的 `response.error.data.errorCode`。

## 7. 安全与还原保证

- 只写入 `-ProjectDir` 指定的工程；仓库样例工程结束后**删除插件副本**并把 `.uproject` 按字节还原（SHA-256 比对，失败即退出码 4）。
- 正常关闭由编辑器自身触发 `bridge.stop()`，删除发现文件并释放端口；仅在强制关闭时才由脚本按 `pid+token` 清理孤儿发现文件。
- 运行前后都检查 18778–18788，确认无残留监听。
- 采集的 8 个 RPC 全部只读，不触碰 `allowWrite/allowConsole/allowExec` 门。
- 证据 JSON 里会出现本次运行的工程绝对路径（运行时数据，不是文档里的示例路径）；发布打包时不需要包含 `Tests/smoke-runs/`。

## 8. 本轮对测试工具的修正（非产品代码）

探针 `probe_ue57.py` 在真机预跑时暴露两个自身缺陷，已修复：

1. 用 `unreal.SystemLibrary.is_editor()` 判断编辑器模式，但该 API 实际是模块级 `unreal.is_editor()`，导致探针在命令下一启动就 `exit 2`；现改为两处都探测、失败降级为 `null`。
2. `-run=pythonscript` 下 UE 只把脚本路径放进 `sys.argv`，`--out`/`--blueprint` 等参数收不到；现同时解析 `unreal.SystemLibrary.get_command_line()`（带引号拆分）。

`Content/Python/` 下的 Bridge 产品代码与 `UEMCPBridge.uplugin` 未改动。
