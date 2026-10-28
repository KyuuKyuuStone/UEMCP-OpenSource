"""Shared validation and UE helpers for bridge handlers.

Handlers run on the game thread.  They validate arguments manually (the
architecture keeps the JSON Schema on the MCP server side) and raise
:class:`RpcError` with contract error codes.
"""

from ..errors import RpcError, invalid_argument
from ..serialization import rotation_to_dict


class HandlerResult(object):
    __slots__ = ("data", "warnings")

    def __init__(self, data=None, warnings=None):
        self.data = data if data is not None else {}
        self.warnings = list(warnings or [])


def get_unreal():
    import unreal  # imported here so the module stays importable in tests

    return unreal


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------

def _add_issue(issues, path, code, message):
    issues.append({"path": path, "code": code, "message": message})


def check_keys(mapping, allowed, path="params"):
    if not isinstance(mapping, dict):
        raise invalid_argument(
            [{"path": path, "code": "invalid_type", "message": "must be an object"}]
        )
    unknown = sorted(set(mapping.keys()) - set(allowed))
    if unknown:
        raise invalid_argument(
            [
                {
                    "path": "%s.%s" % (path, unknown[0]) if path else unknown[0],
                    "code": "additional_property",
                    "message": "additional property '%s' is not allowed" % unknown[0],
                }
            ]
        )


def get_obj(params, key, path=None, allowed_keys=None, required=False):
    value = params.get(key)
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path or key, "code": "required", "message": "is required"}]
            )
        return None
    if not isinstance(value, dict):
        raise invalid_argument(
            [{"path": path or key, "code": "invalid_type", "message": "must be an object"}]
        )
    if allowed_keys is not None:
        check_keys(value, allowed_keys, path or key)
    return value


def get_bool(params, key, default=False, path=None):
    value = params.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise invalid_argument(
        [{"path": path or key, "code": "invalid_type", "message": "must be a boolean"}]
    )


def get_int(params, key, default=None, minimum=None, maximum=None, required=False, path=None):
    value = params.get(key)
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path or key, "code": "required", "message": "is required"}]
            )
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid_argument(
            [{"path": path or key, "code": "invalid_type", "message": "must be an integer"}]
        )
    if minimum is not None and value < minimum:
        raise invalid_argument(
            [{"path": path or key, "code": "minimum", "message": "must be >= %s" % minimum}]
        )
    if maximum is not None and value > maximum:
        raise invalid_argument(
            [{"path": path or key, "code": "maximum", "message": "must be <= %s" % maximum}]
        )
    return value


def get_number(params, key, default=None, minimum=None, maximum=None, required=False, path=None):
    value = params.get(key)
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path or key, "code": "required", "message": "is required"}]
            )
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise invalid_argument(
            [{"path": path or key, "code": "invalid_type", "message": "must be a number"}]
        )
    value = float(value)
    if minimum is not None and value < minimum:
        raise invalid_argument(
            [{"path": path or key, "code": "minimum", "message": "must be >= %s" % minimum}]
        )
    if maximum is not None and value > maximum:
        raise invalid_argument(
            [{"path": path or key, "code": "maximum", "message": "must be <= %s" % maximum}]
        )
    return value


def get_str(
    params,
    key,
    default=None,
    min_length=0,
    max_length=None,
    required=False,
    path=None,
):
    value = params.get(key)
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path or key, "code": "required", "message": "is required"}]
            )
        return default
    if not isinstance(value, str):
        raise invalid_argument(
            [{"path": path or key, "code": "invalid_type", "message": "must be a string"}]
        )
    if len(value) < min_length:
        raise invalid_argument(
            [{"path": path or key, "code": "min_length", "message": "must not be empty"}]
        )
    if max_length is not None and len(value) > max_length:
        raise invalid_argument(
            [
                {
                    "path": path or key,
                    "code": "max_length",
                    "message": "must be at most %d characters" % max_length,
                }
            ]
        )
    return value


def get_enum(params, key, allowed, default=None, required=False, path=None):
    value = params.get(key)
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path or key, "code": "required", "message": "is required"}]
            )
        return default
    if value not in allowed:
        raise invalid_argument(
            [
                {
                    "path": path or key,
                    "code": "invalid_enum_value",
                    "message": "must be one of %s" % ", ".join(sorted(allowed)),
                }
            ]
        )
    return value


def get_list(
    params,
    key,
    default=None,
    min_items=0,
    max_items=None,
    required=False,
    item_type=None,
    path=None,
):
    value = params.get(key)
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path or key, "code": "required", "message": "is required"}]
            )
        return list(default or [])
    if not isinstance(value, list):
        raise invalid_argument(
            [{"path": path or key, "code": "invalid_type", "message": "must be an array"}]
        )
    if len(value) < min_items:
        raise invalid_argument(
            [
                {
                    "path": path or key,
                    "code": "min_items",
                    "message": "must contain at least %d item(s)" % min_items,
                }
            ]
        )
    if max_items is not None and len(value) > max_items:
        raise invalid_argument(
            [
                {
                    "path": path or key,
                    "code": "max_items",
                    "message": "must contain at most %d item(s)" % max_items,
                }
            ]
        )
    if item_type is not None:
        for index, item in enumerate(value):
            if not isinstance(item, item_type):
                raise invalid_argument(
                    [
                        {
                            "path": "%s[%d]" % (path or key, index),
                            "code": "invalid_type",
                            "message": "must be a %s" % item_type.__name__,
                        }
                    ]
                )
    return value


def require_number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise invalid_argument(
            [{"path": path, "code": "invalid_type", "message": "must be a number"}]
        )
    return float(value)


def vec3(value, path, required=False):
    unreal = get_unreal()
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path, "code": "required", "message": "is required"}]
            )
        return None
    if not isinstance(value, dict):
        raise invalid_argument(
            [{"path": path, "code": "invalid_type", "message": "must be an object"}]
        )
    check_keys(value, {"x", "y", "z"}, path)
    for axis in ("x", "y", "z"):
        if axis not in value:
            raise invalid_argument(
                [{"path": "%s.%s" % (path, axis), "code": "required", "message": "is required"}]
            )
    return unreal.Vector(
        require_number(value["x"], path + ".x"),
        require_number(value["y"], path + ".y"),
        require_number(value["z"], path + ".z"),
    )


def rotator(value, path, required=False):
    unreal = get_unreal()
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path, "code": "required", "message": "is required"}]
            )
        return None
    if not isinstance(value, dict):
        raise invalid_argument(
            [{"path": path, "code": "invalid_type", "message": "must be an object"}]
        )
    check_keys(value, {"pitch", "yaw", "roll"}, path)
    for axis in ("pitch", "yaw", "roll"):
        if axis not in value:
            raise invalid_argument(
                [{"path": "%s.%s" % (path, axis), "code": "required", "message": "is required"}]
            )
    result = unreal.Rotator()
    result.pitch = require_number(value["pitch"], path + ".pitch")
    result.yaw = require_number(value["yaw"], path + ".yaw")
    result.roll = require_number(value["roll"], path + ".roll")
    return result


def selector(value, path="selector", required=True):
    if value is None:
        if required:
            raise invalid_argument(
                [{"path": path, "code": "required", "message": "is required"}]
            )
        return None
    if not isinstance(value, dict):
        raise invalid_argument(
            [{"path": path, "code": "invalid_type", "message": "must be an object"}]
        )
    check_keys(value, {"kind", "value"}, path)
    kind = get_enum(
        value,
        "kind",
        {"actorPath", "objectPath", "name", "label"},
        required=True,
        path=path + ".kind",
    )
    text = get_str(
        value, "value", min_length=1, max_length=512, required=True, path=path + ".value"
    )
    return {"kind": kind, "value": text}


# --------------------------------------------------------------------------
# UE helpers
# --------------------------------------------------------------------------

def editor_subsystem():
    unreal = get_unreal()
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)


def actor_subsystem():
    unreal = get_unreal()
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def level_subsystem():
    unreal = get_unreal()
    return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def asset_subsystem():
    unreal = get_unreal()
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def get_editor_world():
    try:
        return editor_subsystem().get_editor_world()
    except Exception:
        return None


def get_game_world():
    try:
        return editor_subsystem().get_game_world()
    except Exception:
        return None


def is_pie_running():
    return get_game_world() is not None


def ensure_not_pie(action="write operation"):
    if is_pie_running():
        raise RpcError(
            "EDITOR_UNSAFE_STATE",
            "PIE is running; %s is not allowed" % action,
            {"state": "pie"},
        )


def vec_dict(vector):
    return {"x": float(vector.x), "y": float(vector.y), "z": float(vector.z)}


def rot_dict(rotation):
    # Accepts both FRotator and FQuat (FTransform.rotation is a Quat).
    return rotation_to_dict(rotation)


def actor_ref(actor):
    unreal = get_unreal()
    path_name = ""
    try:
        path_name = str(actor.get_path_name())
    except Exception:
        path_name = str(actor)
    class_name = ""
    class_path = ""
    try:
        actor_class = actor.get_class()
        class_name = class_name_string(actor_class)
        class_path = class_path_string(actor_class)
    except Exception:
        pass
    label = ""
    try:
        label = str(actor.get_actor_label())
    except Exception:
        pass
    level_path = ""
    try:
        level_path = str(actor.get_level().get_outer().get_path_name())
    except Exception:
        pass
    return {
        "actorPath": path_name,
        "objectPath": path_name,
        "name": str(actor.get_name()),
        "label": label,
        "class": class_name,
        "classPath": class_path,
        "levelPath": level_path,
    }


def actor_transform(actor):
    transform = actor.get_actor_transform()
    translation = transform.translation
    rotation = transform.rotation
    scale = transform.scale3d
    return {
        "location": vec_dict(translation),
        "rotation": rot_dict(rotation),
        "scale": vec_dict(scale),
    }


def resolve_actor(sel):
    actors = actor_subsystem().get_all_level_actors()
    kind = sel["kind"]
    target = sel["value"]
    matches = []
    for actor in actors:
        try:
            if kind == "name":
                matched = str(actor.get_name()) == target
            elif kind == "label":
                matched = str(actor.get_actor_label()) == target
            else:
                path_name = str(actor.get_path_name())
                matched = path_name == target or path_name.lower() == target.lower()
        except Exception:
            matched = False
        if matched:
            matches.append(actor)

    if not matches:
        raise RpcError(
            "ACTOR_NOT_FOUND",
            "Actor not found: %s (%s)" % (target, kind),
            {"selector": sel, "matches": []},
        )
    if len(matches) > 1:
        raise RpcError(
            "AMBIGUOUS_SELECTOR",
            "Selector %s=%s matched %d actors" % (kind, target, len(matches)),
            {"selector": sel, "matches": [actor_ref(item) for item in matches]},
        )
    return matches[0]


def _load_class_candidate(unreal, path):
    """Resolve a class from a class path, object path or Blueprint path.

    In UE 5.4 ``load_class`` returns a ``unreal.Class`` object (not a Python
    type), and some path shapes only resolve through ``load_object`` or
    ``find_object``.  Blueprint assets are unwrapped via ``generated_class()``.
    """
    for loader_name in ("load_class", "load_object", "find_object"):
        loader = getattr(unreal, loader_name, None)
        if not callable(loader):
            continue
        try:
            loaded = loader(None, path)
        except Exception:
            loaded = None
        if loaded is None:
            continue
        generated = getattr(loaded, "generated_class", None)
        if callable(generated):
            try:
                generated_class = generated()
                if generated_class is not None:
                    return generated_class
            except Exception:
                pass
        if isinstance(loaded, type) or isinstance(loaded, unreal.Class):
            return loaded
    return None


def _class_path_candidates(class_name):
    text = str(class_name).strip()
    if "/" in text:
        candidates = [text]
        leaf = text.rsplit("/", 1)[-1]
        if "." not in leaf:
            # /Game/BP_Test -> /Game/BP_Test.BP_Test (+ generated class)
            candidates.append(text + "." + leaf)
            if text.startswith("/Game/"):
                candidates.append(text + "." + leaf + "_C")
        elif text.startswith("/Game/") and not leaf.endswith("_C"):
            # /Game/BP_Test.BP_Test -> /Game/BP_Test.BP_Test_C
            candidates.append(text + "_C")
        return candidates
    if "." in text:
        # Engine.StaticMeshActor -> /Script/Engine.StaticMeshActor
        module, _separator, short_name = text.rpartition(".")
        return ["/Script/%s.%s" % (module, short_name)]
    return ["/Script/Engine." + text]


def actor_matches_class(actor, class_filter):
    """Match an actor against a resolved class (Python type or Class object).

    ``isinstance`` only accepts Python types; path-resolved classes are
    ``unreal.Class`` objects, so compare through the class CDO / class path.
    """
    if class_filter is None:
        return True
    if isinstance(class_filter, type):
        try:
            return isinstance(actor, class_filter)
        except Exception:
            return False
    unreal = get_unreal()
    try:
        if isinstance(class_filter, unreal.Class):
            getter = getattr(unreal, "get_default_object", None)
            cdo = getter(class_filter) if callable(getter) else None
            if cdo is not None:
                return isinstance(actor, type(cdo))
    except Exception:
        pass
    try:
        actor_class = actor.get_class()
        target = class_filter.get_path_name()
        current = actor_class.get_path_name()
        return bool(target) and current == target
    except Exception:
        return False


def _is_actor_class(candidate):
    """Return True when ``candidate`` denotes an AActor subclass.

    ``unreal.Class`` objects reject ``issubclass`` (TypeError) and expose no
    ``is_child_of`` in 5.4, so Class objects are validated through their CDO.
    """
    unreal = get_unreal()
    if candidate is None:
        return False
    if isinstance(candidate, type):
        try:
            return issubclass(candidate, unreal.Actor)
        except Exception:
            return False
    try:
        if isinstance(candidate, unreal.Class):
            # NOTE: Class.get_default_object() returns the CDO of "Class"
            # itself in UE 5.4; the module-level helper returns the CDO of
            # the class being inspected (verified by probe_class_cdo.py).
            getter = getattr(unreal, "get_default_object", None)
            if callable(getter):
                cdo = getter(candidate)
                if cdo is not None:
                    return isinstance(cdo, unreal.Actor)
    except Exception:
        pass
    try:
        generated = getattr(candidate, "generated_class", None)
        if callable(generated):
            return _is_actor_class(generated())
    except Exception:
        pass
    return False


def class_name_string(value):
    if value is None:
        return ""
    try:
        name = value.get_name()
        if name:
            return str(name)
    except Exception:
        pass
    return str(getattr(value, "__name__", "") or "")


def class_path_string(value):
    """Stable class path, e.g. ``/Script/Engine.StaticMeshActor`` or
    ``/Game/BP.BP_C``.  Never returns a debug repr."""
    if value is None:
        return ""
    unreal = get_unreal()
    candidate = value
    try:
        if isinstance(candidate, type):
            static = getattr(candidate, "static_class", None)
            if callable(static):
                candidate = static()
    except Exception:
        candidate = value
    try:
        path = candidate.get_path_name()
        if path:
            return str(path)
    except Exception:
        pass
    try:
        path = unreal.SystemLibrary.get_path_name(candidate)
        if path:
            return str(path)
    except Exception:
        pass
    name = class_name_string(value)
    if name:
        try:
            resolved = unreal.load_class(None, "/Script/Engine." + name)
            if resolved is not None:
                resolved_path = resolved.get_path_name()
                if resolved_path:
                    return str(resolved_path)
        except Exception:
            pass
    return ""


def resolve_actor_class(class_name):
    unreal = get_unreal()
    text = str(class_name).strip()
    candidates = []

    if "/" not in text:
        short_name = text.rpartition(".")[2]
        candidate = getattr(unreal, short_name, None)
        if isinstance(candidate, type):
            candidates.append(candidate)

    for path in _class_path_candidates(text):
        candidate = _load_class_candidate(unreal, path)
        if candidate is not None:
            candidates.append(candidate)

    for candidate in candidates:
        if _is_actor_class(candidate):
            return candidate

    raise RpcError(
        "CLASS_NOT_FOUND",
        "Actor class not found: %s" % class_name,
        {"className": class_name},
    )


def load_asset(asset_path):
    unreal = get_unreal()
    try:
        asset = asset_subsystem().load_asset(asset_path)
    except Exception:
        asset = None
    return asset


def asset_exists(asset_path):
    try:
        return bool(asset_subsystem().does_asset_exist(asset_path))
    except Exception:
        return False


def asset_ref(asset_data):
    try:
        class_name = str(asset_data.asset_class_path.asset_name)
    except Exception:
        try:
            class_name = str(asset_data.asset_class)
        except Exception:
            class_name = ""
    package_name = str(getattr(asset_data, "package_name", ""))
    asset_name = str(getattr(asset_data, "asset_name", ""))
    object_path = "%s.%s" % (package_name, asset_name) if package_name and asset_name else package_name
    package_path = ""
    if package_name:
        package_path = package_name.rsplit("/", 1)[0] if "/" in package_name else ""
    is_redirector = False
    try:
        unreal = get_unreal()
        is_redirector = bool(unreal.AssetRegistryHelpers.is_redirector(asset_data))
    except Exception:
        pass
    disk_size = 0
    try:
        disk_size = int(asset_data.get_tag_value("AssetFileSize") or 0)
    except Exception:
        disk_size = 0
    # TopLevelAssetPath: build a stable "/Script/Module.Class" path instead of
    # serializing the struct repr (review item O-6).
    class_path = ""
    try:
        asset_class_path = getattr(asset_data, "asset_class_path", None)
        if asset_class_path is not None:
            path_package = str(getattr(asset_class_path, "package_name", "") or "")
            path_name = str(getattr(asset_class_path, "asset_name", "") or "")
            if path_package and path_name:
                class_path = "%s.%s" % (path_package, path_name)
    except Exception:
        class_path = ""
    return {
        "packageName": package_name,
        "objectPath": object_path,
        "assetName": asset_name,
        "class": class_name,
        "classPath": class_path,
        "packagePath": package_path,
        "isRedirector": is_redirector,
        "diskSize": disk_size,
    }
