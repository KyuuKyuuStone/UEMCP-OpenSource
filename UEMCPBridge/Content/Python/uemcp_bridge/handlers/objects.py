"""``object.reflect`` (read-only) and ``object.call`` (write) primitives.

These are generic escape hatches for objects the tool-specific handlers do not
know about: enumerate the Python-callable surface of any UObject and invoke a
function by name.  ``object.call`` is a write operation (``allowWrite`` gate)
and refuses dunder/private names plus Python/exec/eval/subprocess lookalikes.
"""

import inspect
import json
import os
import re
import time

from ..errors import RpcError
from . import (
    HandlerResult,
    actor_subsystem,
    check_keys,
    get_bool,
    get_int,
    get_list,
    get_str,
    get_unreal,
)
from . import logs as logs_handler

MAX_FUNCTIONS = 200
MAX_ARGUMENTS = 64
_CAPTURE_LOG_MAX_LINES = 200
_CAPTURE_LOG_MAX_TEXT = 500
_CAPTURE_LOG_MAX_MS = 200
_BLOCKED_FRAGMENTS = ("python", "exec", "eval", "subprocess")
_CAMEL_RE_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_RE_2 = re.compile(r"([a-z0-9])([A-Z])")


def _to_snake(name):
    """``FlyToMonitorPoint`` -> ``fly_to_monitor_point``; snake names unchanged."""
    if "_" in name and not re.search(r"[A-Z]", name):
        return name
    converted = _CAMEL_RE_1.sub(r"\1_\2", name)
    converted = _CAMEL_RE_2.sub(r"\1_\2", converted)
    return converted.lower()


def _is_blocked(name):
    lowered = name.lower()
    if name.startswith("_"):
        return True
    return any(fragment in lowered for fragment in _BLOCKED_FRAGMENTS)


def _class_name(obj):
    try:
        return str(obj.get_class().get_name())
    except Exception:
        return type(obj).__name__


def _scene_actors():
    """Editor-world actors plus PIE-world actors (deduplicated by path)."""
    unreal = get_unreal()
    actors = []
    seen = set()

    def _add(values):
        for actor in values or []:
            try:
                key = str(actor.get_path_name())
            except Exception:
                key = "id:%d" % id(actor)
            if key in seen:
                continue
            seen.add(key)
            actors.append(actor)

    try:
        _add(actor_subsystem().get_all_level_actors())
    except Exception:
        pass
    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        game_world = editor.get_game_world()
        if game_world is not None:
            _add(unreal.GameplayStatics.get_all_actors_of_class(game_world, unreal.Actor))
    except Exception:
        pass
    return actors


def _class_candidates(name):
    """Loaded Python classes that may correspond to a bare class name."""
    unreal = get_unreal()
    found = []
    attribute = getattr(unreal, name, None)
    if isinstance(attribute, type):
        found.append(attribute)
    for loader_name in ("load_class", "find_class"):
        loader = getattr(unreal, loader_name, None)
        if not callable(loader):
            continue
        for candidate in (name, "/Script/Engine." + name):
            try:
                cls = loader(None, candidate)
            except Exception:
                continue
            if isinstance(cls, type) and cls not in found:
                found.append(cls)
    if not found:
        lowered = name.lower()
        for attribute_name in dir(unreal):
            if attribute_name.lower() != lowered:
                continue
            value = getattr(unreal, attribute_name, None)
            if isinstance(value, type):
                found.append(value)
                break
    return found


def _target_candidates(target, actors):
    """Readable full paths for a failed bare-name lookup (max 5)."""
    lowered = target.lower()
    scored = []
    for actor in actors:
        try:
            path = str(actor.get_path_name())
            class_name = str(actor.get_class().get_name()).lower()
        except Exception:
            continue
        if class_name == lowered:
            score = 0
        elif class_name.startswith(lowered) or lowered.startswith(class_name):
            score = 1
        elif lowered in path.lower():
            score = 2
        else:
            continue
        scored.append((score, len(path), path))
    scored.sort()
    candidates = []
    for _score, _length, path in scored:
        if path not in candidates:
            candidates.append(path)
        if len(candidates) >= 5:
            break
    return candidates


def _resolve_target(target):
    unreal = get_unreal()
    for loader_name in ("find_object", "load_object"):
        loader = getattr(unreal, loader_name, None)
        if not callable(loader):
            continue
        try:
            obj = loader(None, target)
        except Exception:
            obj = None
        if obj is not None:
            return obj

    actors = _scene_actors()
    for actor in actors:
        try:
            if str(actor.get_path_name()) == target:
                return actor
        except Exception:
            continue
    for actor in actors:
        try:
            class_name = str(actor.get_class().get_name())
        except Exception:
            continue
        if class_name == target or class_name.lower() == target.lower():
            return actor

    try:
        asset = unreal.EditorAssetLibrary.load_asset(target)
        if asset is not None:
            return asset
    except Exception:
        pass

    # Bare class name: resolve the class (module attribute / load_class) and
    # pick the first scene instance, including PIE-world actors.
    for cls in _class_candidates(target):
        for actor in actors:
            try:
                if isinstance(actor, cls):
                    return actor
            except Exception:
                continue
    return None


def _param_count(function):
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return None
    count = 0
    for parameter in signature.parameters.values():
        if parameter.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            count += 1
    return count


def _callable_members(obj):
    members = []
    seen = set()
    for name in dir(obj):
        if name.startswith("_") or name in seen:
            continue
        seen.add(name)
        try:
            attribute = getattr(obj, name)
        except Exception:
            continue
        if not callable(attribute) or isinstance(attribute, type):
            continue
        members.append((name, attribute))
    members.sort(key=lambda item: item[0])
    return members


def _suggestions(name, candidates, limit=5):
    def distance(left, right):
        if left == right:
            return 0
        previous = list(range(len(right) + 1))
        for i, left_char in enumerate(left, 1):
            current = [i]
            for j, right_char in enumerate(right, 1):
                insertion = current[j - 1] + 1
                deletion = previous[j] + 1
                substitution = previous[j - 1] + (left_char != right_char)
                current.append(min(insertion, deletion, substitution))
            previous = current
        return previous[-1]

    scored = []
    for candidate in candidates:
        if candidate.startswith("_"):
            continue
        score = distance(name, candidate)
        if score <= 3:
            scored.append((score, candidate))
    scored.sort()
    return [candidate for _score, candidate in scored[:limit]]


def _capture_log_path():
    try:
        project_dir = logs_handler._project_dir()
        logs_dir = logs_handler._logs_dir(project_dir)
        path = logs_handler._default_log_path(project_dir)
        if not path:
            return None
        return logs_handler._safe_log_path(path, logs_dir)
    except Exception:
        return None


def _capture_log_marker():
    """Byte offset + line count before the call (captureLog window start)."""
    marker = {"path": None, "offset": 0, "baseLine": 0, "failed": False}
    path = _capture_log_path()
    marker["path"] = path
    if not path or not os.path.isfile(path):
        return marker
    started = time.monotonic()
    try:
        with open(path, "rb") as handle:
            total = 0
            newlines = 0
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                newlines += chunk.count(b"\n")
                if (time.monotonic() - started) * 1000 > _CAPTURE_LOG_MAX_MS:
                    marker["failed"] = True
                    return marker
            marker["offset"] = total
            marker["baseLine"] = newlines
    except OSError:
        marker["failed"] = True
    return marker


def _capture_log_read(marker):
    """Lines appended between the marker and now; never raises."""
    if marker.get("failed"):
        return [], False, ["CAPTURE_LOG_FAILED: log marker exceeded 200 ms"]
    path = marker.get("path") or _capture_log_path()
    if not path:
        return [], False, ["CAPTURE_LOG_FAILED: log file not found"]
    started = time.monotonic()
    offset = int(marker.get("offset") or 0)
    base = int(marker.get("baseLine") or 0)
    chunk = b""
    while True:
        try:
            with open(path, "rb") as handle:
                size = os.fstat(handle.fileno()).st_size
                if offset > size:
                    # Log rotated/replaced during the call: read the new file.
                    offset = 0
                    base = 0
                handle.seek(offset)
                chunk = handle.read()
        except OSError as exc:
            return [], False, ["CAPTURE_LOG_FAILED: %s" % exc]
        if chunk:
            break
        # The engine log writer is buffered; give it a moment to flush before
        # concluding that the call produced no log lines.
        if (time.monotonic() - started) * 1000 >= _CAPTURE_LOG_MAX_MS:
            break
        time.sleep(0.02)
    if (time.monotonic() - started) * 1000 > _CAPTURE_LOG_MAX_MS and not chunk:
        return [], False, []

    text = chunk.decode("utf-8", "replace")
    raw_lines = text.split("\n")
    if raw_lines and raw_lines[-1] == "":
        raw_lines.pop()
    entries = []
    for index, raw in enumerate(raw_lines, 1):
        line = raw.rstrip("\r")
        entries.append(
            {
                "lineNo": base + index,
                "level": logs_handler._classify_level(line),
                "text": line[:_CAPTURE_LOG_MAX_TEXT],
            }
        )
    truncated = len(entries) > _CAPTURE_LOG_MAX_LINES
    if truncated:
        entries = entries[-_CAPTURE_LOG_MAX_LINES:]
    return entries, truncated, []


def handle_reflect(server, params):
    check_keys(params, {"target"})
    target = get_str(params, "target", required=True, min_length=1, max_length=512)

    obj = _resolve_target(target)
    if obj is None:
        raise RpcError(
            "NOT_FOUND",
            "Object not found: %s" % target,
            {
                "target": target,
                "candidates": _target_candidates(target, _scene_actors()),
            },
        )

    members = _callable_members(obj)
    type_dict = getattr(type(obj), "__dict__", {})
    functions = []
    for name, attribute in members:
        functions.append(
            {
                "name": name,
                "pythonName": name,
                "paramCount": _param_count(attribute),
                "inherited": name not in type_dict,
            }
        )

    truncated = len(functions) > MAX_FUNCTIONS
    functions = functions[:MAX_FUNCTIONS]
    return HandlerResult(
        {
            "target": target,
            "targetClass": _class_name(obj),
            "functions": functions,
            "truncated": truncated,
        }
    )


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except Exception:
        return repr(value)


def handle_call(server, params):
    check_keys(params, {"target", "function", "args", "waitMs", "captureLog"})
    target = get_str(params, "target", required=True, min_length=1, max_length=512)
    function = get_str(params, "function", required=True, min_length=1, max_length=128)
    args = get_list(params, "args", default=[], max_items=MAX_ARGUMENTS)
    get_int(params, "waitMs", default=5000, minimum=0, maximum=60000)
    capture_log = get_bool(params, "captureLog", default=False)

    if not server.settings.allow_write:
        raise RpcError(
            "PERMISSION_DENIED",
            "object.call is disabled (allowWrite=false)",
            {"gate": "bridge.allowWrite", "function": function},
        )

    name = _to_snake(function)
    if _is_blocked(name):
        raise RpcError(
            "PERMISSION_DENIED",
            "Function is blocked by the reflection blacklist",
            {"function": name, "blocked": True, "reason": "blacklisted_name"},
        )

    obj = _resolve_target(target)
    if obj is None:
        raise RpcError(
            "NOT_FOUND",
            "Object not found: %s" % target,
            {
                "target": target,
                "function": name,
                "candidates": _target_candidates(target, _scene_actors()),
            },
        )

    candidates = [member[0] for member in _callable_members(obj)]
    attribute = getattr(obj, name, None)
    if not callable(attribute):
        raise RpcError(
            "NOT_FOUND",
            "Function not found on %s: %s" % (_class_name(obj), name),
            {
                "target": target,
                "function": name,
                "suggestions": _suggestions(name, candidates),
            },
        )

    expected = _param_count(attribute)
    log_marker = _capture_log_marker() if capture_log else None
    try:
        value = attribute(*args)
    except TypeError as exc:
        raise RpcError(
            "INVALID_ARGUMENT",
            "Arguments do not match %s: %s" % (name, exc),
            {
                "function": name,
                "expectedParamCount": expected,
                "gotParamCount": len(args),
                "error": str(exc),
            },
        )
    except RpcError:
        raise
    except Exception as exc:
        raise RpcError(
            "EXECUTION_ERROR",
            "Calling %s failed: %s" % (name, exc),
            {"function": name, "target": target, "error": str(exc)},
        )

    data = {
        "target": target,
        "function": name,
        "returned": _json_safe(value),
        "returnedVoid": value is None,
    }
    warnings = []
    if capture_log:
        log_lines, log_truncated, log_warnings = _capture_log_read(log_marker)
        data["logLines"] = log_lines
        data["logTruncated"] = log_truncated
        warnings.extend(log_warnings)
    return HandlerResult(data, warnings)
