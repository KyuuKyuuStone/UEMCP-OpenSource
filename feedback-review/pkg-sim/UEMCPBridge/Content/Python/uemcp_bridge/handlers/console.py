"""``console.command`` handler (architecture doc section 5.8).

MVP never captures console output; ``outputAvailable`` is always ``false``.
"""

import time

from ..errors import RpcError
from . import (
    HandlerResult,
    check_keys,
    get_bool,
    get_enum,
    get_int,
    get_str,
    get_unreal,
    get_editor_world,
    get_game_world,
)

# Single source of truth for the permanent deny list on the bridge side.
# The server/shared copy (architecture section 5.8) is documentation only; do
# not duplicate maintenance of this table elsewhere.
PERMANENTLY_DENIED = {
    "quit",
    "exit",
    "restart",
    "shutdown",
    "reconnect",
    "open",
    "exec",
    "py",
    "python",
    "delete",
    "rm",
    "crash",
    "bugit",
}


def _first_token(command):
    parts = command.strip().split()
    return parts[0].lower() if parts else ""


def _is_allowed(command, allowlist):
    first = _first_token(command)
    if not first:
        return False
    if first in PERMANENTLY_DENIED:
        return False
    lowered = command.strip().lower()
    for prefix in allowlist:
        text = str(prefix).strip().lower()
        if text and lowered.startswith(text):
            return True
    return False


def handle(server, params):
    check_keys(params, {"command", "worldContext", "timeoutMs", "captureOutput"})
    command = get_str(
        params, "command", min_length=1, max_length=2000, required=True
    )
    world_context = get_enum(
        params, "worldContext", {"editor", "pie"}, default="editor"
    )
    get_int(params, "timeoutMs", default=5000, minimum=1000, maximum=30000)
    capture_output = get_bool(params, "captureOutput", default=False)

    if not server.settings.allow_console:
        raise RpcError(
            "PERMISSION_DENIED",
            "Console commands are disabled (allowConsole=false)",
            {"gate": "bridge.allowConsole"},
        )

    if not _is_allowed(command, server.settings.console_allowlist):
        raise RpcError(
            "COMMAND_NOT_ALLOWED",
            "Console command is not allowed: %s" % command,
            {"command": command},
        )

    if world_context == "pie":
        context = get_game_world()
        if context is None:
            raise RpcError(
                "EDITOR_UNSAFE_STATE",
                "PIE world is not available",
                {"state": "pie_not_running"},
            )
    else:
        context = get_editor_world()
        if context is None:
            raise RpcError(
                "EDITOR_UNSAFE_STATE",
                "Editor world is not available",
                {"state": "no_editor_world"},
            )

    unreal = get_unreal()
    started = time.monotonic()
    try:
        unreal.SystemLibrary.execute_console_command(context, command)
    except Exception as exc:
        raise RpcError(
            "INTERNAL", "Console command failed: %s" % exc, {"command": command, "reason": str(exc)}
        )
    duration_ms = int((time.monotonic() - started) * 1000)

    warnings = []
    if capture_output:
        warnings.append("OUTPUT_CAPTURE_UNSUPPORTED")

    return HandlerResult(
        {
            "command": command,
            "dispatched": True,
            "output": None,
            "outputAvailable": False,
            "durationMs": duration_ms,
        },
        warnings,
    )
