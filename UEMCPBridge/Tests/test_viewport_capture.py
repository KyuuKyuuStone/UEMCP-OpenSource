"""``viewport.capture`` self-check (no editor required).

Covers the 2026-10-30 capture enhancements:

* ``activateWindow`` success / foreground failure / non-Windows downgrade;
* absolute ``path`` + ``sha256``/``mtime``/``bytes``;
* PNG ``stats`` (uniqueColors / nonZeroRatio / isBlack);
* timeout grace: a file that lands shortly after the deadline returns
  ``partial: true`` instead of ``CAPTURE_TIMEOUT``;
* timeout without a file still returns ``CAPTURE_TIMEOUT`` with ``targetPath``.

Exit code 0 = PASS, 1 = FAIL.
"""

import os
import tempfile
import threading
import time
import types
import zlib

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

TMP = tempfile.mkdtemp(prefix="uemcp_viewport_")
SAVED = os.path.join(TMP, "Saved")
CONFIG = os.path.join(TMP, "Config")
os.makedirs(SAVED, exist_ok=True)
os.makedirs(CONFIG, exist_ok=True)

CALLS = []


def make_png(path, color, width=4, height=4):
    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))

    def chunk(tag, data):
        return (
            len(data).to_bytes(4, "big")
            + tag
            + data
            + (zlib.crc32(tag + data) & 0xFFFFFFFF).to_bytes(4, "big")
        )

    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, 2, 0, 0, 0])
    )
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as handle:
        handle.write(payload)


class FakeTask(object):
    def __init__(self, done):
        self._done = done

    def is_task_done(self):
        return self._done


class FakeAutomation(object):
    mode = "ok"
    color = (12, 34, 56)

    @staticmethod
    def take_high_res_screenshot(width, height, path, force_game_view=True, **kwargs):
        CALLS.append({"force_game_view": force_game_view, "path": path})
        if FakeAutomation.mode == "never":
            return FakeTask(False)
        make_png(path, FakeAutomation.color)
        return FakeTask(True)


class FakePaths(object):
    @staticmethod
    def project_saved_dir():
        return SAVED + os.sep

    @staticmethod
    def project_config_dir():
        return CONFIG + os.sep


class FakeSystemLibrary(object):
    @staticmethod
    def get_command_line():
        return ""


unreal_stub = types.ModuleType("unreal")
unreal_stub.Paths = FakePaths
unreal_stub.AutomationLibrary = FakeAutomation
unreal_stub.SystemLibrary = FakeSystemLibrary
sys_modules = None
import sys  # noqa: E402

sys.modules["unreal"] = unreal_stub
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge.errors import RpcError  # noqa: E402
from uemcp_bridge.handlers import viewport  # noqa: E402


class _Server(object):
    capabilities = {"screenshot": True}

    class settings(object):
        allow_write = True


def call(params, server=None):
    return viewport.handle(server or _Server(), params)


def drive(pending, limit=600):
    for _ in range(limit):
        outcome = pending.poll()
        if outcome is not None:
            return outcome.value
        time.sleep(0.01)
    raise AssertionError("pending job did not finish")


class FakeApi(object):
    """Deterministic replacement for the Win32 calls in _activate_with_api."""

    def __init__(self, hwnd=100, iconic=False, iconic_after=None, fg_before=None, fg_after=None, other_iconic=False):
        self.hwnd = hwnd
        self.pid = os.getpid()
        self.iconic = iconic
        self.iconic_after = iconic if iconic_after is None else iconic_after
        self.other_iconic = other_iconic
        self.fg_before = fg_before or {"hwnd": 0, "pid": 999}
        self.fg_after = fg_after if fg_after is not None else {"hwnd": hwnd, "pid": self.pid}
        self.calls = []
        self.foreground_calls = 0

    def foreground(self):
        self.foreground_calls += 1
        return self.fg_before if self.foreground_calls == 1 else self.fg_after

    def main(self, pid):
        return self.hwnd

    def class_name(self, hwnd):
        return "UnrealWindow"

    def show(self, hwnd, command):
        self.calls.append(("show", hwnd, command))
        self.iconic = self.iconic_after

    def set_foreground(self, hwnd):
        self.calls.append(("set_foreground", hwnd))

    def bring_to_top(self, hwnd):
        self.calls.append(("bring_to_top", hwnd))

    def is_iconic(self, hwnd):
        return self.iconic

    def sleep(self, seconds):
        self.calls.append(("sleep", seconds))

    def any_iconic(self):
        return self.other_iconic

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        return getattr(self, key)


def base_params(**extra):
    params = {
        "target": "level_viewport",
        "width": 64,
        "height": 64,
        "format": "png",
        "returnMode": "file",
        "timeoutMs": 1000,
    }
    params.update(extra)
    return params


def main():
    failures = []

    def check(name, fn):
        try:
            fn()
            print("PASS %s" % name)
        except Exception as exc:  # noqa: BLE001
            failures.append("%s: %s" % (name, exc))
            print("FAIL %s: %s" % (name, exc))

    def reset():
        CALLS[:] = []
        FakeAutomation.mode = "ok"
        FakeAutomation.color = (12, 34, 56)
        viewport._IS_WINDOWS = True
        viewport._activate_window = original_activate

    original_activate = viewport._activate_window

    def success_payload():
        reset()
        data = drive(call(base_params())).data
        assert data["isPath"] is True, data
        assert os.path.isabs(data["path"]), data["path"]
        assert data["path"].endswith(".png"), data
        assert data["bytes"] > 0, data
        assert len(data["sha256"]) == 64, data
        assert data["mtime"].endswith("Z"), data
        assert data["partial"] is False, data
        stats = data["stats"]
        assert stats["statsAvailable"] is True, stats
        assert stats["uniqueColors"] == 1, stats
        assert stats["nonZeroRatio"] == 1.0, stats
        assert stats["isBlack"] is False, stats
        assert CALLS and CALLS[0]["force_game_view"] is False, CALLS

    def black_stats():
        reset()
        FakeAutomation.color = (0, 0, 0)
        data = drive(call(base_params())).data
        assert data["stats"]["isBlack"] is True, data["stats"]
        assert data["stats"]["nonZeroRatio"] == 0.0, data["stats"]

    def activate_ok():
        reset()
        viewport._activate_window = lambda: {
            "ok": True,
            "alreadyForeground": False,
            "unsupported": False,
            "hwnd": 123,
            "foregroundPid": os.getpid(),
            "editorPid": os.getpid(),
        }
        data = drive(call(base_params(activateWindow=True))).data
        assert data["path"], data

    def activate_fail():
        reset()
        viewport._activate_window = lambda: {
            "ok": False,
            "alreadyForeground": False,
            "unsupported": False,
            "hwnd": 123,
            "foregroundPid": 99999,
            "editorPid": os.getpid(),
        }
        try:
            call(base_params(activateWindow=True))
        except RpcError as exc:
            assert exc.code == "EDITOR_UNSAFE_STATE", exc.code
            assert exc.details.get("reason") == "window_not_foreground", exc.details
        else:
            raise AssertionError("expected EDITOR_UNSAFE_STATE")
        assert CALLS == [], CALLS

    def activate_unsupported():
        reset()
        viewport._IS_WINDOWS = False
        result = drive(call(base_params(activateWindow=True)))
        assert result.data["path"], result.data
        assert any("ACTIVATE_WINDOW_UNSUPPORTED" in w for w in result.warnings), result.warnings

    def timeout_partial():
        reset()
        FakeAutomation.mode = "never"
        capture_dir = os.path.join(SAVED, "UEMCP", "captures")
        os.makedirs(capture_dir, exist_ok=True)
        original_capture_dir = viewport._capture_dir
        original_uuid = viewport.uuid.uuid4
        viewport._capture_dir = lambda: capture_dir
        viewport.uuid.uuid4 = lambda: types.SimpleNamespace(hex="feedface")
        try:
            pending = call(base_params(timeoutMs=1000))
            target = os.path.join(capture_dir, "feedface.png")

            def write_late():
                time.sleep(1.15)
                if not os.path.exists(target):
                    make_png(target, (1, 2, 3))

            thread = threading.Thread(target=write_late)
            thread.start()
            result = drive(pending, limit=1200)
            thread.join()
        finally:
            viewport._capture_dir = original_capture_dir
            viewport.uuid.uuid4 = original_uuid
        assert result.data["partial"] is True, result.data
        assert result.data["isPath"] is True, result.data
        assert any("CAPTURE_PARTIAL" in w for w in result.warnings), result.warnings

    def timeout_no_file():
        reset()
        FakeAutomation.mode = "never"
        try:
            drive(call(base_params(timeoutMs=1000)), limit=1000)
        except RpcError as exc:
            assert exc.code == "CAPTURE_TIMEOUT", exc.code
            assert exc.details.get("fileExists") is False, exc.details
            assert os.path.isabs(exc.details.get("targetPath", "")), exc.details
        else:
            raise AssertionError("expected CAPTURE_TIMEOUT")

    def invalid_activate():
        reset()
        try:
            call(base_params(activateWindow="yes"))
        except RpcError as exc:
            assert exc.code == "INVALID_ARGUMENT", exc.code
        else:
            raise AssertionError("expected INVALID_ARGUMENT")

    def unknown_key_still_rejected():
        reset()
        try:
            call(base_params(notAParam=True))
        except RpcError as exc:
            assert exc.code == "INVALID_ARGUMENT", exc.code
        else:
            raise AssertionError("expected INVALID_ARGUMENT")

    def activation_iconic_fails_fast():
        api = FakeApi(iconic=True, iconic_after=True)
        info = viewport._activate_with_api(api)
        assert info["ok"] is False, info
        assert info["isIconic"] is True, info
        assert ("sleep", 0.5) in api.calls, api.calls

    def activation_not_foreground_fails_fast():
        api = FakeApi(iconic=False, iconic_after=False, fg_after={"hwnd": 777, "pid": 4242})
        info = viewport._activate_with_api(api)
        assert info["ok"] is False, info
        assert info["isIconic"] is False, info
        assert info["foregroundPid"] == 4242, info

    def activation_restore_succeeds():
        api = FakeApi(iconic=True, iconic_after=False)
        info = viewport._activate_with_api(api)
        assert info["ok"] is True, info
        assert info["isIconic"] is False, info

    def activation_already_foreground():
        api = FakeApi(iconic=False, fg_before={"hwnd": 100, "pid": os.getpid()})
        info = viewport._activate_with_api(api)
        assert info["ok"] is True, info
        assert info["alreadyForeground"] is True, info
        assert not any(step[0] == "show" for step in api.calls), api.calls

    def activation_other_window_iconic_fails_fast():
        api = FakeApi(iconic=False, other_iconic=True, fg_before={"hwnd": 100, "pid": os.getpid()})
        info = viewport._activate_with_api(api)
        assert info["ok"] is False, info
        assert info["isIconic"] is True, info

    def handler_iconic_fast_fail():
        reset()
        viewport._activate_window = lambda: {
            "ok": False,
            "alreadyForeground": False,
            "unsupported": False,
            "hwnd": 123,
            "foregroundPid": 999,
            "editorPid": os.getpid(),
            "isIconic": True,
        }
        try:
            call(base_params(activateWindow=True, timeoutMs=20000))
        except RpcError as exc:
            assert exc.code == "EDITOR_UNSAFE_STATE", exc.code
            assert exc.details.get("reason") == "window_not_foreground", exc.details
            assert exc.details.get("isIconic") is True, exc.details
        else:
            raise AssertionError("expected EDITOR_UNSAFE_STATE")
        assert CALLS == [], CALLS

    check("success_payload", success_payload)
    check("black_stats", black_stats)
    check("activate_ok", activate_ok)
    check("activate_fail", activate_fail)
    check("activate_unsupported", activate_unsupported)
    check("activation_iconic_fails_fast", activation_iconic_fails_fast)
    check("activation_not_foreground_fails_fast", activation_not_foreground_fails_fast)
    check("activation_restore_succeeds", activation_restore_succeeds)
    check("activation_already_foreground", activation_already_foreground)
    check("activation_other_window_iconic_fails_fast", activation_other_window_iconic_fails_fast)
    check("handler_iconic_fast_fail", handler_iconic_fast_fail)
    check("timeout_partial", timeout_partial)
    check("timeout_no_file", timeout_no_file)
    check("invalid_activate", invalid_activate)
    check("unknown_key_still_rejected", unknown_key_still_rejected)

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("VIEWPORT_CAPTURE_RESULT FAIL")
        return 1
    print("VIEWPORT_CAPTURE_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
