"""``viewport.capture`` handler (architecture doc section 5.7).

The screenshot task is polled from successive Slate ticks via
:class:`Pending`; the game thread is never blocked waiting for the capture.
"""

import datetime
import glob
import os
import re
import shutil
import time
import uuid

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

    state = {"finished": False, "ticks": 0}

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
            "targetPath": target_path,
            "fileExists": exists,
            "fileBytes": size,
            "forceGameView": force_game_view,
            "renderer": _renderer_details(env),
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
                if time.monotonic() > deadline:
                    raise _capture_timeout()
                return None
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

        warnings = []
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

        data = {
            "path": finalized,
            "isPath": True,
            "width": width,
            "height": height,
            "format": actual_format,
            "bytes": byte_count,
            "capturedAt": datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "returnMode": return_mode,
        }
        return Done(HandlerResult(data, warnings))

    return Pending(poll)
