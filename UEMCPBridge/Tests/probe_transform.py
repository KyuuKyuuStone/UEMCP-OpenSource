"""Real-engine probe for DEFECT-2 (run inside UnrealEditor-Cmd).

Verifies that ``unreal.Transform.rotation`` (a real FQuat, not a stub) is
serialized to ``{pitch,yaw,roll}`` by both ``to_jsonable`` and the handler
helper ``rot_dict``.  Writes the result to
``<Project>/Saved/UEMCP/transform_probe.json`` for deterministic collection.

Command:
  UnrealEditor-Cmd.exe <Project>.uproject -run=pythonscript -script=<this>
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")
RESULT_PATH = os.path.join(PROJECT_DIR, "Saved", "UEMCP", "transform_probe.json")

if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

import unreal  # noqa: E402

from uemcp_bridge.handlers import rot_dict  # noqa: E402
from uemcp_bridge.serialization import to_jsonable  # noqa: E402


def main():
    failures = []
    transform = unreal.Transform()
    quat = transform.rotation

    attributes = {
        "type": type(quat).__name__,
        "has_pitch": hasattr(quat, "pitch"),
        "has_x": hasattr(quat, "x"),
        "has_w": hasattr(quat, "w"),
    }
    if attributes["has_pitch"]:
        # If the engine ever exposes a Rotator here, direct serialization is
        # fine too; record it explicitly.
        pass

    try:
        serialized = to_jsonable(quat)
    except Exception as exc:
        serialized = {"error": repr(exc)}
        failures.append("to_jsonable(Quat) raised: %r" % (exc,))

    try:
        handler_rotation = rot_dict(quat)
    except Exception as exc:
        handler_rotation = {"error": repr(exc)}
        failures.append("rot_dict(Quat) raised: %r" % (exc,))

    for label, value in (("to_jsonable", serialized), ("rot_dict", handler_rotation)):
        if not isinstance(value, dict) or set(value.keys()) != {"pitch", "yaw", "roll"}:
            failures.append("%s did not produce pitch/yaw/roll: %r" % (label, value))

    payload = {
        "ok": not failures,
        "failures": failures,
        "quatAttributes": attributes,
        "toJsonable": serialized,
        "rotDict": handler_rotation,
    }
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print("TRANSFORM_PROBE %s" % json.dumps(payload))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
