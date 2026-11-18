"""Bridge HTTP server (architecture doc section 2.3 / 2.4 / 10.3).

Endpoints (loopback only):

* ``GET  /health`` - discovery / liveness
* ``POST /rpc``    - JSON-RPC 2.0 internal channel (X-UEMCP-Token required)
* ``GET  /events`` - optional SSE heartbeat (token required)
"""

import atexit
import datetime
import hashlib
import json
import os
import socket
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    import unreal  # type: ignore
except Exception:  # pragma: no cover - only absent outside the editor
    unreal = None

from . import discovery, security
from .dispatcher import DispatcherBusy, DispatcherTimeout, GameThreadDispatcher
from .errors import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    PARSE_ERROR,
    RpcError,
)
from .ratelimit import RateLimiter
from .rpc import handle_request
from .settings import (
    BRIDGE_PROTOCOL,
    FALLBACK_PORTS,
    PLUGIN_VERSION,
    Settings,
)
from .handlers.status import detect_capabilities

MAX_BODY_BYTES = 8 * 1024 * 1024

# Plugin root: <Plugin>/Content/Python/uemcp_bridge/server.py -> <Plugin>
_PLUGIN_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
# Stable for the lifetime of this editor process (diagnostics only).
_INSTANCE_ID = uuid.uuid4().hex
_BUILD_INFO = {}


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_hash():
    """Hash of every plugin Python file, computed once per process.

    Files are hashed individually, sorted by relative path, then the joined
    ``path:sha256`` lines are hashed again.  Editing any plugin source file
    changes ``buildHash`` even when ``pluginVersion`` stays the same.
    """
    if "hash" in _BUILD_INFO:
        return _BUILD_INFO["hash"]
    python_dir = os.path.join(_PLUGIN_ROOT, "Content", "Python")
    entries = []
    for root, dirs, files in os.walk(python_dir):
        dirs[:] = sorted(name for name in dirs if name != "__pycache__")
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            relative = os.path.relpath(path, python_dir).replace(os.sep, "/")
            try:
                entries.append("%s:%s" % (relative, _sha256_file(path)))
            except OSError:
                continue
    digest = hashlib.sha256("\n".join(sorted(entries)).encode("utf-8")).hexdigest()
    _BUILD_INFO["hash"] = digest
    return digest


def _file_mtime_iso(path):
    return (
        datetime.datetime.fromtimestamp(
            os.path.getmtime(path), datetime.timezone.utc
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def _build_time():
    if "time" in _BUILD_INFO:
        return _BUILD_INFO["time"]
    candidates = []
    try:
        candidates.extend(
            os.path.join(_PLUGIN_ROOT, name)
            for name in sorted(os.listdir(_PLUGIN_ROOT))
            if name.endswith(".uplugin")
        )
    except OSError:
        pass
    candidates.append(os.path.join(_PLUGIN_ROOT, "Content", "Python", "uemcp_bridge", "__init__.py"))
    value = None
    for path in candidates:
        try:
            if os.path.isfile(path):
                value = _file_mtime_iso(path)
                break
        except OSError:
            continue
    _BUILD_INFO["time"] = value
    return value


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _log(message):
    if unreal is not None:
        try:
            unreal.log("[UEMCP] %s" % message)
            return
        except Exception:
            pass
    print("[UEMCP] %s" % message)


def _log_error(message):
    if unreal is not None:
        try:
            unreal.log_error("[UEMCP] %s" % message)
            return
        except Exception:
            pass
    print("[UEMCP] ERROR: %s" % message)


class _BridgeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    # Do not share a bound port.  On Windows SO_REUSEADDR permits a second
    # bind to an address that is already listening, which would silently
    # defeat the 18778 -> 18779-18788 -> ephemeral fallback chain.
    allow_reuse_address = False

    def __init__(self, address, handler, bridge):
        self.bridge = bridge
        super(_BridgeHTTPServer, self).__init__(address, handler)

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            try:
                self.socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1
                )
            except OSError:
                # Best effort: bind conflicts still surface as OSError and
                # are handled by the fallback loop.
                pass
        super(_BridgeHTTPServer, self).server_bind()


class _RequestHandler(BaseHTTPRequestHandler):
    server_version = "UEMCPBridge/%s" % PLUGIN_VERSION
    protocol_version = "HTTP/1.1"

    # Never let http.server write its default stderr log lines.
    def log_message(self, fmt, *args):
        return

    # -- HTTP verb entry points -------------------------------------------

    def do_OPTIONS(self):
        self._send_json(405, {"error": "method_not_allowed"})

    def do_GET(self):
        bridge = self.server.bridge
        if not self._check_network():
            return
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, bridge.health_payload())
            return
        if path == "/events":
            if not self._check_token():
                return
            self._serve_events()
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        bridge = self.server.bridge
        if not self._check_network():
            return
        path = urlparse(self.path).path
        if path != "/rpc":
            self._send_json(404, {"error": "not_found"})
            return
        if not self._check_content_type():
            return
        if not self._check_token():
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self._send_rpc_error(
                None, "INVALID_REQUEST", "Content-Length is required",
                INVALID_REQUEST, 400,
            )
            return
        if length > MAX_BODY_BYTES:
            self._send_rpc_error(
                None, "PAYLOAD_TOO_LARGE", "Request body exceeds 8 MiB",
                -32011, 413,
            )
            return

        try:
            raw = self.rfile.read(length)
        except Exception:
            self._send_rpc_error(
                None, "INVALID_REQUEST", "Failed to read request body",
                INVALID_REQUEST, 400,
            )
            return

        try:
            request = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_rpc_error(None, "PARSE_ERROR", "Invalid JSON", PARSE_ERROR, 400)
            return

        if not isinstance(request, dict):
            self._send_rpc_error(
                None, "INVALID_REQUEST", "JSON-RPC envelope must be an object",
                INVALID_REQUEST, 400,
            )
            return

        request_id = request.get("id")
        if request.get("jsonrpc") != "2.0":
            self._send_rpc_error(
                request_id, "INVALID_REQUEST", "jsonrpc must be '2.0'",
                INVALID_REQUEST, 400,
            )
            return

        try:
            result = handle_request(bridge, request)
        except RpcError as exc:
            self._send_rpc_error(
                request_id,
                exc.code,
                exc.message,
                exc.rpc_code,
                exc.http_status,
                details=exc.details,
                retryable=exc.retryable,
            )
            return
        except DispatcherBusy as exc:
            self._send_rpc_error(
                request_id, "BRIDGE_BUSY", str(exc), -32002, 429,
                details={"gate": "game_thread.queue"}, retryable=True,
            )
            return
        except DispatcherTimeout as exc:
            self._send_rpc_error(
                request_id, "BRIDGE_TIMEOUT", str(exc), -32020, 504,
                details={"timeoutMs": bridge.settings.request_timeout_ms, "phase": "game_thread"},
                retryable=True,
            )
            return
        except Exception as exc:
            _log_error("rpc handler crashed: %s\n%s" % (exc, traceback.format_exc()))
            self._send_rpc_error(
                request_id, "INTERNAL", str(exc), INTERNAL_ERROR, 500,
                details={"reason": str(exc)},
            )
            return

        self._send_json(
            200, {"jsonrpc": "2.0", "id": request_id, "result": result}
        )

    # -- helpers ----------------------------------------------------------

    def _check_network(self):
        bridge = self.server.bridge
        if not security.is_loopback_peer(self.client_address[0]):
            self._send_json(403, {"error": "loopback_only"})
            return False
        port = self.server.server_address[1]
        if not security.valid_host(self.headers.get("Host"), port):
            self._send_json(421, {"error": "invalid_host"})
            return False
        if not security.valid_origin(self.headers.get("Origin"), port):
            self._send_json(403, {"error": "invalid_origin"})
            return False
        return True

    def _check_content_type(self):
        content_type = (self.headers.get("Content-Type") or "").lower()
        if "application/json" not in content_type:
            self._send_json(415, {"error": "content_type_must_be_json"})
            return False
        return True

    def _check_token(self):
        bridge = self.server.bridge
        supplied = self.headers.get("X-UEMCP-Token")
        if not security.token_matches(bridge.token, supplied):
            self._send_json(401, {"error": "unauthorized"})
            return False
        return True

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._write_response(status, "application/json; charset=utf-8", body)

    def _send_rpc_error(
        self, request_id, error_code, message, rpc_code, status, details=None, retryable=False
    ):
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": rpc_code,
                "message": message,
                "data": {
                    "errorCode": error_code,
                    "retryable": bool(retryable),
                    "details": details or {},
                },
            },
        }
        self._send_json(status, payload)

    def _write_response(self, status, content_type, body):
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_events(self):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while self.server.bridge.running:
                time.sleep(15)
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            return


class BridgeServer(object):
    """Process-wide bridge singleton."""

    _instance = None

    def __init__(self):
        self.settings = None
        self.token = None
        self.port = None
        self.running = False
        self.httpd = None
        self.thread = None
        self.dispatcher = None
        self.rate_limiter = None
        self.capabilities = {}
        self.plugin_version = PLUGIN_VERSION
        self.bridge_protocol = BRIDGE_PROTOCOL
        self.ue_version = "unknown"
        self.project_dir = ""
        self.project_file = ""
        self.started_at = None
        self._record = None
        self._shutdown_registered = False
        self._atexit_registered = False

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = BridgeServer()
        return cls._instance

    # -- lifecycle --------------------------------------------------------

    def start(self, dispatcher=None):
        if self.running:
            return True

        self.project_dir = self._project_dir()
        self.project_file = self._project_file()
        self.ue_version = self._engine_version()
        self.settings = Settings.load(self.project_dir)
        self.token = self.settings.token_override or security.generate_token()
        self.capabilities = detect_capabilities()
        self.rate_limiter = RateLimiter.from_settings(self.settings)
        self.dispatcher = dispatcher if dispatcher is not None else GameThreadDispatcher(
            self.settings.max_queue_size
        )

        httpd = None
        last_error = None
        ports = [self.settings.port]
        for candidate in FALLBACK_PORTS:
            if candidate not in ports:
                ports.append(candidate)
        if 0 not in ports:
            ports.append(0)

        for candidate in ports:
            try:
                httpd = _BridgeHTTPServer(("127.0.0.1", candidate), _RequestHandler, self)
                break
            except OSError as exc:
                last_error = exc
                continue

        if httpd is None:
            _log_error(
                "bridge_bind_failed host=127.0.0.1 ports=%s error=%s"
                % (ports, last_error)
            )
            return False

        self.httpd = httpd
        self.port = httpd.server_address[1]
        self.running = True
        self.started_at = _utc_now()

        self.thread = threading.Thread(
            target=httpd.serve_forever, name="UEMCPBridge", daemon=True
        )
        self.thread.start()

        self._record = {
            "schemaVersion": discovery.SCHEMA_VERSION,
            "pid": os.getpid(),
            "projectDir": discovery.normalize_project_dir(self.project_dir),
            "projectPath": discovery.normalize_project_dir(self.project_dir),
            "projectFile": self.project_file,
            "host": "127.0.0.1",
            "port": self.port,
            "url": "http://127.0.0.1:%d" % self.port,
            "token": self.token,
            "ueVersion": self.ue_version,
            "pluginVersion": PLUGIN_VERSION,
            "bridgeProtocol": BRIDGE_PROTOCOL,
            "capabilities": dict(self.capabilities),
            "startedAt": self.started_at,
        }
        # Remove discovery leftovers from processes that died without running
        # any shutdown callback (crash / force kill) before publishing ours.
        try:
            removed = discovery.cleanup_stale(self.project_dir)
            if removed:
                _log("stale_discovery_removed count=%d" % len(removed))
        except Exception as exc:
            _log_error("stale_discovery_cleanup_failed: %s" % exc)

        try:
            discovery.publish(self._record)
        except Exception as exc:
            _log_error("discovery_write_failed: %s" % exc)

        if not self._shutdown_registered and unreal is not None:
            try:
                unreal.register_python_shutdown_callback(self.stop)
                self._shutdown_registered = True
            except Exception:
                pass

        # atexit covers normal interpreter teardown even if the UE Python
        # shutdown callback never fires (RES-05).
        if not self._atexit_registered:
            try:
                atexit.register(self.stop)
                self._atexit_registered = True
            except Exception:
                pass

        _log(
            "bridge_started port=%d pid=%d project=%s"
            % (self.port, os.getpid(), self.project_dir)
        )
        return True

    def stop(self):
        if not self.running and self.httpd is None:
            return
        self.running = False
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
            except Exception:
                pass
            try:
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None
        if self._record is not None:
            try:
                discovery.remove(self._record)
            except Exception as exc:
                _log_error("discovery_cleanup_failed: %s" % exc)
                # Never leave an unmarked file behind: mark it stale so the
                # MCP server skips it deterministically.
                try:
                    discovery.mark_stale(self._record, "shutdown_cleanup_failed")
                except Exception:
                    pass
            self._record = None
        if self.dispatcher is not None:
            try:
                self.dispatcher.shutdown()
            except Exception:
                pass
            self.dispatcher = None
        self.rate_limiter = None
        _log("bridge_stopped pid=%d" % os.getpid())

    # -- info -------------------------------------------------------------

    def health_payload(self):
        return {
            "app": "uemcp-bridge",
            "ok": True,
            "ueVersion": self.ue_version,
            "pluginVersion": PLUGIN_VERSION,
            "bridgeProtocol": BRIDGE_PROTOCOL,
            "port": self.port,
            "pid": os.getpid(),
            "instanceId": _INSTANCE_ID,
            "buildHash": _build_hash(),
            "buildTime": _build_time(),
            "sourcePath": _PLUGIN_ROOT,
            "projectDir": discovery.normalize_project_dir(self.project_dir),
            "projectFile": self.project_file,
            "startedAt": self.started_at,
            "capabilities": dict(self.capabilities),
            "rateLimit": self.rate_limiter.snapshot() if self.rate_limiter else None,
            "policies": self.settings.policy_snapshot() if self.settings else {},
        }

    def _project_dir(self):
        if unreal is not None:
            try:
                # Paths.project_dir() may be relative to the engine binaries
                # (notably in commandlet mode); discovery requires a stable
                # normalized absolute path because it feeds the project hash.
                return os.path.abspath(str(unreal.Paths.project_dir()))
            except Exception:
                pass
        return os.getcwd()

    def _project_file(self):
        try:
            for entry in os.listdir(self.project_dir):
                if entry.lower().endswith(".uproject"):
                    return entry
        except Exception:
            pass
        return ""

    def _engine_version(self):
        if unreal is not None:
            try:
                return str(unreal.SystemLibrary.get_engine_version())
            except Exception:
                pass
        return "unknown"
