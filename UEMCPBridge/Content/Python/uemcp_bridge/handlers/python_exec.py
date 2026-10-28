"""``python.exec`` handler (architecture doc section 5.9).

The gate check (``allowExec``) happens in ``rpc.py`` before the job is queued.
Execution cannot be interrupted: the request timeout only bounds the HTTP
wait, matching the architecture contract.
"""

import contextlib
import io
import time
import traceback

from ..errors import RpcError
from ..serialization import NotSerializable, to_jsonable
from . import HandlerResult, check_keys, get_bool, get_enum, get_int, get_str, get_unreal

_MAX_CAPTURE_CHARS = 1024 * 1024


def _truncate(text):
    if len(text) <= _MAX_CAPTURE_CHARS:
        return text
    return text[:_MAX_CAPTURE_CHARS] + "\n...[truncated]"


def handle(server, params):
    check_keys(
        params, {"code", "mode", "resultExpression", "timeoutMs", "captureOutput"}
    )
    code = get_str(
        params, "code", min_length=1, max_length=65536, required=True
    )
    mode = get_enum(params, "mode", {"exec", "eval"}, default="exec")
    result_expression = get_str(
        params, "resultExpression", max_length=4096
    )
    get_int(params, "timeoutMs", default=10000, minimum=1000, maximum=120000)
    capture_output = get_bool(params, "captureOutput", default=True)

    if not server.settings.allow_exec:
        raise RpcError(
            "EXEC_DISABLED",
            "Python execution is disabled (allowExec=false)",
            {"gate": "bridge.allowExec"},
        )

    unreal = get_unreal()
    scope = {"__name__": "__uemcp__", "unreal": unreal}
    stdout = io.StringIO()
    stderr = io.StringIO()
    started = time.monotonic()
    value = None

    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if mode == "eval":
                value = eval(compile(code, "<uemcp>", "eval"), scope)
            else:
                exec(compile(code, "<uemcp>", "exec"), scope)
                if result_expression:
                    value = eval(
                        compile(result_expression, "<uemcp-result>", "eval"), scope
                    )
    except Exception:
        detail = traceback.format_exc()
        raise RpcError(
            "PYTHON_ERROR",
            detail.strip().splitlines()[-1] if detail.strip() else "Python error",
            {"traceback": _truncate(detail)},
        )

    duration_ms = int((time.monotonic() - started) * 1000)

    try:
        serialized = to_jsonable(value)
    except NotSerializable as exc:
        raise RpcError(
            "RESULT_NOT_SERIALIZABLE",
            "Execution result cannot be serialized: %s" % exc,
            {"reason": str(exc)},
        )

    out_text = _truncate(stdout.getvalue()) if capture_output else ""
    err_text = _truncate(stderr.getvalue()) if capture_output else ""

    return HandlerResult(
        {
            "mode": mode,
            "result": serialized,
            "stdout": out_text,
            "stderr": err_text,
            "durationMs": duration_ms,
            "timedOut": False,
        }
    )
