# 外部缺陷报告独立复现与定性（2026-10-29）

- 执行人：测试与验证岗（独立验证方，未采信对方描述，未采信 Bridge 岗解释）
- 执行时间窗：2026-10-29 15:30 – 15:44
- 任务号：abce910e-eea1-4826-8a4f-013de535b638（注：任务标注截止 12:00:00，晚于指派送达时刻，实际执行在 15:30 后——时限差异如实记录）
- 环境：
  - 5.7：`ue_p_text\UEMCP_TEXT_57`（UE 5.7.4-51494982，C++ 空壳工程，无 StarterContent/蓝图/umap）+ `UEMCPBridge-5.7.zip`（124,586 B，SHA `9E624493…`）
  - 5.4：`ue_p_text\UEMCP_TEXT_54`（UE 5.4.4-35576357，含 StarterContent：7 个 Actor 蓝图、3 个 .umap）+ `UEMCPBridge-5.4.zip`（SHA `94449126…`）
  - 对方工程 `C:\UE5_P\5.7\DTXCPP_J2_57` 全程未触碰
- 边界合规：未改任何产品代码；两工程 .uproject 均经基线字节还原（TEXT_57=`79CD400F…` 不变；TEXT_54 一度被我的两轮连续装机流程留在"三插件 Enabled"状态，已字节级还原回 `18772170…` 并在 §4 如实说明）；编辑器全程串行、跑完即关；收尾 0 进程、端口全空闲、Plugins 目录两工程均不存在。
- 证据目录：`UEMCPBridge\Tests\smoke-runs\triage-5.7-20261029-153701\`、`triage-5.4-20261029-153803\`、`triage-5.4-20261029-153932\`（case-*.json 全量请求/响应/耗时）

---

## 结论总表

| # | 外部报告 | 我的复现 | 判定 |
|---|----------|----------|------|
| 1 | 截图超时（对方 PixelStreaming 工程） | 普通 5.7 编辑器上**完整复现**：前台 976/480/132ms 成功（281–355KB PNG）；**最小化后 CAPTURE_TIMEOUT（HTTP 504，20.2s，无文件）**；恢复前台又 132ms 成功 | **成立，且非 PixelStreaming 特有——窗口后台/无焦点的普遍现象** |
| 2 | blueprint.query 空成功 | 两个真实 Actor 蓝图（有父类/变量/组件的 StarterContent BP）均返回 200+ok 但 parent/graphs/variables 全空 + `PARENT_CLASS_UNAVAILABLE`；**WidgetBlueprint 样本缺失无法验证**（/Game 与 /Engine/UMG 搜索均 total=0） | **部分成立：所有常规蓝图都返回空成功（非 Widget 特有）；Widget 分支证据不足，待样本** |
| 3 | material.params value 恒 null | 基材质（BasicShapeMaterial）：value=null、editable=false；**4 个 MIC 全部读出真实值**（CubemapRotation=0.0、HDRI_Brightness=1.0、HDRI=true/false、Size=512.0，editable=True） | **定性：基材质 value=null 是设计边界（引擎 API 限制），MIC 读取已实现且工作正常——"没实现读取"不成立** |

---

## 1. 截图超时（ue_viewport_capture）

**环境**：UEMCP_TEXT_57 + UE_5.7 编辑器（zip 装机 Bridge），640×360 PNG，`timeoutMs=20000`，`returnMode=file`。

| 状态 | 耗时 | 结果 | 文件 |
|------|------|------|------|
| 前台（Set-EditorForeground ALT 补丁生效） | 976ms | 200+ok | 355,306 B |
| 前台（第 2 次） | 480ms | 200+ok | 281,550 B |
| **最小化（ShowWindow SW_MINIMIZE）** | **20,234ms** | **HTTP 504 `CAPTURE_TIMEOUT`**（retryable=true） | 无 |
| 恢复前台（SW_RESTORE + 前台化） | 132ms | 200+ok | 335,431 B |

**定性**：超时与 PixelStreaming 无关——任何**无前台焦点的编辑器窗口**（最小化/后台）都会因 UE 后台节流（`Use Less CPU when in Background`，实测 tick 率 ~3fps，见本岗 2026-10-29 写操作任务附录）而使 `take_high_res_screenshot` 无法在超时窗内完成。PixelStreaming 部署形态（编辑器常驻后台/无焦点）必然命中。这与本岗上午在 Smoke_Blank（BP 工程）与 TEXT_54（C++ 工程）上三连复现的根因一致——**同一根因，跨 5.4/5.7、跨工程类型普遍存在**。

**与对方报告的差异**：对方称"阻断"。在本环境，**前台/有焦点时功能完全正常**（三次全成功）——所以准确定性是"**后台窗口下超时**"而非"截图功能不可用"；对无人值守/PixelStreaming 场景，等效于阻断（无法指望外部点击前台化）。

**修复方向（建议 Bridge 岗，非本任务范围）**：capture 前自动 `SetForegroundWindow`（需 ALT 注入，见 ZIP-1）；或超时重试时自动前台化一次；或文档注明"后台窗口下 capture 会超时"。

## 2. blueprint.query 空成功

**环境**：UEMCP_TEXT_54（5.4.4，StarterContent 蓝图），`ue_blueprint query {action:"query", blueprintPath:"/Game/StarterContent/Blueprints/Blueprint_CeilingLight", include:[parent,variables,graphs,compileState]}`。

| 样本 | HTTP | 结果 | 关键字段 |
|------|------|------|----------|
| Blueprint_CeilingLight（Actor BP，有父类/组件/图） | 200+ok（22ms） | 数据全空 | `parentClass=""`（`PARENT_CLASS_UNAVAILABLE`）、graphs=0、variables=0、compileState.status=`unknown` |
| Blueprint_WallSconce（Actor BP） | 200+ok（13ms） | 数据全空 | 同上 |

**WidgetBlueprint 验证**：`asset.search {classNames:["WidgetBlueprint"]}` 在 `/Game`（TEXT_54 全树）与 `/Engine/UMG` 均 **total=0**——本机两个可控工程均无 Widget 样本（引擎未随附 WidgetBlueprint 资产）。

**定性**：
- "空成功"**不是 WidgetBlueprint 类型特有**——普通 Actor 蓝图同样返回空（且带 `PARENT_CLASS_UNAVAILABLE` 警告，说明 handler 明确知道自己没读到 parent）。据此，**"接口坏了"与"类型未覆盖"之外还有第三种定性：读取路径本身对 5.4 Python 暴露面失效**（`parent_class` 属性读取抛异常被吞、`new_variables` 空、函数图枚举为空——三个独立读取点同时为空，指向 UE 5.4 Python API 对 Blueprint 资产的内省能力与 handler 预期不符）。
- **Widget 分支证据不足**：无样本，无法判定 Widget 是否"更空"或报 `NOT_A_BLUEPRINT`。需要对方提供其 Widget 资产路径，或本方在测试工程创建一个 Widget BP 后复测（创建动作会写工程文件，需另行授权）。

**与对方报告的差异**：对方未说明其蓝图类型与字段；我方实测表明**连最基本的 parentClass 都读不出且伴随显式警告**——若对方报告声称"compileState/variables 有值而 nodes 空"之类，则与我方不符（我方全空）；若对方也是全空，则一致且可定为普遍缺陷。

## 3. material.params 的 value 恒 null

**环境**：UEMCP_TEXT_54（5.4.4）。

| 样本 | 类型 | value | editable |
|------|------|-------|----------|
| /Engine/BasicShapes/BasicShapeMaterial | **基材质（Material）** | **null**（Color/Roughness 两个参数） | **false** |
| /Game/StarterContent/Blueprints/Assets/M_LightStage_Skybox_Black | **MIC** | **全部有值**：CubemapRotation=0.0、HDRI=false、HDRI_Brightness=1.0、HDRI_Contrast=1.0（共 6 参数 6 非空） | true |
| /Game/StarterContent/Blueprints/Assets/M_LightStage_Skybox_HDRI | MIC | 6/6 非空（HDRI=true 等） | true |
| /Engine/ArtTools/…/M_TestFlipbookAnimation_Inst | MIC | 2/2 非空（Animation Phase=0.0、Size=512.0） | true |
| /Engine/ArtTools/…/M_FlipBookCounter_01_Inst | MIC | 1/1 非空（Animation Phase=0.0） | true |
| /Engine/ArtTools/…/M_50percent_BaseInst | MIC（无参数实例） | parameters=0（空数组，非 null 值） | — |

**代码级定性**（`handlers/materials.py`，读码证据非推测）：
- `_read_value()` L103：`if not isinstance(material, unreal.MaterialInstanceConstant): return None` —— **基材质的 value 读取未实现且被显式短路**；editable 同样仅对 MIC 为 true（L134）。
- UE 引擎侧原因：参数**默认值**存在于基材质的表达式节点（Expression 图）里，`MaterialEditingLibrary` 的 `get_scalar_parameter_value` 等 getter 只作用于 MaterialInstance 常量；Python 无直接读基材质表达式默认值的 API。

**判定**：
- 对**基材质**："value 恒 null"**成立，且属引擎 API 边界**——不是 Bridge 岗"没实现"能单独解决的（要实现需读 Expression 节点图，Python 无公开路径；若对方强需求，应作为能力缺口记档：`editable=false` 字段其实已向调用方明示）。
- 对 **MIC**："恒 null"**不成立**——实现存在且实测读出真实值。若对方在其工程里对 MIC 也得到 null，那是对方环境/路径问题（或其资产确无参数），建议对方提供 MIC 路径复测。

**与对方报告的差异**：对方报告未区分基材质与实例——**我方实测证明两类资产行为完全不同**，笼统的"value 恒 null"定性不成立。

---

## 4. 过程与自我披露

- 两轮 5.4 会话连续使用同一 `rundir54.txt` 变量：第二轮的 .uproject 基线取在第一轮 Enable 之后，导致 restore 写回"含三插件 Enabled"的状态（restored=True 但相对原始状态未还原）。**发现后已用写操作任务的字节级基线（18772170…）恢复原始状态并核验**。此为我方脚本流程缺陷，非产品缺陷；教训：多轮 prepare/restore 必须轮次隔离基线。
- WidgetBlueprint 与"有参数 MIC 在对方工程的表现"两项超出本机可验证范围：前者需 Widget 样本（对方提供或授权创建），后者需对方 MIC 路径。
- 收尾核验：0 编辑器进程、18778–18788 空闲、两工程 Plugins 目录不存在、TEXT_57.uproject=`79CD400F…` 不变、TEXT_54.uproject=`18772170…` 已还原。
- 复现命令：驱动脚本逻辑即 §1–§3 的请求 JSON，RPC 通道与 `ue_smoke_run.ps1` 相同（discovery 取 token → POST /rpc）；三组请求参数已在各表内给出，第三人可用任意 MCP/HTTP 客户端照抄。

## 5. 一行结论

**截图超时成立且是窗口后台状态的普遍现象（前台完全正常，20.2s 超时仅在最小化时复现，恢复即愈）；blueprint.query"空成功"在普通蓝图上成立（三读取点全空+显式警告），Widget 分支因无样本无法定性；material.params 的 value=null 仅基材质如此（引擎 API 边界、editable=false 已明示），MIC 读取实现正常且有真实值——对方报告的三项中，一项成立需环境级修复、一项部分成立待样本、一项被定性为"报告笼统化"。**

---

# §2 补充：WidgetBlueprint 分支补定（任务 6856cf38-6cd9-4e66-b9f2-110b1c8e521d，2026-10-29 15:53–16:01）

## 样本创建方式（UEMCP_Smoke_Blank，5.7，经 `python.exec`，allowExec 临时开启验后关闭）

- 驱动：`triage_widget.ps1`（%TEMP%，已随任务清理；流程=diable 同款 discovery→/rpc 通道）。
- 创建代码要点：`unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name='WBP_Triage', package_path='/Game', asset_class=unreal.WidgetBlueprint, factory=unreal.WidgetBlueprintFactory())`；对照样本 `BP_TriageControl` 用 `unreal.BlueprintFactory` 同法。
- **两次试错记录**（可复现性关键）：UE 5.7 的 `WidgetBlueprintFactory`/`BlueprintFactory` **均无 `parent_class` Python 属性**（`AttributeError: … has no attribute 'parent_class'`，两次 500 证据在 run 目录 case-01）——不设 parent 直接创建成功（Widget 默认父类 UserWidget、Blueprint 默认 Actor）。
- 创建后 `EditorAssetSubsystem.save_asset` 两资产均 `saved=true`（磁盘证据：`UEMCP_Smoke_Blank/Content/WBP_Triage.uasset` 22,286 B、`BP_TriageControl.uasset` 22,399 B，留在一次性工程供复验）。
- `add_member_variable('TriageHealth', unreal.float)` 失败：`module 'unreal' has no attribute 'float'`——API 存在（见下），类型参数应为属性对象（如 `get_basic_type_by_name` 取得），非本次目标，如实记录。

## ue_blueprint query 结果（5.7，同一 handler、同参数形状）

| 样本 | 类型 | HTTP | parentClass | graphs | variables | compileState | warnings |
|------|------|------|-------------|--------|-----------|--------------|----------|
| /Game/WBP_Triage | **WidgetBlueprint**（新建，父类应为 UserWidget） | 200+ok（29ms） | **""** | 0 | 0 | unknown | **PARENT_CLASS_UNAVAILABLE** |
| /Game/BP_TriageControl | Actor Blueprint（新建，父类 Actor） | 200+ok（13ms） | **""** | 0 | 0 | unknown | **PARENT_CLASS_UNAVAILABLE** |
| （5.4 对照）Blueprint_CeilingLight | Actor BP（StarterContent，有父类/组件/图） | 200+ok（35ms） | **""** | 0 | 0 | unknown | **PARENT_CLASS_UNAVAILABLE** |
| （5.4 对照）Blueprint_WallSconce | Actor BP | 200+ok（10ms） | **""** | 0 | 0 | unknown | **PARENT_CLASS_UNAVAILABLE** |

**Widget 与 Actor 蓝图输出完全一致（全空 + 同一警告）——"空成功"不是 Widget 类型特有。**

## 根因级证据（python.exec 直接探针，绕过 handler 直问引擎）

对 /Game/WBP_Triage 在 5.7 编辑器内直接执行（16:00，case-04）：

```text
loaded          = <class 'WidgetBlueprint'>          # 资产加载成功
generated_class = WBP_Triage_C                        # generated class 内省正常
parent          = ERR WidgetBlueprint: Failed to find property 'parent_class' for attribute 'parent_class' on 'WidgetBlueprint'
num_vars        = ERR WidgetBlueprint: Failed to find property 'new_variables' for attribute 'new_variables' on 'WidgetBlueprint'
```

**定性**：`get_editor_property('parent_class'/'new_variables')` 在 UE Python 里**对这些字段根本没有暴露属性**（"Failed to find property"=属性不存在，不是值为空）——handler 的读取路径（`get_editor_property`）在 Blueprint 资产上天然拿不到这两样，任何蓝图都拿不到。这解释了"空成功 + PARENT_CLASS_UNAVAILABLE"的全部现象，**且 5.4 与 5.7 行为一致**（5.4 侧四个 Actor BP 同样全空）。

**同时探得修复可用面**（`dir(unreal.BlueprintEditorLibrary)` 前 30 项已存证 case-01）：5.7 暴露 `add_member_variable`、`compile_blueprint`、`create_blueprint_asset_with_parent`、`find_graph`、`find_event_graph`、`get_default_object`、`get_basic_type_by_name` 等——Bridge 岗可改用 **generated_class → CDO（get_default_object）→ 父类链** 的路径取 parentClass（generated_class 实测可读出 `WBP_Triage_C`），variables 可改走 `BlueprintEditorLibrary` 系 API；compileState 需另寻（探针证实 `get_blueprint_compile_state` 不存在）。

## 回答任务核心问题

**"空成功"既不是"所有蓝图资产的内省都读不到（接口坏了）"，也不是"Widget 类型未覆盖"——而是"UE Python 的 `get_editor_property` 对 Blueprint 资产的 parent/variables 字段不暴露属性，5.4 与 5.7 一致，与蓝图类型无关"。** 接口契约（200+ok+警告）按设计工作；读取路径需要换 API（见上）。5.4 的 Widget 样本因"禁止写用户工程"边界未能创建——但 5.7 探针已证明该字段在 5.7 同样缺失，版本差异假设不成立，5.4 Widget 样本不再必要。

## 环境与清理

- 两会话串行、各一次编辑器实例、收尾 graceful=True/portsFree=True。
- UEMCP_Smoke_Blank：`.uproject` 字节还原（`91344BCB…` 核验一致）、bridge-settings.json 已删（验证窗口 allowExec=true）、Plugins 已卸；Content 留两个新建样本（22,286/22,399 B）供复验。
- TEXT_54：只读（重查两 StarterContent 蓝图），uproject 还原核验过。
- 证据目录：`smoke-runs\triage-wbp-5.7-20261029-155614`（4 case，含两次试错的 500 证据）、`triage-wbp-5.4-20261029-160034`（2 case）。
