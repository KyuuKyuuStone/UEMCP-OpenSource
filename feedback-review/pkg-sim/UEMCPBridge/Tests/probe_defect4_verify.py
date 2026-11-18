"""Real-engine verification for DEFECT-4 / DEFECT-6 / O-6.

Run with UnrealEditor-Cmd -run=pythonscript.  Writes
``Saved/UEMCP/probe_defect4_verify.json`` and exits non-zero on failure.

Covers:
* resolve_actor_class for /Script path, Engine.Class, short name and a
  Blueprint asset path;
* spawning from the resolved class objects;
* AssetRegistryDependencyOptions against actual UE 5.4 properties and
  non-empty get_dependencies / get_referencers;
* stable classPath strings for actors and assets.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")
RESULT_PATH = os.path.join(PROJECT_DIR, "Saved", "UEMCP", "probe_defect4_verify.json")

if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

import unreal  # noqa: E402

from uemcp_bridge.handlers import (  # noqa: E402
    actor_matches_class,
    asset_ref,
    class_path_string,
    resolve_actor_class,
)
from uemcp_bridge.handlers import assets as assets_handler  # noqa: E402

CLASS_INPUTS = [
    "/Script/Engine.StaticMeshActor",
    "Engine.StaticMeshActor",
    "StaticMeshActor",
    "/Game/BP_MapViewPawn.BP_MapViewPawn",
]

DEPENDENCY_PACKAGE = "/Game/CesiumSettings/CesiumIonServers/CesiumIonSaaS"


def _valid_path(path):
    return bool(path) and path.startswith(("/Script/", "/Game/")) and "<" not in path


def main():
    failures = []
    report = {"ok": False, "failures": failures}

    # 1. Class resolution.
    resolution = {}
    for text in CLASS_INPUTS:
        try:
            resolved = resolve_actor_class(text)
            path = class_path_string(resolved)
            resolution[text] = {
                "ok": True,
                "classPath": path,
                "repr": repr(resolved)[:200],
            }
            if not _valid_path(path):
                failures.append("unstable class path for %s: %r" % (text, path))
        except Exception as exc:
            resolution[text] = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
            failures.append("resolve failed for %s: %r" % (text, exc))
    report["classResolution"] = resolution

    # 2. Spawn from resolved Class objects.
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawn = {}
    for text in ("/Script/Engine.StaticMeshActor", "/Game/BP_MapViewPawn.BP_MapViewPawn"):
        entry = {"ok": False}
        try:
            cls = resolve_actor_class(text)
            actor = actor_subsystem.spawn_actor_from_class(
                cls, unreal.Vector(0, 0, 0), unreal.Rotator()
            )
            if actor is None:
                entry = {"ok": False, "error": "spawn returned None"}
                failures.append("spawn returned None for %s" % text)
            else:
                actor_path = class_path_string(actor.get_class())
                entry = {
                    "ok": True,
                    "actor": repr(actor)[:200],
                    "classPath": actor_path,
                    "label": str(actor.get_actor_label()),
                    # actor.query's filter.class path.
                    "matchesResolvedClass": actor_matches_class(actor, cls),
                    "matchesShortName": actor_matches_class(
                        actor, resolve_actor_class("StaticMeshActor")
                    ),
                }
                if not _valid_path(actor_path):
                    failures.append("unstable spawned classPath: %r" % actor_path)
                if not entry["matchesResolvedClass"]:
                    failures.append("filter.class mismatch for %s" % text)
                expected_short_match = text == "/Script/Engine.StaticMeshActor"
                if entry["matchesShortName"] != expected_short_match:
                    failures.append(
                        "short-name filter match for %s was %r"
                        % (text, entry["matchesShortName"])
                    )
                actor_subsystem.destroy_actor(actor)
        except Exception as exc:
            entry = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
            failures.append("spawn failed for %s: %r" % (text, exc))
        spawn[text] = entry
    report["spawn"] = spawn

    # 3. Dependency options and queries.
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets_handler._ensure_asset_search(registry)
    options, option_warnings = assets_handler._dependency_options(
        {"hard": True, "soft": True, "management": True, "searchableName": False}
    )
    options_report = {
        "warnings": option_warnings,
        "has_legacy_management": hasattr(options, "include_management_references"),
        "hard_management": None,
        "soft_management": None,
    }
    for name in ("include_hard_management_references", "include_soft_management_references"):
        try:
            options_report[name.split("include_")[1]] = bool(
                options.get_editor_property(name)
            )
        except Exception as exc:
            options_report[name] = "error: %s" % exc
    report["dependencyOptions"] = options_report
    if option_warnings:
        failures.append("unexpected dependency option warnings: %r" % option_warnings)

    dependency_report = {"package": DEPENDENCY_PACKAGE, "ok": False}
    try:
        deps = list(registry.get_dependencies(unreal.Name(DEPENDENCY_PACKAGE), options) or [])
        refs = list(registry.get_referencers(unreal.Name(DEPENDENCY_PACKAGE), options) or [])
        dependency_report.update(
            {
                "ok": bool(deps) and bool(refs),
                "dependencyCount": len(deps),
                "referencerCount": len(refs),
                "dependencies": [str(x) for x in deps[:5]],
                "referencers": [str(x) for x in refs[:5]],
            }
        )
        if not deps:
            failures.append("dependencies empty for %s" % DEPENDENCY_PACKAGE)
        if not refs:
            failures.append("referencers empty for %s" % DEPENDENCY_PACKAGE)
    except Exception as exc:
        dependency_report["error"] = "%s: %s" % (type(exc).__name__, exc)
        failures.append("dependency query raised: %r" % (exc,))

    # Exercise the handler path (warnings must stay empty, no exception).
    try:
        collected_deps, collected_refs = assets_handler._collect_relations(
            registry, options, unreal.Name(DEPENDENCY_PACKAGE), True, True, []
        )
        dependency_report["handlerDependencyCount"] = len(collected_deps)
        dependency_report["handlerReferencerCount"] = len(collected_refs)
    except Exception as exc:
        failures.append("_collect_relations raised: %r" % (exc,))
    report["dependencyQuery"] = dependency_report

    # 4. Stable classPath for assets.
    asset_paths = {}
    try:
        assets_data = registry.get_assets_by_path(
            unreal.Name("/Game/CesiumSettings/CesiumIonServers"), False
        )
        for asset_data in list(assets_data)[:3]:
            ref = asset_ref(asset_data)
            asset_paths[ref["packageName"]] = ref["classPath"]
            if not _valid_path(ref["classPath"]):
                failures.append(
                    "unstable asset classPath for %s: %r"
                    % (ref["packageName"], ref["classPath"])
                )
    except Exception as exc:
        failures.append("asset_ref probe raised: %r" % (exc,))
    report["assetClassPaths"] = asset_paths

    report["ok"] = not failures
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
    print("PROBE_DEFECT4_VERIFY %s" % json.dumps({"ok": report["ok"], "failures": failures}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
