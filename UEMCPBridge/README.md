# UEMCP Bridge（UE 5 编辑器侧，v0.1.0）

面向 Unreal Engine 5 编辑器的本地 HTTP JSON-RPC 桥接插件，是 UEMCP 双进程架构中的编辑器执行层。纯 Python，无 C++ 模块，不需要编译。

当前适配：**UE 5.4.4 与 UE 5.7.4**（引擎自带 Python 均为 3.11）。5.7 的逐调用点核查结论见 [`COMPAT-UE57.md`](COMPAT-UE57.md)，不写死引擎版本。

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
├─ Tools/stamp_uplugin.py           # 打包时注入 EngineVersion（标准库）
└─ Tests/                           # 11 个无编辑器自检 + 引擎冒烟/探针
```

## 2. 启用与启动

1. 插件已放在 `<Project>/Plugins/UEMCPBridge/`。
2. 项目 `XQHCPP_54.uproject` 已启用（本插件交付时一并修改）：
   - `PythonScriptPlugin`
   - `EditorScriptingUtilities`
   - `UEMCPBridge`
3. 启动编辑器。`init_unreal.py` 在第一个 Slate tick 后自动启动 Bridge：
   - 监听 `127.0.0.1:18778`；被占用时依次尝试 `18779–18788`，再失败使用系统临时端口；
   - 写发现文件 `~/.uemcp/bridges/<projectHash>.json` 与 `~/.uemcp/bridge.json`；
   - 编辑器正常退出时删除发现文件并释放端口。
4. 失败不会阻断编辑器；查看 `Saved/Logs/*.log` 中的 `[UEMCP]` 行。

插件描述符**不写死引擎版本**（无 `EngineVersion` 字段），因此同一份源码可直接被 5.4 或 5.7 加载。需要固定版本的发行包用脚本注入：

```bash
python UEMCPBridge/Tools/stamp_uplugin.py --engine-root "C:\Program Files\Epic Games\UE_5.7" --out dist/UEMCPBridge.uplugin
# 或显式指定版本：--engine 5.7.4
```

验证：

```bash
curl -s http://127.0.0.1:18778/health
```

预期返回 `app=uemcp-bridge`，含 `ueVersion`、`port`、`pid`、`capabilities`、`rateLimit`。

## 3. 配置

优先级：环境变量 > `<Project>/Saved/UEMCP/bridge-settings.json` > 默认值。

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

默认全部权限门关闭（只读）。写操作、控制台、Python 执行必须分别显式开启。

全局限流默认 `30 req/s`、突发 30（架构 §6.7）。超限请求在**入队之前**被拒绝：`HTTP 429` + JSON-RPC `-32012` + `errorCode="RATE_LIMITED"` + `retryable=true`，不产生任何编辑器副作用；`rateLimitEnabled=false` 或 `rateLimitPerSecond=0` 可关闭。

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

成功响应 `result`：`{"ok":true,"data":{},"warnings":[],"meta":{requestId,durationMs,ueVersion,pluginVersion}}`；失败为 JSON-RPC `error`，`data.errorCode` 使用架构文档 §2.9.3 的字符串码。

## 6. 能力缺口（§8.1）

| 能力 | MVP 行为 |
| --- | --- |
| 蓝图节点创建/连线/删除、动画蓝图编辑 | `CAPABILITY_UNAVAILABLE`（`details.suggestion` 指向 P2 C++ 模块） |
| 控制台输出回显 | 执行成功但 `outputAvailable:false`；`captureOutput=true` 时附 `OUTPUT_CAPTURE_UNSUPPORTED` 警告 |
| 蓝图节点读取 | experimental：成功则 `capabilities.blueprintNodeRead=true`，失败降级为 `nodes:[]` + `NODE_INSPECTION_UNSTABLE` |
| 编辑器 UI/Slate 截图 | 不支持（仅视口/PIE 高分辨率截图） |
| Python 沙箱/中断 | 不支持；超时仅停止等待 |

## 7. 冒烟自测

```bash
"C:\Program Files\Epic Games\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" \
  "C:\UE5_P\5.4\XQHCPP_54\XQHCPP_54.uproject" \
  -run=pythonscript \
  -script="C:\UE5_P\5.4\XQHCPP_54\Plugins\UEMCPBridge\Tests\smoke_bridge.py"
```

脚本会启动 HTTP 层（同步 dispatcher，commandlet 无 Slate tick），自检 `/health`、`bridge.ping`、错误 token（401）、执行门（`EXEC_DISABLED`）、写门（`PERMISSION_DENIED`）、参数校验路径（`INVALID_ARGUMENT` → HTTP 400 / JSON-RPC -32602 / `details.issues`），然后保持监听 `SMOKE_HOLD_SECONDS`（默认 12 秒）供外部 curl。

无需编辑器的补充自检（引擎自带 Python 3.11 或任意 Python 3.11+ 均可）：

```bash
python Plugins/UEMCPBridge/Tests/check_error_codes.py           # 静态错误码表覆盖 + INVALID_ARGUMENT 契约
python Plugins/UEMCPBridge/Tests/check_handler_names.py         # 静态未定义名称扫描（缺失导入回归）
python Plugins/UEMCPBridge/Tests/test_serialization.py          # FQuat/FTransform 序列化回归
python Plugins/UEMCPBridge/Tests/test_class_path_resolution.py  # 类名/类路径/蓝图生成类解析（stub）
python Plugins/UEMCPBridge/Tests/test_dependency_options.py     # 依赖选项映射与查询降级
python Plugins/UEMCPBridge/Tests/test_python_error_mapping.py   # Python 异常 → PYTHON_ERROR
python Plugins/UEMCPBridge/Tests/test_discovery_lifecycle.py    # 发现文件清理与 stale 标记
python Plugins/UEMCPBridge/Tests/test_port_fallback.py          # 占用 18778，断言回退到 18779
python Plugins/UEMCPBridge/Tests/test_rate_limit.py             # 全局令牌桶 + HTTP 429 RATE_LIMITED（入队前）
python Plugins/UEMCPBridge/Tests/test_uplugin_metadata.py       # .uplugin 不写死版本 + stamp 脚本
python Plugins/UEMCPBridge/Tests/test_bridge_timeout_http.py    # 真实 dispatcher 超时 → 504 BRIDGE_TIMEOUT
```

真实引擎探针（结论以探针为准，需 UnrealEditor-Cmd）：

```bash
# FQuat/FTransform 序列化
UnrealEditor-Cmd.exe <Project>.uproject -run=pythonscript \
  -script=Plugins/UEMCPBridge/Tests/probe_transform.py -unattended -nop4 -nosplash -nullrhi
# 类解析 / spawn / 依赖查询 / classPath（结果写入 Saved/UEMCP/probe_defect4_verify.json）
UnrealEditor-Cmd.exe <Project>.uproject -run=pythonscript \
  -script=Plugins/UEMCPBridge/Tests/probe_defect4_verify.py -unattended -nop4 -nosplash -nullrhi
# 5.7 兼容性全量探针（只读；--live-actors --capture --console 需真实编辑器会话）
UnrealEditor-Cmd.exe <Project>.uproject -run=pythonscript \
  -script=Plugins/UEMCPBridge/Tests/probe_ue57.py -unattended -nop4 -nosplash \
  --blueprint /Game/<BP> --material /Game/<MI>
```

5.7 的逐调用点核查结论、真机验证步骤与已知限制见 [`COMPAT-UE57.md`](COMPAT-UE57.md)。

## 8. 商标

Unreal and Unreal Engine are trademarks or registered trademarks of Epic Games, Inc. in the United States and elsewhere. This project is an independent, community-developed tool and is not affiliated with, endorsed by, or sponsored by Epic Games, Inc.
