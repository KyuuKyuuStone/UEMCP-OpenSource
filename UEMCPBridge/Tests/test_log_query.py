"""``log.query`` self-check (no editor required).

Covers: newest project log selection, pattern/level/since filters, paging and
truncation, invalid regex/length, and the realpath escape guard.
"""

import os
import shutil
import sys
import tempfile
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

PROJECT_DIR = tempfile.mkdtemp(prefix="uemcp_log_project_")
EMPTY_PROJECT = tempfile.mkdtemp(prefix="uemcp_log_empty_")
LOGS_DIR = os.path.join(PROJECT_DIR, "Saved", "Logs")
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_LINES = [
    "[2026.10.30-05.00.00:000][  0]LogPluginManager: Warning: The same version (v1) of plugin exists - second location will be ignored.",
    "[2026.10.30-05.00.01:000][  0]LogInit: Display: engine boot",
    "[2026.10.30-05.00.02:000][  0]LogTemp: Error: boom",
    "[2026.10.30-05.00.03:000][  0]LogTemp: Log: plain line",
    "[2026.10.30-05.00.04:000][  0]LogTemp: Log: " + ("x" * 600),
]
with open(os.path.join(LOGS_DIR, "UEMCP_TEXT_57.log"), "w", encoding="utf-8") as handle:
    handle.write("\n".join(LOG_LINES) + "\n")

unreal_stub = types.ModuleType("unreal")


class Paths(object):
    project = PROJECT_DIR

    @staticmethod
    def project_dir():
        return Paths.project


unreal_stub.Paths = Paths
sys.modules["unreal"] = unreal_stub
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge.errors import RpcError  # noqa: E402
from uemcp_bridge.handlers import logs  # noqa: E402


class _Server(object):
    capabilities = {}


def query(params):
    return logs.handle(_Server(), params).data


def _expect(code, fn):
    try:
        fn()
    except RpcError as exc:
        assert exc.code == code, "expected %s, got %s (%s)" % (code, exc.code, exc.message)
        return exc
    raise AssertionError("expected %s, nothing raised" % code)


def main():
    failures = []

    def check(name, fn):
        try:
            fn()
            print("PASS %s" % name)
        except Exception as exc:  # noqa: BLE001
            failures.append("%s: %s" % (name, exc))
            print("FAIL %s: %s" % (name, exc))

    def default_log_and_path():
        data = query({})
        assert data["logPath"].endswith("UEMCP_TEXT_57.log"), data["logPath"]
        assert os.path.isabs(data["logPath"]), data["logPath"]
        assert data["scannedLines"] == 5, data
        assert data["matched"] == 5, data
        assert data["truncated"] is False, data
        assert len(data["lines"]) == 5, data

    def pattern_filter():
        data = query({"pattern": "second location"})
        assert data["matched"] == 1, data
        assert "second location" in data["lines"][0]["text"], data

    def level_filter():
        data = query({"levels": ["Error"]})
        assert data["matched"] == 1, data
        assert data["lines"][0]["level"] == "Error", data

    def since_filter():
        data = query({"since": "2026-10-30T05:00:03"})
        assert data["matched"] == 2, data

    def paging():
        data = query({"limit": 2, "offset": 1})
        assert len(data["lines"]) == 2, data
        assert data["lines"][0]["lineNo"] == 2, data
        assert data["truncated"] is True, data

    def text_truncation():
        data = query({"pattern": "^\\[2026\\.10\\.30-05\\.00\\.04"})
        assert data["matched"] == 1, data
        assert len(data["lines"][0]["text"]) == logs._MAX_TEXT, len(data["lines"][0]["text"])

    def invalid_regex():
        _expect("INVALID_ARGUMENT", lambda: query({"pattern": "("}))

    def pattern_too_long():
        _expect("INVALID_ARGUMENT", lambda: query({"pattern": "a" * 201}))

    def invalid_level():
        _expect("INVALID_ARGUMENT", lambda: query({"levels": ["Trace"]}))

    def escape_guard():
        outside = os.path.join(tempfile.mkdtemp(prefix="uemcp_outside_"), "x.log")
        with open(outside, "w", encoding="utf-8") as handle:
            handle.write("x")
        _expect("PERMISSION_DENIED", lambda: logs._safe_log_path(outside, LOGS_DIR))

    def missing_log():
        Paths.project = EMPTY_PROJECT
        try:
            _expect("NOT_FOUND", lambda: query({}))
        finally:
            Paths.project = PROJECT_DIR

    check("default_log_and_path", default_log_and_path)
    check("pattern_filter", pattern_filter)
    check("level_filter", level_filter)
    check("since_filter", since_filter)
    check("paging", paging)
    check("text_truncation", text_truncation)
    check("invalid_regex", invalid_regex)
    check("pattern_too_long", pattern_too_long)
    check("invalid_level", invalid_level)
    check("escape_guard", escape_guard)
    check("missing_log", missing_log)

    shutil.rmtree(PROJECT_DIR, ignore_errors=True)
    shutil.rmtree(EMPTY_PROJECT, ignore_errors=True)

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("LOG_QUERY_RESULT FAIL")
        return 1
    print("LOG_QUERY_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
