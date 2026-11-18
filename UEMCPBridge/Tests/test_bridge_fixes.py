"""Batch-2 bridge fixes self-check (no editor required).

Covers: Pixel Streaming capture fast-fail + capabilities.pixelStreaming probe,
/health schemaVersion and the full 18-key payload, Settings.load source /
envOverrides presence semantics / policy_snapshot additions /
UEMCP_BRIDGE_SEARCH_TIMEOUT_MS, asset.search maxNodes validation + BFS seed
cap + budget truncation warnings + relationsTruncated + SEARCH_TIMEOUT
positive timeoutMs, and the request-level JSONL log (10 keys, sanitization,
HTTP-rejection coverage, 5 MiB-style rotation via a shrunk threshold).
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

HOME_DIR = tempfile.mkdtemp(prefix="uemcp_fixes_home_")
PROJECT_DIR = tempfile.mkdtemp(prefix="uemcp_fixes_proj_")
CONFIG_DIR = os.path.join(PROJECT_DIR, "Config")
os.makedirs(CONFIG_DIR, exist_ok=True)
os.environ["USERPROFILE"] = HOME_DIR
os.environ["HOME"] = HOME_DIR
for _key in list(os.environ):
    if _key.startswith("UEMCP_BRIDGE_"):
        os.environ.pop(_key)
os.environ["UEMCP_BRIDGE_PORT"] = "0"

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
        return CONFIG_DIR + os.sep


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
    @staticmethod
    def is_redirector(asset_data):
        return False


class _Name(object):
    def __init__(self, value):
        self.value = value


class _DependencyOptions(object):
    """hasattr() is always True; writes go through set_editor_property."""

    def __init__(self):
        self._props = {}

    def __getattr__(self, name):
        return False

    def set_editor_property(self, name, value):
        self._props[name] = value


_stub.Paths = _Paths
_stub.SystemLibrary = _SystemLibrary
_stub.AssetRegistryHelpers = _AssetRegistryHelpers
_stub.AssetRegistryDependencyOptions = _DependencyOptions
_stub.Name = _Name
_stub.register_slate_post_tick_callback = lambda fn: 1
_stub.unregister_slate_post_tick_callback = lambda handle: None
_stub.register_python_shutdown_callback = lambda fn: None
_stub.log = lambda message: None
_stub.log_error = lambda message: None
sys.modules["unreal"] = _stub

sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge import discovery, rpc  # noqa: E402
from uemcp_bridge import server as server_mod  # noqa: E402
from uemcp_bridge.dispatcher import SynchronousDispatcher  # noqa: E402
from uemcp_bridge.errors import RpcError  # noqa: E402
from uemcp_bridge.handlers import HandlerResult, assets, viewport  # noqa: E402
from uemcp_bridge.handlers.status import detect_capabilities  # noqa: E402
from uemcp_bridge.settings import Settings  # noqa: E402

_INI_PATH = os.path.join(CONFIG_DIR, "DefaultWebAPI.ini")


def _write_ini(text):
    with open(_INI_PATH, "w", encoding="utf-8") as handle:
        handle.write(text)


def check_pixel_streaming(failures):
    _write_ini("[/Script/WebAPI.WebAPISettings]\nDataChannelType = PixelStreaming\n")
    env = viewport._render_environment()
    if not env.get("pixelStreaming"):
        failures.append("ps: _render_environment did not detect PixelStreaming")
    caps = detect_capabilities()
    expected_keys = {
        "python", "screenshot", "blueprintRead", "blueprintNodeRead",
        "blueprintCompile", "animBlueprintEdit", "assetRegistry", "console",
        "pieControl", "pixelStreaming",
    }
    if set(caps) != expected_keys:
        failures.append("ps: capabilities keys=%r" % sorted(caps))
    if caps.get("pixelStreaming") is not True:
        failures.append("ps: capabilities.pixelStreaming=%r" % caps.get("pixelStreaming"))
    server = types.SimpleNamespace(
        capabilities={"screenshot": True},
        settings=types.SimpleNamespace(allow_write=True),
    )
    try:
        viewport.handle(server, {})
        failures.append("ps: capture under PixelStreaming did not fast-fail")
    except RpcError as exc:
        if exc.code != "CAPABILITY_UNAVAILABLE":
            failures.append("ps: code=%s" % exc.code)
        if exc.details.get("capability") != "screenshot":
            failures.append("ps: capability=%r" % exc.details.get("capability"))
        renderer = exc.details.get("renderer", {})
        if renderer.get("pixelStreaming") is not True:
            failures.append("ps: renderer=%r" % renderer)
        if not exc.details.get("suggestion"):
            failures.append("ps: suggestion missing")
    _write_ini("[/Script/WebAPI.WebAPISettings]\nDataChannelType = Default\n")
    if viewport._render_environment().get("pixelStreaming"):
        failures.append("ps: negative ini still detected as PixelStreaming")
    if detect_capabilities().get("pixelStreaming") is not False:
        failures.append("ps: negative capabilities.pixelStreaming not False")
    print("PIXEL_STREAMING fast_fail=CAPABILITY_UNAVAILABLE probe=True/False keys=10")


def check_health_schema(failures):
    dummy = types.SimpleNamespace(
        ue_version="0.0.0-test",
        port=18778,
        project_dir=PROJECT_DIR,
        project_file="test.uproject",
        started_at="1970-01-01T00:00:00Z",
        capabilities={},
        rate_limiter=None,
        settings=None,
    )
    payload = server_mod.health_payload(dummy)
    if discovery.SCHEMA_VERSION != 1:
        failures.append("health: SCHEMA_VERSION=%r" % discovery.SCHEMA_VERSION)
    if payload.get("schemaVersion") != discovery.SCHEMA_VERSION:
        failures.append("health: schemaVersion=%r" % payload.get("schemaVersion"))
    expected_keys = {
        "app", "schemaVersion", "ok", "ueVersion", "pluginVersion",
        "bridgeProtocol", "port", "pid", "instanceId", "buildHash", "buildTime",
        "sourcePath", "projectDir", "projectFile", "startedAt", "capabilities",
        "rateLimit", "policies",
    }
    if set(payload) != expected_keys:
        failures.append("health: keys=%r" % sorted(payload))
    print("HEALTH_SCHEMA schemaVersion=%s keys=%d" % (payload.get("schemaVersion"), len(payload)))


def check_settings_source(failures):
    saved_env = {k: v for k, v in os.environ.items() if k.startswith("UEMCP_BRIDGE_")}
    for key in saved_env:
        os.environ.pop(key)
    try:
        settings_dir = os.path.join(PROJECT_DIR, "Saved", "UEMCP")
        os.makedirs(settings_dir, exist_ok=True)
        settings_path = os.path.join(settings_dir, "bridge-settings.json")
        with open(settings_path, "w", encoding="utf-8") as handle:
            json.dump({"searchTimeoutMs": 21000}, handle)
        settings = Settings.load(PROJECT_DIR)
        if settings.source != str(settings_path):
            failures.append("settings: source=%r" % settings.source)
        if settings.search_timeout_ms != 21000:
            failures.append("settings: file searchTimeoutMs=%r" % settings.search_timeout_ms)
        policy = settings.policy_snapshot()
        if policy.get("source") != str(settings_path):
            failures.append("settings: policy.source=%r" % policy.get("source"))
        if "console" not in policy:
            failures.append("settings: policy.console missing")
        if policy.get("envOverrides") != []:
            failures.append("settings: envOverrides=%r, expected []" % policy.get("envOverrides"))
        os.environ["UEMCP_BRIDGE_SEARCH_TIMEOUT_MS"] = "23456"
        settings = Settings.load(PROJECT_DIR)
        if settings.search_timeout_ms != 23456:
            failures.append("settings: env searchTimeoutMs=%r" % settings.search_timeout_ms)
        if "UEMCP_BRIDGE_SEARCH_TIMEOUT_MS" not in settings.env_overrides:
            failures.append("settings: env_overrides=%r" % (settings.env_overrides,))
        os.environ["UEMCP_BRIDGE_ALLOW_WRITE"] = ""
        settings = Settings.load(PROJECT_DIR)
        if settings.allow_write is not False:
            failures.append("settings: empty env allow_write=%r" % settings.allow_write)
        if "UEMCP_BRIDGE_ALLOW_WRITE" not in settings.env_overrides:
            failures.append("settings: presence semantics lost: %r" % (settings.env_overrides,))
        empty_dir = tempfile.mkdtemp(prefix="uemcp_fixes_empty_")
        settings = Settings.load(empty_dir)
        if settings.source != "defaults":
            failures.append("settings: defaults source=%r" % settings.source)
        print("SETTINGS_SOURCE file/env/presence/defaults ok envOverrides=recorded")
    finally:
        for key in list(os.environ):
            if key.startswith("UEMCP_BRIDGE_"):
                os.environ.pop(key)
        os.environ.update(saved_env)


class _FakeAsset(object):
    def __init__(self, name):
        self.package_name = "/Game/" + name
        self.asset_name = name
        self.asset_class_path = types.SimpleNamespace(
            package_name="/Script/Engine", asset_name="StaticMesh"
        )

    def get_tag_value(self, tag):
        return None


class _FakeRegistry(object):
    def __init__(self, assets, deps):
        self._assets = assets
        self._deps = deps

    def get_assets_by_path(self, path, recursive):
        return list(self._assets)

    def get_dependencies(self, package_name, options):
        return list(self._deps.get(str(package_name), []))

    def get_referencers(self, package_name, options):
        return []


def check_bfs_limits(failures):
    big_assets = [_FakeAsset("A%02d" % i) for i in range(60)]
    big_deps = {
        asset.package_name: ["/Game/Dep/%s_%d" % (asset.asset_name, j) for j in range(3)]
        for asset in big_assets
    }
    small_assets = [_FakeAsset("B%d" % i) for i in range(3)]
    small_deps = {
        asset.package_name: ["/Game/Dep/%s_%d" % (asset.asset_name, j) for j in range(2)]
        for asset in small_assets
    }
    server = types.SimpleNamespace(settings=types.SimpleNamespace(search_timeout_ms=20000))
    original_registry = assets._registry
    try:
        assets._registry = lambda: _FakeRegistry(big_assets, big_deps)
        outcome = assets.handle(
            server,
            {"includeDependencies": True, "dependencyDepth": 1, "maxNodes": 2},
        )
        if outcome.data.get("total") != 60:
            failures.append("bfs: total=%r" % outcome.data.get("total"))
        if outcome.data.get("relationsTruncated") is not True:
            failures.append("bfs: relationsTruncated=%r" % outcome.data.get("relationsTruncated"))
        if not any(w.startswith("BFS_SEEDS_TRUNCATED") for w in outcome.warnings):
            failures.append("bfs: seed-cap warning missing: %r" % outcome.warnings)
        if not any(w.startswith("BFS_BUDGET_TRUNCATED") for w in outcome.warnings):
            failures.append("bfs: budget warning missing: %r" % outcome.warnings)
        for bad in (0, 10001, "abc"):
            try:
                assets.handle(server, {"maxNodes": bad})
                failures.append("bfs: maxNodes=%r accepted" % bad)
            except RpcError as exc:
                if exc.code != "INVALID_ARGUMENT":
                    failures.append("bfs: maxNodes=%r code=%s" % (bad, exc.code))
        assets._registry = lambda: _FakeRegistry(small_assets, small_deps)
        outcome = assets.handle(server, {"includeDependencies": True, "dependencyDepth": 1})
        if outcome.data.get("relationsTruncated") is not False:
            failures.append("bfs: small graph relationsTruncated=%r" % outcome.data.get("relationsTruncated"))
        if len(outcome.data.get("dependencies", {})) != 3:
            failures.append("bfs: small dependencies=%r" % outcome.data.get("dependencies"))
        class _CountingRegistry(_FakeRegistry):
            """Counts expansions: the seed cap is only observable via call count,
            because ``_bfs`` returns the relation dict (empty with no deps)."""

            def __init__(self):
                _FakeRegistry.__init__(self, [], {})
                self.calls = []

            def get_dependencies(self, package_name, options):
                self.calls.append(str(package_name))
                return _FakeRegistry.get_dependencies(self, package_name, options)

        counter = _CountingRegistry()
        seeds = ["/Game/S%02d" % i for i in range(51)]
        warnings = []
        assets._bfs(
            counter, None, seeds, 1, True, False,
            time.monotonic() + 60.0, warnings,
        )
        if len(counter.calls) != 50:
            failures.append("bfs: direct seed cap expanded=%d" % len(counter.calls))
        if seeds[50] in counter.calls:
            failures.append("bfs: seed cap expanded the 51st seed: %r" % (seeds[50],))
        if not any(w.startswith("BFS_SEEDS_TRUNCATED") for w in warnings):
            failures.append("bfs: direct seed-cap warning missing")
        try:
            assets._bfs(
                _FakeRegistry([], {}), None, ["/Game/X"], 1, True, False,
                time.monotonic() - 1.0, [], timeout_ms=20000,
            )
            failures.append("bfs: expired deadline did not raise")
        except RpcError as exc:
            if exc.code != "SEARCH_TIMEOUT":
                failures.append("bfs: deadline code=%s" % exc.code)
            if exc.details.get("timeoutMs") != 20000:
                failures.append("bfs: deadline timeoutMs=%r" % exc.details.get("timeoutMs"))
        print("BFS_LIMITS seed_cap=50 budget=maxNodes relationsTruncated=True/False timeoutMs=20000")

        # nextOffset (item 8 / IMP-002): explicit cursor on truncated pages, null on the last page.
        first = assets.handle(server, {"limit": 2, "offset": 0}).data
        if (first.get("total"), first.get("returned")) != (3, 2):
            failures.append("nextOffset: first page total/returned=%r/%r" % (first.get("total"), first.get("returned")))
        if first.get("truncated") is not True:
            failures.append("nextOffset: first page truncated=%r" % first.get("truncated"))
        if first.get("nextOffset") != 2:
            failures.append("nextOffset: first page nextOffset=%r" % first.get("nextOffset"))
        last = assets.handle(server, {"limit": 2, "offset": first.get("nextOffset") or 0}).data
        if (last.get("returned"), last.get("truncated")) != (1, False):
            failures.append("nextOffset: last page returned/truncated=%r/%r" % (last.get("returned"), last.get("truncated")))
        if "nextOffset" not in last or last.get("nextOffset") is not None:
            failures.append("nextOffset: last page nextOffset=%r (want explicit null)" % last.get("nextOffset"))
        print("ASSET_NEXT_OFFSET first=2 last=None")
    finally:
        assets._registry = original_registry


def _rpc(port, token, method="test.logprobe", params=None, request_id=1, with_token=True):
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


def check_request_log(failures):
    rpc.HANDLERS["test.logprobe"] = lambda server, params: HandlerResult({"probe": True})
    os.environ["UEMCP_BRIDGE_RATE_LIMIT_ENABLED"] = "false"
    server = server_mod.BridgeServer.instance()
    log_path = None
    try:
        if not server.start(dispatcher=SynchronousDispatcher()):
            failures.append("reqlog: start failed")
            return
        log_path = server.request_log_path
        if not log_path:
            failures.append("reqlog: request_log_path not wired")
            return
        status1, _ = _rpc(
            server.port, server.token,
            params={"code": "SECRET_CODE_MARKER"}, request_id=31,
        )
        status2, _ = _rpc(server.port, server.token, method="bridge.ping", request_id=32)
        status3, _ = _rpc(server.port, server.token, method="no.such.method", request_id=33)
        status4, _ = _rpc(server.port, server.token, request_id=34, with_token=False)
        if status1 != 200 or status2 != 200 or status4 != 401:
            failures.append(
                "reqlog: statuses=%r" % [status1, status2, status3, status4]
            )
        # The 401 rejection response is written to the socket before the server
        # thread appends its audit record, so poll briefly instead of reading once.
        records = []
        raw = ""
        read_deadline = time.monotonic() + 5.0
        while time.monotonic() < read_deadline:
            try:
                with open(log_path, "r", encoding="utf-8") as handle:
                    raw = handle.read()
            except OSError:
                raw = ""
            records = [json.loads(line) for line in raw.splitlines() if line.strip()]
            if len(records) >= 4:
                break
            time.sleep(0.02)
        if len(records) != 4:
            failures.append("reqlog: records=%d, expected 4" % len(records))
            return
        expected_keys = {
            "ts", "requestId", "method", "ok", "errorCode", "httpStatus",
            "durationMs", "queuedMs", "origin", "stage",
        }
        for index, record in enumerate(records):
            if set(record) != expected_keys:
                failures.append("reqlog[%d]: keys=%r" % (index, sorted(record)))
        first, second, third, fourth = records
        if first.get("ok") is not True or first.get("errorCode") is not None:
            failures.append("reqlog: success record=%r" % first)
        if first.get("httpStatus") != 200 or first.get("queuedMs") != 0:
            failures.append("reqlog: success status/queuedMs=%r" % first)
        if first.get("requestId") != "31" or first.get("method") != "test.logprobe":
            failures.append("reqlog: success id/method=%r" % first)
        if second.get("queuedMs") is not None:
            failures.append("reqlog: ping queuedMs=%r, expected None" % second.get("queuedMs"))
        if third.get("ok") is not False or third.get("errorCode") != "METHOD_NOT_FOUND":
            failures.append("reqlog: envelope record=%r" % third)
        if third.get("origin") != "caller" or third.get("stage") != "dispatch":
            failures.append("reqlog: envelope origin/stage=%r" % third)
        if third.get("httpStatus") != status3:
            failures.append("reqlog: envelope httpStatus=%r vs %r" % (third.get("httpStatus"), status3))
        if fourth.get("errorCode") != "unauthorized" or fourth.get("httpStatus") != 401:
            failures.append("reqlog: rejection record=%r" % fourth)
        if fourth.get("origin") != "caller" or fourth.get("stage") != "http":
            failures.append("reqlog: rejection origin/stage=%r" % fourth)
        for banned in ("SECRET_CODE_MARKER", server.token, '"params"', '"message"', '"code"'):
            if banned in raw:
                failures.append("reqlog: banned content leaked: %r" % banned[:24])
        server.stop()
        # Rotation: shrink the threshold so the existing file must rotate.
        original_max = server_mod._RPC_LOG_MAX_BYTES
        server_mod._RPC_LOG_MAX_BYTES = 64
        try:
            if not server.start(dispatcher=SynchronousDispatcher()):
                failures.append("reqlog: restart failed")
                return
            for index in range(3):
                _rpc(server.port, server.token, request_id=40 + index)
            if not os.path.isfile(log_path + ".1"):
                failures.append("reqlog: rotation file .1 missing")
        finally:
            server_mod._RPC_LOG_MAX_BYTES = original_max
        print("REQUEST_LOG records=4 keys=10 sanitized=ok rotation=ok")
    finally:
        server.stop()
        rpc.HANDLERS.pop("test.logprobe", None)
        os.environ.pop("UEMCP_BRIDGE_RATE_LIMIT_ENABLED", None)


def main():
    failures = []
    check_pixel_streaming(failures)
    check_health_schema(failures)
    check_settings_source(failures)
    check_bfs_limits(failures)
    try:
        check_request_log(failures)
    finally:
        for key in list(os.environ):
            if key.startswith("UEMCP_BRIDGE_"):
                os.environ.pop(key)
    for item in failures:
        print("FAIL: %s" % item)
    if failures:
        print("BRIDGE_FIXES_RESULT FAIL (%d)" % len(failures))
        return 1
    print("BRIDGE_FIXES_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
