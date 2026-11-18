"""Error origin/stage annotation self-check (no editor required).

Covers: annotate_origin_stage defaults and explicit-wins semantics,
invalid_argument caller origin, rpc_error_response envelope annotation,
object.call in-body vs bind errors (caller/object.call), python.exec caller
origin, and the live HTTP paths: METHOD_NOT_FOUND (caller/dispatch),
editor.status INVALID_ARGUMENT (caller/editor.status), RATE_LIMITED
(bridge/rate_limit), success meta.queuedMs (sync=0, HTTP-thread=None) and
BRIDGE_TIMEOUT (bridge/game_thread with the configured timeoutMs).
"""

import json
import os
import sys
import tempfile
import time
import types
import urllib.error
import urllib.request

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

HOME_DIR = tempfile.mkdtemp(prefix="uemcp_origin_home_")
PROJECT_DIR = tempfile.mkdtemp(prefix="uemcp_origin_proj_")
os.environ["USERPROFILE"] = HOME_DIR
os.environ["HOME"] = HOME_DIR
for _key in list(os.environ):
    if _key.startswith("UEMCP_BRIDGE_"):
        os.environ.pop(_key)
os.environ["UEMCP_BRIDGE_PORT"] = "0"

# Minimal in-memory unreal stub (same surface the file stubs provide).
_stub = types.ModuleType("unreal")


class _Paths(object):
    @staticmethod
    def project_dir():
        return PROJECT_DIR + os.sep

    @staticmethod
    def project_saved_dir():
        return os.path.join(PROJECT_DIR, "Saved") + os.sep

    @staticmethod
    def project_config_dir():
        return os.path.join(PROJECT_DIR, "Config") + os.sep


class _SystemLibrary(object):
    @staticmethod
    def get_engine_version():
        return "5.4.4-stub"

    @staticmethod
    def is_editor():
        return True

    @staticmethod
    def get_command_line():
        return ""


class _AssetRegistryHelpers(object):
    pass


_stub.Paths = _Paths
_stub.SystemLibrary = _SystemLibrary
_stub.AssetRegistryHelpers = _AssetRegistryHelpers
_stub.register_slate_post_tick_callback = lambda fn: 1
_stub.unregister_slate_post_tick_callback = lambda handle: None
_stub.register_python_shutdown_callback = lambda fn: None
_stub.log = lambda message: None
_stub.log_error = lambda message: None
sys.modules["unreal"] = _stub

sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge import rpc  # noqa: E402
from uemcp_bridge import server as server_mod  # noqa: E402
from uemcp_bridge.dispatcher import (  # noqa: E402
    GameThreadDispatcher,
    SynchronousDispatcher,
)
from uemcp_bridge.errors import (  # noqa: E402
    RpcError,
    annotate_origin_stage,
    invalid_argument,
    rpc_error_response,
)
from uemcp_bridge.handlers import HandlerResult, objects, python_exec  # noqa: E402


def _rpc(port, token, method="test.noop", params=None, request_id=1, with_token=True):
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params if params is not None else {},
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if with_token:
        headers["X-UEMCP-Token"] = token
    request = urllib.request.Request(
        "http://127.0.0.1:%d/rpc" % port,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body) if body else None
        except ValueError:
            return exc.code, {"raw": body}


def check_annotate(failures):
    cases = [
        ("INVALID_PARAMS", {}, "caller", "envelope"),
        ("PARSE_ERROR", None, "caller", "envelope"),
        ("METHOD_NOT_FOUND", {}, "caller", "rpc"),
        ("METHOD_NOT_FOUND", {"stage": "dispatch"}, "caller", "dispatch"),
        ("BRIDGE_TIMEOUT", {"phase": "game_thread"}, "bridge", "rpc"),
        ("PYTHON_ERROR", {"origin": "caller", "stage": "python.exec"}, "caller", "python.exec"),
        ("RATE_LIMITED", None, "bridge", "rpc"),
        ("INTERNAL", "some-string", "bridge", "rpc"),
    ]
    for code, details, origin, stage in cases:
        out = annotate_origin_stage(code, details)
        if out.get("origin") != origin or out.get("stage") != stage:
            failures.append(
                "annotate(%s, %r) -> %r, expected origin=%s stage=%s"
                % (code, details, out, origin, stage)
            )
    if annotate_origin_stage("BRIDGE_TIMEOUT", {"phase": "game_thread"}).get("phase") != "game_thread":
        failures.append("annotate: existing detail keys lost")
    if annotate_origin_stage("INTERNAL", "some-string").get("value") != "some-string":
        failures.append("annotate: non-dict details not wrapped")
    original = {"origin": "bridge", "stage": "custom"}
    annotate_origin_stage("INVALID_PARAMS", original)
    if original != {"origin": "bridge", "stage": "custom"}:
        failures.append("annotate: input dict mutated")
    print("ANNOTATE_ORIGIN_STAGE cases=%d ok" % len(cases))


def check_invalid_argument(failures):
    issues = [{"path": "sections[0]", "code": "invalid_enum_value", "message": "bad"}]
    err = invalid_argument(issues)
    if err.code != "INVALID_ARGUMENT":
        failures.append("invalid_argument: code=%s" % err.code)
    if err.details.get("issues") != issues or err.details.get("origin") != "caller":
        failures.append("invalid_argument: details=%r" % err.details)
    print("INVALID_ARGUMENT_HELPER origin=caller issues=preserved")


def check_rpc_error_response(failures):
    payload = rpc_error_response(7, "PARSE_ERROR", "bad json", -32700)
    data = payload["error"]["data"]
    if payload["error"]["code"] != -32700 or payload["id"] != 7:
        failures.append("rpc_error_response: envelope=%r" % payload)
    if data["details"] != {"origin": "caller", "stage": "envelope"}:
        failures.append("rpc_error_response: details=%r" % data["details"])
    print("RPC_ERROR_RESPONSE details=%r" % data["details"])


class _FakeTarget(object):
    def boom(self, x):
        raise TypeError("inside body")

    def needs_two(self, a, b):
        return a + b


def check_objects_origin(failures):
    fake = _FakeTarget()
    original_resolver = objects._resolve_target
    objects._resolve_target = lambda target: fake
    server = types.SimpleNamespace(settings=types.SimpleNamespace(allow_write=True))
    try:
        try:
            objects.handle_call(server, {"target": "Fake", "function": "boom", "args": [1]})
            failures.append("objects: in-body TypeError did not raise")
        except RpcError as exc:
            if exc.code != "EXECUTION_ERROR":
                failures.append("objects: in-body code=%s" % exc.code)
            if exc.details.get("phase") != "in-body":
                failures.append("objects: in-body phase=%r" % exc.details.get("phase"))
            if exc.details.get("origin") != "caller" or exc.details.get("stage") != "object.call":
                failures.append("objects: in-body origin/stage=%r" % exc.details)
            if "inside body" not in str(exc.details.get("error", "")):
                failures.append("objects: in-body error text=%r" % exc.details.get("error"))
        try:
            objects.handle_call(server, {"target": "Fake", "function": "needs_two", "args": [1]})
            failures.append("objects: bind error did not raise")
        except RpcError as exc:
            if exc.code != "INVALID_ARGUMENT":
                failures.append("objects: bind code=%s" % exc.code)
            if exc.details.get("origin") != "caller" or exc.details.get("stage") != "object.call":
                failures.append("objects: bind origin/stage=%r" % exc.details)
            if exc.details.get("expectedParamCount") != 2 or exc.details.get("gotParamCount") != 1:
                failures.append("objects: bind counts=%r" % exc.details)
        print("OBJECT_CALL_ORIGIN in-body=caller/object.call bind=caller/object.call")
    finally:
        objects._resolve_target = original_resolver


def check_python_exec_origin(failures):
    server = types.SimpleNamespace(settings=types.SimpleNamespace(allow_exec=True))
    try:
        python_exec.handle(server, {"code": "raise ValueError('boom')"})
        failures.append("python_exec: caller error did not raise")
    except RpcError as exc:
        if exc.code != "PYTHON_ERROR":
            failures.append("python_exec: code=%s" % exc.code)
        if exc.details.get("origin") != "caller" or exc.details.get("stage") != "python.exec":
            failures.append("python_exec: origin/stage=%r" % exc.details)
        if "ValueError: boom" not in str(exc.details.get("traceback", "")):
            failures.append("python_exec: traceback=%r" % exc.details.get("traceback"))
    closed = types.SimpleNamespace(settings=types.SimpleNamespace(allow_exec=False))
    try:
        python_exec.handle(closed, {"code": "1"})
        failures.append("python_exec: closed gate did not raise")
    except RpcError as exc:
        if exc.code != "EXEC_DISABLED" or exc.details.get("gate") != "bridge.allowExec":
            failures.append("python_exec: gate error=%r" % exc.details)
    print("PYTHON_EXEC_ORIGIN caller/python.exec gate=EXEC_DISABLED")


def check_http_rate_limit(failures):
    rpc.HANDLERS["test.noop"] = lambda server, params: HandlerResult({"noop": True})
    os.environ["UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND"] = "1"
    os.environ["UEMCP_BRIDGE_RATE_LIMIT_BURST"] = "1"
    server = server_mod.BridgeServer.instance()
    if not server.start(dispatcher=SynchronousDispatcher()):
        failures.append("http_rate: start failed")
        return
    try:
        status, body = _rpc(server.port, server.token, request_id=1)
        result = (body or {}).get("result", {})
        if status != 200 or not result.get("ok"):
            failures.append("http_rate: first request status=%s body=%r" % (status, body))
        else:
            meta = result.get("meta", {})
            expected_keys = {"requestId", "durationMs", "queuedMs", "ueVersion", "pluginVersion"}
            if set(meta) != expected_keys:
                failures.append("http_rate: meta keys=%r" % sorted(meta))
            if meta.get("queuedMs") != 0:
                failures.append("http_rate: sync queuedMs=%r, expected 0" % meta.get("queuedMs"))
        status, body = _rpc(server.port, server.token, request_id=2)
        if status != 429:
            failures.append("http_rate: second request status=%s, expected 429" % status)
        error = (body or {}).get("error", {})
        data = error.get("data", {})
        if error.get("code") != -32012 or data.get("errorCode") != "RATE_LIMITED":
            failures.append("http_rate: error=%r" % error)
        details = data.get("details", {})
        if details.get("origin") != "bridge" or details.get("stage") != "rate_limit":
            failures.append("http_rate: origin/stage=%r" % details)
        if details.get("gate") != "bridge.rateLimit":
            failures.append("http_rate: gate=%r" % details.get("gate"))
        print("HTTP_RATE_LIMIT meta=5keys queuedMs=0 origin=bridge/rate_limit")
    finally:
        server.stop()
        os.environ.pop("UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND", None)
        os.environ.pop("UEMCP_BRIDGE_RATE_LIMIT_BURST", None)


def check_http_envelope(failures):
    os.environ["UEMCP_BRIDGE_RATE_LIMIT_ENABLED"] = "false"
    server = server_mod.BridgeServer.instance()
    if not server.start(dispatcher=SynchronousDispatcher()):
        failures.append("http_envelope: start failed")
        return
    try:
        status, body = _rpc(server.port, server.token, method="no.such.method", request_id=11)
        data = (body or {}).get("error", {}).get("data", {})
        if data.get("errorCode") != "METHOD_NOT_FOUND":
            failures.append("http_envelope: method_not_found=%r (status=%s)" % (data, status))
        details = data.get("details", {})
        if details.get("origin") != "caller" or details.get("stage") != "dispatch":
            failures.append("http_envelope: MNF origin/stage=%r" % details)
        status, body = _rpc(
            server.port, server.token, method="editor.status",
            params={"sections": ["bogus"]}, request_id=12,
        )
        data = (body or {}).get("error", {}).get("data", {})
        if data.get("errorCode") != "INVALID_ARGUMENT":
            failures.append("http_envelope: editor.status=%r (status=%s)" % (data, status))
        details = data.get("details", {})
        if details.get("origin") != "caller" or details.get("stage") != "editor.status":
            failures.append("http_envelope: status origin/stage=%r" % details)
        if not details.get("issues"):
            failures.append("http_envelope: issues missing=%r" % details)
        status, body = _rpc(server.port, server.token, method="bridge.ping", request_id=13)
        result = (body or {}).get("result", {})
        if status != 200 or not result.get("ok"):
            failures.append("http_envelope: ping status=%s body=%r" % (status, body))
        elif result.get("meta", {}).get("queuedMs") is not None:
            failures.append(
                "http_envelope: HTTP-thread queuedMs=%r, expected None"
                % result.get("meta", {}).get("queuedMs")
            )
        print("HTTP_ENVELOPE MNF=caller/dispatch status=caller/editor.status ping_queuedMs=None")
    finally:
        server.stop()
        os.environ.pop("UEMCP_BRIDGE_RATE_LIMIT_ENABLED", None)


def check_http_timeout(failures):
    os.environ["UEMCP_BRIDGE_RATE_LIMIT_ENABLED"] = "false"
    os.environ["UEMCP_BRIDGE_REQUEST_TIMEOUT_MS"] = "1000"
    executed = []
    rpc.HANDLERS["test.never_runs"] = (
        lambda server, params: executed.append(1) or HandlerResult({"x": 1})
    )
    server = server_mod.BridgeServer.instance()
    if not server.start():
        failures.append("http_timeout: start failed")
        return
    try:
        if not isinstance(server.dispatcher, GameThreadDispatcher):
            failures.append("http_timeout: dispatcher=%r" % type(server.dispatcher))
        started = time.monotonic()
        status, body = _rpc(server.port, server.token, method="test.never_runs", request_id=21)
        elapsed = time.monotonic() - started
        if status != 504:
            failures.append("http_timeout: status=%s, expected 504" % status)
        error = (body or {}).get("error", {})
        data = error.get("data", {})
        if error.get("code") != -32020 or data.get("errorCode") != "BRIDGE_TIMEOUT":
            failures.append("http_timeout: error=%r" % error)
        if data.get("retryable") is not True:
            failures.append("http_timeout: retryable=%r" % data.get("retryable"))
        details = data.get("details", {})
        if details.get("origin") != "bridge" or details.get("stage") != "game_thread":
            failures.append("http_timeout: origin/stage=%r" % details)
        if details.get("timeoutMs") != 1000 or details.get("phase") != "game_thread":
            failures.append("http_timeout: details=%r" % details)
        if elapsed < 0.9:
            failures.append("http_timeout: elapsed=%.3fs too fast" % elapsed)
        server.dispatcher._on_tick(0.016)  # cancelled job must be dropped
        if executed:
            failures.append("http_timeout: timed-out job executed")
        if not server.dispatcher._queue.empty():
            failures.append("http_timeout: queue not empty after tick")
        print("HTTP_BRIDGE_TIMEOUT origin=bridge/game_thread timeoutMs=1000 dropped=ok")
    finally:
        server.stop()
        rpc.HANDLERS.pop("test.never_runs", None)
        os.environ.pop("UEMCP_BRIDGE_RATE_LIMIT_ENABLED", None)
        os.environ.pop("UEMCP_BRIDGE_REQUEST_TIMEOUT_MS", None)


def main():
    failures = []
    check_annotate(failures)
    check_invalid_argument(failures)
    check_rpc_error_response(failures)
    check_objects_origin(failures)
    check_python_exec_origin(failures)
    try:
        check_http_rate_limit(failures)
        check_http_envelope(failures)
        check_http_timeout(failures)
    finally:
        rpc.HANDLERS.pop("test.noop", None)
        for key in list(os.environ):
            if key.startswith("UEMCP_BRIDGE_"):
                os.environ.pop(key)
    for item in failures:
        print("FAIL: %s" % item)
    if failures:
        print("ERROR_ORIGIN_RESULT FAIL (%d)" % len(failures))
        return 1
    print("ERROR_ORIGIN_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
