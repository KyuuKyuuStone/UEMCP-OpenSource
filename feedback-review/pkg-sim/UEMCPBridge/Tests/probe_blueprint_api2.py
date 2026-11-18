r"""Probe #2: which *useful* blueprint facts survive UE Python's protected properties.

Only reads; writes nothing. Run headless:
  UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script=<this file> -unattended -nop4 -nosplash -nullrhi
Result file: %TEMP%\uemcp_bp_probe2.json (override with env UEMCP_BP_PROBE_OUT).
"""

import json
import os
import tempfile
import traceback

OUT = os.environ.get("UEMCP_BP_PROBE_OUT") or os.path.join(
    tempfile.gettempdir(), "uemcp_bp_probe2.json"
)

TARGET = "/Game/StarterContent/Blueprints/Blueprint_CeilingLight"
results = {"target": TARGET, "probes": {}}


def attempt(fn):
    try:
        value = fn()
        return {"ok": True, "value": repr(value)[:400]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (exc.__class__.__name__, str(exc)[:300])}


def main():
    import unreal

    bp = unreal.load_asset(TARGET)
    results["load"] = attempt(lambda: bp.get_name())
    gen = None
    got = attempt(lambda: bp.generated_class())
    results["probes"]["generated_class()"] = got
    try:
        gen = bp.generated_class()
    except Exception:
        gen = None

    p = results["probes"]
    if gen is not None:
        p["generated.get_name()"] = attempt(lambda: gen.get_name())
        p["generated.super_struct"] = attempt(lambda: gen.get_editor_property("super_struct"))
        p["generated.SuperStruct"] = attempt(lambda: gen.get_editor_property("SuperStruct"))
        p["SystemLibrary.get_class_display_name"] = attempt(
            lambda: unreal.SystemLibrary.get_class_display_name(gen)
        )
        p["SystemLibrary.get_class_path_name"] = attempt(
            lambda: unreal.SystemLibrary.get_class_path_name(gen)
        )
        p["cdo.get_class()"] = attempt(
            lambda: unreal.get_default_object(gen).get_class().get_name()
        )

    # BlueprintEditorLibrary enumeration helpers
    p["find_event_graph(bp)"] = attempt(
        lambda: unreal.BlueprintEditorLibrary.find_event_graph(bp)
    )
    eg = None
    try:
        eg = unreal.BlueprintEditorLibrary.find_event_graph(bp)
    except Exception:
        eg = None
    if eg is not None:
        p["event_graph.get_name()"] = attempt(lambda: eg.get_name())
        p["event_graph.nodes"] = attempt(lambda: eg.get_editor_property("nodes"))
        p["event_graph.Nodes"] = attempt(lambda: eg.get_editor_property("Nodes"))
        p["event_graph.get_class()"] = attempt(lambda: eg.get_class().get_name())

    for name in ("EventGraph", "UserConstructionScript"):
        p["find_graph(%s)" % name] = attempt(
            lambda n=name: unreal.BlueprintEditorLibrary.find_graph(bp, n)
        )

    # Asset-level facts that are definitely exposed
    p["bp.get_path_name()"] = attempt(lambda: bp.get_path_name())
    p["bp.get_class()"] = attempt(lambda: bp.get_class().get_name())
    p["asset_data.class"] = attempt(
        lambda: unreal.EditorAssetLibrary.find_asset_data(TARGET).asset_class_path.asset_name
    )

    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    unreal.log("[UEMCP] bp probe2 written to %s" % OUT)


try:
    main()
except Exception as exc:  # noqa: BLE001
    results["fatal"] = "%s: %s" % (exc.__class__.__name__, exc)
    results["traceback"] = traceback.format_exc()
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
