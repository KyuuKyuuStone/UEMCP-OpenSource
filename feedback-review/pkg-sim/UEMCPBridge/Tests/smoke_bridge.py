"""Headless smoke test for UEMCPBridge.

Run inside the editor's Python via the pythonscript commandlet:

    "C:\\Program Files\\Epic Games\\UE_5.4\\Engine\\Binaries\\Win64\\UnrealEditor-Cmd.exe" \
      "C:\\UE5_P\\5.4\\XQHCPP_54\\XQHCPP_54.uproject" \
      -run=pythonscript -script="<this file>"

The script starts the HTTP bridge with a synchronous dispatcher (commandlets
have no Slate tick), verifies ``/health``, ``/rpc bridge.ping`` and the token
gate, then keeps listening for ``SMOKE_HOLD_SECONDS`` (default 12) so an
external ``curl`` can hit it as well.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)
RESULT_PATH = os.path.join(PROJECT_DIR, "Saved", "UEMCP", "smoke_result.json")

from uemcp_bridge.dispatcher import SynchronousDispatcher  # noqa: E402
from uemcp_bridge.server import BridgeServer  # noqa: E402

HOLD_SECONDS = float(os.environ.get("SMOKE_HOLD_SECONDS", "12"))


def _request(url, method="GET", payload=None, token=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-UEMCP-Token"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else None
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed


def _write_result(payload):
    try:
        directory = os.path.dirname(RESULT_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(RESULT_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception as exc:
        print("SMOKE_RESULT_WRITE_FAILED: %s" % exc)


def main():
    server = BridgeServer.instance()
    ok = server.start(dispatcher=SynchronousDispatcher())
    if not ok:
        print("SMOKE_RESULT FAIL start=False")
        return 1

    base = "http://127.0.0.1:%d" % server.port
    print("SMOKE_READY port=%d pid=%d token_len=%d" % (server.port, os.getpid(), len(server.token)))

    failures = []
    try:
        status, health = _request(base + "/health", token=None)
        if status != 200 or not health or health.get("app") != "uemcp-bridge":
            failures.append("health: status=%s body=%s" % (status, health))
        else:
            print(
                "SMOKE_HEALTH ok app=%s ueVersion=%s port=%s pid=%s"
                % (
                    health.get("app"),
                    health.get("ueVersion"),
                    health.get("port"),
                    health.get("pid"),
                )
            )

        status, result = _request(
            base + "/rpc",
            method="POST",
            payload={"jsonrpc": "2.0", "id": 1, "method": "bridge.ping", "params": {}},
            token=server.token,
        )
        if status != 200 or not result or not result.get("result", {}).get("ok"):
            failures.append("ping: status=%s body=%s" % (status, result))
        else:
            print("SMOKE_PING ok result=%s" % json.dumps(result["result"]))

        status, result = _request(
            base + "/rpc",
            method="POST",
            payload={"jsonrpc": "2.0", "id": 2, "method": "bridge.ping", "params": {}},
            token="wrong-token",
        )
        if status != 401:
            failures.append("token gate: expected 401, got %s" % status)
        else:
            print("SMOKE_TOKEN_GATE ok status=401")

        status, result = _request(
            base + "/rpc",
            method="POST",
            payload={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "python.exec",
                "params": {"code": "1+1", "mode": "eval"},
            },
            token=server.token,
        )
        error_code = ((result or {}).get("error") or {}).get("data", {}).get("errorCode")
        if error_code != "EXEC_DISABLED":
            failures.append("exec gate: expected EXEC_DISABLED, got %s (%s)" % (error_code, result))
        else:
            print("SMOKE_EXEC_GATE ok status=%s errorCode=%s" % (status, error_code))

        status, result = _request(
            base + "/rpc",
            method="POST",
            payload={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "actor.edit",
                "params": {"operations": [{"op": "spawn", "class": "StaticMeshActor"}]},
            },
            token=server.token,
        )
        error_code = ((result or {}).get("error") or {}).get("data", {}).get("errorCode")
        if error_code != "PERMISSION_DENIED":
            failures.append("write gate: expected PERMISSION_DENIED, got %s (%s)" % (error_code, result))
        else:
            print("SMOKE_WRITE_GATE ok status=%s errorCode=%s" % (status, error_code))

        # Real-bridge argument validation path (C-1): must be -32602 / 400
        # with INVALID_ARGUMENT and details.issues preserved.
        status, result = _request(
            base + "/rpc",
            method="POST",
            payload={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "editor.status",
                "params": {"sections": ["not_a_section"]},
            },
            token=server.token,
        )
        error = (result or {}).get("error") or {}
        data = error.get("data") or {}
        issues = (data.get("details") or {}).get("issues")
        if (
            status != 400
            or error.get("code") != -32602
            or data.get("errorCode") != "INVALID_ARGUMENT"
            or not isinstance(issues, list)
            or not issues
        ):
            failures.append(
                "invalid argument: expected 400/-32602/INVALID_ARGUMENT+issues, got %s %s"
                % (status, result)
            )
        else:
            print(
                "SMOKE_INVALID_ARGUMENT ok status=%s code=%s errorCode=%s issues=%d"
                % (status, error.get("code"), data.get("errorCode"), len(issues))
            )
    finally:
        if failures:
            print("SMOKE_RESULT FAIL %s" % " | ".join(failures))
        else:
            print("SMOKE_RESULT PASS")
        _write_result(
            {
                "ok": not failures,
                "failures": failures,
                "port": server.port,
                "pid": os.getpid(),
                "ueVersion": server.ue_version,
                "projectDir": server.project_dir,
                "token": server.token,
                "holdSeconds": HOLD_SECONDS,
            }
        )
        print("SMOKE_HOLDING seconds=%s" % HOLD_SECONDS)
        try:
            time.sleep(HOLD_SECONDS)
        except Exception:
            pass
        server.stop()
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
