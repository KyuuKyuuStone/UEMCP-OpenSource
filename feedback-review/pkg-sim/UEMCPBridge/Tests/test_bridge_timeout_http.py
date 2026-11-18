"""Real BRIDGE_TIMEOUT path over HTTP (no editor required).

Known gap: the timeout branch of the bridge was never exercised end to end —
only ``DispatcherTimeout`` was faked in unit tests.  This script starts a real
``BridgeServer`` with the **real** ``GameThreadDispatcher`` (stub ``unreal``
module whose Slate tick is never pumped), sends one ``/rpc`` request and
asserts the complete contract:

* HTTP 504;
* JSON-RPC ``error.code == -32020`` (``BRIDGE_TIMEOUT``);
* ``error.data.retryable == true`` and ``details.phase == "game_thread"``;
* the request really waited for the configured timeout;
* the abandoned job is cancelled and never executes when a tick finally
  arrives, i.e. a timeout cannot produce an editor side effect later.

Exit code 0 = PASS, 1 = FAIL.
"""

import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

HOME_DIR = tempfile.mkdtemp(prefix="uemcp_timeout_home_")
PROJECT_DIR = tempfile.mkdtemp(prefix="uemcp_timeout_project_")
STUB_DIR = tempfile.mkdtemp(prefix="uemcp_timeout_stub_")

os.environ["USERPROFILE"] = HOME_DIR
os.environ["HOME"] = HOME_DIR
for _name in (
    "UEMCP_BRIDGE_TOKEN_FILE",
    "UEMCP_BRIDGE_RATE_LIMIT_ENABLED",
    "UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND",
    "UEMCP_BRIDGE_RATE_LIMIT_BURST",
):
    os.environ.pop(_name, None)
os.environ["UEMCP_BRIDGE_PORT"] = "0"
os.environ["UEMCP_BRIDGE_REQUEST_TIMEOUT_MS"] = "1000"

with open(os.path.join(STUB_DIR, "unreal.py"), "w", encoding="utf-8") as handle:
    handle.write(
        "class Paths:\n"
        "    @staticmethod\n"
        "    def project_dir():\n"
        "        return %r\n"
        "    @staticmethod\n"
        "    def project_saved_dir():\n"
        "        return %r\n"
        "class SystemLibrary:\n"
        "    @staticmethod\n"
        "    def get_engine_version():\n"
        "        return '5.4.4-stub'\n"
        "    @staticmethod\n"
        "    def is_editor():\n"
        "        return True\n"
        "class AssetRegistryHelpers:\n"
        "    pass\n"
        "def register_slate_post_tick_callback(fn):\n"
        "    return 1\n"
        "def unregister_slate_post_tick_callback(handle):\n"
        "    pass\n"
        "def register_python_shutdown_callback(fn):\n"
        "    pass\n"
        "def log(message):\n"
        "    pass\n"
        "def log_error(message):\n"
        "    pass\n"
        % (PROJECT_DIR + os.sep, PROJECT_DIR + os.sep)
    )

sys.path.insert(0, STUB_DIR)
sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge import rpc  # noqa: E402
from uemcp_bridge.handlers import HandlerResult  # noqa: E402
from uemcp_bridge.server import BridgeServer  # noqa: E402


def _post(port, token):
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 41, "method": "test.never_runs", "params": {}}
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:%d/rpc" % port,
        data=payload,
        headers={"Content-Type": "application/json", "X-UEMCP-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body) if body else None
        except Exception:
            return exc.code, {"raw": body}


def main():
    failures = []
    executed = {"count": 0}

    def never_runs(server, params):
        executed["count"] += 1
        return HandlerResult({"executed": True})

    rpc.HANDLERS["test.never_runs"] = never_runs

    server = BridgeServer.instance()
    if not server.start():
        print("TIMEOUT_RESULT FAIL: bridge did not start")
        return 1

    try:
        dispatcher = server.dispatcher
        if dispatcher.__class__.__name__ != "GameThreadDispatcher":
            failures.append(
                "expected the real GameThreadDispatcher, got %s"
                % dispatcher.__class__.__name__
            )
        if server.settings.request_timeout_ms != 1000:
            failures.append(
                "requestTimeoutMs = %r, expected 1000" % server.settings.request_timeout_ms
            )

        started = time.monotonic()
        status, body = _post(server.port, server.token)
        elapsed = time.monotonic() - started

        error = (body or {}).get("error") or {}
        data = error.get("data") or {}
        details = data.get("details") or {}

        if status != 504:
            failures.append("HTTP status = %r, expected 504 (%r)" % (status, body))
        if error.get("code") != -32020:
            failures.append("jsonrpc error.code = %r, expected -32020" % error.get("code"))
        if data.get("errorCode") != "BRIDGE_TIMEOUT":
            failures.append("errorCode = %r, expected BRIDGE_TIMEOUT" % data.get("errorCode"))
        if data.get("retryable") is not True:
            failures.append("retryable = %r, expected true" % data.get("retryable"))
        if details.get("phase") != "game_thread":
            failures.append("details.phase = %r, expected game_thread" % details.get("phase"))
        if details.get("timeoutMs") != 1000:
            failures.append("details.timeoutMs = %r, expected 1000" % details.get("timeoutMs"))
        if "result" in (body or {}):
            failures.append("timeout response carried a result")
        if elapsed < 0.9:
            failures.append("returned after %.3fs, timeout was not really awaited" % elapsed)
        if executed["count"] != 0:
            failures.append("handler ran despite the timeout")

        # A tick that arrives after the timeout must drop the cancelled job
        # instead of running it on the game thread.
        dispatcher._on_tick(0.0)
        if executed["count"] != 0:
            failures.append("cancelled job executed on the next tick")
        if not dispatcher._queue.empty():
            failures.append("cancelled job is still queued after a tick")

        print(
            "TIMEOUT_HTTP status=%d code=%s errorCode=%s retryable=%s elapsed=%.3fs executed=%d"
            % (
                status,
                error.get("code"),
                data.get("errorCode"),
                data.get("retryable"),
                elapsed,
                executed["count"],
            )
        )
    finally:
        server.stop()
        rpc.HANDLERS.pop("test.never_runs", None)

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("TIMEOUT_RESULT FAIL")
        return 1
    print("TIMEOUT_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
