"""``object.reflect`` / ``object.call`` self-check (no editor required).

Covers: target resolution by path and class name, snake_case conversion, void
returns, argument-count errors, missing-function suggestions, the reflection
blacklist and the ``allowWrite`` gate.
"""

import os
import sys
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")


class BaseActor(object):
    def get_name(self):
        return "MyActor"

    def get_path_name(self):
        return "/Game/Maps/Test.Test:PersistentLevel.MyActor"


class FakeClass(object):
    def get_name(self):
        return "MyActor"


class FakeActor(BaseActor):
    def fly_to_monitor_point(self):
        return None

    def sum_two(self, left, right):
        return left + right

    def run_python_code(self):
        return "nope"

    def _private(self):
        return "nope"

    def get_class(self):
        return FakeClass()


ACTOR = FakeActor()


class FakeActorSubsystem(object):
    def get_all_level_actors(self):
        return [ACTOR]


unreal_stub = types.ModuleType("unreal")
unreal_stub.EditorActorSubsystem = object
unreal_stub.get_editor_subsystem = lambda cls: FakeActorSubsystem()


def find_object(outer, target):
    if target in ("/Game/Maps/Test.Test:PersistentLevel.MyActor", "MyActor"):
        return ACTOR
    return None


unreal_stub.find_object = find_object
unreal_stub.load_object = lambda outer, target: None
sys.modules["unreal"] = unreal_stub
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge import rpc  # noqa: E402
from uemcp_bridge.errors import RpcError  # noqa: E402
from uemcp_bridge.handlers import objects  # noqa: E402


class _Settings(object):
    allow_write = True


class _Server(object):
    def __init__(self, allow_write=True):
        self.settings = _Settings()
        self.settings.allow_write = allow_write
        self.capabilities = {}


def call(params, allow_write=True):
    return objects.handle_call(_Server(allow_write), params)


def _expect(code, fn):
    try:
        fn()
    except RpcError as exc:
        assert exc.code == code, "expected %s, got %s (%s)" % (code, exc.code, exc.message)
        return exc
    raise AssertionError("expected %s, nothing raised" % code)


def main():
    failures = []

    def check(name, fn):
        try:
            fn()
            print("PASS %s" % name)
        except Exception as exc:  # noqa: BLE001
            failures.append("%s: %s" % (name, exc))
            print("FAIL %s: %s" % (name, exc))

    def snake_case():
        assert objects._to_snake("FlyToMonitorPoint") == "fly_to_monitor_point"
        assert objects._to_snake("fly_to_monitor_point") == "fly_to_monitor_point"
        assert objects._to_snake("GetActorLabel") == "get_actor_label"

    def reflect_by_path():
        result = objects.handle_reflect(_Server(), {"target": "/Game/Maps/Test.Test:PersistentLevel.MyActor"})
        data = result.data
        assert data["targetClass"] == "MyActor", data
        names = [item["name"] for item in data["functions"]]
        assert "fly_to_monitor_point" in names, names
        assert "get_name" in names, names
        assert data["truncated"] is False, data

    def reflect_by_class():
        data = objects.handle_reflect(_Server(), {"target": "MyActor"}).data
        assert data["targetClass"] == "MyActor", data
        flags = {item["name"]: item["inherited"] for item in data["functions"]}
        assert flags.get("get_name") is True, flags
        assert flags.get("fly_to_monitor_point") is False, flags

    def reflect_missing():
        _expect("NOT_FOUND", lambda: objects.handle_reflect(_Server(), {"target": "Nope"}))

    def call_void():
        data = call({"target": "MyActor", "function": "FlyToMonitorPoint"}).data
        assert data["function"] == "fly_to_monitor_point", data
        assert data["returned"] is None, data
        assert data["returnedVoid"] is True, data

    def call_value():
        data = call({"target": "MyActor", "function": "sum_two", "args": [2, 3]}).data
        assert data["returned"] == 5, data
        assert data["returnedVoid"] is False, data

    def call_bad_args():
        exc = _expect(
            "INVALID_ARGUMENT",
            lambda: call({"target": "MyActor", "function": "sum_two", "args": [1]}),
        )
        assert exc.details["expectedParamCount"] == 2, exc.details
        assert exc.details["gotParamCount"] == 1, exc.details
        assert "error" in exc.details, exc.details

    def call_suggestions():
        exc = _expect(
            "NOT_FOUND",
            lambda: call({"target": "MyActor", "function": "sum_tow"}),
        )
        assert "sum_two" in exc.details["suggestions"], exc.details

    def call_blocked():
        for name in ("_private", "run_python_code", "eval_thing", "subprocess_run"):
            exc = _expect(
                "PERMISSION_DENIED",
                lambda n=name: call({"target": "MyActor", "function": n}),
            )
            assert exc.details.get("blocked") is True, exc.details

    def gate():
        try:
            rpc.enforce_gates(_Server(False), "object.call", {"target": "MyActor", "function": "fly_to_monitor_point"})
        except RpcError as exc:
            assert exc.code == "PERMISSION_DENIED", exc.code
            assert exc.details.get("gate") == "bridge.allowWrite", exc.details
        else:
            raise AssertionError("gate allowed object.call")
        rpc.enforce_gates(_Server(False), "object.reflect", {"target": "MyActor"})

    def handler_gate():
        _expect(
            "PERMISSION_DENIED",
            lambda: call({"target": "MyActor", "function": "fly_to_monitor_point"}, allow_write=False),
        )

    def registry():
        assert rpc.HANDLERS.get("object.reflect") is objects.handle_reflect
        assert rpc.HANDLERS.get("object.call") is objects.handle_call
        assert "object.call" in rpc.WRITE_METHODS

    def truncation():
        class Many(object):
            pass

        for index in range(250):
            setattr(Many, "fn_%03d" % index, lambda self: None)

        fake = Many()
        original = objects._resolve_target
        objects._resolve_target = lambda target: fake
        try:
            data = objects.handle_reflect(_Server(), {"target": "Many"}).data
        finally:
            objects._resolve_target = original
        assert data["truncated"] is True, data
        assert len(data["functions"]) == objects.MAX_FUNCTIONS, len(data["functions"])

    check("snake_case", snake_case)
    check("reflect_by_path", reflect_by_path)
    check("reflect_by_class", reflect_by_class)
    check("reflect_missing", reflect_missing)
    check("call_void", call_void)
    check("call_value", call_value)
    check("call_bad_args", call_bad_args)
    check("call_suggestions", call_suggestions)
    check("call_blocked", call_blocked)
    check("gate", gate)
    check("handler_gate", handler_gate)
    check("registry", registry)
    check("truncation", truncation)

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("OBJECT_CALL_RESULT FAIL")
        return 1
    print("OBJECT_CALL_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
