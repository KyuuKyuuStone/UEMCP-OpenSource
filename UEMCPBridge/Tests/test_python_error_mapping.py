"""Regression test for DEFECT-3: Python exceptions map to PYTHON_ERROR."""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge import rpc  # noqa: E402
from uemcp_bridge.dispatcher import DispatcherTimeout, SynchronousDispatcher  # noqa: E402
from uemcp_bridge.errors import RpcError  # noqa: E402
from uemcp_bridge.handlers import HandlerResult  # noqa: E402


class _FakeSettings(object):
    request_timeout_ms = 30000


class _FakeServer(object):
    def __init__(self, dispatcher=None):
        self.settings = _FakeSettings()
        self.dispatcher = dispatcher or SynchronousDispatcher()
        self.capabilities = {}
        self.ue_version = "5.4.4-test"
        self.plugin_version = "0.1.0"
        self.port = 0


class _TimeoutDispatcher(object):
    def call(self, fn, timeout_s):
        raise DispatcherTimeout("simulated timeout")

    def shutdown(self):
        pass


def _call_with_handler(method, handler, params=None, dispatcher=None):
    original = rpc.HANDLERS.get(method)
    rpc.HANDLERS[method] = handler
    try:
        return rpc.handle_request(
            _FakeServer(dispatcher),
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )
    finally:
        if original is None:
            rpc.HANDLERS.pop(method, None)
        else:
            rpc.HANDLERS[method] = original


def main():
    failures = []

    def boom(_server, _params):
        raise ValueError("kaboom")

    try:
        _call_with_handler("editor.status", boom)
    except RpcError as exc:
        if exc.code != "PYTHON_ERROR":
            failures.append("python error code = %r" % exc.code)
        if exc.rpc_code != -32014:
            failures.append("python error rpc_code = %r" % exc.rpc_code)
        if exc.http_status != 500:
            failures.append("python error http = %r" % exc.http_status)
        if "kaboom" not in exc.message:
            failures.append("python error message = %r" % exc.message)
        traceback_text = (exc.details or {}).get("traceback", "")
        if "ValueError" not in traceback_text or "kaboom" not in traceback_text:
            failures.append("python error traceback missing: %r" % traceback_text[:200])
        print("PYTHON_ERROR code=%s rpc=%d http=%d message=%r" % (
            exc.code, exc.rpc_code, exc.http_status, exc.message))
    else:
        failures.append("ValueError was not mapped to RpcError")

    # Long exception messages must be truncated in details.traceback.
    def long_boom(_server, _params):
        raise ValueError("x" * 20000)

    try:
        _call_with_handler("editor.status", long_boom)
    except RpcError as exc:
        traceback_text = (exc.details or {}).get("traceback", "")
        if len(traceback_text) > 8200:
            failures.append("traceback was not truncated (%d chars)" % len(traceback_text))
        if "traceback truncated" not in traceback_text:
            failures.append("truncation marker missing")
        print("TRACEBACK_TRUNCATED length=%d" % len(traceback_text))
    else:
        failures.append("long ValueError was not mapped")

    # Contract errors must pass through unchanged.
    def contract_error(_server, _params):
        raise RpcError("ACTOR_NOT_FOUND", "nope", {"selector": {"kind": "label", "value": "x"}})

    try:
        _call_with_handler("actor.query", contract_error)
    except RpcError as exc:
        if exc.code != "ACTOR_NOT_FOUND" or exc.rpc_code != -32044:
            failures.append("contract error was rewritten: %r/%r" % (exc.code, exc.rpc_code))
        else:
            print("CONTRACT_ERROR_PRESERVED code=%s rpc=%d" % (exc.code, exc.rpc_code))
    else:
        failures.append("contract RpcError was not propagated")

    # Dispatcher timeouts must not be mistaken for Python errors.
    try:
        _call_with_handler("editor.status", lambda s, p: HandlerResult({}), dispatcher=_TimeoutDispatcher())
    except DispatcherTimeout:
        print("DISPATCHER_TIMEOUT_PRESERVED")
    except RpcError as exc:
        failures.append("timeout was mapped to %r" % exc.code)
    else:
        failures.append("timeout did not raise")

    # Success path still wraps into the result envelope.
    result = _call_with_handler(
        "editor.status", lambda s, p: HandlerResult({"ok_marker": True})
    )
    if not result.get("ok") or result.get("data") != {"ok_marker": True}:
        failures.append("success envelope broken: %r" % (result,))
    else:
        print("SUCCESS_ENVELOPE ok meta_keys=%s" % sorted(result.get("meta", {}).keys()))

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("PYTHON_ERROR_RESULT FAIL")
        return 1
    print("PYTHON_ERROR_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
