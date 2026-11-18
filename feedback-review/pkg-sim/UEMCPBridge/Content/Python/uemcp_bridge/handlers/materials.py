"""``material.params`` handler (architecture doc section 5.6)."""

from ..errors import RpcError
from . import (
    HandlerResult,
    asset_exists,
    check_keys,
    get_bool,
    get_enum,
    get_list,
    get_str,
    get_unreal,
    load_asset,
)

ALL_ACTIONS = {"list", "get", "set", "create_instance"}
PARAMETER_TYPES = {"scalar", "vector", "texture", "staticSwitch"}

_NAME_FUNCTIONS = {
    "scalar": "get_scalar_parameter_names",
    "vector": "get_vector_parameter_names",
    "texture": "get_texture_parameter_names",
    "staticSwitch": "get_static_switch_parameter_names",
}

_VALUE_GETTERS = {
    "scalar": "get_material_instance_scalar_parameter_value",
    "vector": "get_material_instance_vector_parameter_value",
    "texture": "get_material_instance_texture_parameter_value",
    "staticSwitch": "get_material_instance_static_switch_parameter_value",
}

_VALUE_SETTERS = {
    "scalar": "set_material_instance_scalar_parameter_value",
    "vector": "set_material_instance_vector_parameter_value",
    "texture": "set_material_instance_texture_parameter_value",
    "staticSwitch": "set_material_instance_static_switch_parameter_value",
}


def _material_path(params):
    path = get_str(params, "instancePath", max_length=512) or get_str(
        params, "materialPath", max_length=512
    )
    if not path:
        raise RpcError(
            "INVALID_ARGUMENT",
            "materialPath or instancePath is required",
            {
                "issues": [
                    {
                        "path": "materialPath",
                        "code": "required",
                        "message": "materialPath or instancePath is required",
                    }
                ]
            },
        )
    return path


def _load_material(path):
    unreal = get_unreal()
    asset = load_asset(path)
    if asset is None:
        raise RpcError("MATERIAL_NOT_FOUND", "Material not found: %s" % path, {"path": path})
    if not isinstance(asset, unreal.MaterialInterface):
        actual = ""
        try:
            actual = str(asset.get_class().get_name())
        except Exception:
            pass
        raise RpcError(
            "NOT_A_MATERIAL",
            "Asset is not a material: %s" % path,
            {"path": path, "actualClass": actual},
        )
    return asset


def _parameter_names(material, kind):
    unreal = get_unreal()
    function = getattr(unreal.MaterialEditingLibrary, _NAME_FUNCTIONS[kind])
    result = function(material)
    if isinstance(result, tuple):
        result = result[0] if result else []
    names = []
    for value in result or []:
        names.append(str(value))
    return names


def _all_parameters(material):
    inventory = {}
    for kind in ("scalar", "vector", "texture", "staticSwitch"):
        for name in _parameter_names(material, kind):
            inventory.setdefault(name, kind)
    return inventory


def _read_value(material, kind, name):
    unreal = get_unreal()
    if not isinstance(material, unreal.MaterialInstanceConstant):
        return None
    getter = getattr(unreal.MaterialEditingLibrary, _VALUE_GETTERS[kind])
    try:
        value = getter(material, unreal.Name(name))
    except Exception:
        return None
    if kind == "texture":
        try:
            return str(unreal.SystemLibrary.get_path_name(value)) if value else None
        except Exception:
            return None
    if kind == "vector":
        try:
            return {
                "r": float(value.r),
                "g": float(value.g),
                "b": float(value.b),
                "a": float(value.a),
            }
        except Exception:
            return None
    if kind == "scalar":
        try:
            return float(value)
        except Exception:
            return None
    return bool(value)


def _describe_parameters(material, requested_names=None):
    editable = bool(isinstance(material, get_unreal().MaterialInstanceConstant))
    inventory = _all_parameters(material)
    if requested_names is None:
        names = sorted(inventory.keys())
    else:
        names = []
        for name in requested_names:
            if name not in inventory:
                raise RpcError(
                    "PARAM_NOT_FOUND",
                    "Material parameter not found: %s" % name,
                    {
                        "parameterName": name,
                        "parameterType": "unknown",
                        "availableParameters": sorted(inventory.keys())[:50],
                    },
                )
            names.append(name)
    output = []
    for name in names:
        kind = inventory[name]
        output.append(
            {
                "name": name,
                "type": kind,
                "value": _read_value(material, kind, name),
                "editable": editable,
            }
        )
    return output


def _validate_parameters(raw_parameters):
    if not isinstance(raw_parameters, list) or not raw_parameters:
        raise RpcError(
            "INVALID_ARGUMENT",
            "parameters must be a non-empty array",
            {"issues": [{"path": "parameters", "code": "invalid_type", "message": "must be a non-empty array"}]},
        )
    if len(raw_parameters) > 50:
        raise RpcError(
            "INVALID_ARGUMENT",
            "parameters supports at most 50 items",
            {"issues": [{"path": "parameters", "code": "max_items", "message": "at most 50 items"}]},
        )
    seen = set()
    validated = []
    for index, item in enumerate(raw_parameters):
        path = "parameters[%d]" % index
        if not isinstance(item, dict):
            raise RpcError(
                "INVALID_ARGUMENT",
                "%s must be an object" % path,
                {"issues": [{"path": path, "code": "invalid_type", "message": "must be an object"}]},
            )
        check_keys(item, {"name", "type", "value"}, path)
        name = get_str(item, "name", required=True, max_length=128, path=path + ".name")
        kind = get_enum(item, "type", PARAMETER_TYPES, required=True, path=path + ".type")
        if name in seen:
            raise RpcError(
                "INVALID_ARGUMENT",
                "duplicate parameter: %s" % name,
                {"issues": [{"path": path + ".name", "code": "duplicate", "message": "duplicate parameter name"}]},
            )
        seen.add(name)
        value = item.get("value")
        if kind == "scalar":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RpcError(
                    "TYPE_MISMATCH",
                    "parameter %s expects a number" % name,
                    {"parameterName": name, "expected": "number", "actual": type(value).__name__},
                )
            value = float(value)
        elif kind == "vector":
            if not isinstance(value, dict):
                raise RpcError(
                    "TYPE_MISMATCH",
                    "parameter %s expects {r,g,b,a}" % name,
                    {"parameterName": name, "expected": "object", "actual": type(value).__name__},
                )
            check_keys(value, {"r", "g", "b", "a"}, path + ".value")
            for channel in ("r", "g", "b", "a"):
                if channel not in value:
                    raise RpcError(
                        "INVALID_ARGUMENT",
                        "%s.value.%s is required" % (path, channel),
                        {"issues": [{"path": "%s.value.%s" % (path, channel), "code": "required", "message": "is required"}]},
                    )
            value = unreal_linear_color(value)
        elif kind == "texture":
            if not isinstance(value, str) or not value:
                raise RpcError(
                    "TYPE_MISMATCH",
                    "parameter %s expects a texture path" % name,
                    {"parameterName": name, "expected": "string", "actual": type(value).__name__},
                )
        elif kind == "staticSwitch":
            if not isinstance(value, bool):
                raise RpcError(
                    "TYPE_MISMATCH",
                    "parameter %s expects a boolean" % name,
                    {"parameterName": name, "expected": "boolean", "actual": type(value).__name__},
                )
        validated.append({"name": name, "type": kind, "value": value})
    return validated


def unreal_linear_color(value):
    unreal = get_unreal()
    color = unreal.LinearColor()
    color.r = float(value["r"])
    color.g = float(value["g"])
    color.b = float(value["b"])
    color.a = float(value["a"])
    return color


def _apply_parameters(material, parameters):
    unreal = get_unreal()
    inventory = _all_parameters(material)
    missing = [item["name"] for item in parameters if item["name"] not in inventory]
    if missing:
        name = missing[0]
        raise RpcError(
            "PARAM_NOT_FOUND",
            "Material parameter not found: %s" % name,
            {
                "parameterName": name,
                "parameterType": "unknown",
                "availableParameters": sorted(inventory.keys())[:50],
            },
        )

    for item in parameters:
        name = item["name"]
        kind = item["type"]
        actual_kind = inventory[name]
        if actual_kind != kind:
            raise RpcError(
                "TYPE_MISMATCH",
                "parameter %s is %s, not %s" % (name, actual_kind, kind),
                {"parameterName": name, "expected": actual_kind, "actual": kind},
            )

    applied = []
    for item in parameters:
        name = item["name"]
        kind = item["type"]
        value = item["value"]
        if kind == "texture":
            texture = load_asset(value)
            if texture is None:
                raise RpcError(
                    "ASSET_NOT_FOUND", "Texture not found: %s" % value, {"assetPath": value}
                )
            value = texture
        setter = getattr(unreal.MaterialEditingLibrary, _VALUE_SETTERS[kind])
        ok = setter(material, unreal.Name(name), value)
        if not ok:
            raise RpcError(
                "EXECUTION_ERROR",
                "Failed to set material parameter %s" % name,
                {"parameterName": name},
            )
        applied.append(name)

    unreal.MaterialEditingLibrary.update_material_instance(material)
    return applied


def _split_asset_path(asset_path):
    normalized = asset_path.rstrip("/")
    if "." in normalized.rsplit("/", 1)[-1]:
        normalized = normalized.rsplit(".", 1)[0]
    if "/" not in normalized:
        raise RpcError(
            "INVALID_ARGUMENT",
            "instancePath must be a package path like /Game/Materials/MI_Name",
            {"issues": [{"path": "instancePath", "code": "invalid_format", "message": "expected /Game/... path"}]},
        )
    package_path, asset_name = normalized.rsplit("/", 1)
    return package_path, asset_name


def handle(server, params):
    check_keys(
        params,
        {
            "action",
            "materialPath",
            "instancePath",
            "parameterNames",
            "parameters",
            "save",
        },
    )
    action = get_enum(params, "action", ALL_ACTIONS, required=True)
    save = get_bool(params, "save", default=False)
    material_path = get_str(params, "materialPath", max_length=512)
    instance_path = get_str(params, "instancePath", max_length=512)
    parameter_names = get_list(
        params, "parameterNames", default=None, max_items=100, item_type=str
    ) or None

    if save and not server.settings.allow_write:
        raise RpcError(
            "PERMISSION_DENIED",
            "Saving is disabled (allowWrite=false)",
            {"gate": "bridge.allowWrite"},
        )

    if action == "list":
        material = _load_material(_material_path(params))
        return HandlerResult(
            {"parameters": _describe_parameters(material, parameter_names)}
        )

    if action == "get":
        material = _load_material(_material_path(params))
        return HandlerResult(
            {"parameters": _describe_parameters(material, parameter_names)}
        )

    if action == "set":
        unreal = get_unreal()
        path = instance_path or material_path
        if not path:
            raise RpcError(
                "INVALID_ARGUMENT",
                "instancePath is required for action 'set'",
                {"issues": [{"path": "instancePath", "code": "required", "message": "is required"}]},
            )
        material = _load_material(path)
        if not isinstance(material, unreal.MaterialInstanceConstant):
            actual = ""
            try:
                actual = str(material.get_class().get_name())
            except Exception:
                pass
            raise RpcError(
                "NOT_AN_INSTANCE",
                "Only MaterialInstanceConstant can be modified: %s" % path,
                {"path": path, "actualClass": actual},
            )
        raw_parameters = params.get("parameters")
        parameters = _validate_parameters(raw_parameters)
        applied = _apply_parameters(material, parameters)
        saved = False
        if save:
            saved = bool(asset_path_save(instance_path or path))
        return HandlerResult(
            {
                "materialPath": material_path or "",
                "instancePath": instance_path or path,
                "saved": saved,
                "parameters": [
                    {"name": name, "type": next(
                        item["type"] for item in parameters if item["name"] == name
                    ), "value": None, "editable": True}
                    for name in applied
                ],
            }
        )

    if action == "create_instance":
        if not material_path:
            raise RpcError(
                "INVALID_ARGUMENT",
                "materialPath is required for action 'create_instance'",
                {"issues": [{"path": "materialPath", "code": "required", "message": "is required"}]},
            )
        if not instance_path:
            raise RpcError(
                "INVALID_ARGUMENT",
                "instancePath is required for action 'create_instance'",
                {"issues": [{"path": "instancePath", "code": "required", "message": "is required"}]},
            )
        unreal = get_unreal()
        parent = _load_material(material_path)
        if asset_exists(instance_path):
            raise RpcError(
                "ALREADY_EXISTS",
                "Asset already exists: %s" % instance_path,
                {"path": instance_path},
            )
        package_path, asset_name = _split_asset_path(instance_path)
        factory = unreal.MaterialInstanceConstantFactoryNew()
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        instance = asset_tools.create_asset(
            asset_name, package_path, unreal.MaterialInstanceConstant, factory
        )
        if instance is None:
            raise RpcError(
                "EXECUTION_ERROR",
                "create_asset returned None for %s" % instance_path,
                {"path": instance_path},
            )
        unreal.MaterialEditingLibrary.set_material_instance_parent(instance, parent)
        unreal.MaterialEditingLibrary.update_material_instance(instance)
        saved = False
        if save:
            saved = bool(asset_path_save(instance_path))
        return HandlerResult(
            {
                "materialPath": material_path,
                "instancePath": instance_path,
                "created": True,
                "saved": saved,
                "parameters": _describe_parameters(instance),
            }
        )

    raise RpcError("INVALID_ARGUMENT", "Unsupported action: %s" % action, {})


def asset_path_save(path):
    try:
        return bool(
            get_unreal().get_editor_subsystem(
                get_unreal().EditorAssetSubsystem
            ).save_asset(path, False)
        )
    except Exception:
        return False
