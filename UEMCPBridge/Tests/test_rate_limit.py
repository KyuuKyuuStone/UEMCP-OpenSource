"""Bridge-side global rate limit self-check (no editor required).

Covers architecture section 6.7 ("桥接端全局 30 req/s"):

1. token-bucket maths with a fake clock (burst, refill, retry-after, disable);
2. settings precedence (JSON file / environment / defaults, 0 disables);
3. the real HTTP path: requests over the limit get HTTP 429 +
   JSON-RPC -32012 + ``RATE_LIMITED`` + ``retryable:true`` and **never reach
   the dispatcher** (the gate runs before the job is queued);
4. ``/health`` is not rate limited and reports the limiter state.

Exit code 0 = PASS, 1 = FAIL.
"""

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

HOME_DIR = tempfile.mkdtemp(prefix="uemcp_rate_home_")
PROJECT_DIR = tempfile.mkdtemp(prefix="uemcp_rate_project_")
STUB_DIR = tempfile.mkdtemp(prefix="uemcp_rate_stub_")

os.environ["USERPROFILE"] = HOME_DIR
os.environ["HOME"] = HOME_DIR
for _name in (
    "UEMCP_BRIDGE_PORT",
    "UEMCP_BRIDGE_TOKEN_FILE",
    "UEMCP_BRIDGE_RATE_LIMIT_ENABLED",
    "UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND",
    "UEMCP_BRIDGE_RATE_LIMIT_BURST",
    "UEMCP_BRIDGE_ALLOW_WRITE",
    "UEMCP_BRIDGE_ALLOW_CONSOLE",
    "UEMCP_BRIDGE_ALLOW_EXEC",
):
    os.environ.pop(_name, None)
os.environ["UEMCP_BRIDGE_PORT"] = "0"

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
from uemcp_bridge.ratelimit import RateLimiter  # noqa: E402
from uemcp_bridge.server import BridgeServer  # noqa: E402
from uemcp_bridge.settings import Settings  # noqa: E402


class _Clock(object):
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def _check_bucket(failures):
    clock = _Clock()
    limiter = RateLimiter(per_second=1.0, burst=3, clock=clock)
    allowed = [limiter.try_acquire() for _ in range(3)]
    if not all(item[0] for item in allowed):
        failures.append("burst of 3 did not allow the first 3 requests: %r" % (allowed,))
    denied, retry_after = limiter.try_acquire()
    if denied:
        failures.append("4th request was allowed with an empty bucket")
    if abs(retry_after - 1.0) > 1e-6:
        failures.append("retry_after = %r, expected 1.0" % (retry_after,))
    clock.advance(0.5)
    denied, retry_after = limiter.try_acquire()
    if denied:
        failures.append("request allowed before a full token existed")
    if abs(retry_after - 0.5) > 1e-6:
        failures.append("retry_after = %r, expected 0.5" % (retry_after,))
    clock.advance(0.6)
    allowed, _ = limiter.try_acquire()
    if not allowed:
        failures.append("refilled bucket still rejected the request")
    print(
        "TOKEN_BUCKET burst=3 rate=1/s accepted=%d rejected=%d available=%s"
        % (limiter.accepted, limiter.rejected, limiter.snapshot()["available"])
    )

    disabled = RateLimiter(per_second=1.0, burst=1, enabled=False)
    if not all(disabled.try_acquire()[0] for _ in range(50)):
        failures.append("disabled limiter rejected a request")
    zero = RateLimiter(per_second=0, burst=1)
    if zero.enabled or not zero.try_acquire()[0]:
        failures.append("per_second=0 did not disable the limiter")
    print("LIMITER_DISABLE ok")


def _check_settings(failures):
    settings = Settings.load(PROJECT_DIR)
    if (settings.rate_limit_per_second, settings.rate_limit_burst) != (30, 30):
        failures.append(
            "default rate settings = (%r, %r), expected (30, 30)"
            % (settings.rate_limit_per_second, settings.rate_limit_burst)
        )
    if not settings.rate_limit_enabled:
        failures.append("rate limit is disabled by default")

    os.environ["UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND"] = "7"
    os.environ.pop("UEMCP_BRIDGE_RATE_LIMIT_BURST", None)
    settings = Settings.load(PROJECT_DIR)
    if settings.rate_limit_per_second != 7:
        failures.append("env rateLimitPerSecond ignored: %r" % settings.rate_limit_per_second)
    if settings.rate_limit_burst != 7:
        failures.append(
            "burst should default to the configured rate, got %r"
            % settings.rate_limit_burst
        )

    os.environ["UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND"] = "0"
    settings = Settings.load(PROJECT_DIR)
    if RateLimiter.from_settings(settings).enabled:
        failures.append("rateLimitPerSecond=0 did not disable the limiter")
    os.environ.pop("UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND", None)

    settings_path = os.path.join(PROJECT_DIR, "Saved", "UEMCP", "bridge-settings.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump({"rateLimitPerSecond": 12, "rateLimitBurst": 4}, handle)
    settings = Settings.load(PROJECT_DIR)
    if (settings.rate_limit_per_second, settings.rate_limit_burst) != (12, 4):
        failures.append(
            "JSON settings ignored: (%r, %r)"
            % (settings.rate_limit_per_second, settings.rate_limit_burst)
        )
    os.unlink(settings_path)
    print("SETTINGS_PRECEDENCE ok")


class _CountingDispatcher(object):
    def __init__(self):
        self.calls = 0

    def call(self, fn, timeout_s):
        self.calls += 1
        return fn()

    def shutdown(self):
        pass


def _rpc(port, token, request_id=1, method="test.noop"):
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {}}
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:%d/rpc" % port,
        data=payload,
        headers={"Content-Type": "application/json", "X-UEMCP-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body) if body else None
        except Exception:
            return exc.code, {"raw": body}


def _health(port):
    with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _check_http(failures):
    # A method that is routed through the dispatcher (not bridge.ping) so the
    # test can prove rejected requests never reach the queue.
    rpc.HANDLERS["test.noop"] = lambda server, params: HandlerResult({"noop": True})
    dispatcher = _CountingDispatcher()
    server = BridgeServer.instance()

    os.environ["UEMCP_BRIDGE_RATE_LIMIT_PER_SECOND"] = "1"
    os.environ["UEMCP_BRIDGE_RATE_LIMIT_BURST"] = "3"
    if not server.start(dispatcher=dispatcher):
        failures.append("bridge did not start")
        return

    try:
        if not server.rate_limiter or not server.rate_limiter.enabled:
            failures.append("limiter was not created on start")
            return
        if (server.rate_limiter.per_second, server.rate_limiter.burst) != (1.0, 3.0):
            failures.append(
                "limiter built from wrong settings: (%r, %r)"
                % (server.rate_limiter.per_second, server.rate_limiter.burst)
            )

        statuses = []
        rate_limited = []
        for index in range(12):
            status, body = _rpc(server.port, server.token, request_id=index + 1)
            statuses.append(status)
            if status == 429:
                rate_limited.append(body)
        allowed_count = statuses.count(200)
        if allowed_count != 3:
            failures.append(
                "expected exactly 3 allowed requests (burst=3), got %d: %r"
                % (allowed_count, statuses)
            )
        if len(rate_limited) != 9:
            failures.append("expected 9 rate-limited responses, got %d" % len(rate_limited))
        if dispatcher.calls != allowed_count:
            failures.append(
                "rejected requests reached the dispatcher: dispatcher=%d allowed=%d"
                % (dispatcher.calls, allowed_count)
            )

        for body in rate_limited:
            error = (body or {}).get("error") or {}
            data = error.get("data") or {}
            if error.get("code") != -32012:
                failures.append("RATE_LIMITED jsonrpc code = %r" % error.get("code"))
                break
            if data.get("errorCode") != "RATE_LIMITED":
                failures.append("RATE_LIMITED errorCode = %r" % data.get("errorCode"))
                break
            if data.get("retryable") is not True:
                failures.append("RATE_LIMITED retryable = %r" % data.get("retryable"))
                break
            details = data.get("details") or {}
            if details.get("gate") != "bridge.rateLimit":
                failures.append("RATE_LIMITED details.gate = %r" % details.get("gate"))
                break
            if "retryAfterMs" not in details:
                failures.append("RATE_LIMITED details.retryAfterMs missing")
                break
            if "result" in (body or {}):
                failures.append("rate-limited response carried a result")
                break
        print(
            "HTTP_LIMIT statuses=%r dispatcher_calls=%d" % (statuses, dispatcher.calls)
        )

        # /health must stay reachable (discovery polls it) and advertise the
        # limiter state.
        for _ in range(5):
            status, payload = _health(server.port)
            if status != 200 or payload.get("app") != "uemcp-bridge":
                failures.append("/health failed while rate limited: %r" % status)
                break
        rate_limit = payload.get("rateLimit") or {}
        if (
            rate_limit.get("enabled") is not True
            or rate_limit.get("perSecond") != 1.0
            or rate_limit.get("burst") != 3.0
        ):
            failures.append("/health rateLimit payload = %r" % (rate_limit,))
        print("HEALTH_RATE_LIMIT %r" % (rate_limit,))
    finally:
        server.stop()

    # Turning the limiter off must restore unlimited traffic.
    os.environ["UEMCP_BRIDGE_RATE_LIMIT_ENABLED"] = "false"
    dispatcher = _CountingDispatcher()
    if not server.start(dispatcher=dispatcher):
        failures.append("bridge did not restart")
        return
    try:
        statuses = [_rpc(server.port, server.token, request_id=i)[0] for i in range(8)]
        if statuses.count(200) != 8:
            failures.append("disabled limiter still rejected: %r" % statuses)
        if dispatcher.calls != 8:
            failures.append("disabled limiter dispatcher calls = %d" % dispatcher.calls)
        print("HTTP_LIMIT_DISABLED statuses=%r" % (statuses,))
    finally:
        server.stop()
        os.environ.pop("UEMCP_BRIDGE_RATE_LIMIT_ENABLED", None)
        rpc.HANDLERS.pop("test.noop", None)


def main():
    failures = []
    _check_bucket(failures)
    _check_settings(failures)
    _check_http(failures)
    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("RATE_LIMIT_RESULT FAIL")
        return 1
    print("RATE_LIMIT_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
