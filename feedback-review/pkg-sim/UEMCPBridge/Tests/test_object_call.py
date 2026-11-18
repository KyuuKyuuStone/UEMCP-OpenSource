"""``object.reflect`` / ``object.call`` self-check (no editor required).

Covers: target resolution by path and class name, snake_case conversion, void
returns, argument-count errors, missing-function suggestions, the reflection
blacklist and the ``allowWrite`` gate.
"""

import os
import shutil
import sys
import tempfile
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

PROJECT_DIR = tempfile.mkdtemp(prefix="uemcp_objproj_")
EMPTY_PROJECT = tempfile.mkdtemp(prefix="uemcp_objempty_")
LOG_DIR = os.path.join(PROJECT_DIR, "Saved", "Logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, os.path.basename(PROJECT_DIR) + ".log")
with open(LOG_PATH, "w", encoding="utf-8") as _handle:
    _handle.write("[2026.11.03-07.00.00:000][  0]LogTemp: baseline one\n")
    _handle.write("[2026.11.03-07.00.01:000][  0]LogTemp: baseline two\n")


def _log_line_count():
    with open(LOG_PATH, "rb") as handle:
        return handle.read().count(b"\n")


class BaseActor(object):
    def get_name(self):
        return "MyActor"

    def get_path_name(self):
        return "/Game/Maps/Test.Test:PersistentLevel.MyActor"


class FakeClass(object):
    def __init__(self, name):
        self._name = name

    def get_name(self):
        return self._name


class FakeActor(BaseActor):
    def fly_to_monitor_point(self):
        return None

    def sum_two(self, left, right):
        return left + right

    def run_python_code(self):
        return "nope"

    def execute_console_command(self, command):
        return "ran:%s" % command

    def raise_type_error_in_body(self, value):
        return value + 1  # TypeError when value is None

    def _private(self):
        return "nope"

    def write_log(self):
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(
                "[2026.11.03-07.00.02:000][  0]LogMarker: flyToMonitorPoint ok, devices: 25\n"
            )
            handle.write(
                "[2026.11.03-07.00.03:000][  0]LogTemp: Error: device offline\n"
            )
        return None

    def write_many_logs(self):
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            for index in range(250):
                handle.write(
                    "[2026.11.03-07.01:%02d:000][  0]LogMarker: bulk %03d\n"
                    % (index % 60, index)
                )
        return None

    def get_class(self):
        return FakeClass("MyActor")


ACTOR = FakeActor()
PIE_WORLD = object()
PIE_RUNNING = {"value": False}


class FakePieActor(object):
    def fly_to_monitor_point(self):
        return None

    def test_command(self):
        return "ok"

    def get_cmd_prefix(self):
        return "cmd_"

    def get_path_name(self):
        return "/Temp/UEDPIE_0_Map.Map:PersistentLevel.CustomDomainCmdHandler_1"

    def get_class(self):
        return FakeClass("CustomDomainCmdHandler")


PIE_ACTOR = FakePieActor()


class FakeActorSubsystem(object):
    def get_all_level_actors(self):
        return [ACTOR]


class FakeEditorSubsystem(object):
    def get_game_world(self):
        return PIE_WORLD if PIE_RUNNING["value"] else None


class FakeGameplayStatics(object):
    @staticmethod
    def get_all_actors_of_class(world, cls):
        if world is PIE_WORLD:
            return [PIE_ACTOR]
        return []


unreal_stub = types.ModuleType("unreal")
unreal_stub.EditorActorSubsystem = object
unreal_stub.UnrealEditorSubsystem = object
unreal_stub.Actor = object
unreal_stub.GameplayStatics = FakeGameplayStatics


def _get_editor_subsystem(cls):
    if cls is unreal_stub.UnrealEditorSubsystem:
        return FakeEditorSubsystem()
    return FakeActorSubsystem()


unreal_stub.get_editor_subsystem = _get_editor_subsystem


class Paths(object):
    project = PROJECT_DIR

    @staticmethod
    def project_dir():
        return Paths.project


unreal_stub.Paths = Paths


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

    def reflect_bare_class_name_pie():
        PIE_RUNNING["value"] = True
        try:
            data = objects.handle_reflect(_Server(), {"target": "CustomDomainCmdHandler"}).data
        finally:
            PIE_RUNNING["value"] = False
        assert data["targetClass"] == "CustomDomainCmdHandler", data
        names = [item["name"] for item in data["functions"]]
        assert "fly_to_monitor_point" in names, names
        assert "test_command" in names, names

    def reflect_missing_candidates():
        PIE_RUNNING["value"] = True
        try:
            exc = _expect(
                "NOT_FOUND",
                lambda: objects.handle_reflect(_Server(), {"target": "CustomDomainCmdHandlerZ"}),
            )
        finally:
            PIE_RUNNING["value"] = False
        candidates = exc.details.get("candidates") or []
        assert candidates, exc.details
        assert any("CustomDomainCmdHandler" in path for path in candidates), exc.details

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

    def capture_log_window_lines():
        before = _log_line_count()
        result = call({"target": "MyActor", "function": "write_log", "captureLog": True})
        data = result.data
        assert data["returnedVoid"] is True, data
        lines = data["logLines"]
        assert len(lines) == 2, lines
        assert [line["lineNo"] for line in lines] == [before + 1, before + 2], lines
        assert [line["level"] for line in lines] == ["Log", "Error"], lines
        assert "devices: 25" in lines[0]["text"], lines
        assert data["logTruncated"] is False, data

    def capture_log_absent_by_default():
        data = call({"target": "MyActor", "function": "fly_to_monitor_point"}).data
        assert "logLines" not in data, data
        assert "logTruncated" not in data, data

    def capture_log_missing_file():
        Paths.project = EMPTY_PROJECT
        try:
            result = call(
                {"target": "MyActor", "function": "fly_to_monitor_point", "captureLog": True}
            )
        finally:
            Paths.project = PROJECT_DIR
        assert result.data["logLines"] == [], result.data
        assert any("CAPTURE_LOG_FAILED" in w for w in result.warnings), result.warnings

    def capture_log_truncates():
        result = call({"target": "MyActor", "function": "write_many_logs", "captureLog": True})
        lines = result.data["logLines"]
        assert len(lines) == 200, len(lines)
        assert result.data["logTruncated"] is True, result.data
        assert "bulk 249" in lines[-1]["text"], lines[-1]

    def call_bad_args():
        exc = _expect(
            "INVALID_ARGUMENT",
            lambda: call({"target": "MyActor", "function": "sum_two", "args": [1]}),
        )
        assert exc.details["expectedParamCount"] == 2, exc.details
        assert exc.details["gotParamCount"] == 1, exc.details
        assert "error" in exc.details, exc.details
        assert "phase" not in exc.details, exc.details

    def call_in_body_type_error():
        exc = _expect(
            "EXECUTION_ERROR",
            lambda: call({"target": "MyActor", "function": "raise_type_error_in_body", "args": [None]}),
        )
        assert exc.details.get("phase") == "in-body", exc.details
        assert exc.details.get("function") == "raise_type_error_in_body", exc.details
        assert exc.details.get("target") == "MyActor", exc.details
        assert "error" in exc.details, exc.details

    def call_unverified_signature():
        class Holder(object):
            pass

        holder = Holder()

        def boom(value):
            raise TypeError("unverified in-body")

        holder.boom = boom
        original_resolve = objects._resolve_target
        original_signature = objects.inspect.signature

        def _no_signature(*_args, **_kwargs):
            raise TypeError("no signature")

        objects._resolve_target = lambda target: holder
        objects.inspect.signature = _no_signature
        try:
            exc = _expect(
                "INVALID_ARGUMENT",
                lambda: call({"target": "Holder", "function": "boom", "args": [1]}),
            )
        finally:
            objects._resolve_target = original_resolve
            objects.inspect.signature = original_signature
        assert exc.details.get("unverifiedSignature") is True, exc.details
        assert "phase" not in exc.details, exc.details

    def blacklist_rule_units():
        cases = {
            "exec": "exact:exec",
            "Exec": "exact:exec",
            "Python": "exact:python",
            "py": "exact:py",
            "__import__": "exact:__import__",
            "python_path": "prefix:python_",
            "py_run": "prefix:py_",
            "subprocess_run": "prefix:subprocess",
            "exec_flush": "prefix:exec_",
            "runpython_thing": "prefix:runpython",
            "execpython_thing": "prefix:execpython",
            "_private": "leading_underscore",
            "execute_console_command": None,
        }
        for name, rule in cases.items():
            assert objects._blocked_rule(name) == rule, (name, rule, objects._blocked_rule(name))

    def call_blocked_allowlist():
        data = call({"target": "MyActor", "function": "execute_console_command", "args": ["stat unit"]}).data
        assert data["returned"] == "ran:stat unit", data
        assert data["returnedVoid"] is False, data

    def call_suggestions():
        exc = _expect(
            "NOT_FOUND",
            lambda: call({"target": "MyActor", "function": "sum_tow"}),
        )
        assert "sum_two" in exc.details["suggestions"], exc.details

    def call_blocked():
        for name in (
            "_private",
            "exec",
            "Python",
            "python_path",
            "py_run",
            "subprocess_run",
            "exec_flush",
            "runpython_thing",
            "execpython_thing",
        ):
            exc = _expect(
                "PERMISSION_DENIED",
                lambda n=name: call({"target": "MyActor", "function": n}),
            )
            assert exc.details.get("blocked") is True, exc.details
            assert exc.details.get("matchedRule"), (name, exc.details)
            assert exc.details.get("reason") == "blacklisted_name", exc.details

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
    check("reflect_bare_class_name_pie", reflect_bare_class_name_pie)
    check("reflect_missing_candidates", reflect_missing_candidates)
    check("reflect_missing", reflect_missing)
    check("call_void", call_void)
    check("call_value", call_value)
    check("capture_log_window_lines", capture_log_window_lines)
    check("capture_log_absent_by_default", capture_log_absent_by_default)
    check("capture_log_missing_file", capture_log_missing_file)
    check("capture_log_truncates", capture_log_truncates)
    check("call_bad_args", call_bad_args)
    check("call_in_body_type_error", call_in_body_type_error)
    check("call_unverified_signature", call_unverified_signature)
    check("blacklist_rule_units", blacklist_rule_units)
    check("call_blocked_allowlist", call_blocked_allowlist)
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
    shutil.rmtree(PROJECT_DIR, ignore_errors=True)
    shutil.rmtree(EMPTY_PROJECT, ignore_errors=True)
    print("OBJECT_CALL_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
