"""Real-engine probe: class resolution + AssetRegistryDependencyOptions.

Run with:
  UnrealEditor-Cmd.exe <Project>.uproject -run=pythonscript -script=<this>

Writes ``<Project>/Saved/UEMCP/probe_defect4_raw.json``.  This probe only
reports actual UE 5.4 binding behaviour; it does not assert.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
RESULT_PATH = os.path.join(PROJECT_DIR, "Saved", "UEMCP", "probe_defect4_raw.json")

import unreal  # noqa: E402


def safe_call(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as exc:
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}


def describe(value):
    info = {
        "repr": repr(value)[:300],
        "type": type(value).__name__,
        "is_none": value is None,
        "is_python_type": isinstance(value, type),
    }
    try:
        info["is_unreal_class"] = isinstance(value, unreal.Class)
    except Exception as exc:
        info["is_unreal_class"] = "error: %s" % exc
    try:
        info["is_actor_subclass"] = bool(issubclass(value, unreal.Actor))
    except Exception:
        info["is_actor_subclass"] = False
    try:
        info["get_path_name"] = str(value.get_path_name())
    except Exception as exc:
        info["get_path_name"] = "error: %s" % exc
    try:
        info["system_get_path_name"] = str(unreal.SystemLibrary.get_path_name(value))
    except Exception as exc:
        info["system_get_path_name"] = "error: %s" % exc
    return info


def probe_class_inputs():
    inputs = [
        "/Script/Engine.StaticMeshActor",
        "/Script/Engine.StaticMeshActor.StaticMeshActor",
        "Engine.StaticMeshActor",
        "StaticMeshActor",
    ]
    results = {}
    for text in inputs:
        results[text] = {
            "load_class": safe_call(lambda t=text: describe(unreal.load_class(None, t))),
            "load_object": safe_call(lambda t=text: describe(unreal.load_object(None, t))),
            "find_object": safe_call(lambda t=text: describe(unreal.find_object(None, t))),
        }
    results["getattr_unreal.StaticMeshActor"] = safe_call(
        lambda: describe(getattr(unreal, "StaticMeshActor", None))
    )
    return results


def _find_blueprints(limit=5):
    found = []
    subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    try:
        paths = subsystem.list_assets("/Game", True, False)
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc), "items": []}
    for path in paths:
        if len(found) >= limit:
            break
        try:
            asset = subsystem.load_asset(str(path))
        except Exception:
            continue
        if isinstance(asset, unreal.Blueprint):
            generated = None
            try:
                generated = asset.generated_class()
            except Exception:
                generated = None
            found.append(
                {
                    "package": str(path),
                    "asset_type": type(asset).__name__,
                    "generated_repr": repr(generated)[:200] if generated else None,
                    "generated": describe(generated) if generated else None,
                }
            )
    return {"error": None, "items": found}


def probe_blueprint_resolution(blueprints):
    results = []
    for item in blueprints:
        package = item["package"]
        variants = [package, package + "_C"]
        row = {"package": package, "variants": {}}
        for text in variants:
            row["variants"][text] = {
                "load_class": safe_call(lambda t=text: describe(unreal.load_class(None, t))),
                "load_object": safe_call(lambda t=text: describe(unreal.load_object(None, t))),
                "find_object": safe_call(lambda t=text: describe(unreal.find_object(None, t))),
            }
        results.append(row)
    return results


def probe_dependency_options():
    options = unreal.AssetRegistryDependencyOptions()
    try:
        instance_attrs = [name for name in dir(options) if not name.startswith("_")]
    except Exception as exc:
        instance_attrs = ["error: %s" % exc]
    candidates = [
        "include_hard_package_references",
        "include_soft_package_references",
        "include_management_references",
        "include_searchable_names",
        "include_hard_management_references",
        "include_soft_management_references",
        "include_editor_only_references",
        "include_script_package_references",
        "include_cooked_package_references",
    ]
    setters = {}
    for name in candidates:
        try:
            options.set_editor_property(name, True)
            setters[name] = "ok"
        except Exception as exc:
            setters[name] = "%s: %s" % (type(exc).__name__, exc)
    return {
        "instance_attrs": instance_attrs,
        "class_attrs": [name for name in dir(unreal.AssetRegistryDependencyOptions) if not name.startswith("_")],
        "setters": setters,
    }


def probe_dependencies(limit_scan=60):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    options = unreal.AssetRegistryDependencyOptions()
    applied = {}
    for name in (
        "include_hard_package_references",
        "include_soft_package_references",
        "include_searchable_names",
    ):
        try:
            options.set_editor_property(name, True)
            applied[name] = True
        except Exception:
            applied[name] = False

    subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    try:
        paths = list(subsystem.list_assets("/Game", True, False))[:limit_scan]
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc), "applied": applied}

    best = None
    scan = 0
    for path in paths:
        package_name = str(path)
        try:
            deps = list(registry.get_dependencies(unreal.Name(package_name), options) or [])
            refs = list(registry.get_referencers(unreal.Name(package_name), options) or [])
        except Exception as exc:
            return {
                "error": "%s: %s" % (type(exc).__name__, exc),
                "applied": applied,
                "failed_package": package_name,
            }
        scan += 1
        candidate = {
            "package": package_name,
            "dependency_count": len(deps),
            "referencer_count": len(refs),
            "dependencies": [str(x) for x in deps[:10]],
            "referencers": [str(x) for x in refs[:10]],
        }
        if best is None or (candidate["dependency_count"] and candidate["referencer_count"]):
            best = candidate
        if candidate["dependency_count"] and candidate["referencer_count"]:
            break
    return {"error": None, "applied": applied, "scanned": scan, "best": best}


def main():
    report = {
        "classInputs": probe_class_inputs(),
        "dependencyOptions": probe_dependency_options(),
    }
    blueprints = _find_blueprints()
    report["blueprintsSearch"] = blueprints
    if blueprints.get("items"):
        report["blueprintResolution"] = probe_blueprint_resolution(blueprints["items"])
    report["dependencies"] = probe_dependencies()

    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
    print("PROBE_DEFECT4_RAW written=%s" % RESULT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
