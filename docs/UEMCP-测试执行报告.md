# UEMCP MVP 测试执行报告

| 项 | 值 |
|---|---|
| 报告版本 | 1.2（2026-10-20，v1.1 + 最终端到端复测轮） |
| 测试执行 | 测试角色（会话 f785ec80-67ad-401a-b02b-52b779261daf） |
| 依据 | 《UEMCP MVP 测试计划与验收标准》v0.1.1（86 条用例）、《UEMCP 架构设计》v0.2.0 |
| 被测版本 | MCP Server 0.1.0（`uemcp/packages/server/dist/index.js`，开发自测后交付）；UEMCPBridge 0.1.0（含主管确认的 3 项修复：Critical-1 INVALID_ARGUMENT 错误码等，编辑器 PID 57376 起生效） |
| 环境 | Windows 11 Pro 10.0.26200；Node v24.18.0；UE 5.4.4-35576357；工程 `C:\UE5_P\5.4\XQHCPP_54`；编辑器 UnrealEditor.exe 5.4 |

---

## 1. 总体结论

**v1.2（最终复测后）：全部 6 个缺陷均已验证修复，无未决缺陷——可进入联调。**

| 维度 | 结论 | 证据 |
|---|---|---|
| 阶段 A：Server 侧（协议/策略/安全/传输/审计） | **全部通过** | smoke 65/65；runner-a/b/sse 共 33 项断言全 PASS |
| 阶段 B：真实编辑器集成 | **全部通过**（复测轮 + 最终轮） | 见 §3.4/§3.5 |
| 阶段 C：客户端接入 | **通用客户端 + Claude Code 通过；Cursor BLOCKED** | 附录 A.1 curl 全序列 PASS；`claude mcp list` ✓ Connected；Cursor 未安装 |

**缺陷最终状态（6/6 已验证修复）**：

| 缺陷 | 状态 | 验证轮次 |
|---|---|---|
| DEFECT-1 asset_search get_enum | ✅ 已验证修复 | v1.1（TOOL-17 total=64、TOOL-18 total=5443） |
| DEFECT-2 actor_query Quat.pitch | ✅ 已验证修复 | v1.1（rotation `{pitch,yaw,roll}`） |
| DEFECT-3 错误码映射 PYTHON_ERROR | ✅ 已验证修复 | v1.1（traceback 完整含文件行号） |
| DEFECT-4 类路径解析 | ✅ 已验证修复 | v1.2（spawn `/Script/Engine.X`/`Engine.X` 成功；`filter.class` 类路径与短名结果一致；created.classPath 规范化为 `/Script/Engine.StaticMeshActor`） |
| DEFECT-5 发现文件清理 | ✅ 已验证修复 | v1.1（优雅关闭清空 + 陈旧残留清除；v1.2 再次确认） |
| DEFECT-6 依赖查询 include_management_references | ✅ 已验证修复 | v1.2（CesiumIonSaaS deps=[/Script/CesiumRuntime]；MIC 依赖父材质与贴图非空、无 warning） |

**最终结论：可进入联调。** 全部阻断与 P1/P2 缺陷修复验证通过；未决仅剩环境受限的 UNTESTED 项（TOOL-19b/c、Cursor、elicitation 等，见 §5），均不阻塞联调。

**未执行/环境受阻项**全部如实标注于 §5，未将任何未执行用例记为通过。

---

## 2. 执行环境与命令

### 阶段 A（Server 侧，mock bridge）

```bash
cd uemcp && node scripts/smoke.mjs                                   # 65/65
node scripts/mock-bridge.mjs --port 0 --home <tmp>                   # → {port:36625, token:...}
node packages/server/dist/index.js --transport http --policy standard \
  --port 18790..18796 [--allow-console] [--allow-exec] [--allow-destructive] [--disable-legacy-sse] \
  --bridge-url http://127.0.0.1:36625 --bridge-token <t>
node .test-run/runner-a.mjs http://127.0.0.1:18790 proto|sec        # PROTO 组 / SEC-04/05/16
node .test-run/runner-b.mjs http://127.0.0.1:<port> ro|st|full|fc|fb|fd   # 矩阵 + SEC-01/11/11c/12/15
node .test-run/runner-sse.mjs http://127.0.0.1:18790                # PROTO-13/14/15 服务端侧
```

- 测试实例端口：18790（standard）、18791（read-only）、18792（full）、18793（full+console）、18794（full+双开关）、18795（full+仅 destructive）、18796（disable-legacy-sse）；审计目录 `.test-run/audit-a`。

### 阶段 B（真实编辑器）

```powershell
Start-Process "C:\Program Files\Epic Games\UE_5.4\Engine\Binaries\Win64\UnrealEditor.exe" 'C:\UE5_P\5.4\XQHCPP_54\XQHCPP_54.uproject'
# 编辑器 PID：47952（初启）→ 57376（allowWrite:true）→ 69328（allowWrite:false 复测/终验）
# 桥接就绪：http://127.0.0.1:18778/health 200 且 app=uemcp-bridge，约 22 秒
```

```bash
node packages/server/dist/index.js --transport http --policy standard --port 18799   # 走真实发现文件链路
node .test-run/runner-b2.mjs http://127.0.0.1:18799 status|actorQuery|actorEdit|level|assets|material|capture|blueprint|p2hidden
```

- 桥接写权限经 `<Project>/Saved/UEMCP/bridge-settings.json` 控制（allowWrite true/false 两轮实测）；**测试结束已删除该文件并关闭编辑器**。
- 安全约束全程遵守：未保存关卡、未删除/重命名任何现有资产、未打包、未改动 Content/Source；自建测试 Actor（label `UEMCP_Test_Cube_A`）全部删除，终态泄漏 0。

### 阶段 C（客户端）

```bash
# 附录 A.1 curl 序列（initialize → initialized 202 → tools/list → tools/call → DELETE 204）
claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp   # ✓，验证后已移除
claude mcp list                                                    # uemcp ✓ Connected
```

---

## 3. 用例结果清单

图例：PASS=通过；FAIL=失败（附证据）；BLOCKED=环境受阻/未测。括号内为测试计划用例号。判定标准以测试计划 v0.1.1 为准。

### 3.1 阶段 A：Server 侧（32 项断言 + smoke 65，全部 PASS）

| 用例 | 结果 | 关键证据 |
|---|---|---|
| smoke 复跑 | PASS 65/65 | `SMOKE RESULT: 65/65 passed`（覆盖 RES-03/06、PROTO-08 TTL、PROTO-09、SEC-02 默认参数、TOOL-26 降级、SEC-11 等） |
| PROTO-01 initialize | PASS | 200；`mcp-session-id` 头；protocolVersion 回显 2025-06-18；serverInfo.name=uemcp |
| PROTO-02 initialized | PASS | 202 + 空 body |
| PROTO-05 缺会话 | PASS | 400 + -32600 INVALID_REQUEST |
| PROTO-06 未知会话 | PASS | 404 + -32001 SESSION_NOT_FOUND |
| PROTO-07 DELETE | PASS | 204 → 后续 404/-32001 |
| PROTO-10 非法 JSON | PASS | 400 + -32700 PARSE_ERROR |
| PROTO-11 未知 method | PASS | 404 + -32601 METHOD_NOT_FOUND |
| PROTO-12 工具层校验失败 | PASS | 200 + isError + INVALID_ARGUMENT + `details.issues[0]`（path/code/message）+ content 前缀 `INVALID_ARGUMENT: sections.0: ` |
| PROTO-12b arguments 数组 | PASS | 400 + -32602 + INVALID_PARAMS，无 result |
| PROTO-12c 未知工具名 | PASS | 400 + -32602 + INVALID_PARAMS |
| PROTO-17 未来版本协商 | PASS | 9999-01-01 → 协商回 2025-06-18 |
| PROTO-16 stdio | PASS | stdout 逐行合法 JSON-RPC（2 行），tools/list=8 |
| PROTO-03 五组矩阵 | PASS | read-only=7、standard=8、full=8、full+console=9、full+双开关=10；集合完全相等 |
| PROTO-03 收窄 + 注解 | PASS | level_control=`["get_current","list_dirty"]`、material_params=`["list","get"]`、blueprint=`["query"]`；三混合工具 readOnlyHint=true、destructiveHint=false |
| SEC-01(a) 隐藏不可见 | PASS | read-only 列表 7 个，无 actor_edit/console/python |
| SEC-01(b) actor_edit 直调 | PASS | 200 + TOOL_DISABLED + gate=server.policy |
| SEC-01(c) python_exec 直调 | PASS | 200 + TOOL_DISABLED + gate=server.allowExec，message 不泄露细节 |
| SEC-01(d)(e)(f) 混合工具写 action | PASS | 三者均 200 + INVALID_ARGUMENT（收窄 enum 拒绝） |
| SEC-04 bad Host | PASS | 421 + INVALID_REQUEST（curl 实测；undici fetch 忽略 Host 头不可用） |
| SEC-05 bad Origin | PASS | 403 + INVALID_REQUEST |
| SEC-11 桥接 exec 门 | PASS | 200 + EXEC_DISABLED + gate=bridge.allowExec（mock deny-exec） |
| SEC-11c 桥接 console 门 | PASS | 200 + PERMISSION_DENIED + gate=bridge.allowConsole（mock deny-console） |
| SEC-11b 桥接写门 | PASS | 真实编辑器：allowWrite=false → PERMISSION_DENIED + gate=bridge.allowWrite + 无副作用（见 §3.2 复测） |
| SEC-12 审计 | PASS | `argsSummary.codeSha256`（64 hex）+ codeLength=3；无源码原文；confirmationMode=policy + confirmationSwitch=--allow-exec |
| SEC-15 仅 destructive | PASS | exec 不在 tools/list（8 个）；直调 → TOOL_DISABLED + gate=server.allowExec |
| PROTO-13/14/15 SSE 服务端侧 | PASS 6/6 | /sse `text/event-stream` + endpoint 事件（/messages?sessionId=）；POST /messages 202；SSE 流 id 匹配响应（initialize 回显 2024-11-05、tools/list=8、tools/call ok=true）；`--disable-legacy-sse` 后 GET /sse → 404 |

### 3.2 阶段 B：真实编辑器集成（关键）

| 用例 | 结果 | 关键证据 |
|---|---|---|
| 桥接启动（RES-01 近似） | PASS | 启动后约 22s `/health` 200；app=uemcp-bridge、pid=47952（与编辑器一致）、ueVersion 5.4.4、capabilities 全 |
| RES-02 发现文件 | PASS | `~/.uemcp/bridges/4d3b0ef5bce52db7.json` 生成，schemaVersion/pid/projectDir/port/url/token/ueVersion/capabilities 完整 |
| Server 经发现链路连接 | PASS | 18799 `/health` bridge.connected=true（source=bridge-json） |
| TOOL-01 editor_status | PASS 2/2 | ueVersion/level.path/policies.mode；sections 子集裁剪正确（editor/level 无 selection） |
| TOOL-03 actor_query 分页 | PASS | `limit:2,offset:0` → total=138、returned=2、truncated；offset=2 结果位移正确。**前提 `fields:["identity"]` 绕过 DEFECT-2**；默认参数 FAIL（见缺陷） |
| TOOL-04 filter.class / nameContains | PASS | class=StaticMeshActor → 1 个全匹配；nameContains=Light → 2 个 |
| TOOL-05(c) 无效类 | PASS | 200 + CLASS_NOT_FOUND + details.className="NoSuchClassXYZ" |
| TOOL-07 dryRun | PASS | 200 + ok=true + data.dryRun=true，无场景变更 |
| TOOL-08 spawn | PASS | results[0].created[0] 返回 actorPath/name/label |
| TOOL-09 set_transform | PASS | modified=[actorPath] |
| TOOL-10 delete + verify | PASS | deleted=[actorPath]；终态查询泄漏 0（delete 后立即查询有 ≤1s 最终一致性延迟，重试即 0——测试脚本已加重试） |
| TOOL-13 get_current | PASS | data.path=/Temp/Untitled_1.Untitled_1、isDirty=false |
| TOOL-14 list_dirty | PASS | data.packages=[]（新关卡无脏包；字段与架构 §5.4/计划一致，初稿 O-1 记载有误，裁决后关闭） |
| TOOL-15 open 无脏包直执行 | PASS | 不存在关卡 → LEVEL_NOT_FOUND + details.levelPath（裁决 §2.6 无脏包 → 执行打开路径） |
| SEC-08 save_all 未确认 | PASS | CONFIRMATION_REQUIRED（"client elicitation not available and --allow-destructive is off"） |
| SEC-11b 复测（修复后桥接 PID 69328） | PASS | PERMISSION_DENIED + gate=bridge.allowWrite；查询确认无副作用。首次验证在 PID 47952，按主管要求于修复后代码复测通过 |
| PROTO-09 会话上限 | PASS | 第 33 个 initialize → 429 + -32012 RATE_LIMITED（"Too many concurrent sessions (max 32)"，实测触发） |
| TOOL-20 material list | PASS | 真实材质实例 `/Game/Meshs/水务局建筑/M_MS_Surface_Material_Inst` → 参数数组（AO Strength scalar、Albedo texture、Albedo Controls vector…） |
| TOOL-21 material get | PASS | parameterNames=["AO Strength"] → value=1, editable=true |
| TOOL-22 PARAM_NOT_FOUND | PASS | details.parameterName + availableParameters（21 项） |
| TOOL-22 MATERIAL_NOT_FOUND | PASS | details.path=/Game/Meshs/No_Such_Mat_XYZ |
| TOOL-24 capture file | PASS | path 指向 Saved/UEMCP/captures/*.png；bytes=20293；PNG 魔数 89504e47；宽高 128×128（D3 判定标准：文件存在+PNG 头+尺寸） |
| TOOL-26 capture image | PASS | content[0] type=image、mimeType=image/png；base64 解码 20016 字节 PNG、128×128；bytes 字段一致 |
| TOOL-27 blueprint query | PASS | BP_ThirdPersonCharacter → parentClass/variables/graphs/compileState；warnings 含 PARENT_CLASS_UNAVAILABLE（见观察项 O-3） |
| TOOL-28 blueprint compile | PASS | 200 + ok=true + compileState 对象（status="unknown"，符合架构 §5.10 枚举，裁决后 O-2 关闭） |
| TOOL-29 NOT_A_BLUEPRINT | PASS | 对材质实例 query → NOT_A_BLUEPRINT + details.path + actualClass=MaterialInstanceConstant |
| SEC-01 p2hidden（真实环境） | PASS | tools/list 8 个无 P2；console/python 直调 → TOOL_DISABLED + gate=server.allowConsole/allowExec |
| TOOL-24 首次截图 | FAIL→复测 PASS | 编辑器重启后首次截图 BRIDGE_TIMEOUT（30s game-thread job 超时）；复测 148ms 成功。判定：启动初期视口未就绪的环境时序问题，非稳定缺陷；建议实现侧预热或文档标注（观察项 O-4） |
| TOOL-11 AMBIGUOUS_SELECTOR | BLOCKED | 真实环境未构造重复 label Actor（mock 阶段 smoke 未覆盖该分支） |
| TOOL-16/17/18/19 asset_search | FAIL/BLOCKED | 被 DEFECT-1 阻断（见缺陷清单）；空查询的 INVALID_ARGUMENT 分支在 mock 阶段由 zod 层验证 |
| TOOL-22 material set | BLOCKED | 安全约束：不修改材质参数 |
| TOOL-15 UNSAVED_CHANGES/CONFIRMATION_REQUIRED 分支 | BLOCKED | 需脏包前提；安全约束禁止制造脏包（不保存关卡） |
| TOOL-30/31/32/33 P2 真实路径 | BLOCKED | 桥接 allowConsole/allowExec 保持 false（安全约束）；mock 阶段已覆盖命令白名单/EXEC_DISABLED/审计路径 |
| RES-04 端口回退 18778–18788 全占分支 | 未测 | 需占用 11 个端口的环境准备，本轮未执行 |
| RES-05 桥接退出清理 | FAIL（P2） | 编辑器关闭后发现文件残留（见缺陷 DEFECT-5） |

### 3.3 阶段 C：客户端接入

| 用例 | 结果 | 证据 |
|---|---|---|
| CLIENT-01 通用 HTTP 客户端（附录 A.1） | PASS | initialize 200+SID → notifications/initialized **202**（须带 `Accept: application/json, text/event-stream`，缺省 406——已文档化）→ tools/list（SSE 帧）→ tools/call ok=true → DELETE 204 |
| CLIENT-02 Claude Code | PASS | `claude mcp add --transport http uemcp http://127.0.0.1:18777/mcp` 成功；`claude mcp list` → `uemcp ✓ Connected`（CLI 999.0.0-local；测试条目已移除恢复原状） |
| CLIENT-05 Cursor | BLOCKED | 本机未安装 Cursor（`%LOCALAPPDATA%/Programs/cursor` 不存在），不得写成通过 |
| PROTO-14 脚本基线 `sse_client.py` | BLOCKED（脚本部分） | 脚本属测试资产未随实现交付；服务端侧行为已在阶段 A 验证（§3.1 SSE 6/6），脚本与 Cursor 就位后即可补测 |

### 3.4 复测轮（v1.1，2026-10-20 14:13–14:22，编辑器 PID 72184→78852，桥接含全部 5 项修复）

| 用例 | 结果 | 关键证据 |
|---|---|---|
| DEFECT-2/TOOL-03 默认 fields | PASS | `ue_actor_query {limit:3}` → total=138；rotation=`{pitch:-16.29,yaw:43.73,roll:112.36}`、location/scale 正常 |
| TOOL-04 filter.class / nameContains | PASS 2/2 | 同 v1.0 结论（现默认 fields 亦通过） |
| TOOL-05(c) | PASS | CLASS_NOT_FOUND + details.className |
| DEFECT-1/TOOL-17 基础搜索 | PASS | query="Material_Inst",path=/Game → total=64；packageName/objectPath/assetName/class 齐全；默认无 Redirector |
| TOOL-18 分页与类过滤 | PASS | classNames=[MaterialInstanceConstant]，limit=10×两批无重复，total=5443 |
| TOOL-19(a) 依赖查询 | **FAIL（DEFECT-6）** | PYTHON_ERROR + traceback（`include_management_references` property 不存在于 UE 5.4） |
| DEFECT-3 错误码断言 | PASS | 由 TOOL-19(a) 自然触发：`code=PYTHON_ERROR`、`retryable=false`、`details.traceback` 完整（rpc.py:173→dispatcher→assets.py:52）、`exceptionType=Exception` |
| DEFECT-4 类路径 spawn | **FAIL（未修复）** | `/Script/Engine.StaticMeshActor` 与 `Engine.StaticMeshActor` 均 CLASS_NOT_FOUND（TRANSACTION_FAILED，details.rolledBack=true 回滚正确）；短名对照成功（已清理，泄漏 0）；`actor_query filter.class` 类路径同样不支持 |
| DEFECT-5 发现文件清理 | PASS | WM_CLOSE 优雅关闭（EXITED_GRACEFULLY）→ `~/.uemcp/bridges/` 目录空（此前陈旧残留 4d3b0ef5….json 一并清除）；18778 无监听 |
| TOOL-19(b) SEARCH_TIMEOUT | UNTESTED | D7 允许：样例工程资产量不足，慢查询未构造 |
| TOOL-19(c) ASSET_REGISTRY_UNAVAILABLE | UNTESTED | 桥接就绪即轮询 editor_status 30 次（1.6s 间隔）未捕捉到 `isAssetRegistryLoading==true` 窗口 |

复测命令：`node .test-run/runner-r.mjs http://127.0.0.1:18799 regwindow|retest`（编辑器 PID 72184：DEFECT-2/1/3 断言 + 优雅关闭验证 DEFECT-5；PID 78852 allowWrite=true：DEFECT-4 与对照）。

**复测发现的新观察项 O-6（P2）**：asset_search 返回的 `classPath` 字段为调试串（如 `<Struct 'TopLevelAssetPath' (0x000005593B7F495C) {package_name: "/Script/Engine", asset_name: "MaterialInstanceConstant"}>`），非干净路径字符串；`class`/`packageName`/`objectPath` 均正常。建议序列化改取 `asset_name`+`package_name` 拼接。

### 3.5 最终端到端复测轮（v1.2，2026-10-20，编辑器 PID 64296→48924→64368，含 DEFECT-4/6/O-6 修复）

| 用例 | 结果 | 关键证据 |
|---|---|---|
| TOOL-06/07 spawn 类路径 `/Script/Engine.StaticMeshActor` | PASS | ok=true，created 含 actorPath/label，`classPath` 规范化为 `/Script/Engine.StaticMeshActor`；测试 Actor 已删除（终态 0） |
| TOOL-06/07 spawn 类路径 `Engine.StaticMeshActor` | PASS | 同上，成功创建并删除 |
| TOOL-04 filter.class 类路径 vs 短名 | PASS | `/Script/Engine.StaticMeshActor` 与 `StaticMeshActor` 结果一致（total=1，sameSets=true） |
| TOOL-19(a) 依赖查询 CesiumIonSaaS | PASS | deps=[`/Script/CesiumRuntime`] 非空、无 PYTHON_ERROR、无 warning |
| TOOL-19(a) 依赖查询 MIC（`M_MS_Surface_Material_Inst`） | PASS | deps 键 5 个（Inst~Inst4），依赖含父材质 `M_MS_Surface_Material` 与贴图资产，无 warning |
| O-6 classPath 稳定性 | PASS | AssetRef.classPath=`/Script/Engine.MaterialInstanceConstant`、ActorRef.classPath=`/Script/Engine.DirectionalLight`——均为稳定路径字符串（无调试串） |
| 回归抽查：TOOL-17 基础搜索 | PASS | total=64（修复未引入回归） |
| 回归抽查：TOOL-03 默认 fields | PASS | total=138，transform 正常（修复未引入回归） |
| DEFECT-5 再次确认 | PASS | 强杀脏实例后以干净实例优雅关闭（WM_CLOSE → EXITED_GRACEFULLY）→ `~/.uemcp/bridges/` 空、端口释放 |

终验命令：`node .test-run/runner-f.mjs http://127.0.0.1:18799` → **RESULT final pass=10 fail=0 untested=0**。第一轮（read-only 编辑器）验证了非写用例 6/8 PASS（spawn 因桥接写门默认关闭标 FAIL，重启 allowWrite 后补测通过）；全程测试 Actor 清零、未保存关卡、未删现有资产。



## 4. 缺陷清单

> 状态标记（v1.2 最终复测后）：**[已验证修复]** DEFECT-1/2/3/4/5/6（全部关闭）。

### DEFECT-1（P1，阻断 asset_search 全部用例）【已验证修复 2026-10-20】
- **现象**：`ue_asset_search` 任意 query/path/limit 组合返回 `INTERNAL`。
- **复现**：`tools/call ue_asset_search {"query":"M_Test","limit":10}` → HTTP 200 + `isError:true` + `{"code":"INTERNAL","message":"name 'get_enum' is not defined","details":{"reason":"name 'get_enum' is not defined"}}`。
- **预期**：正常返回资产列表；若为 Python 异常应按架构 §2.4 返回 `PYTHON_ERROR`（含 traceback）。
- **定位**：桥接插件 Python 处理器（AssetRegistry 查询路径）。
- **复测**：桥接 PID 47952（修复前）与 57376（修复 Critical-1 后）均 100% 复现；终验桥接 69328 同代码。
- **实际 vs 预期差异**：工具完全不可用；错误码语义偏差（见 DEFECT-3）。

### DEFECT-2（P0，阻断 actor_query 默认用法）【已验证修复 2026-10-20】
- **现象**：`ue_actor_query` 只要 `fields` 含 `transform`（**默认值即含**）即失败：`INTERNAL "'Quat' object has no attribute 'pitch'"`。
- **复现**：`tools/call ue_actor_query {"limit":2}` → 同上形态；`{"limit":2,"fields":["identity"]}` 正常（total=138）。
- **预期**：transform 序列化输出 location/rotation/scale（rotation 应由四元数转欧拉或按架构 §5.2 契约输出）。
- **定位**：桥接序列化代码对 FQuat 使用了不存在的 pitch 属性（FQuat 仅 X/Y/Z/W；FRotator 才有 pitch/yaw/roll）。
- **影响**：MCP 客户端按默认 Schema 调用必然失败，P0 级可用性问题。
- **复测**：同 DEFECT-1，两代桥接均复现。

### DEFECT-3（P2，错误码语义偏差）【已验证修复 2026-10-20】
- **现象**：桥接 Python 异常统一映射为 `INTERNAL`（-32603，details.reason 仅短 message）。
- **预期**：架构 §2.4/裁决补充 §2.4：Python 异常应为 `PYTHON_ERROR`（-32014，含 traceback）；「具体错误优先于通用错误」。
- **影响**：客户端无法按错误码区分「Python 异常」与「服务端未分类异常」；排障缺 traceback。

### DEFECT-4（P2，类路径解析不支持）【已验证修复 2026-10-20（v1.2）】

- **v1.2 验证**：spawn `class:"/Script/Engine.StaticMeshActor"` 与 `"Engine.StaticMeshActor"` 均成功（created.classPath 规范化）；`actor_query filter.class` 类路径与短名结果一致（total=1）；蓝图类（`/Game/BP_MapViewPawn.BP_MapViewPawn` → `_C`）由主管独立探针验证。
- **现象**：`ue_actor_edit` spawn `class:"/Script/Engine.StaticMeshActor"` → `CLASS_NOT_FOUND`（事务回滚形态 TRANAction_FAILED 收敛）；仅短类名 `StaticMeshActor` 成功。
- **预期**：Schema 描述「类名或类路径」——类路径应可解析（测试计划 TOOL-06 也按类路径构造）。
- **附带**：`TRANSACTION_FAILED` 的 `details.rolledBack/reason` 断言可用（details.reason 存在；回滚行为正确，场景无残留）。

### DEFECT-5（P2，发现文件退出未清理）【已验证修复 2026-10-20】

- **现象（v1.0 记录）**：编辑器（PID 69328）关闭后 `~/.uemcp/bridges/4d3b0ef5bce52db7.json` 残留（pid 指向已死进程）。
- **预期**：RES-05——桥接退出时清理或标记陈旧。
- **缓解（v1.0 时）**：Server 端 discovery 校验 pid 存活 + GET /health，陈旧文件会被跳过（防御有效，未产生误连）。
- **复测证据（已修复）**：WM_CLOSE 优雅关闭（进程 EXITED_GRACEFULLY）后 `~/.uemcp/bridges/` 目录为空（连此前版本残留的 `4d3b0ef5bce52db7.json` 也被清除）；端口 18778 释放。

### DEFECT-6（P1，新增于复测轮：依赖查询不可用）【已验证修复 2026-10-20（v1.2）】

- **v1.2 验证**：CesiumIonSaaS deps=[`/Script/CesiumRuntime`]；MIC 依赖父材质与贴图非空；均无 PYTHON_ERROR、无 warning。

- **现象**：`ue_asset_search` 携带 `includeDependencies` 或 `includeReferencers` 时返回 `PYTHON_ERROR`。
- **复现**：`tools/call ue_asset_search {"query":"M_MS_Surface_Material_Inst","includeDependencies":true,"includeReferencers":true,"limit":10}` → `{"code":"PYTHON_ERROR","message":"Exception: AssetRegistryDependencyOptions: Failed to find property 'include_management_references' for attribute 'include_management_references' on 'AssetRegistryDependencyOptions'","details":{"traceback":"…handlers\\assets.py:52 in _dependency_options → options.set_editor_property(…)","exceptionType":"Exception"}}`。
- **预期**：返回 `data.dependencies[<package>]` 数组（测试计划 TOOL-19(a)）。
- **定位**：`Plugins/UEMCPBridge/Content/Python/uemcp_bridge/handlers/assets.py:52` 使用了 UE 5.4 的 `AssetRegistryDependencyOptions` 上不存在的属性 `include_management_references`。
- **级别**：P1（依赖查询功能不可用；此前被 DEFECT-1 挡住未暴露）。

### 观察项（不判缺陷，建议确认）
- **O-1**（已裁决关闭，2026-10-20）：初稿记载「计划与架构写 `dirtyPackages`」有误——经核对，测试计划 TOOL-13/14 与架构 v0.2.0 §5.4 的出参均为 `data.packages`，实现正确，三方一致，非契约差异。裁决：计划中唯一 `details.dirtyPackages`（UNSAVED_CHANGES 附带字段）保持不变。
- **O-2**（已裁决关闭，2026-10-20）：`ue_blueprint compile` 返回 `compileState:{status:"unknown",errors:0,warnings:0}`——架构 §5.10 枚举即 `unknown/up_to_date/dirty/error`，`unknown` 合法，**已确认符合契约**，非缺陷。
- **O-3**：`BP_ThirdPersonCharacter` query 返回 warning `PARENT_CLASS_UNAVAILABLE`（插件环境缺 ThirdPerson 模块）——warning 机制工作正常；数据为空属工程环境，非缺陷（按裁决保持为环境说明）。
- **O-4**：编辑器重启后首次截图 BRIDGE_TIMEOUT（30s），复测即成功——建议桥接预热视口或在 README 标注「启动后首次截图可能超时，重试即可」。
- **O-5**：delete 后立即 actor_query 可见 ≤1s 残影（最终一致性）——建议文档标注或实现同步刷新。
- **O-6**（复测轮新增，P2；**v1.2 已验证修复并关闭**）：v1.1 时 asset_search 返回的 `classPath` 为调试串；v1.2 验证已改为稳定路径字符串（`/Script/Engine.MaterialInstanceConstant`）。

---

## 5. 未测项汇总与原因

| 范围 | 用例 | 原因 |
|---|---|---|
| elicitation 确认流 | SEC-09/10 的 elicitation 分支、CONFIRMATION_DENIED | 无 elicitation 客户端（curl/脚本不声明该 capability）；policy 分支已由 smoke 覆盖（confirmationMode=policy） |
| 写操作扩展 | TOOL-22 set、TOOL-15 脏包分支、TOOL-11 歧义选择器、TOOL-30/31/32/33 P2 真实路径 | 安全约束（不保存关卡/不构造脏包/不开桥接 console-exec）或需专门造数 |
| asset_search 深度用例 | TOOL-16/17/18/19 | 被 DEFECT-1 阻断 |
| 端口/恢复类 | RES-04 回退全占分支、RES-07 桥接全占、RES-08/09 | 环境准备成本，本轮未执行 |
| 传输安全 | SEC-03 非回环拒绝、SEC-06 桥接 token 三态、SEC-13 审计降级、SEC-14 限流 | SEC-14 未实现（P2 选测）；其余需独立网络环境/目录 ACL 构造 |
| 客户端基线 | CLIENT-03~06（Cursor）、PROTO-14 脚本基线 | Cursor 未安装；`sse_client.py` 未交付（服务端侧行为已验证） |
| TTL 真实等待 | PROTO-08 的 30 分钟真实等待 | smoke 以 `--session-ttl-ms` 短 TTL 覆盖逻辑（D4 转实现方已提供参数） |

---

## 6. 风险与结论适用范围

**v1.2 最终结论**：全部 6 个缺陷已验证修复（最终轮 PASS 10 / FAIL 0 / UNTESTED 0），**可进入联调**。未决项仅剩环境受限 UNTESTED（TOOL-19b SEARCH_TIMEOUT 按 D7、TOOL-19c 注册表窗口、Cursor、elicitation 分支等，见 §5），均不阻塞联调。O-6 已随 DEFECT-6 修复关闭（classPath 稳定字符串验证通过）。结论适用于「Server 0.1.0 + UEMCPBridge 0.1.0（含全部修复）+ UE 5.4.4 + 本工程」组合；桥接策略默认 read-only，写路径验证均基于显式开启 `allowWrite` 的场景。

1. **结论适用范围**：本报告结论基于「Server 0.1.0 + UEMCPBridge 0.1.0（含 3 项修复）+ UE 5.4.4 + 本工程」组合；桥接侧 3 项修复的完整回归（含主管提到的 discovery/重试路径）未在 Server 侧最终版本上重复执行——Server 侧修复仍在进行，discovery/重试/限流相关问题按主管指示记为待复测，不下最终结论。
2. **DEFECT-1/2 修复回归范围**：TOOL-03/04/16/17/18/19 + DEFECT-3 错误码断言。
3. 偶发问题 1 项：启动初期首次截图超时（O-4），复测未再出现；如批量 CI 使用建议加预热重试。
4. 测试过程对工程的副作用已清零：测试 Actor 全部删除、`Saved/UEMCP/bridge-settings.json` 已删除、claude mcp 测试条目已移除、测试 Server/编辑器进程已关闭；`~/.uemcp/bridges/4d3b0ef5bce52db7.json` 残留保留作 DEFECT-5 证据（Server pid 校验可防误连，可手动删除）。
5. 测试资产（可重复执行）：`.test-run/runner-a.mjs`、`runner-b.mjs`、`runner-sse.mjs`、`runner-b2.mjs`（含全部断言与判定标准）。
