"""JSON-RPC method routing and permission gates (architecture doc 2.8 / 6.3)."""

import os
import time
import traceback
import uuid

from .dispatcher import DispatcherBusy, DispatcherTimeout
from .errors import (
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    RpcError,
)
from .handlers import HandlerResult
from .handlers import (
    actors,
    assets,
    blueprints,
    console,
    levels,
    logs,
    materials,
    objects,
    pie,
    python_exec,
    status,
)
from .handlers import viewport as viewport_handler

# Methods whose whole body is a write operation.
WRITE_METHODS = {"actor.edit", "object.call"}

# Methods where only some actions are writes.
WRITE_ACTIONS = {
    "level.control": {"open", "save_current", "save_all", "new"},
    "material.params": {"set", "create_instance"},
    "blueprint.query": {"compile"},
    "pie.control": {"start", "stop", "restart"},
}


def _handle_ping(server, params):
    return HandlerResult({"pong": True, "pid": os.getpid(), "port": server.port})


def _handle_capabilities(server, params):
    return HandlerResult(dict(server.capabilities))


HANDLERS = {
    "bridge.ping": _handle_ping,
    "bridge.capabilities": _handle_capabilities,
    "editor.status": status.handle,
    "actor.query": actors.handle_query,
    "actor.edit": actors.handle_edit,
    "level.control": levels.handle,
    "asset.search": assets.handle,
    "material.params": materials.handle,
    "viewport.capture": viewport_handler.handle,
    "console.command": console.handle,
    "python.exec": python_exec.handle,
    "blueprint.query": blueprints.handle,
    "pie.control": pie.handle,
    "object.reflect": objects.handle_reflect,
    "object.call": objects.handle_call,
    "log.query": logs.handle,
}

# These do not touch the unreal API and therefore bypass the game-thread queue.
_HTTP_THREAD_METHODS = {"bridge.ping", "bridge.capabilities"}


def enforce_gates(server, method, params):
    """Bridge-side hard gates.  Must run before a job is queued."""
    action = params.get("action") if isinstance(params, dict) else None
    is_write = method in WRITE_METHODS or action in WRITE_ACTIONS.get(method, ())
    if is_write and not server.settings.allow_write:
        raise RpcError(
            "PERMISSION_DENIED",
            "Write operations are disabled (allowWrite=false)",
            {"gate": "bridge.allowWrite"},
        )
    if method == "console.command" and not server.settings.allow_console:
        raise RpcError(
            "PERMISSION_DENIED",
            "Console commands are disabled (allowConsole=false)",
            {"gate": "bridge.allowConsole"},
        )
    if method == "python.exec" and not server.settings.allow_exec:
        raise RpcError(
            "EXEC_DISABLED",
            "Python execution is disabled (allowExec=false)",
            {"gate": "bridge.allowExec"},
        )


_MAX_TRACEBACK_CHARS = 8000


def _python_error(exc):
    """Map an unexpected Python exception (handler or capture poll) to the
    PYTHON_ERROR contract code, with a length-limited traceback."""
    detail = traceback.format_exc()
    if len(detail) > _MAX_TRACEBACK_CHARS:
        detail = detail[:_MAX_TRACEBACK_CHARS] + "\n...[traceback truncated]"
    message = str(exc)
    if message:
        message = "%s: %s" % (exc.__class__.__name__, message)
    else:
        message = exc.__class__.__name__
    return RpcError(
        "PYTHON_ERROR",
        message,
        {"traceback": detail, "exceptionType": exc.__class__.__name__},
    )


def _request_timeout_seconds(server, request):
    meta = request.get("meta")
    timeout_ms = None
    if isinstance(meta, dict):
        value = meta.get("timeoutMs")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            timeout_ms = int(value)
    params = request.get("params")
    if isinstance(params, dict):
        value = params.get("timeoutMs")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # Give the game-thread job a small grace period beyond the
            # tool-level timeout so it can return its own structured error.
            timeout_ms = max(timeout_ms or 0, int(value) + 5000)
    if timeout_ms is None:
        timeout_ms = server.settings.request_timeout_ms
    timeout_ms = max(1000, min(120000, timeout_ms))
    return timeout_ms / 1000.0


def handle_request(server, request):
    """Process a validated JSON-RPC request object and return the result payload."""
    method = request.get("method")
    if not isinstance(method, str) or not method:
        raise RpcError(
            "INVALID_REQUEST",
            "method must be a non-empty string",
            {},
            rpc_code=INVALID_REQUEST,
            http_status=400,
        )
    params = request.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise RpcError(
            "INVALID_PARAMS",
            "params must be an object",
            {},
            rpc_code=INVALID_PARAMS,
            http_status=400,
        )

    handler = HANDLERS.get(method)
    if handler is None:
        raise RpcError(
            "METHOD_NOT_FOUND",
            "Unknown method: %s" % method,
            {"method": method},
            rpc_code=METHOD_NOT_FOUND,
            http_status=404,
        )

    # Global bridge rate limit (architecture 6.7).  This must run before the
    # permission gates and before the job is queued so a rejected request can
    # never produce an editor side effect.  Unknown methods were already
    # rejected above and therefore do not consume a token.
    limiter = getattr(server, "rate_limiter", None)
    if limiter is not None:
        allowed, retry_after = limiter.try_acquire()
        if not allowed:
            raise RpcError(
                "RATE_LIMITED",
                "Bridge rate limit exceeded (%g req/s, burst %d)"
                % (limiter.per_second, int(limiter.burst)),
                {
                    "gate": "bridge.rateLimit",
                    "limitPerSecond": limiter.per_second,
                    "burst": int(limiter.burst),
                    "retryAfterMs": int(round(retry_after * 1000.0)),
                },
            )

    enforce_gates(server, method, params)

    timeout_s = _request_timeout_seconds(server, request)
    started = time.monotonic()

    try:
        if method in _HTTP_THREAD_METHODS:
            outcome = handler(server, params)
        else:
            outcome = server.dispatcher.call(
                lambda: handler(server, params), timeout_s
            )
    except (DispatcherBusy, DispatcherTimeout):
        # Queue/timeout conditions are bridge-level, not Python failures.
        raise
    except RpcError:
        # Contract errors raised deliberately by handlers pass through.
        raise
    except Exception as exc:
        # Any other exception originates in Python (handler or capture poll).
        raise _python_error(exc)

    duration_ms = int((time.monotonic() - started) * 1000)
    if not isinstance(outcome, HandlerResult):
        outcome = HandlerResult(outcome)

    request_id = request.get("id")
    meta = {
        "requestId": request_id if request_id is not None else "req_" + uuid.uuid4().hex,
        "durationMs": duration_ms,
        "ueVersion": server.ue_version,
        "pluginVersion": server.plugin_version,
    }
    return {
        "ok": True,
        "data": outcome.data,
        "warnings": outcome.warnings,
        "meta": meta,
    }
