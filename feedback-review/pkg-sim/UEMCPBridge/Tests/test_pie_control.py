"""``pie.control`` state-machine self-check (no editor required).

Stubs a minimal ``unreal`` module and asserts:

* status on a stopped editor (no side effects);
* start -> running -> stop -> stopped;
* stop is idempotent when PIE is not running;
* start with ``simulate=true`` uses the Simulate entry point;
* restart goes through stop and starts again;
* invalid action -> INVALID_ARGUMENT;
* ``start``/``stop``/``restart`` are rejected by the write gate while
  ``status`` stays available;
* ``detect_capabilities()`` reports ``pieControl`` from the API surface.

Exit code 0 = PASS, 1 = FAIL.
"""

import os
import sys
import time
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

STATE = {"running": False, "simulate": False, "calls": []}


class FakeWorld(object):
    def get_path_name(self):
        return "/Game/Maps/TestMap.TestMap"


class FakeLevelEditorSubsystem(object):
    def editor_request_begin_play(self):
        STATE["calls"].append("begin_play")
        STATE["running"] = True
        STATE["simulate"] = False

    def editor_play_simulate(self):
        STATE["calls"].append("play_simulate")
        STATE["running"] = True
        STATE["simulate"] = True

    def editor_request_end_play(self):
        STATE["calls"].append("end_play")
        STATE["running"] = False
        STATE["simulate"] = False

    def is_in_play_in_editor(self):
        return STATE["running"]


class FakeEditorSubsystem(object):
    def get_game_world(self):
        return FakeWorld() if STATE["running"] else None


class LevelEditorSubsystem(object):
    pass


class UnrealEditorSubsystem(object):
    pass


def get_editor_subsystem(cls):
    if cls is LevelEditorSubsystem:
        return FakeLevelEditorSubsystem()
    if cls is UnrealEditorSubsystem:
        return FakeEditorSubsystem()
    return None


unreal_stub = types.ModuleType("unreal")
unreal_stub.LevelEditorSubsystem = LevelEditorSubsystem
unreal_stub.UnrealEditorSubsystem = UnrealEditorSubsystem
unreal_stub.get_editor_subsystem = get_editor_subsystem
sys.modules["unreal"] = unreal_stub

if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge import rpc  # noqa: E402
from uemcp_bridge.dispatcher import Done  # noqa: E402
from uemcp_bridge.errors import RpcError  # noqa: E402
from uemcp_bridge.handlers import pie, status  # noqa: E402


class _Settings(object):
    allow_write = True


class _Server(object):
    def __init__(self, allow_write=True):
        self.settings = _Settings()
        self.settings.allow_write = allow_write
        self.capabilities = {"pieControl": True}


def _reset():
    STATE["running"] = False
    STATE["simulate"] = False
    STATE["calls"] = []
    pie._SESSION["simulate"] = False
    pie._SESSION["started_at"] = None


def _drive(pending, limit=400):
    for _ in range(limit):
        outcome = pending.poll()
        if isinstance(outcome, Done):
            return outcome.value
        time.sleep(0.005)
    raise AssertionError("pending job did not finish")


def _call(params, allow_write=True):
    return pie.handle(_Server(allow_write), params)


def _expect_error(code, params, allow_write=True):
    try:
        _call(params, allow_write)
    except RpcError as exc:
        if exc.code != code:
            raise AssertionError("expected %s, got %s (%s)" % (code, exc.code, exc.message))
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

    def status_stopped():
        _reset()
        result = _call({"action": "status"})
        data = result.data
        assert data["isPieRunning"] is False, data
        assert data["isSimulating"] is False, data
        assert data["world"] is None, data
        assert data["startedAt"] is None, data
        assert data["durationMs"] >= 0, data
        assert STATE["calls"] == [], STATE["calls"]

    def start_and_stop():
        _reset()
        pending = _call({"action": "start", "waitReadyMs": 2000})
        data = _drive(pending).data
        assert data["action"] == "start", data
        assert data["isPieRunning"] is True, data
        assert data["isSimulating"] is False, data
        assert data["world"] == "/Game/Maps/TestMap.TestMap", data
        assert data["startedAt"], data
        assert STATE["calls"] == ["begin_play"], STATE["calls"]

        running = _call({"action": "status"}).data
        assert running["isPieRunning"] is True, running
        assert running["world"], running
        assert running["startedAt"], running

        stopped = _drive(_call({"action": "stop"})).data
        assert stopped["isPieRunning"] is False, stopped
        assert stopped["world"] is None, stopped
        assert stopped["startedAt"] is None, stopped
        assert STATE["calls"][-1] == "end_play", STATE["calls"]

    def stop_idempotent():
        _reset()
        result = _call({"action": "stop"})
        assert result.data["isPieRunning"] is False, result.data
        assert STATE["calls"] == [], STATE["calls"]

    def simulate_path():
        _reset()
        data = _drive(_call({"action": "start", "simulate": True})).data
        assert data["isPieRunning"] is True, data
        assert data["isSimulating"] is True, data
        assert STATE["calls"] == ["play_simulate"], STATE["calls"]
        _drive(_call({"action": "stop"}))

    def restart_sequence():
        _reset()
        _drive(_call({"action": "start"}))
        STATE["calls"] = []
        data = _drive(_call({"action": "restart", "waitReadyMs": 2000})).data
        assert data["action"] == "restart", data
        assert data["isPieRunning"] is True, data
        assert STATE["calls"] == ["end_play", "begin_play"], STATE["calls"]

    def invalid_action():
        _reset()
        _expect_error("INVALID_ARGUMENT", {"action": "pause"})

    def invalid_wait():
        _reset()
        _expect_error("INVALID_ARGUMENT", {"action": "start", "waitReadyMs": -1})

    def write_gate():
        _reset()
        for action in ("start", "stop", "restart"):
            try:
                rpc.enforce_gates(_Server(False), "pie.control", {"action": action})
            except RpcError as exc:
                assert exc.code == "PERMISSION_DENIED", exc.code
                assert exc.details.get("gate") == "bridge.allowWrite", exc.details
            else:
                raise AssertionError("gate allowed pie.control %s" % action)
        rpc.enforce_gates(_Server(False), "pie.control", {"action": "status"})

    def handler_gate():
        _reset()
        _expect_error("PERMISSION_DENIED", {"action": "start"}, allow_write=False)

    def registry():
        assert rpc.HANDLERS.get("pie.control") is pie.handle
        assert rpc.WRITE_ACTIONS.get("pie.control") == {"start", "stop", "restart"}

    def capabilities():
        _reset()
        caps = status.detect_capabilities()
        assert caps.get("pieControl") is True, caps
        original = unreal_stub.get_editor_subsystem

        def broken(_cls):
            raise RuntimeError("no editor")

        unreal_stub.get_editor_subsystem = broken
        try:
            caps = status.detect_capabilities()
            assert caps.get("pieControl") is False, caps
        finally:
            unreal_stub.get_editor_subsystem = original

    check("status_stopped", status_stopped)
    check("start_and_stop", start_and_stop)
    check("stop_idempotent", stop_idempotent)
    check("simulate_path", simulate_path)
    check("restart_sequence", restart_sequence)
    check("invalid_action", invalid_action)
    check("invalid_wait", invalid_wait)
    check("write_gate", write_gate)
    check("handler_gate", handler_gate)
    check("registry", registry)
    check("capabilities", capabilities)

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("PIE_CONTROL_RESULT FAIL")
        return 1
    print("PIE_CONTROL_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
