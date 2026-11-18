"""Regression test for DEFECT-4 / O-6 (no editor).

Models UE 5.4 behaviour discovered by the real-engine probes:

* ``unreal.load_class`` returns an ``unreal.Class`` object, not a Python type;
* ``issubclass(Class, Actor)`` raises TypeError;
* actor-ness must be checked through ``Class.get_default_object()``;
* Blueprint assets expose ``generated_class()``;
* Python types (short names) expose ``static_class()``.

The real-engine probe (``probe_defect4_verify.py``) remains authoritative.
"""

import os
import sys
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")


class Actor(object):
    pass


class NotActor(object):
    pass


class Class(object):
    def __init__(self, path, cdo):
        self._path = path
        self._cdo = cdo

    def get_path_name(self):
        return self._path

    def get_name(self):
        return self._path.rsplit(".", 1)[-1]


def get_default_object(value):
    # Matches UE 5.4: module-level helper returns the inspected class' CDO.
    if isinstance(value, Class):
        return value._cdo
    return None


class StaticMeshActor(Actor):
    @classmethod
    def static_class(cls):
        return NATIVE_CLASS


class ObjectOnlyActor(Actor):
    pass


class NonActorObject(NotActor):
    pass


NATIVE_CLASS = Class("/Script/Engine.StaticMeshActor", StaticMeshActor())
OBJECT_ONLY_CLASS = Class("/Script/Engine.ObjectOnlyActor", ObjectOnlyActor())
NON_ACTOR_CLASS = Class("/Script/Engine.Texture2D", NonActorObject())
BP_CLASS = Class("/Game/BP_Test.BP_Test_C", ObjectOnlyActor())


class BlueprintAsset(object):
    def __init__(self, generated):
        self._generated = generated

    def generated_class(self):
        return self._generated


CLASS_PATHS = {
    "/Script/Engine.StaticMeshActor": NATIVE_CLASS,
    "/Script/Engine.StaticMeshActor.StaticMeshActor": NATIVE_CLASS,
}
OBJECT_PATHS = {
    "/Script/Engine.ObjectOnlyActor": OBJECT_ONLY_CLASS,
    "/Script/Engine.Texture2D": NON_ACTOR_CLASS,
    "/Game/BP_Test.BP_Test": BlueprintAsset(BP_CLASS),
    "/Game/BP_Test.BP_Test.BP_Test": BlueprintAsset(BP_CLASS),
}


def load_class(_outer, path):
    return CLASS_PATHS.get(path)


def load_object(_outer, path):
    return OBJECT_PATHS.get(path)


def find_object(_outer, path):
    return None


unreal_stub = types.ModuleType("unreal")
unreal_stub.Actor = Actor
unreal_stub.Class = Class
unreal_stub.StaticMeshActor = StaticMeshActor
unreal_stub.load_class = load_class
unreal_stub.load_object = load_object
unreal_stub.find_object = find_object
unreal_stub.get_default_object = get_default_object
unreal_stub.SystemLibrary = types.SimpleNamespace(
    get_path_name=lambda obj: getattr(obj, "get_path_name", lambda: "")()
)
unreal_stub.AssetRegistryHelpers = types.SimpleNamespace(
    is_redirector=lambda asset: False
)
sys.modules["unreal"] = unreal_stub

if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge.errors import RpcError  # noqa: E402
from uemcp_bridge.handlers import (  # noqa: E402
    asset_ref,
    class_path_string,
    resolve_actor_class,
)


class _FakeTopLevelAssetPath(object):
    package_name = "/Script/Engine"
    asset_name = "StaticMeshActor"


class _FakeAssetData(object):
    package_name = "/Game/M_Test"
    asset_name = "M_Test"
    asset_class_path = _FakeTopLevelAssetPath()

    @staticmethod
    def get_tag_value(_name):
        return None


def main():
    failures = []

    cases = [
        ("short name", "StaticMeshActor", "/Script/Engine.StaticMeshActor"),
        ("module.class", "Engine.StaticMeshActor", "/Script/Engine.StaticMeshActor"),
        ("class path", "/Script/Engine.StaticMeshActor", "/Script/Engine.StaticMeshActor"),
        ("object path suffix", "/Script/Engine.StaticMeshActor.StaticMeshActor", "/Script/Engine.StaticMeshActor"),
        ("load_object fallback", "/Script/Engine.ObjectOnlyActor", "/Script/Engine.ObjectOnlyActor"),
        ("blueprint asset", "/Game/BP_Test.BP_Test", "/Game/BP_Test.BP_Test_C"),
    ]
    for label, value, expected_path in cases:
        try:
            resolved = resolve_actor_class(value)
        except Exception as exc:
            failures.append("%s (%s) raised %r" % (label, value, exc))
            continue
        path = class_path_string(resolved)
        if path != expected_path:
            failures.append("%s (%s) path=%r expected %r" % (label, value, path, expected_path))
        else:
            print("RESOLVED %-22s %s -> %s" % (label, value, path))

    for invalid in ("NoSuchActorClassXYZ", "/Script/Engine.Texture2D"):
        try:
            resolve_actor_class(invalid)
        except RpcError as exc:
            if exc.code != "CLASS_NOT_FOUND":
                failures.append("%s error code: %r" % (invalid, exc.code))
            else:
                print("NOT_ACTOR_REJECTED %s" % invalid)
        except Exception as exc:
            failures.append("%s raised wrong type: %r" % (invalid, exc))
        else:
            failures.append("%s did not raise" % invalid)

    # O-6: classPath must be a stable path, never a debug struct repr.
    actor_path = class_path_string(NATIVE_CLASS)
    if actor_path != "/Script/Engine.StaticMeshActor":
        failures.append("class_path_string(Class) = %r" % actor_path)
    python_type_path = class_path_string(StaticMeshActor)
    if python_type_path != "/Script/Engine.StaticMeshActor":
        failures.append("class_path_string(Python type) = %r" % python_type_path)
    if "<" in actor_path or "<" in python_type_path:
        failures.append("classPath contains a debug repr")

    asset = asset_ref(_FakeAssetData())
    if asset.get("classPath") != "/Script/Engine.StaticMeshActor":
        failures.append("asset_ref classPath = %r" % asset.get("classPath"))
    else:
        print("ASSET_CLASS_PATH %s" % asset["classPath"])

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("CLASS_PATH_RESULT FAIL")
        return 1
    print("CLASS_PATH_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
