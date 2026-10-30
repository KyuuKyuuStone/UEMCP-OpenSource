"""``object.reflect`` (read-only) and ``object.call`` (write) primitives.

These are generic escape hatches for objects the tool-specific handlers do not
know about: enumerate the Python-callable surface of any UObject and invoke a
function by name.  ``object.call`` is a write operation (``allowWrite`` gate)
and refuses dunder/private names plus Python/exec/eval/subprocess lookalikes.
"""

import inspect
import json
import re

from ..errors import RpcError
from . import (
    HandlerResult,
    actor_subsystem,
    check_keys,
    get_int,
    get_list,
    get_str,
    get_unreal,
)

MAX_FUNCTIONS = 200
MAX_ARGUMENTS = 64
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

    try:
        actors = list(actor_subsystem().get_all_level_actors())
    except Exception:
        actors = []

    for actor in actors:
        try:
            if str(actor.get_path_name()) == target:
                return actor
        except Exception:
            continue
    for actor in actors:
        try:
            class_names = {str(actor.get_class().get_name())}
        except Exception:
            continue
        if target in class_names:
            return actor

    try:
        asset = unreal.EditorAssetLibrary.load_asset(target)
        if asset is not None:
            return asset
    except Exception:
        pass
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


def handle_reflect(server, params):
    check_keys(params, {"target"})
    target = get_str(params, "target", required=True, min_length=1, max_length=512)

    obj = _resolve_target(target)
    if obj is None:
        raise RpcError(
            "NOT_FOUND",
            "Object not found: %s" % target,
            {"target": target},
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
    check_keys(params, {"target", "function", "args", "waitMs"})
    target = get_str(params, "target", required=True, min_length=1, max_length=512)
    function = get_str(params, "function", required=True, min_length=1, max_length=128)
    args = get_list(params, "args", default=[], max_items=MAX_ARGUMENTS)
    get_int(params, "waitMs", default=5000, minimum=0, maximum=60000)

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
            {"target": target, "function": name},
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

    return HandlerResult(
        {
            "target": target,
            "function": name,
            "returned": _json_safe(value),
            "returnedVoid": value is None,
        }
    )
