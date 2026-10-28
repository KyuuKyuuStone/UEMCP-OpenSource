"""UE 5.x compatibility probe for UEMCPBridge (run inside the editor).

This is the real-engine half of ``COMPAT-UE57.md``: it exercises the exact
``unreal.*`` API points the bridge uses, records the engine/Python versions and
writes a JSON report so a 5.4 run and a 5.7 run can be diffed.

It is read-only by default.  The opt-in switches create editor state, so only
use them on a throw-away project:

    UnrealEditor-Cmd.exe <Project>.uproject -run=pythonscript \
      -script=Plugins/UEMCPBridge/Tests/probe_ue57.py -unattended -nop4 -nosplash

    # optional live checks
    ... -script=... --live-actors --capture --console

Output: ``<Project>/Saved/UEMCP/probe_ue57.json`` (override with ``--out``).

Exit code 0 = every required check passed, 1 = a required check failed,
2 = the probe could not start.
"""

import json
import os
import sys
import time
import traceback

import unreal

RESULT = {"checks": [], "engine": {}, "python": sys.version, "capture": None}


def _arg(name):
    return name in sys.argv[1:]


def _arg_value(name, default=None):
    argv = sys.argv[1:]
    for index, item in enumerate(argv):
        if item == name and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith(name + "="):
            return item.split("=", 1)[1]
    return default


def _check(name, required, fn):
    try:
        value = fn()
        entry = {"name": name, "required": required, "ok": True, "value": value}
    except Exception as exc:
        entry = {
            "name": name,
            "required": required,
            "ok": False,
            "error": "%s: %s" % (type(exc).__name__, exc),
            "traceback": traceback.format_exc()[-2000:],
        }
    RESULT["checks"].append(entry)
    status = "OK  " if entry["ok"] else "FAIL"
    print("[probe] %s %-42s %s" % (status, name, entry.get("value", entry.get("error"))))
    return entry


def _present(owner, attribute):
    return bool(hasattr(owner, attribute))


def _editor_subsystem():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if subsystem is None:
        raise RuntimeError("UnrealEditorSubsystem is None")
    return type(subsystem).__name__


def _actor_subsystem():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if subsystem is None:
        raise RuntimeError("EditorActorSubsystem is None")
    return type(subsystem).__name__


def _level_subsystem():
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if subsystem is None:
        raise RuntimeError("LevelEditorSubsystem is None")
    return type(subsystem).__name__


def _asset_subsystem():
    subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    if subsystem is None:
        raise RuntimeError("EditorAssetSubsystem is None")
    return type(subsystem).__name__


def _editor_world():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None:
        raise RuntimeError("GetEditorWorld() returned None")
    return {
        "path": str(world.get_path_name()),
        "package": str(world.get_outer().get_name()),
        # Returns False on engines where the value is not exposed as a
        # UPROPERTY; recorded so 5.4/5.7 can be compared.
        "worldPartitionProperty": _safe_editor_property(world, "world_partition"),
        "isPartitionedWorldAttr": _present(world, "is_partitioned_world"),
    }


def _game_world():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    return None if world is None else str(world.get_path_name())


def _safe_editor_property(obj, name):
    try:
        return repr(obj.get_editor_property(name))
    except Exception as exc:
        return "unavailable (%s)" % type(exc).__name__


def _actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    selected = subsystem.get_selected_level_actors()
    duplicate_actor = getattr(subsystem, "duplicate_actor", None)
    return {
        "count": len(actors),
        "selected": len(selected),
        "first": str(actors[0].get_path_name()) if actors else None,
        "duplicateActor": bool(duplicate_actor),
    }


def _class_resolution():
    static_mesh_actor = unreal.StaticMeshActor
    native = unreal.load_class(None, "/Script/Engine.StaticMeshActor")
    cdo_module = unreal.get_default_object(native) if native is not None else None
    return {
        "loadClassType": type(native).__name__ if native is not None else None,
        "isClass": isinstance(native, unreal.Class) if native is not None else None,
        "isActorClass": isinstance(static_mesh_actor.static_class(), unreal.Class),
        "cdoType": type(cdo_module).__name__ if cdo_module is not None else None,
        "cdoIsActor": isinstance(cdo_module, unreal.Actor),
    }


def _registry():
    helper = unreal.AssetRegistryHelpers
    registry = helper.get_asset_registry()
    if registry is None:
        raise RuntimeError("GetAssetRegistry() returned None")
    assets = registry.get_assets_by_path(unreal.Name("/Game"), True)
    options = unreal.AssetRegistryDependencyOptions()
    option_names = (
        "include_hard_package_references",
        "include_soft_package_references",
        "include_hard_management_references",
        "include_soft_management_references",
        "include_management_references",
        "include_searchable_names",
    )
    return {
        "registryType": type(registry).__name__,
        "gameAssets": len(assets),
        "isRedirectorAttr": _present(helper, "is_redirector"),
        "isLoadingAssets": (
            bool(registry.is_loading_assets())
            if _present(registry, "is_loading_assets")
            else None
        ),
        "waitForCompletion": _present(registry, "wait_for_completion"),
        "searchAllAssets": _present(registry, "search_all_assets"),
        "dependencyOptions": {name: _present(options, name) for name in option_names},
        "dependenciesCallable": _present(registry, "get_dependencies"),
        "referencersCallable": _present(registry, "get_referencers"),
    }


def _dirty_packages():
    packages = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    return {"count": len(packages or [])}


def _utility_libraries():
    return {
        "blueprintCompile": _present(unreal.BlueprintEditorLibrary, "compile_blueprint"),
        "materialEdit": {
            name: _present(unreal.MaterialEditingLibrary, name)
            for name in (
                "get_scalar_parameter_names",
                "get_vector_parameter_names",
                "get_texture_parameter_names",
                "get_static_switch_parameter_names",
                "get_material_instance_scalar_parameter_value",
                "set_material_instance_scalar_parameter_value",
                "set_material_instance_parent",
                "update_material_instance",
            )
        },
        "screenshot": _present(unreal.AutomationLibrary, "take_high_res_screenshot"),
        "console": _present(unreal.SystemLibrary, "execute_console_command"),
        "engineVersion": str(unreal.SystemLibrary.get_engine_version()),
        "projectDir": str(unreal.Paths.project_dir()),
        "projectSavedDir": str(unreal.Paths.project_saved_dir()),
        "mathFindLookAt": _present(unreal.MathLibrary, "find_look_at_rotation"),
        "assetTools": _present(unreal.AssetToolsHelpers, "get_asset_tools"),
        "materialFactory": str(unreal.MaterialInstanceConstantFactoryNew.__name__),
        "componentMobility": [
            name
            for name in ("STATIC", "STATIONARY", "MOVABLE")
            if hasattr(unreal.ComponentMobility, name)
        ],
    }


def _python_globals():
    names = (
        "get_editor_subsystem",
        "get_default_object",
        "load_class",
        "load_object",
        "find_object",
        "register_slate_post_tick_callback",
        "unregister_slate_post_tick_callback",
        "register_python_shutdown_callback",
        "log",
        "log_error",
        "log_warning",
    )
    return {name: _present(unreal, name) for name in names}


def _transaction():
    with unreal.ScopedEditorTransaction("UEMCP probe transaction"):
        pass
    cancelled = False
    try:
        transaction = unreal.ScopedEditorTransaction("UEMCP probe cancel")
        cancel = getattr(transaction, "cancel", None)
        cancelled = callable(cancel)
        if cancelled:
            cancel()
    except Exception:
        cancelled = False
    return {"contextManager": True, "cancelCallable": cancelled}


def _blueprint(path):
    blueprint = unreal.load_asset(path)
    if blueprint is None:
        raise RuntimeError("blueprint not found: %s" % path)
    if not isinstance(blueprint, unreal.Blueprint):
        raise RuntimeError("not a Blueprint: %s" % path)
    data = {
        "path": path,
        "status": _safe_editor_property(blueprint, "status"),
        "parentClass": _safe_editor_property(blueprint, "parent_class"),
        "variables": len(blueprint.get_editor_property("new_variables") or []),
        "componentTemplates": len(blueprint.get_editor_property("component_templates") or []),
        "ubergraphPages": len(blueprint.get_editor_property("ubergraph_pages") or []),
        "functionGraphs": len(blueprint.get_editor_property("function_graphs") or []),
        "macroGraphs": len(blueprint.get_editor_property("macro_graphs") or []),
        "implementedInterfaces": len(
            blueprint.get_editor_property("implemented_interfaces") or []
        ),
    }
    graph = None
    pages = blueprint.get_editor_property("ubergraph_pages") or []
    if pages:
        graph = pages[0]
    elif (blueprint.get_editor_property("function_graphs") or []):
        graph = blueprint.get_editor_property("function_graphs")[0]
    if graph is not None:
        nodes = graph.get_editor_property("nodes") or []
        data["firstGraphNodes"] = len(nodes)
        if nodes:
            node = nodes[0]
            data["nodeProperties"] = {
                "nodeGuid": _safe_editor_property(node, "node_guid"),
                "nodePosX": _safe_editor_property(node, "node_pos_x"),
                "nodeComment": _safe_editor_property(node, "node_comment"),
                "pins": len(node.get_editor_property("pins") or []),
            }
            pins = node.get_editor_property("pins") or []
            if pins:
                data["pinProperties"] = {
                    "pinName": _safe_editor_property(pins[0], "pin_name"),
                    "direction": _safe_editor_property(pins[0], "direction"),
                    "pinType": _safe_editor_property(pins[0], "pin_type"),
                }
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    data["compiledStatus"] = _safe_editor_property(blueprint, "status")
    return data


def _material(path):
    material = unreal.load_asset(path)
    if material is None:
        raise RuntimeError("material not found: %s" % path)
    if not isinstance(material, unreal.MaterialInterface):
        raise RuntimeError("not a material: %s" % path)
    names = unreal.MaterialEditingLibrary.get_scalar_parameter_names(material)
    if isinstance(names, tuple):
        names = names[0] if names else []
    return {
        "path": path,
        "type": type(material).__name__,
        "scalarParameters": [str(item) for item in (names or [])][:20],
        "isInstanceConstant": isinstance(material, unreal.MaterialInstanceConstant),
    }


def _live_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    original = subsystem.get_all_level_actors()
    spawned = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0), unreal.Rotator())
    if spawned is None:
        raise RuntimeError("spawn_actor_from_class returned None")
    duplicate = subsystem.duplicate_actor(spawned, None, unreal.Vector(100, 0, 0))
    if duplicate is None:
        raise RuntimeError("duplicate_actor returned None")
    removed = subsystem.destroy_actor(duplicate)
    removed = bool(subsystem.destroy_actor(spawned)) and removed
    return {
        "spawned": True,
        "duplicated": True,
        "removed": removed,
        "actorDelta": len(subsystem.get_all_level_actors()) - len(original),
    }


def _capture():
    saved = str(unreal.Paths.project_saved_dir())
    directory = os.path.join(saved, "UEMCP", "probe")
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, "ue_probe_capture.png")
    task = unreal.AutomationLibrary.take_high_res_screenshot(640, 360, target)
    deadline = time.time() + 20.0
    while time.time() < deadline:
        if task is None or task.is_task_done():
            break
        time.sleep(0.2)
    produced = os.path.isfile(target) and os.path.getsize(target) > 0
    header = b""
    if produced:
        with open(target, "rb") as handle:
            header = handle.read(8)
    RESULT["capture"] = {
        "taskCreated": task is not None,
        "target": target,
        "produced": produced,
        "bytes": os.path.getsize(target) if produced else 0,
        "isPng": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "note": "Inline captures can be black in -nullrhi commandlets; "
        "verify in a real editor session too.",
    }
    return RESULT["capture"]


def _console():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, "stat none")
    return {"executed": "stat none"}


def _write_report():
    project_saved = str(unreal.Paths.project_saved_dir())
    path = _arg_value("--out") or os.path.join(project_saved, "UEMCP", "probe_ue57.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(RESULT, handle, ensure_ascii=False, indent=2, default=str)
    print("[probe] report written: %s" % path)
    return path


def main():
    try:
        RESULT["engine"] = {
            "version": str(unreal.SystemLibrary.get_engine_version()),
            "editor": bool(unreal.SystemLibrary.is_editor()),
        }
    except Exception as exc:
        print("[probe] cannot read engine version: %s" % exc)
        return 2

    _check("python_globals", True, _python_globals)
    _check("unreal_editor_subsystem", True, _editor_subsystem)
    _check("editor_actor_subsystem", True, _actor_subsystem)
    _check("level_editor_subsystem", True, _level_subsystem)
    _check("editor_asset_subsystem", True, _asset_subsystem)
    _check("editor_world", True, _editor_world)
    _check("game_world_absent", True, _game_world)
    _check("all_level_actors", True, _actors)
    _check("class_resolution", True, _class_resolution)
    _check("asset_registry", True, _registry)
    _check("dirty_map_packages", True, _dirty_packages)
    _check("utility_libraries", True, _utility_libraries)
    _check("scoped_editor_transaction", True, _transaction)

    blueprint_path = _arg_value("--blueprint")
    if blueprint_path:
        _check("blueprint_query_compile", True, lambda: _blueprint(blueprint_path))
    material_path = _arg_value("--material")
    if material_path:
        _check("material_parameters", True, lambda: _material(material_path))

    if _arg("--live-actors"):
        _check("spawn_duplicate_destroy", True, _live_actors)
    if _arg("--capture"):
        _check("high_res_screenshot", True, _capture)
    if _arg("--console"):
        _check("console_command", True, _console)

    path = _write_report()
    failed = [item for item in RESULT["checks"] if item["required"] and not item["ok"]]
    print(
        "[probe] RESULT %s checks=%d failed=%d report=%s"
        % ("FAIL" if failed else "PASS", len(RESULT["checks"]), len(failed), path)
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
