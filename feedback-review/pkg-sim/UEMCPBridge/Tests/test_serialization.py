"""Regression test for DEFECT-2: FQuat serialization (no editor required).

``FTransform.rotation`` is an ``unreal.Quat`` (x/y/z/w); the previous
implementation read ``.pitch`` and raised AttributeError for the default
``actor.query`` fields.  This test uses a stub ``unreal`` module with a
Quat/Rotator pair and validates both ``to_jsonable`` and ``rot_dict``.
"""

import math
import os
import sys
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")


class FakeVector(object):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class FakeRotator(object):
    def __init__(self, pitch=0.0, yaw=0.0, roll=0.0):
        self.pitch, self.yaw, self.roll = float(pitch), float(yaw), float(roll)


class FakeQuat(object):
    """FQuat shape: x/y/z/w only, intentionally no pitch/yaw/roll."""

    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        self.x, self.y, self.z, self.w = float(x), float(y), float(z), float(w)


class FakeLinearColor(object):
    def __init__(self, r=0.0, g=0.0, b=0.0, a=1.0):
        self.r, self.g, self.b, self.a = r, g, b, a


class FakeName(str):
    pass


class FakeText(str):
    pass


class FakeObject(object):
    pass


class FakeSystemLibrary(object):
    @staticmethod
    def get_path_name(obj):
        return "/Fake/%s" % type(obj).__name__


unreal_stub = types.ModuleType("unreal")
unreal_stub.Vector = FakeVector
unreal_stub.Rotator = FakeRotator
unreal_stub.Quat = FakeQuat
unreal_stub.LinearColor = FakeLinearColor
unreal_stub.Name = FakeName
unreal_stub.Text = FakeText
unreal_stub.Object = FakeObject
unreal_stub.SystemLibrary = FakeSystemLibrary
sys.modules["unreal"] = unreal_stub

if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge.serialization import rotation_to_dict, to_jsonable  # noqa: E402
from uemcp_bridge.handlers import rot_dict  # noqa: E402


def _quat_from_axis(axis, degrees):
    half = math.radians(degrees) / 2.0
    s = math.sin(half)
    return {
        "x": axis[0] * s,
        "y": axis[1] * s,
        "z": axis[2] * s,
        "w": math.cos(half),
    }


def _approx(actual, expected, tolerance=1e-5):
    return abs(actual - expected) <= tolerance


def main():
    failures = []

    # Rotator passthrough.
    rotator = FakeRotator(10.0, 20.0, 30.0)
    result = rotation_to_dict(rotator)
    if result != {"pitch": 10.0, "yaw": 20.0, "roll": 30.0}:
        failures.append("rotator passthrough: %r" % (result,))

    # Identity quat -> zeros (this is the exact path that used to raise).
    identity = FakeQuat(0.0, 0.0, 0.0, 1.0)
    result = rotation_to_dict(identity)
    if not all(_approx(result[key], 0.0) for key in ("pitch", "yaw", "roll")):
        failures.append("identity quat: %r" % (result,))

    # Yaw 90 about Z.
    q = _quat_from_axis((0.0, 0.0, 1.0), 90.0)
    result = rotation_to_dict(FakeQuat(**q))
    if not _approx(result["yaw"], 90.0) or not _approx(result["pitch"], 0.0) or not _approx(result["roll"], 0.0):
        failures.append("yaw 90 quat: %r" % (result,))

    # UE's FQuat::Rotator() maps a positive rotation about +Y to negative
    # Pitch and about +X to negative Roll (left-handed axes).  Use the axes
    # that produce positive Pitch/Roll to make the expectation explicit.
    q = _quat_from_axis((0.0, -1.0, 0.0), 30.0)
    result = rotation_to_dict(FakeQuat(**q))
    if not _approx(result["pitch"], 30.0):
        failures.append("pitch 30 quat: %r" % (result,))

    q = _quat_from_axis((-1.0, 0.0, 0.0), 45.0)
    result = rotation_to_dict(FakeQuat(**q))
    if not _approx(result["roll"], 45.0):
        failures.append("roll 45 quat: %r" % (result,))

    # to_jsonable must recognise Quat before generic repr.
    converted = to_jsonable(FakeQuat(0.0, 0.0, 0.0, 1.0))
    if not isinstance(converted, dict) or set(converted.keys()) != {"pitch", "yaw", "roll"}:
        failures.append("to_jsonable(Quat): %r" % (converted,))

    # rot_dict (used by actor_transform) must accept Quat.
    result = rot_dict(FakeQuat(0.0, 0.0, 0.0, 1.0))
    if not isinstance(result, dict) or "pitch" not in result:
        failures.append("rot_dict(Quat): %r" % (result,))

    # Simulate a transform payload (location/rotation/scale).
    transform_payload = {
        "location": FakeVector(1.0, 2.0, 3.0),
        "rotation": FakeQuat(0.0, 0.0, 0.0, 1.0),
        "scale": FakeVector(1.0, 1.0, 1.0),
    }
    converted = to_jsonable(transform_payload)
    if converted["rotation"] != {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}:
        failures.append("transform rotation: %r" % (converted.get("rotation"),))
    if converted["location"] != {"x": 1.0, "y": 2.0, "z": 3.0}:
        failures.append("transform location: %r" % (converted.get("location"),))

    print("SERIALIZATION_CHECK quat_identity=%r yaw90=%r" % (
        rotation_to_dict(FakeQuat()), rotation_to_dict(FakeQuat(**_quat_from_axis((0, 0, 1), 90.0)))
    ))
    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("SERIALIZATION_RESULT FAIL")
        return 1
    print("SERIALIZATION_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
