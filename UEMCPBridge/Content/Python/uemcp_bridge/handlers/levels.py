"""``level.control`` handler (architecture doc section 5.4)."""

from ..errors import RpcError
from . import (
    HandlerResult,
    asset_exists,
    check_keys,
    ensure_not_pie,
    get_bool,
    get_editor_world,
    get_enum,
    get_str,
    get_unreal,
    is_pie_running,
    level_subsystem,
)

READ_ACTIONS = {"get_current", "list_dirty"}
WRITE_ACTIONS = {"open", "save_current", "save_all", "new"}
ALL_ACTIONS = READ_ACTIONS | WRITE_ACTIONS


def _dirty_packages():
    unreal = get_unreal()
    try:
        packages = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        return list(packages or [])
    except Exception:
        return []


def _package_entries():
    entries = []
    for package in _dirty_packages():
        path = ""
        name = ""
        is_map = False
        try:
            name = str(package.get_name())
            path = str(package.get_path_name())
        except Exception:
            name = str(package)
            path = name
        try:
            is_map = bool(package.get_editor_property("is_map"))
        except Exception:
            # UPackage has no "is_map" editor property (map-ness is the
            # PKG_ContainsMap package flag), so the probe above always raises.
            # Every package from get_dirty_map_packages() is a map by
            # definition, so report the truth instead of a silent False.
            is_map = True
        entries.append({"path": path, "name": name, "isMap": is_map})
    return entries


def _current_info(previous_path=None, saved=None):
    world = get_editor_world()
    path = ""
    name = ""
    is_dirty = False
    is_partitioned = False
    if world is not None:
        try:
            path = str(world.get_path_name())
            name = str(world.get_name())
        except Exception:
            pass
        try:
            is_partitioned = bool(world.get_editor_property("world_partition"))
        except Exception:
            is_partitioned = False
        package_name = ""
        try:
            package_name = str(world.get_outer().get_name())
        except Exception:
            pass
        dirty_names = []
        for entry in _package_entries():
            dirty_names.append(entry["name"])
        is_dirty = package_name in dirty_names if package_name else False

    data = {
        "path": path,
        "name": name,
        "isDirty": is_dirty,
        "isPartitioned": is_partitioned,
    }
    if previous_path is not None:
        data["previousPath"] = previous_path
    if saved is not None:
        data["saved"] = bool(saved)
    return data


def _level_asset_exists(path):
    if asset_exists(path):
        return True
    # Level asset paths sometimes omit the object name; Accept the object path.
    if "." not in path:
        return asset_exists(path + "." + path.rsplit("/", 1)[-1])
    return False


def handle(server, params):
    check_keys(
        params,
        {
            "action",
            "levelPath",
            "templatePath",
            "partitioned",
            "allowDiscardUnsaved",
            "confirm",
        },
    )
    action = get_enum(params, "action", ALL_ACTIONS, required=True)
    level_path = get_str(params, "levelPath", max_length=512)
    template_path = get_str(params, "templatePath", max_length=512)
    partitioned = get_bool(params, "partitioned", default=False)
    allow_discard = get_bool(params, "allowDiscardUnsaved", default=False)
    confirm = get_bool(params, "confirm", default=False)

    if action == "get_current":
        return HandlerResult(_current_info())

    if action == "list_dirty":
        return HandlerResult({"packages": _package_entries()})

    if action in WRITE_ACTIONS:
        ensure_not_pie("level %s" % action)

    subsystem = level_subsystem()

    if action == "open":
        if not level_path:
            raise RpcError(
                "INVALID_ARGUMENT",
                "levelPath is required for action 'open'",
                {"issues": [{"path": "levelPath", "code": "required", "message": "is required"}]},
            )
        previous = _current_info()["path"]
        dirty = _package_entries()
        if dirty:
            if not allow_discard:
                raise RpcError(
                    "UNSAVED_CHANGES",
                    "%d dirty package(s); set allowDiscardUnsaved=true to discard"
                    % len(dirty),
                    {"dirtyPackages": [item["path"] or item["name"] for item in dirty]},
                )
            if not confirm:
                raise RpcError(
                    "CONFIRMATION_REQUIRED",
                    "Opening a level discards unsaved changes; confirm=true is required",
                    {"dirtyPackages": [item["path"] or item["name"] for item in dirty]},
                )
        if not _level_asset_exists(level_path):
            raise RpcError(
                "LEVEL_NOT_FOUND",
                "Level not found: %s" % level_path,
                {"levelPath": level_path},
            )
        try:
            opened = bool(subsystem.load_level(level_path))
        except Exception as exc:
            raise RpcError(
                "LEVEL_LOAD_FAILED",
                "Failed to load level %s: %s" % (level_path, exc),
                {"levelPath": level_path, "reason": str(exc)},
            )
        if not opened:
            raise RpcError(
                "LEVEL_LOAD_FAILED",
                "Failed to load level %s" % level_path,
                {"levelPath": level_path, "reason": "load_level returned false"},
            )
        return HandlerResult(_current_info(previous_path=previous))

    if action == "save_current":
        try:
            saved = bool(subsystem.save_current_level())
        except Exception as exc:
            raise RpcError(
                "SAVE_FAILED", "Failed to save current level: %s" % exc, {"reason": str(exc)}
            )
        if not saved:
            raise RpcError(
                "SAVE_FAILED",
                "save_current_level returned false",
                {"reason": "save_current_level returned false"},
            )
        return HandlerResult(_current_info(saved=True))

    if action == "save_all":
        if not confirm:
            raise RpcError(
                "CONFIRMATION_REQUIRED",
                "save_all overwrites every dirty package; confirm=true is required",
                {"dirtyPackages": [item["path"] or item["name"] for item in _package_entries()]},
            )
        try:
            saved = bool(subsystem.save_all_dirty_levels())
        except Exception as exc:
            raise RpcError(
                "SAVE_FAILED", "Failed to save dirty levels: %s" % exc, {"reason": str(exc)}
            )
        if not saved:
            raise RpcError(
                "SAVE_FAILED",
                "save_all_dirty_levels returned false",
                {"reason": "save_all_dirty_levels returned false"},
            )
        return HandlerResult(_current_info(saved=True))

    if action == "new":
        if not level_path:
            raise RpcError(
                "INVALID_ARGUMENT",
                "levelPath is required for action 'new'",
                {"issues": [{"path": "levelPath", "code": "required", "message": "is required"}]},
            )
        previous = _current_info()["path"]
        try:
            if template_path:
                created = bool(subsystem.new_level_from_template(level_path, template_path))
            else:
                created = bool(subsystem.new_level(level_path, partitioned))
        except Exception as exc:
            raise RpcError(
                "LEVEL_LOAD_FAILED",
                "Failed to create level %s: %s" % (level_path, exc),
                {"levelPath": level_path, "reason": str(exc)},
            )
        if not created:
            raise RpcError(
                "LEVEL_LOAD_FAILED",
                "Failed to create level %s" % level_path,
                {"levelPath": level_path, "reason": "new_level returned false"},
            )
        return HandlerResult(_current_info(previous_path=previous))

    raise RpcError("INVALID_ARGUMENT", "Unsupported action: %s" % action, {})
