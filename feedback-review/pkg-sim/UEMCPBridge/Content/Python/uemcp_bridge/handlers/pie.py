"""``pie.control`` handler: start, stop and restart Play-In-Editor.

All work runs on the game thread.  Starting/stopping PIE is asynchronous, so
the handler returns a :class:`Pending` job that polls the editor state once per
tick instead of blocking the game thread (which would prevent PIE from coming
up in the first place).

Writes (start/stop/restart) are gated by ``allowWrite`` in ``rpc.enforce_gates``
before the job is queued; ``status`` is read-only and always available.
"""

import datetime
import time

from ..dispatcher import Done, Pending
from ..errors import RpcError
from . import (
    HandlerResult,
    check_keys,
    get_bool,
    get_enum,
    get_game_world,
    get_int,
    is_pie_running,
    level_subsystem,
)

ACTIONS = {"start", "stop", "restart", "status"}
WRITE_ACTIONS = {"start", "stop", "restart"}
_STOP_TIMEOUT_MS = 30000

# Best-effort state of the PIE session this bridge started.  UE exposes no
# Python API for "is simulating", so we remember what we asked for.
_SESSION = {"simulate": False, "started_at": None}


def _utc_now_iso():
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _world_path():
    world = get_game_world()
    if world is None:
        return None
    try:
        return str(world.get_path_name())
    except Exception:
        return str(world)


def _is_simulating():
    return bool(_SESSION["simulate"] and is_pie_running())


def _result(action, started_monotonic, warnings=None):
    running = is_pie_running()
    return HandlerResult(
        {
            "action": action,
            "isPieRunning": running,
            "isSimulating": _is_simulating() if running else False,
            "world": _world_path() if running else None,
            "startedAt": _SESSION["started_at"] if running else None,
            "durationMs": int((time.monotonic() - started_monotonic) * 1000),
        },
        warnings or [],
    )


def _subsystem():
    try:
        return level_subsystem()
    except Exception:
        return None


def _require(subsystem, name, capability, suggestion):
    function = getattr(subsystem, name, None)
    if not callable(function):
        raise RpcError(
            "CAPABILITY_UNAVAILABLE",
            "PIE control is not available in this editor build",
            {
                "capability": capability,
                "missing": name,
                "suggestion": suggestion,
            },
        )
    return function


def _start_request(subsystem, simulate):
    if simulate:
        function = _require(
            subsystem,
            "editor_play_simulate",
            "pieSimulate",
            "This editor build does not expose EditorPlaySimulate().",
        )
    else:
        function = _require(
            subsystem,
            "editor_request_begin_play",
            "piePlay",
            "This editor build exposes only Simulate; retry with simulate=true "
            "(Play start requires UE 5.7+).",
        )
    try:
        function()
    except Exception as exc:
        raise RpcError(
            "EXECUTION_ERROR",
            "Failed to start PIE: %s" % exc,
            {"action": "start", "simulate": simulate, "reason": str(exc)},
        )


def _stop_request(subsystem):
    function = _require(
        subsystem,
        "editor_request_end_play",
        "pieStop",
        "This editor build does not expose EditorRequestEndPlay().",
    )
    try:
        function()
    except Exception as exc:
        raise RpcError(
            "EXECUTION_ERROR",
            "Failed to stop PIE: %s" % exc,
            {"action": "stop", "reason": str(exc)},
        )


def handle(server, params):
    check_keys(params, {"action", "waitReadyMs", "simulate"})
    action = get_enum(params, "action", ACTIONS, required=True)
    wait_ready_ms = get_int(
        params, "waitReadyMs", default=15000, minimum=0, maximum=120000
    )
    simulate = get_bool(params, "simulate", default=False)

    started_monotonic = time.monotonic()

    if action == "status":
        return _result("status", started_monotonic)

    # Defence in depth: rpc.enforce_gates already rejected this before queueing.
    if not server.settings.allow_write:
        raise RpcError(
            "PERMISSION_DENIED",
            "PIE control is disabled (allowWrite=false)",
            {"gate": "bridge.allowWrite", "action": action},
        )

    subsystem = _subsystem()
    if subsystem is None:
        raise RpcError(
            "CAPABILITY_UNAVAILABLE",
            "LevelEditorSubsystem is not available",
            {"capability": "pieControl"},
        )

    if action == "stop":
        if not is_pie_running():
            return _result("stop", started_monotonic)
        _stop_request(subsystem)
        deadline = started_monotonic + _STOP_TIMEOUT_MS / 1000.0

        def poll_stop():
            if not is_pie_running():
                _SESSION["simulate"] = False
                _SESSION["started_at"] = None
                return Done(_result("stop", started_monotonic))
            if time.monotonic() > deadline:
                return Done(
                    _result("stop", started_monotonic, ["PIE_STOP_TIMEOUT"])
                )
            return None

        return Pending(poll_stop)

    if action == "restart":
        if not is_pie_running():
            return _start_pending(
                subsystem, simulate, wait_ready_ms, started_monotonic, "restart"
            )
        _stop_request(subsystem)
        stop_deadline = started_monotonic + _STOP_TIMEOUT_MS / 1000.0
        state = {"stopped": False, "started_at": None}

        def poll_restart():
            if not state["stopped"]:
                if is_pie_running():
                    if time.monotonic() > stop_deadline:
                        return Done(
                            _result("restart", started_monotonic, ["PIE_STOP_TIMEOUT"])
                        )
                    return None
                state["stopped"] = True
                _SESSION["simulate"] = False
                _SESSION["started_at"] = None
                _start_request(subsystem, simulate)
                state["start_deadline"] = time.monotonic() + wait_ready_ms / 1000.0

            if is_pie_running():
                _mark_started(simulate)
                return Done(_result("restart", started_monotonic))
            if time.monotonic() > state["start_deadline"]:
                return Done(
                    _result("restart", started_monotonic, ["PIE_START_TIMEOUT"])
                )
            return None

        return Pending(poll_restart)

    # action == "start"
    if is_pie_running():
        return HandlerResult(
            {
                "action": "start",
                "isPieRunning": True,
                "isSimulating": _is_simulating(),
                "world": _world_path(),
                "startedAt": _SESSION["started_at"],
                "durationMs": int((time.monotonic() - started_monotonic) * 1000),
            },
            ["PIE_ALREADY_RUNNING"],
        )
    return _start_pending(
        subsystem, simulate, wait_ready_ms, started_monotonic, "start"
    )


def _mark_started(simulate):
    _SESSION["simulate"] = bool(simulate)
    _SESSION["started_at"] = _utc_now_iso()


def _start_pending(subsystem, simulate, wait_ready_ms, started_monotonic, action):
    _start_request(subsystem, simulate)
    deadline = time.monotonic() + wait_ready_ms / 1000.0

    def poll_start():
        if is_pie_running():
            _mark_started(simulate)
            return Done(_result(action, started_monotonic))
        if time.monotonic() > deadline:
            return Done(_result(action, started_monotonic, ["PIE_START_TIMEOUT"]))
        return None

    return Pending(poll_start)
