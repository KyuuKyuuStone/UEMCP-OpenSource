"""UEMCP Bridge startup hook.

Executed by PythonScriptPlugin when the editor scans enabled plugins'
``Content/Python`` directories.  Startup is deferred by one Slate tick and is
fully guarded: a failure is logged and never blocks the editor.
"""

import unreal

_START_ATTEMPTED = False
_TICK_HANDLE = None


def _start_once():
    global _START_ATTEMPTED
    if _START_ATTEMPTED:
        return
    _START_ATTEMPTED = True
    try:
        try:
            is_editor = bool(unreal.SystemLibrary.is_editor())
        except Exception:
            is_editor = True
        if not is_editor:
            # Commandlets (e.g. -run=pythonscript) do not host the editor UI;
            # the bridge is only started by editor sessions.
            return
        from uemcp_bridge.server import BridgeServer

        BridgeServer.instance().start()
    except Exception as exc:
        try:
            unreal.log_error("[UEMCP] failed to start bridge: %s" % exc)
        except Exception:
            pass


def _on_tick(_delta_seconds):
    global _TICK_HANDLE
    handle = _TICK_HANDLE
    _TICK_HANDLE = None
    if handle is not None:
        try:
            unreal.unregister_slate_post_tick_callback(handle)
        except Exception:
            pass
    _start_once()


if not _START_ATTEMPTED:
    try:
        _TICK_HANDLE = unreal.register_slate_post_tick_callback(_on_tick)
    except Exception as exc:
        try:
            unreal.log_error(
                "[UEMCP] failed to schedule bridge startup, starting immediately: %s" % exc
            )
        except Exception:
            pass
        _start_once()
