# UEMCP Bridge（UE 5 编辑器侧，v0.1.0）

面向 Unreal Engine 5 编辑器的本地 HTTP JSON-RPC 桥接插件，是 UEMCP 双进程架构中的编辑器执行层。纯 Python，无 C++ 模块，不需要编译。

当前适配：**UE 5.4.4 与 UE 5.7.4**（引擎自带 Python 均为 3.11.8）。5.7 的逐调用点核查结论见 [`COMPAT-UE57.md`](COMPAT-UE57.md)，插件不写死引擎版本。

本文档自包含：限流配置见 §3.1，本轮行为变化见 §7，5.7 兼容与验证见 §8，已知限制见 §9，自测见 §10。

依据：《UEMCP 架构设计与工具清单》v0.2.0（§2.3、§2.4、§2.6、§2.8、§5、§6、§8.1）。

## 1. 目录

```
UEMCPBridge/
├─ UEMCPBridge.uplugin              # Type=Editor, Modules=[], 不写死 EngineVersion
├─ COMPAT-UE57.md                   # 5.7 兼容性核查表（逐 unreal.* 调用点）
├─ Content/Python/
│  ├─ init_unreal.py                # 编辑器启动后自动拉起 Bridge（失败只写日志）
│  └─ uemcp_bridge/
│     ├─ server.py                  # ThreadingHTTPServer：/health、/rpc、/events
│     ├─ rpc.py                     # RPC 路由 + 限流 + 权限门（入队前）
│     ├─ ratelimit.py               # 全局令牌桶（默认 30 req/s，可配置/可关闭）
│     ├─ dispatcher.py              # 游戏线程单队列（Slate post-tick 泵）
│     ├─ discovery.py               # 发现文件原子写/按 PID+token 删除
│     ├─ security.py                # token / 回环 / Host / Origin
│     ├─ errors.py                  # 契约错误码 → JSON-RPC 码/HTTP 状态
│     ├─ settings.py                # 环境变量 > Saved/UEMCP/bridge-settings.json > 默认
│     ├─ serialization.py           # UE 类型 → JSON
│     └─ handlers/                  # 10 个工具对应的 12 个 RPC method
├─ Tools/stamp_uplugin.py           # 打包时注入 EngineVersion（标准库；仅源码仓库，发行包内不含）
└─ Tests/                           # 11 个无编辑器自检 + 引擎冒烟/探针
```

> **发行包（zip）与源码仓库的差异**：发行包内含 `UEMCPBridge.uplugin`（打包时已注入 `EngineVersion` 与版本化 `Description`）、`Content/`、`README.md`、`LICENSE`（MIT 全文）、`COMPAT-UE57.md`（5.7 兼容核查表）与 `Tests/`（`*.py` 自检脚本及 `Tests/SMOKE-REAL-ENGINE.md` 真机验证说明；不含 `*.ps1` 执行器与 `smoke-runs/` 运行产物）。`Tools/` 与 `Tests/*.ps1` **仅在源码仓库中提供**（not included in the archive）：`Tools/stamp_uplugin.py` 由维护者在打包时执行，`ue_smoke_run.ps1` / `ue_probe_run.ps1` / `ue_common.ps1` 是维护者的一键真机执行器，二者均不随包分发；下文凡引用上述文件之处，均指源码仓库中的副本。发行包内的 `Tests/*.py` 自检可在解包后直接运行（第 10 项 `test_uplugin_metadata.py` 依赖 `Tools/`，请在源码检出中运行）。

## 2. 启用与启动

> 文档占位符：`<UE_ROOT>` = 引擎安装根目录（Windows 默认位于 `Program Files\Epic Games\UE_5.7`，按你的实际版本替换）；`<YourProject>` = 你的 UE 工程目录；`<RepoRoot>` = 本仓库根目录。

1. 插件已放在 `<YourProject>/Plugins/UEMCPBridge/`。
2. 项目 `<YourProject>.uproject` 已启用（本插件交付时一并修改）：
   - `PythonScriptPlugin`
   - `EditorScriptingUtilities`
   - `UEMCPBridge`
3. 启动编辑器。`init_unreal.py` 在第一个 Slate tick 后自动启动 Bridge：
   - 监听 `127.0.0.1:18778`；被占用时依次尝试 `18779–18788`，再失败使用系统临时端口；
   - 写发现文件 `~/.uemcp/bridges/<projectHash>.json` 与 `~/.uemcp/bridge.json`；
   - 编辑器正常退出时删除发现文件并释放端口。
4. 失败不会阻断编辑器；查看 `Saved/Logs/*.log` 中的 `[UEMCP]` 行。

插件描述符**不写死引擎版本**（无 `EngineVersion` 字段），因此同一份源码可直接被 5.4 或 5.7 加载。需要固定版本的发行包由维护者在打包时注入（工具仅在源码仓库中可用，发行包内不含该工具）：

```bash
python UEMCPBridge/Tools/stamp_uplugin.py --engine-root "<UE_ROOT>" --out dist/UEMCPBridge.uplugin
# 或显式指定版本：--engine 5.7.4
```

验证：

```bash
curl -s http://127.0.0.1:18778/health
```

预期返回 `app=uemcp-bridge`，含 `ueVersion`、`port`、`pid`、`capabilities`、`rateLimit`。

## 3. 配置

优先级：环境变量 > `<YourProject>/Saved/UEMCP/bridge-settings.json` > 默认值。

```json
{
  "port": 18778,
  "allowWrite": false,
  "allowConsole": false,
  "allowExec": false,
  "consoleAllowlist": ["stat", "show", "r.", "sg.", "viewmode", "log", "help", "dumpticks", "obj", "memreport", "camera"],
  "maxQueueSize": 64,
  "requestTimeoutMs": 30000,
  "searchTimeoutMs": 20000,
  "rateLimitEnabled": true,
  "rateLimitPerSecond": 30,
  "rateLimitBurst": 30
}
```

环境变量：`UEMCP_BRIDGE_PORT`、`UEMCP_BRIDGE_ALLOW_WRITE`、`UEMCP_BRIDGE_ALLOW_CONSOLE`、`UEMCP_BRIDGE_ALLOW_EXEC`、`UEMCP_BRIDGE_TOKEN_FILE`、`UEMCP_BRIDGE_RATE_LIMIT_ENABLED`、`UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND`、`UEMCP_BRIDGE_RATE_LIMIT_BURST`。

### 3.1 全局限流

架构 §6.7 要求桥接端全局 30 req/s。本版本实现为**令牌桶**，默认开启：

| 配置键 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `rateLimitEnabled` | `UEMCP_BRIDGE_RATE_LIMIT_ENABLED` | `true` | 总开关；`false` 完全关闭限流 |
| `rateLimitPerSecond` | `UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND` | `30` | 每秒补充的令牌数；设为 `0` 等价于关闭 |
| `rateLimitBurst` | `UEMCP_BRIDGE_RATE_LIMIT_BURST` | `30` | 桶容量（允许的瞬时突发）；未配置时默认等于 `rateLimitPerSecond` |

- 判定发生在**权限门之前、游戏线程入队之前**：被拒绝的请求不排队、不触达 `unreal`，不会产生任何编辑器副作用。
- 超限响应：`HTTP 429`，JSON-RPC `error.code = -32012`，`error.data.errorCode = "RATE_LIMITED"`，`error.data.retryable = true`，`details` 含 `gate="bridge.rateLimit"`、`limitPerSecond`、`burst`、`retryAfterMs`；响应中没有 `result`。
- 关闭方式（二选一）：`"rateLimitEnabled": false`，或 `"rateLimitPerSecond": 0`；也可用同名环境变量覆盖。
- `/health` 的 `rateLimit` 字段实时展示 `enabled / perSecond / burst / available / accepted / rejected`，便于确认当前策略。
- `GET /health` 与 `GET /events` 不受限流影响（发现与心跳不会被误伤）。

默认全部权限门关闭（只读）。写操作、控制台、Python 执行必须分别显式开启。

## 4. 安全

- 仅绑定 `127.0.0.1`；非回环 peer 直接拒绝。
- `Host` 只接受 `127.0.0.1[:port]` / `localhost[:port]`；`Origin` 只接受回环或 `null`；不启用 CORS，`OPTIONS` 返回 405。
- `/rpc` 必须携带 `X-UEMCP-Token`；token 为 32 字节随机数（base64url），每次编辑器启动轮换，仅写入本机发现文件（0600，尽力而为）。
- 全局令牌桶限流（默认 30 req/s）在**权限门与入队之前**判定，超限请求不排队、不触达 `unreal`。
- 权限门在**游戏线程入队之前**执行，拒绝不会产生任何编辑器副作用。
- 写操作使用 `ScopedEditorTransaction`；PIE 运行中拒绝写操作（`EDITOR_UNSAFE_STATE`）。
- 控制台命令：白名单前缀（11 项，见架构 §5.8）+ 永久拒绝表（`quit`/`exit`/`py`/`exec`/`open` 等）。
  - **单一事实来源**：白名单定义在 `uemcp_bridge/settings.py::DEFAULT_CONSOLE_ALLOWLIST`，永久拒绝表定义在 `uemcp_bridge/handlers/console.py::PERMANENTLY_DENIED`。`shared` 中的同名表仅作文档/死代码，不再逐字维护；如在 server 侧使用，由后端引用或删除，Bridge 侧不复制。
- Python 执行的超时只限制 HTTP 等待，**不能中断**已在游戏线程运行的代码；`allowExec=true` 等价于把编辑器控制权交给调用方，生产/演示环境不要开启。

## 5. RPC 方法

| method | 工具 | 最低权限 |
| --- | --- | --- |
| `bridge.ping` | 公共 | 无 |
| `bridge.capabilities` | `ue_editor_status` | 无 |
| `editor.status` | `ue_editor_status` | read-only |
| `actor.query` | `ue_actor_query` | read-only |
| `actor.edit` | `ue_actor_edit` | `allowWrite` |
| `level.control` | `ue_level_control` | 写动作需 `allowWrite` |
| `asset.search` | `ue_asset_search` | read-only |
| `material.params` | `ue_material_params` | 写动作需 `allowWrite` |
| `viewport.capture` | `ue_viewport_capture` | read-only |
| `console.command` | `ue_console_command` | `allowConsole` |
| `python.exec` | `ue_python_exec` | `allowExec` |
| `blueprint.query` | `ue_blueprint` | 写动作（compile）需 `allowWrite` |
| `pie.control` | `ue_pie_control` | `status` 只读；`start`/`stop`/`restart` 需 `allowWrite` |

成功响应 `result`：`{"ok":true,"data":{},"warnings":[],"meta":{requestId,durationMs,ueVersion,pluginVersion}}`；失败为 JSON-RPC `error`，`data.errorCode` 使用架构文档 §2.9.3 的字符串码。

## 6. 能力缺口（§8.1）

| 能力 | MVP 行为 |
| --- | --- |
| 蓝图节点创建/连线/删除、动画蓝图编辑 | `CAPABILITY_UNAVAILABLE`（`details.suggestion` 指向 P2 C++ 模块） |
| 控制台输出回显 | 执行成功但 `outputAvailable:false`；`captureOutput=true` 时附 `OUTPUT_CAPTURE_UNSUPPORTED` 警告 |
| 蓝图节点读取 | experimental：成功则 `capabilities.blueprintNodeRead=true`，失败降级为 `nodes:[]` + `NODE_INSPECTION_UNSTABLE` |
| 编辑器 UI/Slate 截图 | 不支持（仅视口/PIE 高分辨率截图） |
| Python 沙箱/中断 | 不支持；超时仅停止等待 |

## 7. 本轮行为变化（升级必读）

协议与方法名不变，但有 5 处可观察变化。**从旧包升级的 5.4 用户请先读这一节。**

| 变化 | 你会感觉到什么 | 如何恢复旧行为 |
| --- | --- | --- |
| 全局限流默认开启（30 req/s、突发 30） | 此前不限流；持续高并发调用（例如脚本批量遍历）会开始收到 `HTTP 429` / `RATE_LIMITED` | `rateLimitEnabled=false` 或 `rateLimitPerSecond=0`（见 §3.1） |
| `/health` 新增 `rateLimit` 字段 | 只增字段，旧解析器不受影响 | 无需处理 |
| `level.control` 的 `list_dirty`：`isMap` 由恒 `false` 改为 `true` | 返回的每个脏包都是地图包（来源就是 `get_dirty_map_packages()`），字段现在说了真话 | 无（旧值是错的） |
| `viewport.capture` 的 `format` 改为文件真实格式，并新增 `FORMAT_MISMATCH` / `SCREENSHOT_FALLBACK_PATH` 警告 | 请求 `jpeg` 时返回 `format:"png"`（引擎只写 PNG），并附 `FORMAT_MISMATCH`；走回退取图时附 `SCREENSHOT_FALLBACK_PATH` | 无（旧行为会谎报格式） |
| `.uplugin` 不再声明 `EngineVersion` | 本地 5.4/5.7 都能直接加载；发行包需打包时注入版本 | 打包命令见 §2 |

## 8. 引擎版本与 UE 5.7 兼容性

**结论：本插件在 UE 5.4.4 与 UE 5.7.4 上不需要版本分支代码。** 全部 83 处 `unreal.*` 调用点（46 个不同符号）在两版引擎中均存在，签名与返回类型无破坏性变化；仅有两处向后兼容的函数增量（`DuplicateActor` 新增重载、static switch setter 新增可选尾参）。

逐调用点核查表（调用点 / 5.4 状态 / 5.7 状态 / 依据 / 是否需改）、7 项真机验证步骤、证据来源与已知限制见 [`COMPAT-UE57.md`](COMPAT-UE57.md)（随发行包分发）。

怎么确认你的环境兼容：

1. 启动编辑器后看 `GET /health`：`ueVersion` 应为 `5.4.x` 或 `5.7.x`，`capabilities` 含 `screenshot` / `blueprintCompile` / `pieControl`，并出现 `rateLimit`；
2. 同一响应里核对可追溯字段：`pluginVersion`（应等于 `.uplugin` 的 `VersionName`，本版为 `0.1.3`）、`buildHash`（插件 Python 全量 sha256）、`buildTime`、`sourcePath`（**实际加载的插件目录**，用于排除「备份目录顶替」）、`instanceId`；
3. 跑 §10.2 的 14 个无编辑器自检，全部 exit 0；
4. 需要引擎的用例按 §10.1 跑 `smoke_bridge.py`（看到 `SMOKE_RESULT PASS`）与 `probe_ue57.py`（看到 `RESULT PASS`，报告写入 `<YourProject>/Saved/UEMCP/probe_ue57.json`）。

## 9. 已知限制

| 项 | 现状 | 说明 |
| --- | --- | --- |
| `level.control` / `editor.status` 的 `isPartitioned` | 恒 `false` | `UWorld::IsPartitionedWorld()` 不是 `UFUNCTION`，`world_partition` 也不是 UPROPERTY，纯 Python 读不到；需 C++ 或引擎侧新增绑定，超出本插件边界 |
| `.uplugin` 的 `EngineVersion` | 源码中缺省 | 发行包在打包时由维护者注入（源码仓库内完成）；缺省时任意 UE5 版本均可加载 |
| `jpeg` 截图 | 引擎只产出 PNG | 响应按真实格式返回并附 `FORMAT_MISMATCH`；不做转码（不引入第三方依赖） |
| 截图回退 | 引擎可能忽略绝对目标路径 | 回退到 `Saved/Screenshots` 下最新 PNG，并附 `SCREENSHOT_FALLBACK_PATH` |

其余能力边界（蓝图节点编辑、控制台回显、Python 中断、UI 截图）见 §6。

## 10. 自测

### 10.1 需要引擎的用例

`smoke_bridge.py` 与 `probe_ue57.py` 必须由 `UnrealEditor-Cmd.exe` 执行（依赖真实 `unreal` 模块）；`probe_transform.py`、`probe_defect4_verify.py` 同理。

先确认 `<YourProject>/Plugins/UEMCPBridge/` 指向本插件（开发期可用目录联接或拷贝），然后：

```bat
:: HTTP 全链路冒烟（判定 SMOKE_RESULT PASS）
"<UE_ROOT>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "<YourProject>\<YourProject>.uproject" -run=pythonscript -script="<RepoRoot>\UEMCPBridge\Tests\smoke_bridge.py" -unattended -nop4 -nosplash -nullrhi

:: 5.7 兼容性全量探针（判定 RESULT PASS；报告写入 Saved/UEMCP/probe_ue57.json）
"<UE_ROOT>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "<YourProject>\<YourProject>.uproject" -run=pythonscript -script="<RepoRoot>\UEMCPBridge\Tests\probe_ue57.py" -unattended -nop4 -nosplash

:: FQuat / FTransform 序列化探针
"<UE_ROOT>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "<YourProject>\<YourProject>.uproject" -run=pythonscript -script="<RepoRoot>\UEMCPBridge\Tests\probe_transform.py" -unattended -nop4 -nosplash -nullrhi

:: 类解析 / spawn / 依赖查询 / classPath（结果写入 Saved/UEMCP/probe_defect4_verify.json）
"<UE_ROOT>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "<YourProject>\<YourProject>.uproject" -run=pythonscript -script="<RepoRoot>\UEMCPBridge\Tests\probe_defect4_verify.py" -unattended -nop4 -nosplash -nullrhi
```

- `smoke_bridge.py`：启动 HTTP 层（同步 dispatcher，commandlet 无 Slate tick），自检 `/health`、`bridge.ping`、错误 token（401）、执行门（`EXEC_DISABLED`）、写门（`PERMISSION_DENIED`）、参数校验路径（`INVALID_ARGUMENT` → HTTP 400 / -32602 / `details.issues`），随后保持监听 `SMOKE_HOLD_SECONDS`（默认 12 秒）供外部 curl。判定：`SMOKE_RESULT PASS`。
- `probe_ue57.py`：默认只读，输出各 `unreal.*` API 的可用性与取值到 `Saved/UEMCP/probe_ue57.json`；`--live-actors`、`--capture`、`--console` 会创建编辑器状态，仅在一次性测试工程使用；可加 `--blueprint /Game/<BP>`、`--material /Game/<MI>`。判定：`RESULT PASS`。

### 10.2 无需编辑器的 11 个自检

用引擎自带 Python（UE 5.4.4 / 5.7.4 均为 3.11.8）逐个执行，也可用任意 Python 3.11+：

```powershell
$py = "<UE_ROOT>\Engine\Binaries\ThirdParty\Python3\Win64\python.exe"
Get-ChildItem "<RepoRoot>\UEMCPBridge\Tests" -Filter *.py |
  Where-Object { $_.Name -match '^(check_|test_)' } |
  ForEach-Object { & $py $_.FullName; "exit=$LASTEXITCODE  $($_.Name)" }
```

预期 11 个脚本全部 `exit=0`：

| # | 脚本 | 覆盖 |
| --- | --- | --- |
| 1 | `check_error_codes.py` | 错误码表覆盖 + `INVALID_ARGUMENT` 契约 |
| 2 | `check_handler_names.py` | 未定义名称静态扫描（缺失导入回归） |
| 3 | `test_serialization.py` | FQuat / FTransform 序列化 |
| 4 | `test_class_path_resolution.py` | 类名 / 类路径 / 蓝图生成类解析（stub） |
| 5 | `test_dependency_options.py` | 依赖选项映射与查询降级 |
| 6 | `test_python_error_mapping.py` | Python 异常 → `PYTHON_ERROR` |
| 7 | `test_discovery_lifecycle.py` | 发现文件清理与 stale 标记 |
| 8 | `test_port_fallback.py` | 占用 18778，断言回退到 18779 |
| 9 | `test_rate_limit.py` | 令牌桶、配置优先级、HTTP 429 `RATE_LIMITED`、入队前拦截 |
| 10 | `test_uplugin_metadata.py` | `.uplugin` 不写死版本 + `stamp_uplugin.py` |
| 11 | `test_bridge_timeout_http.py` | 真实 dispatcher 超时 → HTTP 504 `BRIDGE_TIMEOUT` |

本次交付已在 UE 5.4.4 自带 Python 3.11.8 上实跑，11/11 exit 0；需要引擎的 4 个脚本（`smoke_bridge.py`、`probe_ue57.py`、`probe_transform.py`、`probe_defect4_verify.py`）待与 QA 用 5.7 工程联跑。

一键真机验证（自动装插件、启动编辑器、采集 8 个 RPC、关闭并还原工程）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_smoke_run.ps1 -EngineVersion 5.7
powershell -NoProfile -ExecutionPolicy Bypass -File UEMCPBridge\Tests\ue_probe_run.ps1
```

用法、每步证据与已知不可自动化项见 [`Tests/SMOKE-REAL-ENGINE.md`](Tests/SMOKE-REAL-ENGINE.md)（随发行包分发）。

> 注：上述 `.ps1` 执行器（`ue_smoke_run.ps1` / `ue_probe_run.ps1` / `ue_common.ps1`）仅在源码仓库中提供（not included in the archive）——它们会启动编辑器、写入 `~/.uemcp` 与 `Saved/`，属维护者工具，不随包分发；发行包内只含 Python 自检脚本。

## 11. 商标

Unreal and Unreal Engine are trademarks or registered trademarks of Epic Games, Inc. in the United States and elsewhere. This project is an independent, community-developed tool and is not affiliated with, endorsed by, or sponsored by Epic Games, Inc.

## 12. 许可（License）

本项目代码以 MIT 许可发布：发行包内附带 MIT 全文（`UEMCPBridge/LICENSE`，与源码仓库根 `LICENSE` 完全一致），不是指针或摘要。

MIT 许可仅覆盖本仓库中的项目代码，**不覆盖** Unreal Engine 引擎本身（受 Epic Games《Unreal Engine 最终用户许可协议》约束），也**不覆盖**你在自己工程中创建的资产与内容；把本插件放入你的工程时，请自行确认与适用许可的兼容性。

## 13. 三个常见使用坑（升级与排错必读）

业务团队两天真实试用中踩到、并为此浪费过排查时间的三个坑。升级或排错前先读：

1. **`Plugins/` 目录扫描坑：升级备份可能顶掉新版。** `Plugins/` 下任何含 `.uplugin` 描述符的目录都会被引擎当作插件扫描。做升级备份时如果直接把 `UEMCPBridge` 复制成 `Plugins/UEMCPBridge.bak`，备份里的旧描述符仍会被扫描；当日志出现 `second location will be ignored` 时，引擎实际加载运行的**可能仍是旧代码**。正确做法：备份时把描述符一并改名（如 `UEMCPBridge.uplugin.bak`），或把整个备份目录移出 `Plugins/`。
2. **版本辨识：只看 `pluginVersion` 不够。** 历史上出现过两个不同构建共用同一个版本号的情况。升级后请核对 `GET /health` 的 `buildHash` 与 `sourcePath`（**本版新增**字段）：字段存在且值与升级前不同，才说明引擎加载了新构建；若 `/health` 响应里没有这两个字段，说明加载的仍是旧包（结合第 1 条排查 `Plugins/` 下的多副本）。
3. **两个会导向错误结论的 Python 绑定：**
   - `unreal.GameplayStatics.project_world_to_screen` 返回 **`Vector2D`**，不是 `(bool, Vector2D)` 元组——按“返回值第一位是 bool”写出的判断会静默地得出错误结论。
   - `TraceTypeQuery` 可用的枚举成员名与直觉不同：不要照搬 C++ 的 trace channel 名，先用 Python 打印 `unreal.TraceTypeQuery` 的实际成员，再写代码。
