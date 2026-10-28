"""``editor.status`` handler (architecture doc section 5.1)."""

import os

from ..errors import RpcError
from . import (
    HandlerResult,
    actor_ref,
    actor_subsystem,
    check_keys,
    editor_subsystem,
    get_bool,
    get_int,
    get_list,
    get_unreal,
    get_editor_world,
    is_pie_running,
    level_subsystem,
    rot_dict,
    vec_dict,
)

ALL_SECTIONS = {"editor", "level", "selection", "viewport", "capabilities", "policies"}
DEFAULT_SECTIONS = ["editor", "level", "selection", "capabilities"]


def detect_capabilities():
    unreal = get_unreal()
    automation = getattr(unreal, "AutomationLibrary", None)
    blueprint_library = getattr(unreal, "BlueprintEditorLibrary", None)
    system_library = getattr(unreal, "SystemLibrary", None)
    return {
        "python": True,
        "screenshot": automation is not None
        and hasattr(automation, "take_high_res_screenshot"),
        "blueprintRead": blueprint_library is not None,
        "blueprintNodeRead": False,
        "blueprintCompile": blueprint_library is not None
        and hasattr(blueprint_library, "compile_blueprint"),
        "animBlueprintEdit": False,
        "assetRegistry": hasattr(unreal, "AssetRegistryHelpers"),
        "console": system_library is not None
        and hasattr(system_library, "execute_console_command"),
    }


def _dirty_map_packages():
    unreal = get_unreal()
    try:
        packages = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        return list(packages or [])
    except Exception:
        return []


def _dirty_package_names():
    names = []
    for package in _dirty_map_packages():
        try:
            names.append(str(package.get_name()))
        except Exception:
            names.append(str(package))
    return names


def _editor_section(server):
    unreal = get_unreal()
    try:
        ue_version = str(unreal.SystemLibrary.get_engine_version())
    except Exception:
        ue_version = server.ue_version
    return {
        "ueVersion": ue_version,
        "pluginVersion": server.plugin_version,
        "bridgeProtocol": server.bridge_protocol,
        "processId": os.getpid(),
        "isPieRunning": is_pie_running(),
        "isSimulating": False,
        "isCompiling": False,
        "isAssetRegistryLoading": _asset_registry_loading(),
    }


def _asset_registry_loading():
    unreal = get_unreal()
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        if hasattr(registry, "is_loading_assets"):
            return bool(registry.is_loading_assets())
    except Exception:
        pass
    return False


def _level_section():
    world = get_editor_world()
    dirty_names = _dirty_package_names()
    if world is None:
        return {
            "path": "",
            "name": "",
            "isDirty": False,
            "isPartitioned": False,
            "dirtyPackageCount": len(dirty_names),
        }

    path = ""
    name = ""
    try:
        path = str(world.get_path_name())
        name = str(world.get_name())
    except Exception:
        pass

    package_name = ""
    try:
        package_name = str(world.get_outer().get_name())
    except Exception:
        pass
    is_dirty = package_name in dirty_names if package_name else False

    is_partitioned = False
    try:
        is_partitioned = bool(world.get_editor_property("world_partition"))
    except Exception:
        is_partitioned = False

    return {
        "path": path,
        "name": name,
        "isDirty": is_dirty,
        "isPartitioned": is_partitioned,
        "dirtyPackageCount": len(dirty_names),
    }


def _selection_section(limit):
    actors = actor_subsystem().get_selected_level_actors()
    total = len(actors)
    shown = actors[:limit] if limit >= 0 else actors
    return {
        "count": total,
        "actors": [actor_ref(actor) for actor in shown],
        "truncated": total > len(shown),
    }


def _viewport_section():
    try:
        info = editor_subsystem().get_level_viewport_camera_info()
    except Exception as exc:
        raise RpcError(
            "INTERNAL", "Failed to read viewport camera: %s" % exc, {"reason": str(exc)}
        )
    location = None
    rotation = None
    if isinstance(info, tuple):
        values = list(info)
        # Accept both (Location, Rotation) and (bool, Location, Rotation).
        for value in values:
            if location is None and getattr(value, "x", None) is not None:
                location = value
            elif rotation is None and getattr(value, "pitch", None) is not None:
                rotation = value
    if location is None or rotation is None:
        raise RpcError("INTERNAL", "Viewport camera info unavailable", {})
    return {
        "cameraLocation": vec_dict(location),
        "cameraRotation": rot_dict(rotation),
        "width": 0,
        "height": 0,
    }


def handle(server, params):
    check_keys(params, {"sections", "selectionLimit"})
    sections = get_list(
        params,
        "sections",
        default=DEFAULT_SECTIONS,
        max_items=len(ALL_SECTIONS),
        item_type=str,
    )
    for index, section in enumerate(sections):
        if section not in ALL_SECTIONS:
            raise RpcError(
                "INVALID_ARGUMENT",
                "sections[%d] must be one of %s"
                % (index, ", ".join(sorted(ALL_SECTIONS))),
                {
                    "issues": [
                        {
                            "path": "sections[%d]" % index,
                            "code": "invalid_enum_value",
                            "message": "must be one of %s" % ", ".join(sorted(ALL_SECTIONS)),
                        }
                    ]
                },
            )
    selection_limit = get_int(
        params, "selectionLimit", default=20, minimum=0, maximum=200
    )

    data = {}
    warnings = []

    if "editor" in sections:
        data["editor"] = _editor_section(server)
    if "level" in sections:
        data["level"] = _level_section()
    if "selection" in sections:
        data["selection"] = _selection_section(selection_limit)
    if "viewport" in sections:
        try:
            data["viewport"] = _viewport_section()
        except RpcError as exc:
            warnings.append("VIEWPORT_UNAVAILABLE: %s" % exc.message)
    if "capabilities" in sections:
        data["capabilities"] = dict(server.capabilities)
    if "policies" in sections:
        data["policies"] = server.settings.policy_snapshot()

    return HandlerResult(data, warnings)
