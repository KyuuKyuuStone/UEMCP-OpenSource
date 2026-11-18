"""Real-engine probe #2: class predicates, class paths, dependencies, spawn.

Run with UnrealEditor-Cmd -run=pythonscript.  Writes
``Saved/UEMCP/probe_defect4_raw2.json``.  Reports actual behaviour only.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
RESULT_PATH = os.path.join(PROJECT_DIR, "Saved", "UEMCP", "probe_defect4_raw2.json")

import unreal  # noqa: E402


def attempt(label, fn):
    try:
        value = fn()
        return {
            "label": label,
            "ok": True,
            "repr": repr(value)[:300],
            "type": type(value).__name__,
            "value": value if isinstance(value, (bool, int, float, str)) or value is None else None,
        }
    except Exception as exc:
        return {"label": label, "ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}


def probe_class_predicates():
    cls_obj = unreal.load_class(None, "/Script/Engine.StaticMeshActor")
    methods = [name for name in dir(cls_obj) if not name.startswith("_")]
    return {
        "methods": methods,
        "results": [
            attempt("issubclass(Class, Actor)", lambda: issubclass(cls_obj, unreal.Actor)),
            attempt("is_child_of(Actor)", lambda: cls_obj.is_child_of(unreal.Actor)),
            attempt("get_super_class()", lambda: cls_obj.get_super_class()),
            attempt("get_super_class().get_name()", lambda: cls_obj.get_super_class().get_name()),
            attempt("cast(Actor)", lambda: cls_obj.cast(unreal.Actor)),
            attempt("Actor.cast(Class)", lambda: unreal.Actor.cast(cls_obj)),
            attempt("isinstance(Class, unreal.Class)", lambda: isinstance(cls_obj, unreal.Class)),
            attempt("get_class()", lambda: cls_obj.get_class()),
            attempt("get_path_name()", lambda: cls_obj.get_path_name()),
            attempt("get_name()", lambda: cls_obj.get_name()),
            attempt("class_display_name", lambda: unreal.SystemLibrary.get_class_display_name(cls_obj.get_class())),
        ],
    }


def probe_python_type_paths():
    py_type = getattr(unreal, "StaticMeshActor")
    cdo = None
    try:
        cdo = unreal.get_default_object(py_type)
    except Exception:
        cdo = None
    return {
        "python_type": {
            "repr": repr(py_type),
            "name": getattr(py_type, "__name__", None),
            "module": getattr(py_type, "__module__", None),
            "is_type": isinstance(py_type, type),
        },
        "results": [
            attempt("py_type.static_class()", lambda: py_type.static_class()),
            attempt("py_type.static_class().get_path_name()", lambda: py_type.static_class().get_path_name()),
            attempt("py_type.static_class().is_child_of(Actor)", lambda: py_type.static_class().is_child_of(unreal.Actor)),
            attempt("unreal.SystemLibrary.get_path_name(py_type)", lambda: unreal.SystemLibrary.get_path_name(py_type)),
            attempt("load_class('/Script/Engine.' + name)", lambda: unreal.load_class(None, "/Script/Engine." + py_type.__name__)),
            attempt("get_default_object(type)", lambda: cdo),
            attempt("cdo.get_class()", lambda: cdo.get_class() if cdo else None),
            attempt("cdo.get_class().get_path_name()", lambda: cdo.get_class().get_path_name() if cdo else None),
            attempt("cdo.get_class().static_class()", lambda: cdo.get_class().static_class() if cdo else None),
        ],
    }


def probe_asset_class_path():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    try:
        if hasattr(registry, "wait_for_completion"):
            registry.wait_for_completion()
    except Exception:
        pass
    assets = registry.get_assets_by_path(unreal.Name("/Game"), True)
    samples = []
    for asset_data in list(assets)[:5]:
        acp = getattr(asset_data, "asset_class_path", None)
        samples.append(
            {
                "package_name": str(getattr(asset_data, "package_name", "")),
                "asset_name": str(getattr(asset_data, "asset_name", "")),
                "asset_class": str(getattr(asset_data, "asset_class", "")),
                "asset_class_path_repr": repr(acp)[:200],
                "asset_class_path_type": type(acp).__name__,
                "acp_package_name": attempt("pkg", lambda: str(acp.package_name)),
                "acp_asset_name": attempt("asset", lambda: str(acp.asset_name)),
                "built": attempt(
                    "build",
                    lambda: "%s.%s" % (acp.package_name, acp.asset_name),
                ),
            }
        )
    return {"asset_count": len(assets), "samples": samples}


def probe_dependencies():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    try:
        if hasattr(registry, "wait_for_completion"):
            registry.wait_for_completion()
    except Exception as exc:
        return {"error": "wait_for_completion: %s" % exc}

    options = unreal.AssetRegistryDependencyOptions()
    applied = {}
    for name in (
        "include_hard_package_references",
        "include_soft_package_references",
        "include_searchable_names",
        "include_hard_management_references",
        "include_soft_management_references",
    ):
        try:
            options.set_editor_property(name, name != "include_searchable_names")
            applied[name] = True
        except Exception:
            applied[name] = False

    assets = list(registry.get_assets_by_path(unreal.Name("/Game"), True))
    scans = []
    best = None
    for asset_data in assets[:200]:
        package_name = getattr(asset_data, "package_name", None)
        if package_name is None:
            continue
        deps = attempt("deps", lambda p=package_name: [str(x) for x in (registry.get_dependencies(p, options) or [])])
        refs = attempt("refs", lambda p=package_name: [str(x) for x in (registry.get_referencers(p, options) or [])])
        row = {
            "package_name": str(package_name),
            "deps_ok": deps["ok"],
            "refs_ok": refs["ok"],
            "deps": deps.get("value") if deps["ok"] else None,
            "refs": refs.get("value") if refs["ok"] else None,
            "deps_count": len(deps["value"]) if deps["ok"] and isinstance(deps["value"], list) else -1,
            "refs_count": len(refs["value"]) if refs["ok"] and isinstance(refs["value"], list) else -1,
            "deps_error": deps.get("error"),
            "refs_error": refs.get("error"),
        }
        scans.append(row)
        if row["deps_count"] > 0 and row["refs_count"] > 0:
            best = row
            break
        if best is None and row["deps_count"] > 0:
            best = row
    return {
        "applied": applied,
        "asset_count": len(assets),
        "scanned": len(scans),
        "best": best,
        "first_10": scans[:10],
    }


def probe_spawn():
    editor_ss = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actor_ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = None
    try:
        world = editor_ss.get_editor_world()
    except Exception as exc:
        world = "error: %s" % exc
    if world is None:
        return {"world": None, "spawn": "skipped (no editor world)"}
    cls_obj = unreal.load_class(None, "/Script/Engine.StaticMeshActor")
    result = attempt(
        "spawn(Class from /Script path)",
        lambda: actor_ss.spawn_actor_from_class(cls_obj, unreal.Vector(0, 0, 0), unreal.Rotator()),
    )
    actor = result.get("value")
    cleanup = None
    actor_class_info = None
    if actor is not None:
        actor_class_info = {
            "class_type": type(actor.get_class()).__name__,
            "class_repr": repr(actor.get_class())[:200],
            "get_class().static_class()": attempt(
                "static_class", lambda: actor.get_class().static_class()
            ),
            "get_class().static_class().get_path_name()": attempt(
                "path", lambda: actor.get_class().static_class().get_path_name()
            ),
            "SystemLibrary.get_path_name(actor.get_class())": attempt(
                "system_path", lambda: unreal.SystemLibrary.get_path_name(actor.get_class())
            ),
        }
        cleanup = attempt("destroy", lambda: actor_ss.destroy_actor(actor))
    return {"world": str(world), "spawn": result, "actorClass": actor_class_info, "cleanup": cleanup}


def main():
    report = {
        "classPredicates": probe_class_predicates(),
        "pythonTypePaths": probe_python_type_paths(),
        "assetClassPath": probe_asset_class_path(),
        "dependencies": probe_dependencies(),
        "spawn": probe_spawn(),
    }
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
    print("PROBE_DEFECT4_RAW2 written=%s" % RESULT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
