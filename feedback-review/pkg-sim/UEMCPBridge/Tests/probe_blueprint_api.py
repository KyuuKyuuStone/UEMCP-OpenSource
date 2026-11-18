r"""Probe: which Unreal Python APIs can actually read a Blueprint asset's structure.

Run headless:
  UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script=<this file> -unattended -nop4 -nosplash -nullrhi

Writes results to %TEMP%\uemcp_bp_probe.json (override with env UEMCP_BP_PROBE_OUT).
"""

import json
import os
import tempfile
import traceback

OUT = os.environ.get("UEMCP_BP_PROBE_OUT") or os.path.join(
    tempfile.gettempdir(), "uemcp_bp_probe.json"
)

TARGETS = [
    "/Game/StarterContent/Blueprints/Blueprint_CeilingLight",
    "/Game/StarterContent/Blueprints/Blueprint_Effect_Fire",
]

results = {"targets": {}, "module": {}}


def attempt(fn):
    try:
        return {"ok": True, "value": repr(fn())}
    except Exception as exc:  # noqa: BLE001 - probe wants the message
        return {"ok": False, "error": "%s: %s" % (exc.__class__.__name__, exc)}


def main():
    import unreal

    names = [n for n in dir(unreal) if "lueprint" in n]
    results["module"]["blueprint_symbols"] = names

    for lib_name in ("BlueprintEditorLibrary", "KismetEditorUtilities", "EditorAssetLibrary"):
        lib = getattr(unreal, lib_name, None)
        if lib is None:
            results["module"][lib_name] = None
            continue
        funcs = [f for f in dir(lib) if not f.startswith("_")]
        results["module"][lib_name] = funcs

    for path in TARGETS:
        entry = {}
        bp = None
        for loader in (
            lambda p=path: unreal.load_asset(p),
            lambda p=path: unreal.EditorAssetLibrary.load_asset(p),
        ):
            got = attempt(loader)
            if got["ok"] and got["value"] not in ("None", ""):
                try:
                    bp = unreal.load_asset(path)
                except Exception:
                    bp = None
                break
        entry["loaded"] = attempt(lambda: bp.get_class().get_name() if bp else None)

        probes = {}
        for prop in (
            "parent_class",
            "ParentClass",
            "new_variables",
            "NewVariables",
            "VariableGuids",
            "ubergraph_pages",
            "UbergraphPages",
            "function_graphs",
            "FunctionGraphs",
            "macro_graphs",
            "MacroGraphs",
            "SimpleConstructionScript",
        ):
            probes["get_editor_property(%s)" % prop] = attempt(
                lambda p=prop: bp.get_editor_property(p)
            )
            probes["getattr(%s)" % prop] = attempt(lambda p=prop: getattr(bp, p))

        # Parent class via generated class -> super class.
        probes["generated_class()"] = attempt(lambda: bp.generated_class())
        probes["generated_class.get_super_class"] = attempt(
            lambda: bp.generated_class().get_super_class().get_name()
        )
        probes["get_class().get_super_class()"] = attempt(
            lambda: bp.get_class().get_super_class().get_name()
        )
        probes["BlueprintEditorLibrary.find_event_graph"] = attempt(
            lambda: unreal.BlueprintEditorLibrary.find_event_graph(bp).get_name()
        )
        probes["BlueprintEditorLibrary.list_functions"] = attempt(
            lambda: [f.get_name() for f in unreal.BlueprintEditorLibrary.list_functions(bp)]
        )
        entry["probes"] = probes
        results["targets"][path] = entry

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    unreal.log("[UEMCP] bp probe written to %s" % OUT)


try:
    main()
except Exception as exc:  # noqa: BLE001
    results["fatal"] = "%s: %s" % (exc.__class__.__name__, exc)
    results["traceback"] = traceback.format_exc()
    try:
        with open(OUT, "w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=2)
    except Exception:
        pass
