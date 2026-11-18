# 0.1.5 第二批修复 · 桥接侧（接管补完）报告

- 版本：**0.1.5（未升版）** —— `settings.py:12 PLUGIN_VERSION`、`UEMCPBridge.uplugin` `VersionName`、`README.md:1` 三处一致
- 范围：仅 `UEMCPBridge/`（`Content/Python/uemcp_bridge/**`、`Tests/**`、`README.md`）与 `feedback-review/` 证据
- 基线提交：`bacbe1c048f590020592528241fda93b04f5ce99`（branch `main`）
- 前任基线快照：`feedback-review/logs/bridgefix-hash-before.txt`（56 条：55 个 `UEMCPBridge/` 文件 + 1 个 `feedback-review/bridge-verification.md`，**不含** `uemcp/` 路径）

## 0. 结论

1. 主管裁定的清单 **8 项全部落地**：`PS 快速失败 / 错误来源 / 请求级日志 / BFS / 文档生成化 ＋ settings.source / policy_snapshot / health schemaVersion`。前任已正确完成的项**只复核、未重做**。
2. 离线门禁全绿：AST 解析 `AST_PARSE_OK 24`（24/24 文件）；**20 个无编辑器自检 20/20 `exit=0`**，`TOTAL=20 FAILED=0`。**未启动 UE 编辑器、未跑真机冒烟**（不在本任务范围）。
3. 接管期补齐 3 类遗留：(a) `/health` 的 schema 只能在 `BridgeServer` 上取到，自检 `AttributeError`；(b) `asset.search` 缺分页游标；(c) README 与代码计数漂移（`11/11`、11 个脚本等）。
4. 新增 `check_readme_tables.py` 把 README §5 方法表与 §10.2 自检表**改为由代码生成 + 门禁校验**；该门禁**先红后绿**：修 `README:248` 前如实 `exit=1` 并抓到 `stale '11/11'`，修复后 `README_TABLES_CHECK methods=16 scripts=20 PASS`。原始失败日志一并保留。
5. 未决 4 条（第 9 项黑名单语义 2 条按主管裁定仅记录、`nextOffset` 归属待确认、TS 侧契约对齐），见 §6。

## 1. 任务与裁定

主管裁定原文（本报告的验收口径）：

> 清单＝PS快速失败/错误来源/请求级日志/BFS/文档生成化＋settings.source/policy_snapshot/health schemaVersion

第 9 项（`objects.py` 黑名单匹配语义）裁定原文：

> 本批不动黑名单匹配语义 …… ①项9不在本任务修复清单内 …… ②严格版 allow-list 会大幅改变放行面 …… 宽松版削弱防护 …… ③现状按裸名拦截属 fail-safe 过拦截，可接受。要求：在 bridgefix-report.md 未决项中如实记录两条——class-qualified 匹配建议（含同名误拦现象，objects.py:33-63 锚点）与 camel→snake 理论绕过面（bridge-verification.md 项9，需真机验证），标注「留待后续批次单独裁决」；不改 objects.py 黑名单逻辑。

禁止项执行情况：未改 `uemcp/**`；未改 QA 冒烟脚本/`smoke-plan`；未启动 UE 编辑器、未跑真机冒烟；未触碰任何 ZM 目录；`server-verification.md:284-297` §12「保持不动」条目未改；未被要求重做的前任修复未重做。

## 2. 盘点：前任改动 vs 本批净变化

比对方式：用前任 `bridgefix-hash-before.txt`（56 条 SHA256）逐条比当前文件（`bridgefix2-inventory.log` §6）。结果：

| 项 | 数值 | 说明 |
| --- | --- | --- |
| 基线条目 | 56 | 55 个桥接文件 + `bridge-verification.md` |
| SAME | 42 | 未变，含只读依据 `bridge-verification.md`（`readonly_basis_unchanged=SAME`） |
| CHANGED | 14 | 11 项前任已改 + **3 项本批我改**（标注 `CHANGED*`） |
| MISSING | 0 | 无文件丢失 |

CHANGED 全量（14）：`dispatcher.py`、`errors.py`、`handlers\assets.py`、`handlers\objects.py`、`handlers\python_exec.py`、`handlers\status.py`、`handlers\viewport.py`、`rpc.py`、`server.py`、`settings.py`、`README.md`、`test_python_error_mapping.py`、`test_rate_limit.py`、`test_uplugin_metadata.py`。
其中本批我经手的 3 个：`server.py`、`handlers\assets.py`、`README.md`。

新增文件（本仓未跟踪，故不在 56 条基线内）：

| 文件 | 性质 | 行数 | SHA256 |
| --- | --- | --- | --- |
| `UEMCPBridge/Tests/test_bridge_fixes.py` | 新增自检（覆盖清单 8 项） | 500 | `A67F647DD01906FD78C404F517EBC9086FE4EF256A7E8CDEF85BE4EC1075A611` |
| `UEMCPBridge/Tests/check_readme_tables.py` | 新增 README 生成/门禁 | 302 | `BC0C01569847C33637C87AC205047B4D1E1052E97B4D98C96EC4732989E5C460` |

本批净改动 = 3 改 + 2 增，共 5 个文件；`bridgefix2-hash-after.txt` 收录 61 条（56 基线路径 + 5 新增），其中 56 条基线的 14 项变更全部可追溯。备份与一致性见 §5.3。

## 3. 逐项：清单项 → 修复锚点 → 证据

| # | 清单项 | 代码锚点（当前行号） | 行为 | 证据日志（关键行） |
| --- | --- | --- | --- | --- |
| 1 | **PS 快速失败** | `handlers/viewport.py:601-634`（3 处 `CAPABILITY_UNAVAILABLE`）、`Tests/test_bridge_fixes.py:121 check_pixel_streaming` | Pixel Streaming / headless 下 `viewport.capture` 立即失败（−32016 / HTTP 501 / `retryable=false`），不再耗满采集超时 | `bridgefix2-selfcheck-test_bridge_fixes.log`：`PIXEL_STREAMING fast_fail=CAPABILITY_UNAVAILABLE probe=True/False keys=10` |
| 2 | **错误来源** | `errors.py:82-114`（`CALLER_ORIGIN_CODES` / `ENVELOPE_STAGE_CODES` / `annotate_origin_stage`）；`server.py:250,258,265,272`（`caller`/`http`）、`:369-370`（`bridge`/`queue`）、`:388-389`（`bridge`/`game_thread`）、`:402`（`bridge`/`rpc`） | 每个错误封套带 `data.details.origin` ∈ {`caller`,`bridge`} 与 `stage` | `bridgefix2-selfcheck-test_error_origin.log`、`-test_bridge_timeout_http.log`、`-test_rate_limit.log`：均 `exit=0` |
| 3 | **请求级日志** | `server.py:480-529`（`_log_rpc_request`）、`:505-514`（10 键行）、`:520-523`（`_RPC_LOG_LOCK` + `os.replace(...".1")`）、`:52`（5 MiB 上限）、`:612`（`Saved/UEMCP/rpc-requests.jsonl`）、`:243`（`started`） | 每次 `POST /rpc` 落一行 JSONL；5 MiB 轮转；不含 params/代码/token | `...test_bridge_fixes.log`：`REQUEST_LOG records=4 keys=10 sanitized=ok rotation=ok`；落盘实证见 §5.4 |
| 4 | **BFS 上限** | `handlers/assets.py:20`（`_MAX_SEEDS=50`）、`:157`（`_bfs`）、`:181`（`BFS_SEEDS_TRUNCATED`）、`:236`（只返回关系项）、`:285,301,304`（`SEARCH_TIMEOUT` + `timeoutMs`）、`:375`（`relationsTruncated`） | 单次最多展开 50 个种子，余量以 warning 报出；超时给 `SEARCH_TIMEOUT` 且保留部分结果 | `...test_bridge_fixes.log`：`BFS_LIMITS seed_cap=50 budget=maxNodes relationsTruncated=True/False timeoutMs=20000` |
| 5 | **文档生成化** | `Tests/check_readme_tables.py`（`--emit` 生成 §5 行；5 组校验：标题版本 / §5 集合双向相等+顺序 / §10.2 集合与序号 / 引用计数 / 陈旧串）；`README.md:118`（§5）、`:212`（§10.2） | README 表由 `rpc.HANDLERS` 生成，漂移即失败 | `bridgefix2-selfcheck-check_readme_tables.log`：`README_TABLES_CHECK methods=16 scripts=20 PASS`；`bridgefix2-readme-emit.log`：16 行 + `missing=0` |
| 6 | **`settings.source`** | `settings.py:87`（`"source"` 键）、`:246,262`（写入 `policy_snapshot`） | 取值 = 实际生效的 settings 文件路径，无文件时 `"defaults"`；`envOverrides` 只报环境变量**名** | `...test_bridge_fixes.log`：`SETTINGS_SOURCE file/env/presence/defaults ok envOverrides=recorded` |
| 7 | **`policy_snapshot`** | `settings.py:250-263`（7 键） | `mode` 由 `allow_write` 推导（`standard`/`read-only`），`destructive` 恒 `false` | 同上 + `/health.policies` |
| 8 | **`health.schemaVersion`** | `server.py:134-162`（模块级 `health_payload`，18 键，`schemaVersion=discovery.SCHEMA_VERSION`）、`:745`（`BridgeServer.health_payload` 委派） | `/health` 顶层暴露 `schemaVersion` 供 TS 侧判版 | `...test_bridge_fixes.log`：`HEALTH_SCHEMA schemaVersion=1 keys=18` |
| 11 | **README 一致性（项 11）** | `README.md:1,29,31,135-137,173,212,223,239,248` 共 8 处 | 标题版本、方法计数 16、工具 14、自检 20、§5 补 3 行、§10.2 补 5 行、`:248` 环境说明改写 | §5.1 门禁日志（含先红后绿） |
| 附 | **`asset.search` 分页游标** | `handlers/assets.py:353-354` | `nextOffset` 显式游标，末页为 `null`（键存在） | `...test_bridge_fixes.log`：`ASSET_NEXT_OFFSET first=2 last=None` |

补充说明（项 11 范围纪律）：项 11 只改 CMD 列举的不一致（标题版本 / 方法计数与 §5 行 / 自检计数与表 / `:248` 统计口径 / 5 个漏列脚本）。README §7「本轮行为变化」以及请求日志、`nextOffset` 的文档化**不属于项 11 要求**，未擅自扩写——对应契约形状改在本报告 §4 向 TS 侧交付。

## 4. 接口契约形状（供 TS 侧对齐）

以下为桥接侧**实际实现**的形状，供 `uemcp/packages/server` 侧对齐；本批未改 `uemcp/**`。

### 4.1 `GET /health` → 200，**恰好 18 个键**

```json
{
  "app": "uemcp-bridge",
  "schemaVersion": 1,
  "ok": true,
  "ueVersion": "5.4.4-…",
  "pluginVersion": "0.1.5",
  "bridgeProtocol": 1,
  "port": 18778,
  "pid": 12345,
  "instanceId": "<32 位 hex>",
  "buildHash": "<内容哈希>",
  "buildTime": "<ISO8601 Z> | null",
  "sourcePath": "<插件根目录>",
  "projectDir": "<规范化项目目录>",
  "projectFile": "<绝对 .uproject>",
  "startedAt": "<ISO8601 Z> | null",
  "capabilities": { "screenshot": true },
  "rateLimit": { "…": "…" } ,
  "policies": { "…": "见 4.2 …" }
}
```

约束：**不要新增/依赖第 19 个键**（如 `portFallbackHistory`）——第 1 项不在本批清单内，自检按 18 键等值断言。`rateLimit` 可为 `null`。

### 4.2 `policies` = `policy_snapshot()`（7 键）

```json
{
  "mode": "standard" | "read-only",
  "write": true,
  "exec": false,
  "console": true,
  "destructive": false,
  "source": "<生效的 settings 路径>" | "defaults",
  "envOverrides": ["UEMCP_ALLOW_WRITE"]
}
```

- `mode`：`allow_write` 为真 → `"standard"`，否则 `"read-only"`（`settings.py:252-255`）。
- `destructive`：桥接侧恒 `false`（当前无破坏性接口）。
- `envOverrides`：环境变量**名**列表，不含值。

### 4.3 错误封套

```json
{
  "jsonrpc": "2.0",
  "id": 31,
  "error": {
    "code": -32016,
    "message": "…",
    "data": {
      "errorCode": "CAPABILITY_UNAVAILABLE",
      "retryable": false,
      "details": { "origin": "bridge", "stage": "rpc", "…": "…" }
    }
  }
}
```

- `data.errorCode` 为大写下划线码；`retryable` 由码表决定（`errors.py:14-42`）。
- `details.origin` ∈ {`caller`, `bridge`}：默认由 `CALLER_ORIGIN_CODES` 判定，调用点可显式覆盖（`errors.py:102-114`）。
- `details.stage`：默认 `envelope`（`ENVELOPE_STAGE_CODES` 内）或 `rpc`；本批实测出现的显式值有 `http`、`queue`、`game_thread`、`rpc`。TS 侧应把 `stage` 当作**开放字符串**（记录用），`origin` 才是分支依据。

### 4.4 请求级日志（`<project>/Saved/UEMCP/rpc-requests.jsonl`）

每次 `POST /rpc` 一行，键**恰好 10 个**：

```json
{"ts":"2026-11-18T07:12:33.412Z","requestId":"31","method":"bridge.ping","ok":true,
 "errorCode":null,"httpStatus":200,"durationMs":3,"queuedMs":0,"origin":null,"stage":null}
```

| 字段 | 语义 |
| --- | --- |
| `ts` | UTC ISO8601，毫秒精度 |
| `requestId` | **字符串**（实测 `"31"`）；HTTP 层拒绝时 `null` |
| `method` | 方法名；HTTP 层拒绝（如 401）时 `null` |
| `ok` | 是否成功 |
| `errorCode` | 失败时的 `errorCode`，成功为 `null` |
| `httpStatus` | 实际 HTTP 状态码 |
| `durationMs` | 请求耗时（毫秒） |
| `queuedMs` | 入队→出队毫秒；未到队首（HTTP 层拒绝）为 `null`；同步 dispatcher 为 `0` |
| `origin`/`stage` | 取自错误封套；成功时为 `null` |

不记录 params、Python 代码、token。轮转：单文件 5 MiB，`os.replace(path, path + ".1")`，仅保留 `.1` 一份，整个过程持 `_RPC_LOG_LOCK`。

### 4.5 `asset.search` 分页

```json
{ "total": 120, "returned": 20, "assets": ["…"], "nextOffset": 40 }
```

`nextOffset` = `offset + len(window)`，**仅当还有剩余页时存在非 `null` 值**；最后一页键仍存在但为 `null`（不要按“键缺失”判断结束）。`SEARCH_TIMEOUT` 的部分结果返回 `{total, returned, assets}` 与 `details.timeoutMs`，**不带游标**。

### 4.6 搜索/依赖预算

- 单次 `get_dependencies` 最多展开 **50** 个种子（`_MAX_SEEDS`），超出部分不展开并以 `BFS_SEEDS_TRUNCATED` warning 报出；
- 节点预算 `maxNodes`；关系数组被截断时 `relationsTruncated: true`；
- 超时 → `SEARCH_TIMEOUT`，`details.timeoutMs` = `settings.search_timeout_ms`（实测 20000）。

### 4.7 `viewport.capture` 快速失败（Pixel Streaming）

| 条件 | `errorCode` | `httpStatus` | `retryable` | 附加 details |
| --- | --- | --- | --- | --- |
| 无 `screenshot` 能力 | `CAPABILITY_UNAVAILABLE` | 501 | `false` | `capability: "screenshot"` |
| headless / offscreen | `CAPABILITY_UNAVAILABLE` | 501 | `false` | `capability`, `renderer`, `suggestion` |
| 开启 Pixel Streaming | `CAPABILITY_UNAVAILABLE` | 501 | `false` | `capability`, `renderer`, `suggestion`（关 `DefaultWebAPI.ini` 的 DataChannelType，或改用串流客户端截图） |

## 5. 证据

### 5.1 门禁日志（主证据，SHA256 为写入时实测）

| 日志 | 字节 | 行 | 结论行 | SHA256 |
| --- | --- | --- | --- | --- |
| `feedback-review/logs/bridgefix2-compile.log` | 278 | 5 | `AST_PARSE_OK 24` / `exit=0` | `B401AD89EE6C80585340AD84504647F0AF95E6C4468A6DE63F5089001F65E4D6` |
| `feedback-review/logs/bridgefix2-selfcheck-all.log` | 649 | 21 | 20 × `exit=0`，`TOTAL=20 FAILED=0` | `2048CFF3F6F7FDEF991DA7ABF0A7320B8F0BF40BCC0DF37DF6C8BCA175F2C58C` |
| `feedback-review/logs/bridgefix2-selfcheck-check_readme_tables.log` | 280 | 5 | `README_TABLES_CHECK methods=16 scripts=20 PASS` / `exit=0` | `0FEF370733255EA99AA987D3E20FA0CEE8FA102234E99CA7BB9AD9CD7195B274` |
| `feedback-review/logs/bridgefix2-readme-emit.log` | 1107 | 20 | 16 行方法表 + `missing=0` / `exit=0` | `A85E124473E5F39D1722EB866D542C55BDF761AE08FB9138DF886CFD7DAC3A14` |
| `feedback-review/logs/bridgefix2-inventory.log` | 232372 | 4523 | §1-§8 全量盘点 | `060167020F58092B09BB81C4DA9DE804844F29CEE5AD30BBECC74AE99A0D2D9A` |
| `feedback-review/logs/bridgefix2-hash-after.txt` | 7083 | 65 | 61 条（56 基线 + 5 新增） | `A7EFE8A3CCA1E3A23BDC73FDB997C694E8A520BDD6362ABAA51F05F6375A101B` |
| `feedback-review/logs/bridgefix2-deliverable-hash.log` | 1854 | 27 | `DELIVERABLE_HASH MATCH=5 MISMATCH=0 files=5` | `4DB88CA7E31457880A56E8DC894ABAC1591163F69FB3FC083EC451935F142EBD` |

### 5.2 20 个自检（每个一份原始日志 `bridgefix2-selfcheck-<name>.log`）

`check_error_codes`、`check_handler_names`、`check_plugin_version`、`check_readme_tables`、`test_bridge_fixes`、`test_bridge_timeout_http`、`test_class_path_resolution`、`test_dependency_options`、`test_discovery_lifecycle`、`test_dispatcher_meta`、`test_error_origin`、`test_log_query`、`test_object_call`、`test_pie_control`、`test_port_fallback`、`test_python_error_mapping`、`test_rate_limit`、`test_serialization`、`test_uplugin_metadata`、`test_viewport_capture` —— 全部 `exit=0`。

门禁**先红后绿**的失败记录（保留，未删除）：修 `README:248` 前同一命令 `exit=1`，输出 `FAIL: line 248: 11/11 exit 0, actual 20`、`FAIL: line 248: stale '11/11' (self-check tally before the test set grew)`、`README_TABLES_CHECK methods=16 scripts=20 FAIL(2)`。这证明门禁确实会拦漂移，不是空跑。

### 5.3 交付物与备份一致性

`feedback-review/bridge-backup/bridgefix2/` 存 5 个字节级副本；`bridgefix2-deliverable-hash.log` 逐文件比对结果 `MATCH=5 MISMATCH=0`，即"磁盘上的交付文件 = 备份副本"，不存在报告与代码不同步。

### 5.4 落盘实证（非模拟）

`<Temp>\uemcp_fixes_proj_kc25bx_c\Saved\UEMCP\rpc-requests.jsonl`：831 B / 4 行，含 3 条成功记录（`"requestId": "31"/"32"/"33"`）与 1 条 HTTP 层拒绝记录（`"requestId": null, "method": null, "errorCode": "unauthorized", "httpStatus": 401`），验证 4.4 的键集与 null 语义。

## 6. 未决

1. **项 9-a：class-qualified 匹配建议（留待后续批次单独裁决）**。现状 `objects.py:33-63` 按**裸名**拦截，同名不同类的对象会被一并拦下（过拦截）；建议改为 class-qualified（`/Game/Path/BP.BP:Class`）匹配。属 fail-safe 过拦截，可接受但会误伤同名资产。
2. **项 9-b：camel→snake 理论绕过面（留待后续批次单独裁决）**。见 `bridge-verification.md` 项 9，属理论面，**需真机验证**才能定性；本批按裁定不动 `objects.py` 黑名单逻辑。
3. **`nextOffset` 归属**：本批在 `asset.search` 补齐分页游标（`assets.py:353-354`）并加断言；该点是否计入正式清单第 N 项，请主管确认归属。
4. **TS 侧契约对齐**：本批未改 `uemcp/**`，TS 侧尚未消费 4.1-4.7 的新形状（`schemaVersion`、`policies.source`、请求日志、`nextOffset`、快速失败码）。契约形状已在本报告 §4 给出，需 TS owner 按其排期对齐。

其他说明（已知偏差，非未决）：`server-verification.md:295` 把 README 划给 release owner，而本任务包把项 11 交给桥接侧——本批按任务包执行，偏差在此如实记录。

## 7. 版本与约束遵守

| 约束 | 状态 | 证据 |
| --- | --- | --- |
| 保持 0.1.5，不升版 | 遵守 | `settings.py:12`、`UEMCPBridge.uplugin`、`README.md:1` 三处一致；`check_plugin_version`/`test_uplugin_metadata` `exit=0` |
| 只改桥接侧 | 遵守 | 写操作只落在 `UEMCPBridge/**` 与 `feedback-review/**`；inventory §1/§7 |
| 不改 `uemcp/**` | 遵守 | 本批无 `uemcp/` 写操作；基线 56 条不含 `uemcp/` 路径 |
| 不改 QA 冒烟/`smoke-plan` | 遵守 | 未出现在 CHANGED 或新增清单 |
| 不启动编辑器/真机冒烟 | 遵守 | 全部为离线自检；`exit=0` 均来自 `python -B` 直跑 |
| 不碰 ZM 目录 | 遵守 | 未出现在 CHANGED 或新增清单 |
| 不改 §12「保持不动」 | 遵守 | 对应文件 SAME（`readonly_basis_unchanged=SAME`） |
| 不重做已正确的前任修复 | 遵守 | 项 2/3/4/5/6/7/8-partial/12 仅复核 |

## 8. 复现步骤

```powershell
$root = 'C:\UE5_P\5.4\UEMCP'
$py   = 'C:\Python314\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'

# 1) AST 解析门禁（24 个文件，不导入 unreal）
& $py -B -c "…"        # 见 feedback-review/logs/bridgefix2-compile.log 内联脚本
#    期望：AST_PARSE_OK 24

# 2) 全量离线自检（20 个）
Get-ChildItem "$root\UEMCPBridge\Tests\check_*.py","$root\UEMCPBridge\Tests\test_*.py" |
  ForEach-Object { & $py -B $_.FullName; "exit=$LASTEXITCODE  $($_.Name)" }
#    期望：20/20 exit=0，TOTAL=20 FAILED=0

# 3) README 表生成（与 §5 对比，可 --emit 打印应写入的行）
& $py -B "$root\UEMCPBridge\Tests\check_readme_tables.py" --emit
#    期望：README_TABLES_EMIT methods=16 missing=0

# 4) 交付物 ↔ 备份一致性
Get-Content "$root\feedback-review\logs\bridgefix2-deliverable-hash.log" | Select-String 'DELIVERABLE_HASH'
#    期望：DELIVERABLE_HASH MATCH=5 MISMATCH=0 files=5
```

JSONL 落盘复现：跑 `Tests\test_bridge_fixes.py` 后检查临时工程下 `Saved\UEMCP\rpc-requests.jsonl`（4 行，含 401 记录）。

---

本报告自身的路径、行数与 SHA256 记录在 `report_task` 交付摘要中（自引用不回写正文，避免写入即改变哈希）。