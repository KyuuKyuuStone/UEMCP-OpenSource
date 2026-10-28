# UEMCPBridge UE 5.7 兼容性核查

| 项 | 值 |
| --- | --- |
| 核查日期 | 2026-10-28 |
| 插件版本 | UEMCPBridge 0.1.0（纯 Python，Modules=[]） |
| 对照引擎 | UE 5.4.4 与 UE 5.7.4（均本机安装，引擎自带 Python 均为 3.11.8） |
| 核查范围 | `UEMCPBridge/Content/Python/` 下全部 `unreal.*` 调用点（83 处，46 个不同符号） |
| 核查方式 | 引擎头文件逐行对照 + 引擎二进制符号扫描 + PythonScriptPlugin C++ 源码对照 + 官方文档；**未启动编辑器** |
| 关联任务 | 411760ab-8b5e-4b99-965c-67b6bc750fa2（UEMCPBridge 适配 UE 5.7 并修复已知缺陷） |

> 占位符：`<UE_ROOT>` = 引擎安装根目录（Windows 默认位于 `Program Files\Epic Games\UE_5.7`，按实际版本替换）；`<YourProject>` = 你的 UE 工程目录；`<RepoRoot>` = 本仓库根目录。文档中不出现本机用户目录或私有工程路径。

## 1. 结论

1. **未发现破坏性 API 变更**：本插件用到的全部 `unreal.*` 类、函数、属性在 5.4.4 与 5.7.4 中都存在，签名与返回类型一致；没有任何一个符号只在 5.4 存在。**不需要为 5.7 增加版本分支代码。**
2. 5.7 只有两处**增量**（向后兼容）：
   - `UEditorActorSubsystem::DuplicateActor/DuplicateActors` 新增带 `FActorDuplicateParameters` 的 C++ 重载（该重载**没有** `UFUNCTION` 标记，Python 暴露的仍是原来的 3 参数版本）；
   - `UMaterialEditingLibrary::SetMaterialInstanceStaticSwitchParameterValue` 末尾新增可选参数 `bUpdateMaterialInstance = true`；现有 3 参数调用继续有效。
3. 核查中发现两处**与引擎版本无关**的健壮性缺陷（5.4 同样存在），已修复：
   - `level.control` 的 `isMap` 恒为 `false`（`UPackage` 没有 `is_map` 属性）；
   - `viewport.capture` 在请求 `jpeg` 时返回 `format:"jpeg"`，但引擎实际只写 PNG。
4. 另有三项行为差异只能靠真机确认（§5）：Slate tick 泵、截图内容、事务回滚/蓝图属性读取。
5. `.uplugin` 不再写死 `EngineVersion`，改为打包时用 `Tools/stamp_uplugin.py` 注入（§6）。

## 2. 证据与方法

| 代号 | 方法 | 说明 |
| --- | --- | --- |
| E1 | 引擎头文件逐行对照 | `<UE_ROOT>\Engine\Source\...` 下 5.4.4 与 5.7.4 同一头文件对比（UFUNCTION 签名、UPROPERTY 名、`UE_DEPRECATED` 标记） |
| E2 | 二进制 FName 符号扫描 | 在 `Engine\Binaries\Win64\UnrealEditor-*.dll` 中检索 UCLASS/UFUNCTION 名（79 个符号 × 16 个模块 × 两个版本）：**除 `EditorAssetLibrary`（仅 5.7 出现、属弃用类、本项目未使用）外，其余符号两版均存在；没有任何符号只在 5.4 存在** |
| E3 | PythonScriptPlugin 源码对照 | `PyEditor.cpp` 5.4/5.7 **均为 234 行且逐行相同**（`ScopedEditorTransaction` 的实现与 `cancel()` 语义不变）；`PyCore.cpp` 的 `GetDefaultObject` 实现逐字相同；`PySlate.cpp` 有 1 处 tick 守卫变更（见 §5-V1）；模块级 Python 全局函数（`register_slate_post_tick_callback`、`get_editor_subsystem`、`get_default_object`、`load_class`、`load_object`、`find_object`、`log_warning` 等）两版方法表中均存在 |
| E4 | 官方文档 | dev.epicgames.com 5.7 文档仍列出 `TakeHighResScreenshot` 等函数 |
| E5 | 无编辑器自检 | `UEMCPBridge/Tests` 下 11 个脚本，全部 exit 0（§7） |
| E6 | 真机探针 | `Tests/probe_ue57.py`（需引擎，尚未运行，见 §5） |

复现 E1 的关键路径：

```
Engine\Source\Editor\UnrealEd\Public\Subsystems\EditorActorSubsystem.h
Engine\Source\Editor\UnrealEd\Public\Subsystems\UnrealEditorSubsystem.h
Engine\Source\Editor\UnrealEd\Public\Subsystems\EditorAssetSubsystem.h
Engine\Source\Editor\LevelEditor\Public\LevelEditorSubsystem.h
Engine\Source\Editor\MaterialEditor\Public\MaterialEditingLibrary.h
Engine\Source\Editor\BlueprintEditorLibrary\Public\BlueprintEditorLibrary.h
Engine\Source\Developer\FunctionalTesting\Public\AutomationBlueprintFunctionLibrary.h
Engine\Source\Editor\UnrealEd\Public\FileHelpers.h            (UEditorLoadingAndSavingUtils)
Engine\Source\Runtime\AssetRegistry\Public\AssetRegistry\IAssetRegistry.h
Engine\Source\Runtime\AssetRegistry\Public\AssetRegistry\AssetRegistryHelpers.h
Engine\Source\Runtime\Engine\Classes\GameFramework\Actor.h
Engine\Source\Runtime\Engine\Classes\Kismet\KismetSystemLibrary.h
Engine\Source\Runtime\Engine\Classes\Kismet\KismetMathLibrary.h
Engine\Source\Runtime\Core\Public\Misc\Paths.h
Engine\Source\Runtime\Engine\Classes\Engine\Blueprint.h
Engine\Source\Runtime\Engine\Classes\EdGraph\EdGraphNode.h
Engine\Source\Runtime\Engine\Classes\EdGraph\EdGraphPin.h
Engine\Plugins\Experimental\PythonScriptPlugin\Source\PythonScriptPlugin\Private\{PyCore,PyEditor,PySlate,PyWrapperObject}.cpp
```

## 3. 模块级 API 核查表

| # | 调用点 | 5.4.4 | 5.7.4 | 依据 | 需不需要改 |
| --- | --- | --- | --- | --- | --- |
| 1 | `unreal.log / log_error / log_warning` `server.py:56,66` `errors.py:131` | 存在 | 存在，未变 | E3：`PyCore.cpp` 方法表两版一致 | 不改 |
| 2 | `unreal.register_slate_post_tick_callback` `dispatcher.py:70` | 存在 | 存在，未变 | E2/E3：`PySlate.cpp` 方法名与参数（`Callable[[float], None]`）一致 | 不改；**行为需真机验证（V1）** |
| 3 | `unreal.unregister_slate_post_tick_callback` `dispatcher.py:186` | 存在 | 存在，未变 | E2/E3 | 同上 |
| 4 | `unreal.register_python_shutdown_callback` `dispatcher.py:72` `server.py:422` | 存在 | 存在，未变 | E3：`PyCore.cpp` | 不改 |
| 5 | `unreal.get_editor_subsystem` + `UnrealEditorSubsystem` `handlers/__init__.py:330` | 存在 | 存在，未变 | E1（`UnrealEditorSubsystem.h`）/E2/E3 | 不改 |
| 6 | `... + EditorActorSubsystem` `handlers/__init__.py:335` | 存在 | 存在，未变 | E1（`EditorActorSubsystem.h`，5.7 仅新增与本次无关的转换/委托成员）/E2 | 不改 |
| 7 | `... + LevelEditorSubsystem` `handlers/__init__.py:340` | 存在 | 存在，未变 | E1（`LevelEditorSubsystem.h`）/E2 | 不改 |
| 8 | `... + EditorAssetSubsystem` `handlers/__init__.py:345` | 存在 | 存在，未变 | E1（`EditorAssetSubsystem.h`）/E2 | 不改 |
| 9 | `unreal.Class` / `unreal.Actor`（`isinstance`、`issubclass`）`handlers/__init__.py:469,491,521,532,551,559,563,571` | 存在 | 存在，未变 | E1（`PyCore.cpp::GetDefaultObject` 逐字相同，仍返回被检类的 CDO）/E2 | 不改 |
| 10 | `unreal.load_class / load_object / find_object` `handlers/__init__.py:624` `actors.py:197` | 存在 | 存在，未变 | E3：`PyCore.cpp` 方法表 | 不改 |
| 11 | `unreal.SystemLibrary.get_path_name` `handlers/__init__.py:616` `serialization.py:156` `blueprints.py:88` `materials.py:112` | 存在 | 存在，未变 | E1：`KismetSystemLibrary.h` `GetPathName(const UObject*)` 两版一致 | 不改 |
| 12 | `unreal.SystemLibrary.get_engine_version` `server.py:519` `status.py:69` | 存在 | 存在，未变 | E1/E2 | 不改（返回串形如 `5.7.4-...`，不做版本号解析） |
| 13 | `unreal.Paths.project_dir / project_saved_dir` `server.py:502` `viewport.py:41,109` | 存在 | 存在，未变 | E1：`Paths.h`（5.7 新增 `CanGetProjectDir()`，原函数保留）/E2 | 不改 |
| 14 | `unreal.Vector / Rotator / LinearColor / Name / Quat / Text / Object` | 存在 | 存在，未变 | E2（引擎核心结构体，5.x 内稳定）；序列化逻辑不依赖版本分支 | 不改 |
| 15 | `unreal.ScopedEditorTransaction`（含上下文管理与 `cancel()`）`actors.py:777` | 存在 | 存在，未变 | E3：`PyEditor.cpp` 两版**逐行相同**（234 行） | 不改；**回滚需真机验证（V3）** |
| 16 | 插件启动方式：`Plugin Content/Python/init_unreal.py` 被自动执行 | 存在 | 存在，未变 | E3：`PythonScriptPlugin.cpp` 两版都会在插件 Python 路径下查找并执行 `init_unreal.py`（5.4:1355 / 5.7:1591） | 不改 |
| 17 | 插件描述符无 `EngineVersion` 时的加载 | 允许（字段可选） | 允许（字段可选） | E4：`EngineVersion` 是可选字段，缺省时不做版本兼容性拦截 | 不改（打包可用 `Tools/stamp_uplugin.py` 注入） |

## 4. Handler / 调用点核查表

说明：`已改` 表示本次有代码改动；`真机` 表示静态证据充分但行为需引擎确认（§5 有验证步骤）。

### 4.1 actors.py（`actor.query` / `actor.edit`）

| 调用点 | 5.4.4 | 5.7.4 | 依据 | 结论 |
| --- | --- | --- | --- | --- |
| `unreal.ActorComponent`（`get_components_by_class` 的类参数）`:124` | 存在 | 存在 | E1 `Actor.h` / E2 | 不改 |
| `unreal.load_class`（组件类回退）`:197` | 存在 | 存在 | E3 | 不改 |
| `unreal.StaticMesh` / `SkeletalMesh` / `MeshComponent` `:421,426,541` | 存在 | 存在 | E2 | 不改 |
| `unreal.Vector` `:442,646,651`、`unreal.Rotator` `:443` | 存在 | 存在 | E2 | 不改 |
| `unreal.Name` `:464,517`、`unreal.ComponentMobility` `:483` | 存在 | 存在 | E2（枚举成员 STATIC/STATIONARY/MOVABLE 两版均存在） | 不改 |
| `unreal.ScopedEditorTransaction` `:777` | 存在 | 存在 | E3 | 不改；真机 V3 |
| `AActor.get_actor_bounds / set_actor_label / get_editor_property / set_editor_property / set_actor_location / set_actor_rotation / set_actor_scale3d / get_actor_transform / get_actor_forward_vector / get_folder_path / set_folder_path / get_level` | 存在 | 存在，UFUNCTION 声明未变 | E1 `Actor.h`（差异仅为 `FORCEINLINE`→`inline` 等修饰，非签名） | 不改 |
| `EditorActorSubsystem.get_all_level_actors / get_selected_level_actors / set_selected_level_actors / spawn_actor_from_class / destroy_actor / duplicate_actor` | 存在 | 存在，签名未变 | E1 `EditorActorSubsystem.h`；5.7 为 `DuplicateActor` 增加**非 UFUNCTION** 重载，Python 仍暴露 3 参数版本 | 不改 |

### 4.2 levels.py（`level.control`）

| 调用点 | 5.4.4 | 5.7.4 | 依据 | 结论 |
| --- | --- | --- | --- | --- |
| `unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages` `:26`（`status.py:50` 同） | 存在 | 存在，未变 | E1 `FileHelpers.h` | 不改 |
| `LevelEditorSubsystem.load_level / save_current_level / save_all_dirty_levels / new_level / new_level_from_template` | 存在 | 存在，签名逐字相同 | E1 | 不改 |
| `world.get_path_name / get_name / get_outer / get_editor_property("world_partition")` `:65` | 前三者存在；`world_partition` **不是 UPROPERTY** | 同 5.4 | E1 `World.h`：`UWorld::IsPartitionedWorld()` 不是 `UFUNCTION`，Python 无法读取 | **已知限制**（§7），不改语义；真机 V6 顺带记录 |
| `package.get_name / get_path_name / get_editor_property("is_map")` `:45` | 前两者存在；`is_map` **不是 UPROPERTY** | 同 5.4 | E1 `Package.h`：地图性是 `PKG_ContainsMap` 包标志，无同名属性 | **已改**：来源是 `get_dirty_map_packages()`，`isMap` 直接为 `true` |

### 4.3 assets.py（`asset.search`）

| 调用点 | 5.4.4 | 5.7.4 | 依据 | 结论 |
| --- | --- | --- | --- | --- |
| `unreal.AssetRegistryHelpers.get_asset_registry` `:25`（`status.py:87` 同） | 存在 | 存在，未变 | E1 `AssetRegistryHelpers.h` | 不改 |
| `unreal.AssetRegistryDependencyOptions` + 6 个 `include_*` 属性 `:93` | 存在 | 存在，字段集合相同 | E1 `IAssetRegistry.h` 结构体定义 | 不改（缺字段时已降级为 warning） |
| `registry.get_assets_by_path(Name(path), recursive)` `:259` | 存在 | 存在，签名未变 | E1 `IAssetRegistry.h`；5.6 起仅 `GetAssetByObjectPath(FName)` 被标记弃用，本插件未用 | 不改 |
| `registry.get_dependencies / get_referencers` `:138,147` | 存在 | 存在，`K2_GetDependencies/K2_GetReferencers` 的 `ScriptName` 映射与参数未变 | E1 | 不改 |
| `registry.is_loading_assets / wait_for_completion / search_all_assets` `:59,63,31` | 存在 | 存在，未变 | E1 | 不改 |
| `unreal.AssetRegistryHelpers.is_redirector` `:285`（`handlers/__init__.py:694` 同） | 存在 | 存在，未变 | E1 | 不改 |
| `unreal.Name` `:259` | 存在 | 存在 | E2 | 不改 |

### 4.4 materials.py（`material.params`）

| 调用点 | 5.4.4 | 5.7.4 | 依据 | 结论 |
| --- | --- | --- | --- | --- |
| `unreal.MaterialInterface` `:67`、`MaterialInstanceConstant` `:103,368,424`、`MaterialInstanceConstantFactoryNew` `:421` | 存在 | 存在 | E2 | 不改 |
| `unreal.AssetToolsHelpers.get_asset_tools` `:422` | 存在 | 存在 | E2（`AssetTools.dll` 两版均导出 `GetAssetTools`） | 不改 |
| `MaterialEditingLibrary.get_*_parameter_names` `:83` | 存在 | 存在，签名（`void (Material, TArray<FName>&)`）未变 | E1 | 不改 |
| `MaterialEditingLibrary.get/set_material_instance_*_parameter_value` `:105,291` | 存在 | 存在；仅 static switch setter 末尾新增可选 `bUpdateMaterialInstance=true` | E1 | 不改（3 参数调用兼容） |
| `MaterialEditingLibrary.set_material_instance_parent / update_material_instance` `:432,433,301` | 存在 | 存在，签名未变 | E1 | 不改 |
| `unreal.LinearColor` `:244`、`unreal.Name` `:107,292` | 存在 | 存在 | E2 | 不改 |
| `EditorAssetSubsystem.save_asset(path, False)` `:453` | 存在 | 存在，签名未变 | E1 | 不改 |

### 4.5 blueprints.py（`blueprint.query`）

| 调用点 | 5.4.4 | 5.7.4 | 依据 | 结论 |
| --- | --- | --- | --- | --- |
| `unreal.Blueprint` `:64` | 存在 | 存在 | E2 | 不改 |
| `unreal.SystemLibrary.get_path_name` `:88` | 存在 | 存在 | E1 | 不改 |
| `EditorAssetSubsystem.save_asset` `:317` | 存在 | 存在 | E1 | 不改 |
| `unreal.BlueprintEditorLibrary.compile_blueprint` `:392` | 存在 | 存在，签名 `void (UBlueprint*)` 未变 | E1 | 不改；真机 V4 |
| `UBlueprint` 属性：`parent_class`、`new_variables`、`component_templates`、`ubergraph_pages`、`function_graphs`、`macro_graphs`、`implemented_interfaces`、`status` | 存在 | 存在，UPROPERTY 名未变 | E1 `Blueprint.h` | 不改；真机 V4 |
| `UEdGraphNode` 属性：`node_guid`、`node_pos_x/y`、`node_comment`、`pins` | 存在 | 存在，未变 | E1 `EdGraphNode.h` | 不改；真机 V4 |
| `UEdGraphPin` / `FEdGraphPinType` 属性：`pin_name`、`direction`、`pin_type`、`linked_to`、`pin_category`、`pin_sub_category`、`pin_sub_object` | 存在 | 存在，未变 | E1 `EdGraphPin.h` | 不改；真机 V4 |

### 4.6 viewport.py（`viewport.capture`）

| 调用点 | 5.4.4 | 5.7.4 | 依据 | 结论 |
| --- | --- | --- | --- | --- |
| `unreal.Paths.project_saved_dir` `:41,109` | 存在 | 存在 | E1 | 不改 |
| `unreal.Vector` `:94`、`unreal.MathLibrary.find_look_at_rotation` `:101` | 存在 | 存在，签名未变 | E1 `KismetMathLibrary.h` | 不改 |
| `UnrealEditorSubsystem.get_level_viewport_camera_info / set_level_viewport_camera_info` | 存在 | 存在，签名逐字相同（返回 `bool` + 2 个出参；入参 `FVector, FRotator`） | E1 | 不改 |
| `unreal.AutomationLibrary.take_high_res_screenshot(width, height, path)` `:232` | 存在 | 存在，签名未变（`ResX, ResY, Filename, Camera=null, bMaskEnabled=false, bCaptureHDR=false, ComparisonTolerance=Low, ComparisonNotes="", Delay=0, bForceGameView=true`） | E1 `AutomationBlueprintFunctionLibrary.h` / E4 | 不改；**内容需真机验证（V2）** |
| `task.is_task_done()` `:252` | 存在 | 存在，未变 | E1 | 不改 |

### 4.7 console.py / python_exec.py

| 调用点 | 5.4.4 | 5.7.4 | 依据 | 结论 |
| --- | --- | --- | --- | --- |
| `unreal.SystemLibrary.execute_console_command(context, command)` `console.py:105` | 存在 | 存在，签名逐字相同 | E1 `KismetSystemLibrary.h` | 不改 |
| `python_exec.py`：`compile/exec/eval` + `unreal` 模块对象（无 API 调用） | 引擎 Python 3.11 | 引擎 Python 3.11 | 两版 `python311.dll`，`sys.version` 均为 3.11.8 | 不改 |

### 4.8 status.py / server.py / dispatcher.py / serialization.py

| 调用点 | 5.4.4 | 5.7.4 | 依据 | 结论 |
| --- | --- | --- | --- | --- |
| `unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages` `status.py:50` | 存在 | 存在 | E1 | 不改 |
| `unreal.SystemLibrary.get_engine_version` `status.py:69` | 存在 | 存在 | E1/E2 | 不改 |
| `unreal.AssetRegistryHelpers.get_asset_registry` + `is_loading_assets` `status.py:87` | 存在 | 存在 | E1 | 不改 |
| `world.get_editor_property("world_partition")` `status.py:124` | 非 UPROPERTY | 非 UPROPERTY | E1 | 已知限制（§7） |
| `unreal.register_python_shutdown_callback` `server.py:422` | 存在 | 存在 | E3 | 不改 |
| `unreal.Paths.project_dir` `server.py:502` | 存在 | 存在 | E1 | 不改 |
| `unreal.log / log_error` `server.py:56,66` | 存在 | 存在 | E3 | 不改 |
| `register/unregister_slate_post_tick_callback` `dispatcher.py:70,186` | 存在 | 存在；5.7 内部守卫改为 `PyUtil::CanTickPython()` | E3 | 不改；真机 V1 |
| `unreal.SystemLibrary.get_path_name` `serialization.py:156` | 存在 | 存在 | E1 | 不改 |
| 类型判定 `unreal.Vector/Quat/Rotator/LinearColor/Name/Text/Object` `serialization.py:139-158` | 存在 | 存在 | E2 | 不改 |

## 5. 需真机验证的项（静态无法判定）

> 前提：主管确认允许启动引擎、并指定工程后进行；**不要**装进用户现有 5.4/5.7 工程，使用你本机任一测试工程或临时拷贝工程。
> 所有命令均为 `UnrealEditor-Cmd.exe <YourProject>.uproject -run=pythonscript -script=<RepoRoot>\UEMCPBridge\Tests\<脚本> -unattended -nop4 -nosplash`。

| ID | 项目 | 为什么静态判不了 | 验证步骤 | 判定标准 |
| --- | --- | --- | --- | --- |
| V1 | Slate tick 泵与游戏线程队列 | 5.7 把 tick 守卫从 `GIsSavingPackage/IsGarbageCollecting/IsRoutingPostLoad` 改为 `PyUtil::CanTickPython()`，静态无法证明回调仍按预期触发 | 1) 5.4 与 5.7 分别跑 `Tests/probe_ue57.py`（默认只读）；2) 分别跑 `Tests/smoke_bridge.py`；3) 在两个版本各发一次 `editor.status`（真实 HTTP，非同步 dispatcher） | 探针 `RESULT PASS`；smoke `SMOKE_RESULT PASS`；`editor.status` 在 5 秒内返回且 `meta.ueVersion` 为对应版本 |
| V2 | 截图内容与格式 | `bForceGameView` 默认 `true`，编辑器视口截图是否取到正确画面、是否只产出 PNG，只能看文件 | `probe_ue57.py --capture`（在**非** `-nullrhi` 的真实编辑器会话再跑一次），检查 `Saved/UEMCP/probe/ue_probe_capture.png` | `produced=true`、`isPng=true`、`bytes>0`，人工打开图片非全黑；随后调 `viewport.capture`（`format=png` 与 `format=jpeg` 各一次），确认 `result.format` 与实际文件一致且带 `FORMAT_MISMATCH`（jpeg 请求时） |
| V3 | 事务回滚 / dryRun | `ScopedEditorTransaction.cancel()` 的撤销效果只能实测 | 1) `allowWrite=true`；2) `actor.edit` 提交“spawn + 非法 class”且 `atomic=true`；3) `dryRun=true` 再发一次 | 第 2 步返回 `TRANSACTION_FAILED` 且 `details.rolledBack=true`、场景中**没有**新 Actor；`dryRun` 返回 `dryRun:true` 且场景零变化 |
| V4 | 蓝图读取/编译 | `get_editor_property` 的可用性取决于属性是否仍是 UPROPERTY（已静态确认，但仍需运行验证返回值形状） | `probe_ue57.py --blueprint /Game/<BP>`，再对同一 BP 调 `blueprint.query`（`includeNodes=true`）与 `action=compile` | 探针 `blueprint_query_compile` OK，`variables/graphs/nodeProperties/pinProperties` 非空；`blueprint.query` 不返回 `NODE_INSPECTION_UNSTABLE`；compile 后 `compileState.status` 为 `up_to_date`/`dirty` 而非 `error` |
| V5 | 材质参数读写 | 参数名枚举返回 tuple 的形状与 setter 返回值需实测 | `probe_ue57.py --material /Game/<MI>`，再调 `material.params` 的 `get`/`set` | 探针列出 scalar 参数；`get` 有值、`set` 成功后 `get` 反映新值，无 `PYTHON_ERROR` |
| V6 | Actor 生成/复制/类解析与 PIE 拒绝 | `unreal.Class`/CDO 的 5.4 怪癖在 5.7 是否保持，以及 PIE 状态判定 | `probe_ue57.py --live-actors`；再跑 `Tests/probe_defect4_verify.py`；启动 PIE 后发 `actor.edit` | 探针 `spawn_duplicate_destroy` OK 且 `actorDelta=0`；类解析结果与 5.4 记录一致；PIE 中写操作返回 `EDITOR_UNSAFE_STATE` |
| V7 | 控制台执行 | 需要真实 world context | `probe_ue57.py --console`，再调 `console.command`（`stat none`） | 探针 `console_command` OK；`console.command` 返回 `dispatched:true`、`outputAvailable:false` |

## 6. 本次改动清单（文件 / 原因 / 风险）

| 文件 | 改动 | 原因 | 风险 |
| --- | --- | --- | --- |
| `UEMCPBridge.uplugin` | 删除 `EngineVersion`；`Description` 改为版本无关 | 源码不应写死 5.4；缺省该字段时任意 UE5 均可加载 | 打包产物若需显式版本，必须用 `Tools/stamp_uplugin.py` 注入（已提供脚本+自检） |
| `Tools/stamp_uplugin.py`（新增） | 从 `--engine` 或 `<Engine>/Build/Build.version` 注入 `EngineVersion` | 满足“打包脚本注入、本地默认可用” | 纯离线脚本，不参与运行时；`--inplace` 对仓库文件默认拒绝 |
| `uemcp_bridge/ratelimit.py`（新增） | 线程安全令牌桶 | 架构 §6.7“桥接端全局 30 req/s”此前未实现 | 低：默认 30/s 突发 30，仅超限请求受影响 |
| `uemcp_bridge/settings.py` | 新增 `rateLimitEnabled / rateLimitPerSecond / rateLimitBurst`（JSON + 环境变量，0 或 false 可关闭） | 可配置、可关闭 | 低：新增键，旧配置文件不受影响 |
| `uemcp_bridge/rpc.py` | 在**权限门之前、入队之前**做全局限流，超限抛 `RATE_LIMITED` | 拒绝不得产生编辑器副作用 | 低：仅新增 429 分支；未知 method 在限流前已被拒，不消耗令牌 |
| `uemcp_bridge/server.py` | 启动时创建限流器、停止时释放；`/health` 增加 `rateLimit` 字段 | 运维与自检可见 | 低：`/health` 为附加字段，MCP Server 只读取已知字段 |
| `uemcp_bridge/handlers/levels.py` | `isMap` 由恒 `false` 改为 `true` | 来源就是“脏地图包”，且 `UPackage` 无 `is_map` 属性 | 低：修正错误值（5.4/5.7 同样修正） |
| `uemcp_bridge/handlers/viewport.py` | `format` 按文件头返回真实格式；新增 `FORMAT_MISMATCH` / `SCREENSHOT_FALLBACK_PATH` 警告 | 引擎只写 PNG，旧代码在 jpeg 请求时谎报格式 | 低：jpeg 请求的 `format` 现为 `"png"`（真实值），并带警告 |
| `Tests/test_port_fallback.py` | 占用 18778 时短暂重试 | 连续跑测试时端口刚释放可能瞬时 `WSAEADDRINUSE` | 无（仅测试） |
| `Tests/test_rate_limit.py`（新增） | 令牌桶/配置/HTTP 429/入队前拦截 | 交付验收 | 无 |
| `Tests/test_bridge_timeout_http.py`（新增） | 真实 dispatcher 超时 → 504/`BRIDGE_TIMEOUT` | 已知技术债：真实超时路径从未覆盖 | 无 |
| `Tests/test_uplugin_metadata.py`（新增） | 元数据与 stamp 脚本校验 | 防止 `EngineVersion` 回潮 | 无 |
| `Tests/probe_ue57.py`（新增） | 真机探针（只读默认） | 支撑 §5 | 无（需引擎，未在本次运行） |
| `README.md` / `COMPAT-UE57.md` | 文档更新 | 交付 | 无 |

### 5.4 上可能产生的行为变化（明确列出）

1. **新增全局限流**：默认开启（30 req/s、突发 30）。此前不限流；超过阈值会收到 `HTTP 429` + `RATE_LIMITED`（`retryable=true`）。可用 `rateLimitEnabled=false` 或 `rateLimitPerSecond=0` 恢复旧行为。
2. **`/health` 新增 `rateLimit` 字段**（含 `enabled/perSecond/burst/available/accepted/rejected`）。
3. **`level.control` 的 `list_dirty` / `get_current`**：`isMap` 由恒 `false` 变为 `true`（仅 `list_dirty` 输出该字段）。
4. **`viewport.capture`**：`format` 改为文件真实格式；请求 `jpeg` 时现在返回 `format:"png"` + `FORMAT_MISMATCH`（此前返回 `format:"jpeg"`）；引擎写盘路径与请求不一致时新增 `SCREENSHOT_FALLBACK_PATH` 警告。
5. **`.uplugin` 不再声明 `EngineVersion=5.4.0`**：编辑器/打包器不再看到 5.4 引脚。

除上述 5 条外，5.4 上的 API 调用路径与返回值不变。

## 7. 已知限制（与引擎版本无关，本次未改语义）

| 项 | 现状 | 说明 |
| --- | --- | --- |
| `isPartitioned` | 恒 `false` | `UWorld::IsPartitionedWorld()` 不是 `UFUNCTION`，Python 无对应可读属性；`get_editor_property("world_partition")` 在两个版本都不存在。属既有技术债，需 C++ 或引擎侧新增绑定才能解决（不在本插件“纯 Python”边界内） |
| `jpeg` 输出 | 引擎只产出 PNG | 已在响应中如实报告并给警告；不伪造转码（避免引入第三方依赖） |
| 截图 fallback | 引擎可能忽略绝对目标路径 | 回退到 `Saved/Screenshots` 下最新 PNG，并在 `warnings` 明示 |
| `elicitation` | Bridge 侧不涉及 | 该分支在 MCP Server 侧；Bridge 只接收已决请求 |
| 蓝图节点编辑 | `CAPABILITY_UNAVAILABLE` | 5.4/5.7 Python 均无节点编辑 API；边界不变 |

## 8. 自检与验收

`UEMCPBridge/Tests` 下 11 个无编辑器脚本，使用引擎自带 Python 3.11.8 实跑，全部 exit 0：

| # | 脚本 | 覆盖 | 退出码 |
| --- | --- | --- | --- |
| 1 | `check_error_codes.py` | 错误码表 + `INVALID_ARGUMENT` 契约 | 0 |
| 2 | `check_handler_names.py` | 未定义名称静态扫描 | 0 |
| 3 | `test_serialization.py` | FQuat/FTransform 序列化 | 0 |
| 4 | `test_class_path_resolution.py` | 类名/类路径/蓝图生成类解析 | 0 |
| 5 | `test_dependency_options.py` | 依赖选项映射与降级 | 0 |
| 6 | `test_python_error_mapping.py` | Python 异常 → `PYTHON_ERROR` | 0 |
| 7 | `test_discovery_lifecycle.py` | 发现文件生命周期 | 0 |
| 8 | `test_port_fallback.py` | 18778 占用 → 回退 18779 | 0 |
| 9 | `test_rate_limit.py`（新增） | 令牌桶/配置/429/入队前拦截 | 0 |
| 10 | `test_uplugin_metadata.py`（新增） | `.uplugin` 与 stamp 脚本 | 0 |
| 11 | `test_bridge_timeout_http.py`（新增） | 真实 `BRIDGE_TIMEOUT`（504/-32020/retryable） | 0 |

需引擎的用例（`smoke_bridge.py`、`probe_transform.py`、`probe_defect4_verify.py`、`probe_ue57.py`）按 §5 与 QA 联跑后补实测记录。
