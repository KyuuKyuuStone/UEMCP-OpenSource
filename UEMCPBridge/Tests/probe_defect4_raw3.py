"""Real-engine probe #3: asset dependency queries in a commandlet.

Run with UnrealEditor-Cmd -run=pythonscript.  Writes
``Saved/UEMCP/probe_defect4_raw3.json``.
"""

import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
RESULT_PATH = os.path.join(PROJECT_DIR, "Saved", "UEMCP", "probe_defect4_raw3.json")

import unreal  # noqa: E402


def summarize(value):
    if value is None:
        return {"none": True}
    try:
        items = list(value)
    except Exception:
        return {"repr": repr(value)[:300], "type": type(value).__name__}
    return {
        "type": type(value).__name__,
        "count": len(items),
        "items": [str(x) for x in items[:10]],
    }


def query(registry, options, package, use_name):
    key = unreal.Name(package) if use_name else package
    started = time.monotonic()
    try:
        deps = summarize(registry.get_dependencies(key, options))
        deps["error"] = None
    except Exception as exc:
        deps = {"error": "%s: %s" % (type(exc).__name__, exc)}
    try:
        refs = summarize(registry.get_referencers(key, options))
        refs["error"] = None
    except Exception as exc:
        refs = {"error": "%s: %s" % (type(exc).__name__, exc)}
    return {
        "package": package,
        "use_name": use_name,
        "dependencies": deps,
        "referencers": refs,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


def main():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    report = {
        "methods": {
            name: hasattr(registry, name)
            for name in (
                "wait_for_completion",
                "search_all_assets",
                "get_dependencies",
                "get_referencers",
                "get_assets_by_path",
                "is_loading_assets",
            )
        },
        "docs": {},
        "search": None,
        "queries": [],
    }
    for name in ("get_dependencies", "get_referencers", "search_all_assets"):
        try:
            report["docs"][name] = str(getattr(registry, name).__doc__)[:800]
        except Exception as exc:
            report["docs"][name] = "error: %s" % exc

    try:
        if hasattr(registry, "wait_for_completion"):
            registry.wait_for_completion()
        report["wait"] = "ok"
    except Exception as exc:
        report["wait"] = "%s: %s" % (type(exc).__name__, exc)

    try:
        if hasattr(registry, "search_all_assets"):
            started = time.monotonic()
            result = registry.search_all_assets(True)
            report["search"] = {
                "ok": True,
                "result": repr(result)[:200],
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
        else:
            report["search"] = {"ok": False, "reason": "no search_all_assets"}
    except Exception as exc:
        report["search"] = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    options = unreal.AssetRegistryDependencyOptions()
    for name, value in (
        ("include_hard_package_references", True),
        ("include_soft_package_references", True),
        ("include_hard_management_references", True),
        ("include_soft_management_references", True),
        ("include_searchable_names", True),
    ):
        try:
            options.set_editor_property(name, value)
        except Exception:
            pass

    assets = list(registry.get_assets_by_path(unreal.Name("/Game"), True))
    samples = []
    for asset_data in assets[:200]:
        package = str(getattr(asset_data, "package_name", ""))
        if not package:
            continue
        sample = query(registry, options, package, use_name=True)
        samples.append(sample)
        if sample["dependencies"].get("count", 0) > 0:
            break
    report["queries"] = samples

    # Also exercise a known blueprint (load it first).
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
        bp = subsystem.load_asset("/Game/BP_MapViewPawn.BP_MapViewPawn")
        report["loaded_blueprint"] = repr(bp)[:200]
        report["blueprint_query"] = query(
            registry, options, "/Game/BP_MapViewPawn", use_name=True
        )
        report["blueprint_query_str"] = query(
            registry, options, "/Game/BP_MapViewPawn", use_name=False
        )
    except Exception as exc:
        report["loaded_blueprint_error"] = "%s: %s" % (type(exc).__name__, exc)

    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
    print("PROBE_DEFECT4_RAW3 written=%s" % RESULT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
