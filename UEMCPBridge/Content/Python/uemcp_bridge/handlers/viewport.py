"""``viewport.capture`` handler (architecture doc section 5.7).

The screenshot task is polled from successive Slate ticks via
:class:`Pending`; the game thread is never blocked waiting for the capture.
"""

import datetime
import glob
import hashlib
import os
import re
import shutil
import time
import uuid
import zlib

from ..errors import RpcError
from ..dispatcher import Done, Pending
from . import (
    HandlerResult,
    check_keys,
    editor_subsystem,
    ensure_not_pie,
    get_bool,
    get_enum,
    get_int,
    get_obj,
    get_unreal,
    is_pie_running,
    resolve_actor,
    rotator,
    selector,
    vec3,
)

_CAMERA_MODES = {"current", "actor", "explicit"}
_FORMATS = {"png", "jpeg"}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"

# Windows-only window activation support (tests patch this flag).
_IS_WINDOWS = os.name == "nt"
_PARTIAL_GRACE_SECONDS = 0.5
_STATS_MAX_ROWS = 96
_STATS_MAX_SAMPLES = 60000
_STATS_MAX_COLORS = 100000


def _capture_dir():
    unreal = get_unreal()
    saved_dir = str(unreal.Paths.project_saved_dir())
    return os.path.join(saved_dir, "UEMCP", "captures")


def _project_config_dir():
    try:
        return str(get_unreal().Paths.project_config_dir())
    except Exception:
        return ""


_PIXEL_STREAMING_RE = re.compile(
    r"(?im)^\s*DataChannelType\s*=\s*PixelStreaming\s*$"
)


def _render_environment():
    """Collect renderer clues used to explain capture failures.

    ``TakeHighResScreenshot(..., bForceGameView=True)`` synchronously toggles
    the level viewport into game view before scheduling the capture.  That
    toggle is the part that misbehaves on PixelStreaming projects (the game
    viewport there belongs to the streaming path), so the handler never forces
    game view for ``level_viewport`` captures.
    """
    env = {
        "pixelStreaming": False,
        "offscreen": False,
        "commandLine": "",
        "webApiConfig": "",
    }
    unreal = get_unreal()
    try:
        env["commandLine"] = str(unreal.SystemLibrary.get_command_line())
    except Exception:
        env["commandLine"] = ""
    lowered = env["commandLine"].lower()
    env["offscreen"] = ("-renderoffscreen" in lowered) or ("-nullrhi" in lowered)

    config_path = os.path.join(_project_config_dir(), "DefaultWebAPI.ini")
    env["webApiConfig"] = config_path
    try:
        if os.path.isfile(config_path):
            with open(config_path, "r", encoding="utf-8", errors="replace") as handle:
                env["pixelStreaming"] = bool(_PIXEL_STREAMING_RE.search(handle.read()))
    except Exception:
        pass
    return env


def _renderer_details(env):
    return {
        "pixelStreaming": env.get("pixelStreaming", False),
        "offscreen": env.get("offscreen", False),
        "commandLine": env.get("commandLine", "")[:400],
        "webApiConfig": env.get("webApiConfig", ""),
    }


def _foreground_window_info():
    """Return ``{"hwnd", "pid"}`` for the current foreground window."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"hwnd": 0, "pid": None}
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {"hwnd": int(hwnd), "pid": int(pid.value)}


def _main_window_for_pid(pid):
    """Best visible top-level window owned by ``pid``.

    Prefers the engine's main frame class (``UnrealWindow``) and, among
    candidates, the largest window.  Minimized windows report a tiny rect, so
    size alone is not enough when a tool window is also open.
    """
    import ctypes
    from ctypes import wintypes

    class _WindowPlacement(ctypes.Structure):
        _fields_ = [
            ("length", wintypes.UINT),
            ("flags", wintypes.UINT),
            ("showCmd", wintypes.UINT),
            ("ptMinPosition", wintypes.POINT),
            ("ptMaxPosition", wintypes.POINT),
            ("rcNormalPosition", wintypes.RECT),
        ]

    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        owner = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindowTextLengthW(hwnd) <= 0:
            return True
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        # Use the restored rectangle: minimized windows report a tiny current
        # rect, which would make the real main window look like a tool window.
        placement = _WindowPlacement()
        placement.length = ctypes.sizeof(_WindowPlacement)
        if not user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
            return True
        rect = placement.rcNormalPosition
        area = (rect.right - rect.left) * (rect.bottom - rect.top)
        is_main_class = 1 if class_name.value.lower().startswith("unrealwindow") else 0
        found.append((is_main_class, area, int(hwnd)))
        return True

    user32.EnumWindows(_callback, 0)
    if not found:
        return 0
    return max(found)[2]


def _win_api():
    """Thin wrapper over the Win32 calls used by ``_activate_window``.

    Kept injectable so the fast-fail decisions can be unit-tested without a
    real window (``_activate_with_api``).
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    def _foreground():
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "pid": None}
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return {"hwnd": int(hwnd), "pid": int(pid.value)}

    def _class_name(hwnd):
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, 256)
        return buffer.value

    def _any_iconic():
        """True when any visible engine main-frame window is minimized."""
        minimized = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _callback(hwnd, _lparam):
            owner = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value != os.getpid() or not user32.IsWindowVisible(hwnd):
                return True
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buffer, 256)
            if buffer.value.lower().startswith("unrealwindow") and user32.IsIconic(hwnd):
                minimized.append(int(hwnd))
                return False
            return True

        user32.EnumWindows(_callback, 0)
        return bool(minimized)

    return {
        "foreground": _foreground,
        "main": _main_window_for_pid,
        "class_name": _class_name,
        "any_iconic": _any_iconic,
        "show": lambda hwnd, command: user32.ShowWindow(hwnd, command),
        "set_foreground": lambda hwnd: user32.SetForegroundWindow(hwnd),
        "bring_to_top": lambda hwnd: user32.BringWindowToTop(hwnd),
        "is_iconic": lambda hwnd: bool(user32.IsIconic(hwnd)),
        "sleep": time.sleep,
    }


def _activate_window(api=None):
    """Restore + foreground the editor window and verify the result.

    Returns a dict with ``ok``/``alreadyForeground``/``unsupported`` plus the
    observed state (``hwnd``, ``foregroundPid``, ``isIconic``).  After the
    restore + settle there is a single re-check; if the window is still
    minimized or some other window owns the foreground, the caller raises
    ``EDITOR_UNSAFE_STATE`` immediately instead of letting the screenshot wait
    for its timeout.
    """
    info = {
        "ok": False,
        "alreadyForeground": False,
        "unsupported": False,
        "hwnd": 0,
        "foregroundPid": None,
        "editorPid": os.getpid(),
        "isIconic": False,
    }
    if not _IS_WINDOWS:
        info["unsupported"] = True
        return info
    return _activate_with_api(api or _win_api(), info)


def _activate_with_api(api, info=None):
    info = info or {
        "ok": False,
        "alreadyForeground": False,
        "unsupported": False,
        "hwnd": 0,
        "foregroundPid": None,
        "editorPid": os.getpid(),
        "isIconic": False,
    }
    pid = os.getpid()
    current = api["foreground"]()
    info["foregroundPid"] = current["pid"]
    if current["pid"] == pid and current["hwnd"]:
        hwnd = current["hwnd"]
    else:
        hwnd = api["main"](pid)
    info["hwnd"] = hwnd
    if not hwnd:
        return info
    info["windowClass"] = api["class_name"](hwnd)

    if current["hwnd"] == hwnd and not api["is_iconic"](hwnd) and not (
        api.get("any_iconic") and api["any_iconic"]()
    ):
        info["ok"] = True
        info["alreadyForeground"] = True
        return info

    api["show"](hwnd, 9)  # SW_RESTORE
    api["set_foreground"](hwnd)
    api["bring_to_top"](hwnd)
    api["sleep"](0.5)

    current = api["foreground"]()
    info["foregroundPid"] = current["pid"]
    info["isIconic"] = bool(api["is_iconic"](hwnd))
    if api.get("any_iconic"):
        info["isIconic"] = info["isIconic"] or bool(api["any_iconic"]())
    if info["isIconic"] or current["hwnd"] != hwnd:
        # Fast fail: the editor cannot be trusted to render a capture now, so
        # do not wait for the screenshot timeout.
        return info
    info["ok"] = True
    return info


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mtime_iso(path):
    return (
        datetime.datetime.fromtimestamp(
            os.path.getmtime(path), datetime.timezone.utc
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def _png_stats(path):
    """Cheap PNG statistics: top scanlines, unfiltered, pixel-sampled.

    Pure stdlib (``zlib`` + manual PNG chunk parsing).  Only 8-bit,
    non-interlaced PNGs are decoded; ``statsAvailable`` is false otherwise.
    ``uniqueColors`` is capped at 100000 sampled RGB triples and
    ``nonZeroRatio`` counts sampled pixels that are not exactly black.
    """
    result = {
        "statsAvailable": False,
        "statsAlgorithm": "png-scanlines-sample-v1",
    }
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        result["statsError"] = str(exc)
        return result
    if not data.startswith(_PNG_SIGNATURE):
        result["statsError"] = "not a PNG file"
        return result

    pos = 8
    width = height = bit_depth = color_type = interlace = None
    idat = []
    try:
        while pos + 8 <= len(data):
            length = int.from_bytes(data[pos : pos + 4], "big")
            chunk_type = data[pos + 4 : pos + 8]
            chunk = data[pos + 8 : pos + 8 + length]
            pos += 12 + length
            if chunk_type == b"IHDR":
                width = int.from_bytes(chunk[0:4], "big")
                height = int.from_bytes(chunk[4:8], "big")
                bit_depth = chunk[8]
                color_type = chunk[9]
                interlace = chunk[12] if len(chunk) > 12 else 0
            elif chunk_type == b"IDAT":
                idat.append(chunk)
            elif chunk_type == b"IEND":
                break
        channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
        if (
            not width
            or not height
            or bit_depth != 8
            or interlace != 0
            or channels is None
        ):
            result["statsError"] = "unsupported PNG layout"
            return result
        raw = zlib.decompress(b"".join(idat))
    except Exception as exc:  # noqa: BLE001 - stats must never fail the call
        result["statsError"] = "decode failed: %s" % exc
        return result

    stride = width * channels
    rows = min(height, _STATS_MAX_ROWS)
    step = max(1, (width * rows) // _STATS_MAX_SAMPLES)
    prev = bytearray(stride)
    colors = set()
    sampled = 0
    non_zero = 0
    offset = 0
    for _y in range(rows):
        if offset + 1 + stride > len(raw):
            break
        filter_type = raw[offset]
        row = bytearray(raw[offset + 1 : offset + 1 + stride])
        offset += 1 + stride
        if filter_type == 1:
            for i in range(channels, stride):
                row[i] = (row[i] + row[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = row[i - channels] if i >= channels else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                a = row[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                predictor = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[i] = (row[i] + predictor) & 0xFF
        prev = row
        for x in range(0, width, step):
            base = x * channels
            if color_type in (2, 6):
                r, g, b = row[base], row[base + 1], row[base + 2]
            else:
                r = g = b = row[base]
            sampled += 1
            if r or g or b:
                non_zero += 1
            if len(colors) < _STATS_MAX_COLORS:
                colors.add((r, g, b))
    if sampled == 0:
        result["statsError"] = "no scanlines decoded"
        return result
    result.update(
        {
            "statsAvailable": True,
            "uniqueColors": len(colors),
            "nonZeroRatio": round(non_zero / float(sampled), 4),
            "isBlack": non_zero == 0,
            "statsSampledPixels": sampled,
            "statsSampledRows": rows,
        }
    )
    return result


def _read_camera():
    unreal = get_unreal()
    info = editor_subsystem().get_level_viewport_camera_info()
    location = None
    rotation = None
    if isinstance(info, tuple):
        for value in info:
            if location is None and getattr(value, "x", None) is not None:
                location = value
            elif rotation is None and getattr(value, "pitch", None) is not None:
                rotation = value
    return location, rotation


def _restore_camera(saved):
    if saved is None:
        return
    location, rotation = saved
    if location is None or rotation is None:
        return
    try:
        editor_subsystem().set_level_viewport_camera_info(location, rotation)
    except Exception:
        pass


def _actor_camera(actor, distance_multiplier):
    unreal = get_unreal()
    origin = None
    extent = None
    try:
        bounds = actor.get_actor_bounds(False)
        if isinstance(bounds, tuple):
            for value in bounds:
                if origin is None and getattr(value, "x", None) is not None:
                    origin = value
                elif extent is None and getattr(value, "x", None) is not None:
                    extent = value
    except Exception:
        pass
    if origin is None or extent is None:
        raise RpcError(
            "CAPTURE_FAILED",
            "Cannot compute actor bounds for capture",
            {"target": "level_viewport", "reason": "actor bounds unavailable"},
        )
    radius = max(float(extent.x), float(extent.y), float(extent.z))
    distance = max(radius, 1.0) * float(distance_multiplier)
    forward = actor.get_actor_forward_vector()
    location = unreal.Vector(
        float(origin.x) - float(forward.x) * distance,
        float(origin.y) - float(forward.y) * distance,
        float(origin.z) - float(forward.z) * distance,
    )
    rotation = None
    try:
        rotation = unreal.MathLibrary.find_look_at_rotation(location, origin)
    except Exception:
        rotation = actor.get_actor_rotation()
    return location, rotation


def _find_recent_screenshot(since_seconds):
    unreal = get_unreal()
    base = os.path.join(str(unreal.Paths.project_saved_dir()), "Screenshots")
    pattern = os.path.join(base, "**", "*.png")
    cutoff = time.time() - max(5.0, since_seconds)
    candidates = []
    for path in glob.glob(pattern, recursive=True):
        try:
            if os.path.getmtime(path) >= cutoff:
                candidates.append(path)
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def _finalize_file(target_path, started_at):
    """Return ``(path, used_fallback)`` for the produced screenshot."""
    if os.path.isfile(target_path) and os.path.getsize(target_path) > 0:
        return target_path, False
    fallback = _find_recent_screenshot(time.time() - started_at)
    if fallback:
        try:
            shutil.move(fallback, target_path)
            return target_path, True
        except Exception:
            return fallback, True
    return None, False


def handle(server, params):
    check_keys(
        params,
        {
            "target",
            "width",
            "height",
            "format",
            "jpegQuality",
            "camera",
            "returnMode",
            "hideEditorUI",
            "activateWindow",
            "timeoutMs",
        },
    )
    target = get_enum(params, "target", {"level_viewport", "pie"}, default="level_viewport")
    width = get_int(params, "width", default=1280, minimum=64, maximum=7680)
    height = get_int(params, "height", default=720, minimum=64, maximum=4320)
    image_format = get_enum(params, "format", _FORMATS, default="png")
    get_int(params, "jpegQuality", default=90, minimum=1, maximum=100)
    return_mode = get_enum(params, "returnMode", {"image", "file"}, default="image")
    get_bool(params, "hideEditorUI", default=True)
    activate_window = get_bool(params, "activateWindow", default=False)
    timeout_ms = get_int(params, "timeoutMs", default=15000, minimum=1000, maximum=30000)
    camera = get_obj(params, "camera") or {"mode": "current"}
    mode = get_enum(camera, "mode", _CAMERA_MODES, default="current", required=True)
    if mode == "actor":
        camera_selector = selector(camera.get("actorPath"), "camera.actorPath")
        distance_multiplier = camera.get("distanceMultiplier", 2.5)
        if isinstance(distance_multiplier, bool) or not isinstance(
            distance_multiplier, (int, float)
        ):
            raise RpcError(
                "INVALID_ARGUMENT",
                "camera.distanceMultiplier must be a number",
                {"issues": [{"path": "camera.distanceMultiplier", "code": "invalid_type", "message": "must be a number"}]},
            )
    elif mode == "explicit":
        camera_location = vec3(camera.get("location"), "camera.location", required=True)
        camera_rotation = rotator(camera.get("rotation"), "camera.rotation", required=True)
    else:
        camera_selector = None
        distance_multiplier = 2.5

    if target == "pie" and not is_pie_running():
        raise RpcError(
            "PIE_NOT_RUNNING", "PIE is not running", {"target": "pie"}
        )

    if not server.capabilities.get("screenshot"):
        raise RpcError(
            "CAPABILITY_UNAVAILABLE",
            "Screenshot capability is unavailable",
            {"capability": "screenshot"},
        )

    env = _render_environment()
    if env.get("offscreen"):
        # A headless editor has no rendered level viewport; failing fast beats
        # waiting for a screenshot task that can never produce a frame.
        raise RpcError(
            "CAPABILITY_UNAVAILABLE",
            "Viewport capture is unavailable in a headless/offscreen editor",
            {
                "capability": "screenshot",
                "renderer": _renderer_details(env),
                "suggestion": "Run the editor with a visible level viewport, or use an external screen capture tool.",
            },
        )

    capture_warnings = []
    activation_info = None
    if activate_window:
        activation = _activate_window()
        activation_info = dict(activation)
        if activation.get("unsupported"):
            capture_warnings.append(
                "ACTIVATE_WINDOW_UNSUPPORTED: window activation is only implemented on Windows"
            )
        elif not activation.get("ok"):
            raise RpcError(
                "EDITOR_UNSAFE_STATE",
                "Editor window could not be brought to the foreground",
                {
                    "reason": "window_not_foreground",
                    "attempted": True,
                    "editorPid": activation.get("editorPid"),
                    "foregroundPid": activation.get("foregroundPid"),
                    "hwnd": activation.get("hwnd"),
                    "isIconic": bool(activation.get("isIconic", False)),
                    "hint": "编辑器窗口未能置前/仍在最小化，请手动恢复窗口后重试，或传 activateWindow=false 并自行保证前台。",
                },
            )

    unreal = get_unreal()
    capture_dir = _capture_dir()
    try:
        os.makedirs(capture_dir, exist_ok=True)
    except Exception as exc:
        raise RpcError(
            "CAPTURE_FAILED",
            "Cannot create capture directory: %s" % exc,
            {"target": target, "reason": str(exc)},
        )

    extension = "jpg" if image_format == "jpeg" else "png"
    filename = "%s.%s" % (uuid.uuid4().hex, extension)
    target_path = os.path.join(capture_dir, filename)

    saved_camera = None
    try:
        if mode == "explicit":
            saved_camera = _read_camera()
            editor_subsystem().set_level_viewport_camera_info(camera_location, camera_rotation)
        elif mode == "actor":
            saved_camera = _read_camera()
            actor = resolve_actor(camera_selector)
            location, rotation = _actor_camera(actor, distance_multiplier)
            editor_subsystem().set_level_viewport_camera_info(location, rotation)
    except RpcError:
        _restore_camera(saved_camera)
        raise
    except Exception as exc:
        _restore_camera(saved_camera)
        raise RpcError(
            "CAPTURE_FAILED",
            "Failed to position capture camera: %s" % exc,
            {"target": target, "reason": str(exc)},
        )

    started_at = time.time()
    started_monotonic = time.monotonic()
    # Head-room under the caller's timeout so the structured CAPTURE_TIMEOUT
    # wins over the dispatcher's generic BRIDGE_TIMEOUT.
    deadline = started_monotonic + max(1.0, (timeout_ms / 1000.0) - 1.0)

    # Never force game view for level_viewport: TakeHighResScreenshot toggles
    # the viewport into game view synchronously, and that toggle is the path
    # that stalls on PixelStreaming projects (defect report 2026-10-29).
    force_game_view = target == "pie"
    try:
        task = unreal.AutomationLibrary.take_high_res_screenshot(
            width, height, target_path, force_game_view=force_game_view
        )
    except TypeError:
        # Builds without the keyword keep the legacy 3-argument behaviour.
        try:
            task = unreal.AutomationLibrary.take_high_res_screenshot(
                width, height, target_path
            )
        except Exception as exc:
            _restore_camera(saved_camera)
            raise RpcError(
                "CAPTURE_FAILED",
                "Failed to start screenshot task: %s" % exc,
                {"target": target, "reason": str(exc)},
            )
    except Exception as exc:
        _restore_camera(saved_camera)
        raise RpcError(
            "CAPTURE_FAILED",
            "Failed to start screenshot task: %s" % exc,
            {"target": target, "reason": str(exc)},
        )
    if task is None:
        _restore_camera(saved_camera)
        raise RpcError(
            "CAPTURE_FAILED",
            "take_high_res_screenshot returned None",
            {"target": target, "reason": "task is None", "renderer": _renderer_details(env)},
        )

    state = {
        "finished": False,
        "ticks": 0,
        "partial": False,
        "grace": False,
        "grace_deadline": 0.0,
    }

    def _capture_timeout():
        _restore_camera(saved_camera)
        exists = os.path.isfile(target_path)
        try:
            size = os.path.getsize(target_path) if exists else 0
        except OSError:
            size = 0
        details = {
            "target": target,
            "timeoutMs": timeout_ms,
            "waitedMs": int((time.monotonic() - started_monotonic) * 1000),
            "ticks": state["ticks"],
            "targetPath": os.path.abspath(target_path),
            "fileExists": exists,
            "fileBytes": size,
            "partialGraceMs": int(_PARTIAL_GRACE_SECONDS * 1000),
            "forceGameView": force_game_view,
            "renderer": _renderer_details(env),
            "activation": activation_info,
        }
        if env.get("pixelStreaming"):
            details["hint"] = (
                "PixelStreaming is configured (DefaultWebAPI.ini DataChannelType=PixelStreaming). "
                "The engine screenshot path may not produce new frames here; capture runs on the "
                "editor viewport with forceGameView=false. If it keeps timing out, use an external "
                "screen capture tool or disable PixelStreaming for the capture session."
            )
        return RpcError(
            "CAPTURE_TIMEOUT",
            "Screenshot task timed out after %d ms" % timeout_ms,
            details,
        )

    def poll():
        state["ticks"] += 1
        if not state["finished"]:
            try:
                done = bool(task.is_task_done())
            except Exception:
                done = True
            if not done:
                now = time.monotonic()
                if now <= deadline:
                    return None
                if not state["grace"]:
                    state["grace"] = True
                    state["grace_deadline"] = now + _PARTIAL_GRACE_SECONDS
                # The engine frequently finishes the write a few dozen ms after
                # our deadline; give it a short grace window instead of failing
                # a capture whose file is already on disk.
                candidate, _fallback_used = _finalize_file(target_path, started_at)
                if candidate is not None and os.path.isfile(candidate):
                    state["partial"] = True
                    state["finished"] = True
                    _restore_camera(saved_camera)
                elif now > state["grace_deadline"]:
                    raise _capture_timeout()
                else:
                    return None
            if not state["finished"]:
                state["finished"] = True
                _restore_camera(saved_camera)

        finalized, used_fallback = _finalize_file(target_path, started_at)
        if finalized is None or not os.path.isfile(finalized):
            raise RpcError(
                "CAPTURE_FAILED",
                "Screenshot file was not produced",
                {"target": target, "reason": "file missing after capture"},
            )
        try:
            byte_count = int(os.path.getsize(finalized))
        except OSError as exc:
            raise RpcError(
                "CAPTURE_FAILED",
                "Cannot stat screenshot file: %s" % exc,
                {"target": target, "reason": str(exc)},
            )

        warnings = list(capture_warnings)
        if state["partial"]:
            warnings.append(
                "CAPTURE_PARTIAL: screenshot file appeared within the %d ms grace window"
                % int(_PARTIAL_GRACE_SECONDS * 1000)
            )
        if used_fallback:
            # The engine may ignore the requested path and write to
            # Saved/Screenshots instead; _finalize_file recovers the newest
            # matching file.  Surface that so a caller can tell the recovered
            # file apart from a direct hit.
            warnings.append(
                "SCREENSHOT_FALLBACK_PATH: engine wrote %s instead of the requested path"
                % finalized
            )

        actual_format = image_format
        try:
            with open(finalized, "rb") as handle_file:
                header = handle_file.read(8)
            if header.startswith(_PNG_SIGNATURE):
                actual_format = "png"
            elif header.startswith(_JPEG_SIGNATURE):
                actual_format = "jpeg"
            else:
                warnings.append("FORMAT_UNRECOGNIZED: output is neither PNG nor JPEG")
            if actual_format != image_format:
                # take_high_res_screenshot always writes PNG; never claim a
                # format the file does not actually have.
                warnings.append(
                    "FORMAT_MISMATCH: requested %s but the engine produced %s"
                    % (image_format, actual_format)
                )
        except OSError:
            pass

        try:
            sha256 = _sha256_file(finalized)
            mtime = _mtime_iso(finalized)
        except OSError as exc:
            raise RpcError(
                "CAPTURE_FAILED",
                "Cannot hash screenshot file: %s" % exc,
                {"target": target, "reason": str(exc)},
            )
        if actual_format == "png":
            stats = _png_stats(finalized)
        else:
            stats = {
                "statsAvailable": False,
                "statsAlgorithm": None,
                "statsError": "statistics are only computed for PNG output",
            }

        data = {
            "path": os.path.abspath(finalized),
            "targetPath": os.path.abspath(target_path),
            "isPath": True,
            "partial": bool(state["partial"]),
            "width": width,
            "height": height,
            "format": actual_format,
            "bytes": byte_count,
            "sha256": sha256,
            "mtime": mtime,
            "stats": stats,
            "capturedAt": datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "returnMode": return_mode,
        }
        return Done(HandlerResult(data, warnings))

    return Pending(poll)
