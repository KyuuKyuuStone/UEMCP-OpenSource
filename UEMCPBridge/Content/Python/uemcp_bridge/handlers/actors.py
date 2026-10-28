"""``actor.query`` and ``actor.edit`` handlers (architecture doc 5.2 / 5.3)."""

from ..errors import RpcError
from . import (
    HandlerResult,
    actor_matches_class,
    actor_ref,
    actor_subsystem,
    actor_transform,
    check_keys,
    ensure_not_pie,
    get_bool,
    get_enum,
    get_int,
    get_list,
    get_obj,
    get_str,
    get_unreal,
    load_asset,
    resolve_actor,
    resolve_actor_class,
    rotator,
    selector,
    vec3,
)

QUERY_FIELDS = {
    "identity",
    "transform",
    "bounds",
    "tags",
    "components",
    "mobility",
    "folder",
}

OP_ALLOWED_KEYS = {
    "spawn": {
        "op",
        "class",
        "assetPath",
        "location",
        "rotation",
        "scale",
        "label",
        "tags",
        "folderPath",
        "selectAfterSpawn",
    },
    "delete": {"op", "selector", "confirm"},
    "set_transform": {"op", "selector", "location", "rotation", "scale", "snapToGrid"},
    "set_properties": {"op", "selector", "properties"},
    "duplicate": {"op", "selector", "count", "offset", "labelSuffix"},
    "select": {"op", "selector", "mode"},
}

PROPERTY_KEYS = {
    "label",
    "hidden",
    "mobility",
    "folderPath",
    "tags",
    "staticMesh",
    "materials",
}

_MOBILITY = {
    "static": "STATIC",
    "stationary": "STATIONARY",
    "movable": "MOVABLE",
}


# --------------------------------------------------------------------------
# actor.query
# --------------------------------------------------------------------------

def _mobility_name(actor):
    unreal = get_unreal()
    value = None
    try:
        value = actor.get_editor_property("mobility")
    except Exception:
        try:
            value = actor.root_component.get_editor_property("mobility")
        except Exception:
            value = None
    if value is None:
        return "static"
    name = str(getattr(value, "name", value)).lower()
    if "stationary" in name:
        return "stationary"
    if "movable" in name:
        return "movable"
    return "static"


def _actor_bounds(actor):
    try:
        result = actor.get_actor_bounds(False)
    except Exception:
        return None
    if not isinstance(result, tuple):
        return None
    origin = None
    extent = None
    for value in result:
        if origin is None and getattr(value, "x", None) is not None:
            origin = value
        elif extent is None and getattr(value, "x", None) is not None:
            extent = value
    if origin is None or extent is None:
        return None
    return {
        "origin": {"x": float(origin.x), "y": float(origin.y), "z": float(origin.z)},
        "extent": {"x": float(extent.x), "y": float(extent.y), "z": float(extent.z)},
    }


def _actor_components(actor):
    unreal = get_unreal()
    components = []
    try:
        entries = actor.get_components_by_class(unreal.ActorComponent)
    except Exception:
        entries = []
    for component in entries:
        try:
            components.append(
                {
                    "name": str(component.get_name()),
                    "class": str(component.get_class().get_name()),
                }
            )
        except Exception:
            continue
    return components


def _actor_tags(actor):
    tags = []
    try:
        values = actor.get_editor_property("tags")
        tags = [str(item) for item in values]
    except Exception:
        try:
            tags = [str(item) for item in actor.tags]
        except Exception:
            tags = []
    return tags


def _actor_folder(actor):
    try:
        return str(actor.get_folder_path())
    except Exception:
        return ""


def _query_actor(actor, fields):
    item = actor_ref(actor)
    if "transform" in fields:
        item["transform"] = actor_transform(actor)
    if "bounds" in fields:
        bounds = _actor_bounds(actor)
        if bounds is not None:
            item["bounds"] = bounds
    if "tags" in fields:
        item["tags"] = _actor_tags(actor)
    if "mobility" in fields:
        item["mobility"] = _mobility_name(actor)
    if "folder" in fields:
        item["folderPath"] = _actor_folder(actor)
    if "components" in fields:
        item["components"] = _actor_components(actor)
    return item


def _filter_actors(actors, filters):
    unreal = get_unreal()
    class_name = filters.get("class")
    class_filter = None
    if class_name:
        class_filter = resolve_actor_class(class_name)

    name_contains = (filters.get("nameContains") or "").lower()
    label_contains = (filters.get("labelContains") or "").lower()
    tags = filters.get("tags") or {}
    folders = filters.get("folders") or []
    component_class_name = filters.get("hasComponentClass")

    component_class = None
    if component_class_name:
        component_class = getattr(unreal, component_class_name, None)
        if not isinstance(component_class, type):
            try:
                component_class = unreal.load_class(None, component_class_name)
            except Exception:
                component_class = None
        if component_class is None:
            raise RpcError(
                "CLASS_NOT_FOUND",
                "Component class not found: %s" % component_class_name,
                {"className": component_class_name},
            )

    result = []
    for actor in actors:
        if class_filter is not None and not actor_matches_class(actor, class_filter):
            continue
        if name_contains and name_contains not in str(actor.get_name()).lower():
            continue
        if label_contains and label_contains not in str(actor.get_actor_label()).lower():
            continue
        if tags:
            actor_tags = _actor_tags(actor)
            tag_names = set(actor_tags)
            matched_tags = True
            for key, value in tags.items():
                if key not in tag_names:
                    matched_tags = False
                    break
                if str(value) and str(value) not in actor_tags:
                    matched_tags = False
                    break
            if not matched_tags:
                continue
        if folders:
            folder = _actor_folder(actor)
            if not any(folder.startswith(prefix) for prefix in folders):
                continue
        if component_class is not None:
            try:
                if not actor.get_components_by_class(component_class):
                    continue
            except Exception:
                continue
        result.append(actor)
    return result


def handle_query(server, params):
    check_keys(
        params,
        {"scope", "filter", "fields", "limit", "offset", "sortBy"},
    )
    scope = get_enum(params, "scope", {"level", "selection"}, default="level")
    filter_obj = get_obj(
        params,
        "filter",
        allowed_keys={
            "class",
            "nameContains",
            "labelContains",
            "tags",
            "folders",
            "hasComponentClass",
        },
    ) or {}
    fields = get_list(
        params,
        "fields",
        default=["identity", "transform", "tags"],
        max_items=len(QUERY_FIELDS),
        item_type=str,
    )
    for field_name in fields:
        if field_name not in QUERY_FIELDS:
            raise RpcError(
                "INVALID_ARGUMENT",
                "fields contains unsupported value: %s" % field_name,
                {
                    "issues": [
                        {
                            "path": "fields",
                            "code": "invalid_enum_value",
                            "message": "must be one of %s" % ", ".join(sorted(QUERY_FIELDS)),
                        }
                    ]
                },
            )
    limit = get_int(params, "limit", default=50, minimum=1, maximum=1000)
    offset = get_int(params, "offset", default=0, minimum=0, maximum=100000)
    sort_by = get_enum(
        params, "sortBy", {"name", "label", "class", "path"}, default="name"
    )

    subsystem = actor_subsystem()
    if scope == "level":
        actors = subsystem.get_all_level_actors()
    else:
        actors = subsystem.get_selected_level_actors()

    # Validate the class filter even when no actors exist.
    if filter_obj.get("class"):
        resolve_actor_class(filter_obj["class"])

    filtered = _filter_actors(actors, filter_obj)

    def sort_key(actor):
        if sort_by == "label":
            return str(actor.get_actor_label())
        if sort_by == "class":
            return str(actor.get_class().get_name())
        if sort_by == "path":
            return str(actor.get_path_name())
        return str(actor.get_name())

    filtered.sort(key=sort_key)
    total = len(filtered)
    window = filtered[offset : offset + limit]

    return HandlerResult(
        {
            "total": total,
            "returned": len(window),
            "truncated": offset + len(window) < total,
            "actors": [_query_actor(actor, fields) for actor in window],
        }
    )


# --------------------------------------------------------------------------
# actor.edit
# --------------------------------------------------------------------------

def _validate_operations(raw_operations):
    if not isinstance(raw_operations, list):
        raise RpcError(
            "INVALID_ARGUMENT",
            "operations must be an array",
            {"issues": [{"path": "operations", "code": "invalid_type", "message": "must be an array"}]},
        )
    if not raw_operations:
        raise RpcError(
            "INVALID_ARGUMENT",
            "operations must contain at least one item",
            {"issues": [{"path": "operations", "code": "min_items", "message": "must not be empty"}]},
        )
    if len(raw_operations) > 50:
        raise RpcError(
            "INVALID_ARGUMENT",
            "operations supports at most 50 items",
            {"issues": [{"path": "operations", "code": "max_items", "message": "at most 50 items"}]},
        )
    for index, operation in enumerate(raw_operations):
        path = "operations[%d]" % index
        if not isinstance(operation, dict):
            raise RpcError(
                "INVALID_ARGUMENT",
                "%s must be an object" % path,
                {"issues": [{"path": path, "code": "invalid_type", "message": "must be an object"}]},
            )
        op_name = operation.get("op")
        if op_name not in OP_ALLOWED_KEYS:
            raise RpcError(
                "INVALID_ARGUMENT",
                "%s.op must be one of %s" % (path, ", ".join(sorted(OP_ALLOWED_KEYS))),
                {
                    "issues": [
                        {
                            "path": path + ".op",
                            "code": "invalid_enum_value",
                            "message": "must be one of %s" % ", ".join(sorted(OP_ALLOWED_KEYS)),
                        }
                    ]
                },
            )
        check_keys(operation, OP_ALLOWED_KEYS[op_name], path)

        if op_name in ("delete", "set_transform", "set_properties", "duplicate", "select"):
            selector(operation.get("selector"), path + ".selector")
        if op_name == "spawn":
            get_str(operation, "class", required=True, max_length=256, path=path + ".class")
            vec3(operation.get("location"), path + ".location")
            rotator(operation.get("rotation"), path + ".rotation")
            vec3(operation.get("scale"), path + ".scale")
            get_str(operation, "label", max_length=128, path=path + ".label")
            get_list(operation, "tags", default=[], max_items=20, item_type=str, path=path + ".tags")
            get_str(operation, "folderPath", max_length=256, path=path + ".folderPath")
            get_bool(operation, "selectAfterSpawn", default=False, path=path + ".selectAfterSpawn")
        elif op_name == "set_transform":
            vec3(operation.get("location"), path + ".location")
            rotator(operation.get("rotation"), path + ".rotation")
            vec3(operation.get("scale"), path + ".scale")
            get_bool(operation, "snapToGrid", default=False, path=path + ".snapToGrid")
        elif op_name == "set_properties":
            properties = get_obj(
                operation, "properties", path=path + ".properties", allowed_keys=PROPERTY_KEYS, required=True
            )
            if "mobility" in properties:
                get_enum(
                    properties,
                    "mobility",
                    {"static", "stationary", "movable"},
                    required=True,
                    path=path + ".properties.mobility",
                )
            if "tags" in properties:
                get_list(
                    properties, "tags", default=[], max_items=20, item_type=str,
                    path=path + ".properties.tags",
                )
            if "materials" in properties:
                get_obj(properties, "materials", path=path + ".properties.materials")
        elif op_name == "duplicate":
            get_int(operation, "count", default=1, minimum=1, maximum=50, path=path + ".count")
            vec3(operation.get("offset"), path + ".offset")
            get_str(operation, "labelSuffix", default="_copy", max_length=64, path=path + ".labelSuffix")
        elif op_name == "select":
            get_enum(
                operation, "mode", {"replace", "add", "remove"}, default="replace",
                path=path + ".mode",
            )
    return raw_operations


def _apply_asset(actor, asset, asset_path):
    unreal = get_unreal()
    applied = False
    if isinstance(asset, unreal.StaticMesh):
        component = getattr(actor, "static_mesh_component", None)
        if component is not None:
            component.set_static_mesh(asset)
            applied = True
    elif isinstance(asset, unreal.SkeletalMesh):
        component = getattr(actor, "skeletal_mesh_component", None)
        if component is not None:
            component.set_skeletal_mesh(asset)
            applied = True
    if not applied:
        raise RpcError(
            "EXECUTION_ERROR",
            "assetPath %s cannot be applied to %s" % (asset_path, actor.get_class().get_name()),
            {"assetPath": asset_path},
        )


def _spawn(operation, path):
    unreal = get_unreal()
    actor_class = resolve_actor_class(get_str(operation, "class", required=True, path=path + ".class"))
    location = vec3(operation.get("location"), path + ".location") or unreal.Vector(0.0, 0.0, 0.0)
    rotation = rotator(operation.get("rotation"), path + ".rotation") or unreal.Rotator()
    scale = vec3(operation.get("scale"), path + ".scale")
    label = get_str(operation, "label", max_length=128, path=path + ".label")
    tags = get_list(operation, "tags", default=[], max_items=20, item_type=str, path=path + ".tags")
    folder_path = get_str(operation, "folderPath", max_length=256, path=path + ".folderPath")
    select_after = get_bool(operation, "selectAfterSpawn", default=False, path=path + ".selectAfterSpawn")
    asset_path = get_str(operation, "assetPath", max_length=512, path=path + ".assetPath")

    actor = actor_subsystem().spawn_actor_from_class(actor_class, location, rotation)
    if actor is None:
        raise RpcError(
            "EXECUTION_ERROR",
            "spawn_actor_from_class returned None",
            {"className": get_str(operation, "class")},
        )
    if scale is not None:
        actor.set_actor_scale3d(scale)
    if label:
        actor.set_actor_label(label)
    if tags:
        try:
            actor.set_editor_property("tags", [unreal.Name(item) for item in tags])
        except Exception:
            pass
    if folder_path:
        actor.set_folder_path(folder_path)
    if asset_path:
        asset = load_asset(asset_path)
        if asset is None:
            raise RpcError(
                "ASSET_NOT_FOUND", "Asset not found: %s" % asset_path, {"assetPath": asset_path}
            )
        _apply_asset(actor, asset, asset_path)
    if select_after:
        actor_subsystem().set_selected_level_actors([actor])
    return actor


def _apply_mobility(actor, mobility):
    unreal = get_unreal()
    enum_value = getattr(unreal.ComponentMobility, _MOBILITY[mobility])
    root = getattr(actor, "root_component", None)
    if root is not None:
        root.set_editor_property("mobility", enum_value)
    else:
        actor.set_editor_property("mobility", enum_value)


def _apply_properties(actor, properties):
    unreal = get_unreal()
    modified = []

    label = properties.get("label")
    if label is not None:
        actor.set_actor_label(str(label))
        modified.append("label")

    hidden = properties.get("hidden")
    if hidden is not None:
        actor.set_editor_property("bHidden", bool(hidden))
        modified.append("hidden")

    mobility = properties.get("mobility")
    if mobility is not None:
        _apply_mobility(actor, mobility)
        modified.append("mobility")

    folder_path = properties.get("folderPath")
    if folder_path is not None:
        actor.set_folder_path(str(folder_path))
        modified.append("folderPath")

    tags = properties.get("tags")
    if tags is not None:
        actor.set_editor_property("tags", [unreal.Name(str(item)) for item in tags])
        modified.append("tags")

    static_mesh_path = properties.get("staticMesh")
    if static_mesh_path:
        mesh = load_asset(static_mesh_path)
        if mesh is None:
            raise RpcError(
                "ASSET_NOT_FOUND",
                "Asset not found: %s" % static_mesh_path,
                {"assetPath": static_mesh_path},
            )
        component = getattr(actor, "static_mesh_component", None)
        if component is None:
            raise RpcError(
                "EXECUTION_ERROR",
                "Actor has no static mesh component",
                {"actorPath": str(actor.get_path_name())},
            )
        component.set_static_mesh(mesh)
        modified.append("staticMesh")

    materials = properties.get("materials")
    if materials:
        mesh_components = list(actor.get_components_by_class(unreal.MeshComponent))
        for key, material_path in materials.items():
            material = load_asset(str(material_path))
            if material is None:
                raise RpcError(
                    "ASSET_NOT_FOUND",
                    "Material not found: %s" % material_path,
                    {"assetPath": str(material_path)},
                )
            target = None
            slot = 0
            key_text = str(key)
            if key_text.isdigit():
                slot = int(key_text)
                target = mesh_components[0] if mesh_components else None
            else:
                for component in mesh_components:
                    try:
                        if str(component.get_name()) == key_text:
                            target = component
                            break
                    except Exception:
                        continue
            if target is None:
                raise RpcError(
                    "INVALID_ARGUMENT",
                    "Material target not found: %s" % key_text,
                    {
                        "issues": [
                            {
                                "path": "properties.materials.%s" % key_text,
                                "code": "not_found",
                                "message": "no matching mesh component or slot",
                            }
                        ]
                    },
                )
            target.set_material(slot, material)
        modified.append("materials")

    return modified


def _execute_operation(operation, index):
    unreal = get_unreal()
    path = "operations[%d]" % index
    op_name = operation["op"]

    if op_name == "spawn":
        actor = _spawn(operation, path)
        return {
            "index": index,
            "op": op_name,
            "ok": True,
            "created": [actor_ref(actor)],
        }

    if op_name == "delete":
        sel = selector(operation.get("selector"), path + ".selector")
        actor = resolve_actor(sel)
        actor_path = str(actor.get_path_name())
        removed = bool(actor_subsystem().destroy_actor(actor))
        return {
            "index": index,
            "op": op_name,
            "ok": removed,
            "deleted": [actor_path] if removed else [],
        }

    if op_name == "set_transform":
        sel = selector(operation.get("selector"), path + ".selector")
        actor = resolve_actor(sel)
        location = vec3(operation.get("location"), path + ".location")
        rotation = rotator(operation.get("rotation"), path + ".rotation")
        scale = vec3(operation.get("scale"), path + ".scale")
        if location is not None:
            actor.set_actor_location(location, False, False)
        if rotation is not None:
            actor.set_actor_rotation(rotation, False)
        if scale is not None:
            actor.set_actor_scale3d(scale)
        return {
            "index": index,
            "op": op_name,
            "ok": True,
            "modified": [str(actor.get_path_name())],
        }

    if op_name == "set_properties":
        sel = selector(operation.get("selector"), path + ".selector")
        actor = resolve_actor(sel)
        properties = operation["properties"]
        modified = _apply_properties(actor, properties)
        return {
            "index": index,
            "op": op_name,
            "ok": True,
            "modified": [str(actor.get_path_name())],
            "properties": modified,
        }

    if op_name == "duplicate":
        sel = selector(operation.get("selector"), path + ".selector")
        actor = resolve_actor(sel)
        count = get_int(operation, "count", default=1, minimum=1, maximum=50, path=path + ".count")
        offset = vec3(operation.get("offset"), path + ".offset") or unreal.Vector(0.0, 0.0, 0.0)
        suffix = get_str(operation, "labelSuffix", default="_copy", path=path + ".labelSuffix")
        base_label = str(actor.get_actor_label())
        created = []
        for copy_index in range(count):
            step = unreal.Vector(offset.x * (copy_index + 1), offset.y * (copy_index + 1), offset.z * (copy_index + 1))
            duplicate = actor_subsystem().duplicate_actor(actor, None, step)
            if duplicate is None:
                raise RpcError(
                    "EXECUTION_ERROR",
                    "duplicate_actor returned None",
                    {"actorPath": str(actor.get_path_name())},
                )
            try:
                duplicate.set_actor_label("%s%s%d" % (base_label, suffix, copy_index + 1))
            except Exception:
                pass
            created.append(actor_ref(duplicate))
        return {"index": index, "op": op_name, "ok": True, "created": created}

    if op_name == "select":
        sel = selector(operation.get("selector"), path + ".selector")
        actor = resolve_actor(sel)
        mode = get_enum(operation, "mode", {"replace", "add", "remove"}, default="replace", path=path + ".mode")
        subsystem = actor_subsystem()
        current = list(subsystem.get_selected_level_actors())
        if mode == "replace":
            selected = [actor]
        elif mode == "add":
            selected = current if actor in current else current + [actor]
        else:
            selected = [item for item in current if item != actor]
        subsystem.set_selected_level_actors(selected)
        return {
            "index": index,
            "op": op_name,
            "ok": True,
            "modified": [str(actor.get_path_name())],
        }

    raise RpcError("INVALID_ARGUMENT", "Unsupported operation: %s" % op_name, {})


def _dry_run_operation(operation, index):
    unreal = get_unreal()
    path = "operations[%d]" % index
    op_name = operation["op"]

    if op_name == "spawn":
        class_name = get_str(operation, "class", required=True, path=path + ".class")
        resolve_actor_class(class_name)
        asset_path = get_str(operation, "assetPath", max_length=512, path=path + ".assetPath")
        if asset_path and load_asset(asset_path) is None:
            raise RpcError(
                "ASSET_NOT_FOUND", "Asset not found: %s" % asset_path, {"assetPath": asset_path}
            )
        return {
            "index": index,
            "op": op_name,
            "ok": True,
            "created": [
                {
                    "actorPath": "",
                    "objectPath": "",
                    "name": "",
                    "label": get_str(operation, "label", default="") or "",
                    "class": class_name,
                    "classPath": "",
                    "levelPath": "",
                    "wouldCreate": True,
                }
            ],
        }

    if op_name == "delete":
        sel = selector(operation.get("selector"), path + ".selector")
        actor = resolve_actor(sel)
        return {
            "index": index,
            "op": op_name,
            "ok": True,
            "deleted": [str(actor.get_path_name())],
            "wouldDelete": True,
        }

    if op_name in ("set_transform", "set_properties", "duplicate", "select"):
        sel = selector(operation.get("selector"), path + ".selector")
        actor = resolve_actor(sel)
        return {
            "index": index,
            "op": op_name,
            "ok": True,
            "modified": [str(actor.get_path_name())],
            "wouldModify": True,
        }

    raise RpcError("INVALID_ARGUMENT", "Unsupported operation: %s" % op_name, {})


def handle_edit(server, params):
    check_keys(params, {"operations", "atomic", "dryRun", "transactionName"})
    operations = _validate_operations(params.get("operations"))
    atomic = get_bool(params, "atomic", default=True)
    dry_run = get_bool(params, "dryRun", default=False)
    transaction_name = get_str(
        params, "transactionName", default="UEMCP Actor Edit", max_length=128
    ) or "UEMCP Actor Edit"

    ensure_not_pie("actor edit")

    if dry_run:
        results = [_dry_run_operation(operation, index) for index, operation in enumerate(operations)]
        return HandlerResult(
            {
                "dryRun": True,
                "results": results,
                "summary": {
                    "requested": len(operations),
                    "succeeded": len(results),
                    "failed": 0,
                    "rolledBack": False,
                },
            }
        )

    unreal = get_unreal()
    results = []
    warnings = []
    rolled_back = False

    try:
        with unreal.ScopedEditorTransaction(transaction_name) as transaction:
            for index, operation in enumerate(operations):
                try:
                    results.append(_execute_operation(operation, index))
                except RpcError as exc:
                    results.append(
                        {
                            "index": index,
                            "op": operation.get("op", ""),
                            "ok": False,
                            "error": {
                                "code": exc.code,
                                "message": exc.message,
                                "retryable": exc.retryable,
                                "details": exc.details,
                            },
                        }
                    )
                    if atomic:
                        rolled_back = True
                        try:
                            transaction.cancel()
                        except Exception:
                            rolled_back = False
                            warnings.append("ROLLBACK_FAILED: ScopedEditorTransaction.cancel() failed")
                        raise
    except RpcError as exc:
        if not atomic:
            raise
        succeeded = len([item for item in results if item.get("ok")])
        failed = len([item for item in results if not item.get("ok")])
        raise RpcError(
            "TRANSACTION_FAILED",
            "Transaction rolled back after %s: %s" % (exc.code, exc.message),
            {
                "rolledBack": rolled_back,
                "reason": exc.code,
                "failedIndex": results[-1]["index"] if results else -1,
                "succeeded": succeeded,
                "failed": failed,
            },
        )

    succeeded = len([item for item in results if item.get("ok")])
    failed = len(results) - succeeded

    if failed and not atomic:
        warnings.append("PARTIAL_SUCCESS: %d operation(s) failed" % failed)

    return HandlerResult(
        {
            "dryRun": False,
            "results": results,
            "summary": {
                "requested": len(operations),
                "succeeded": succeeded,
                "failed": failed,
                "rolledBack": False,
            },
        },
        warnings,
    )
