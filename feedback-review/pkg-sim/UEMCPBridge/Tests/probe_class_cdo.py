"""Minimal probe: how to test actor-ness of a unreal.Class object (UE 5.4)."""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
RESULT_PATH = os.path.join(PROJECT_DIR, "Saved", "UEMCP", "probe_class_cdo.json")

import unreal  # noqa: E402


def attempt(label, fn):
    try:
        value = fn()
        return {
            "label": label,
            "ok": True,
            "repr": repr(value)[:200],
            "type": type(value).__name__,
            "bool": value if isinstance(value, bool) else None,
        }
    except Exception as exc:
        return {"label": label, "ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}


def main():
    cls = unreal.load_class(None, "/Script/Engine.StaticMeshActor")
    texture = unreal.load_class(None, "/Script/Engine.Texture2D")
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(
        "/Game/BP_MapViewPawn.BP_MapViewPawn"
    )
    bp_cls = bp.generated_class()

    report = {}
    for name, candidate in (("StaticMeshActorClass", cls), ("Texture2DClass", texture), ("BPClass", bp_cls)):
        cdo = None
        tests = []
        try:
            cdo = candidate.get_default_object()
        except Exception as exc:
            tests.append({"label": "get_default_object", "ok": False, "error": repr(exc)})
        tests.extend(
            [
                attempt("candidate.get_default_object()", lambda c=candidate: c.get_default_object()),
                attempt(
                    "isinstance(cdo, unreal.Actor)",
                    lambda c=cdo: isinstance(c, unreal.Actor) if c is not None else "cdo None",
                ),
                attempt(
                    "isinstance(cdo.get_class(), unreal.Class)",
                    lambda c=cdo: isinstance(c.get_class(), unreal.Class) if c is not None else "cdo None",
                ),
                attempt(
                    "isinstance(cdo.get_class().get_default_object(), unreal.Actor)",
                    lambda c=cdo: isinstance(c.get_class().get_default_object(), unreal.Actor)
                    if c is not None
                    else "cdo None",
                ),
                attempt("unreal.get_default_object(candidate)", lambda c=candidate: unreal.get_default_object(c)),
                attempt(
                    "isinstance(unreal.get_default_object(candidate), unreal.Actor)",
                    lambda c=candidate: isinstance(unreal.get_default_object(c), unreal.Actor),
                ),
                attempt("candidate.static_class()", lambda c=candidate: c.static_class()),
                attempt(
                    "isinstance(candidate.static_class().get_default_object(), unreal.Actor)",
                    lambda c=candidate: isinstance(c.static_class().get_default_object(), unreal.Actor),
                ),
                attempt("unreal.Actor.cast(cdo)", lambda c=cdo: unreal.Actor.cast(c) if c is not None else "cdo None"),
                attempt("candidate.get_class_path_name()", lambda c=candidate: c.get_class_path_name()),
            ]
        )
        report[name] = {
            "path": attempt("path", lambda c=candidate: c.get_path_name()),
            "tests": tests,
        }

    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
    print("PROBE_CLASS_CDO written=%s" % RESULT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
