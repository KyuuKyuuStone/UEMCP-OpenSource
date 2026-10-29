"""``blueprint.query`` handler (architecture doc section 5.10).

Node editing is not available through the UE 5.4 Python API; such requests
return ``CAPABILITY_UNAVAILABLE`` (architecture doc section 8.1).
"""

from ..errors import RpcError
from . import (
    HandlerResult,
    check_keys,
    get_bool,
    get_enum,
    get_int,
    get_list,
    get_str,
    get_unreal,
    load_asset,
)

ALL_ACTIONS = {"query", "compile"}
EDIT_ACTIONS = {
    "edit",
    "add_node",
    "add_nodes",
    "create_node",
    "connect",
    "connect_pins",
    "link",
    "disconnect",
    "disconnect_pins",
    "delete_node",
    "remove_node",
    "add_variable",
    "remove_variable",
    "edit_anim_blueprint",
    "add_state",
    "connect_state",
}
INCLUDE_VALUES = {
    "parent",
    "variables",
    "components",
    "graphs",
    "interfaces",
    "compileState",
}
DEFAULT_INCLUDE = ["parent", "variables", "graphs", "compileState"]

# EPropertyFlags (stable across UE versions).
_CPF_EDIT = 0x0000000000000001
_CPF_NET = 0x0000000000000020
_CPF_EXPOSE_ON_SPAWN = 0x0000000000000080


def _describe_exception(exc):
    message = str(exc)
    return "%s: %s" % (exc.__class__.__name__, message) if message else exc.__class__.__name__


_STRUCTURE_PROBES = (
    "parent_class",
    "new_variables",
    "ubergraph_pages",
    "function_graphs",
    "macro_graphs",
)


def _structure_diagnostics(blueprint):
    """Record what each introspection probe returned or raised.

    Used to turn a silent "empty success" into an actionable error: when the
    editor Python API exposes none of the structure properties we report the
    per-property outcome instead of returning an empty blueprint.
    """
    diagnostics = {}
    for prop in _STRUCTURE_PROBES:
        try:
            value = blueprint.get_editor_property(prop)
        except Exception as exc:
            diagnostics[prop] = {"ok": False, "error": _describe_exception(exc)}
            continue
        try:
            count = len(value) if isinstance(value, (list, tuple)) else None
        except Exception:
            count = None
        diagnostics[prop] = {"ok": True, "type": type(value).__name__, "count": count}
    return diagnostics


def _load_blueprint(path):
    unreal = get_unreal()
    asset = load_asset(path)
    if asset is None:
        raise RpcError(
            "BLUEPRINT_NOT_FOUND",
            "Blueprint not found: %s" % path,
            {"blueprintPath": path},
        )
    if not isinstance(asset, unreal.Blueprint):
        actual = ""
        try:
            actual = str(asset.get_class().get_name())
        except Exception:
            pass
        raise RpcError(
            "NOT_A_BLUEPRINT",
            "Asset is not a Blueprint: %s" % path,
            {"path": path, "actualClass": actual},
        )
    return asset


def _pin_type_string(pin_type):
    unreal = get_unreal()
    try:
        category = str(getattr(pin_type, "pin_category", ""))
        sub_category = str(getattr(pin_type, "pin_sub_category", ""))
        sub_object = getattr(pin_type, "pin_sub_object", None)
    except Exception:
        return ""
    if sub_object is not None:
        try:
            sub_category = str(unreal.SystemLibrary.get_path_name(sub_object)) or sub_category
        except Exception:
            pass
    if sub_category:
        return "%s:%s" % (category, sub_category)
    return category


def _variables(bp):
    variables = []
    try:
        entries = bp.get_editor_property("new_variables")
    except Exception:
        return variables
    for entry in entries or []:
        flags = 0
        try:
            flags = int(getattr(entry, "property_flags", 0) or 0)
        except Exception:
            flags = 0
        variables.append(
            {
                "name": str(getattr(entry, "var_name", "")),
                "type": _pin_type_string(getattr(entry, "var_type", None)),
                "defaultValue": str(getattr(entry, "default_value", "")),
                "instanceEditable": bool(flags & _CPF_EDIT),
                "exposeOnSpawn": bool(flags & _CPF_EXPOSE_ON_SPAWN),
                "replicated": bool(flags & _CPF_NET),
            }
        )
    return variables


def _components(bp):
    components = []
    try:
        templates = bp.get_editor_property("component_templates")
    except Exception:
        templates = []
    for template in templates or []:
        class_name = ""
        try:
            component_class = getattr(template, "component_class", None)
            class_name = str(component_class.get_name()) if component_class else ""
        except Exception:
            class_name = ""
        components.append(
            {
                "name": str(getattr(template, "component_name", "")),
                "class": class_name,
                "parent": None,
            }
        )
    return components


def _node_count(graph):
    try:
        return len(graph.get_editor_property("nodes"))
    except Exception:
        return 0


def _graphs(bp):
    events = []
    functions = []
    macros = []
    try:
        for graph in bp.get_editor_property("ubergraph_pages") or []:
            events.append(graph)
    except Exception:
        pass
    try:
        for graph in bp.get_editor_property("function_graphs") or []:
            functions.append(graph)
    except Exception:
        pass
    try:
        for graph in bp.get_editor_property("macro_graphs") or []:
            macros.append(graph)
    except Exception:
        pass
    return events, functions, macros


def _graph_entries(events, functions, macros):
    entries = []
    for graph in events:
        entries.append((graph, "event"))
    for graph in functions:
        entries.append((graph, "function"))
    for graph in macros:
        entries.append((graph, "macro"))
    result = []
    for graph, kind in entries:
        try:
            name = str(graph.get_name())
        except Exception:
            name = ""
        result.append(
            {"name": name, "kind": kind, "nodeCount": _node_count(graph)}
        )
    return result


def _interfaces(bp):
    names = []
    try:
        entries = bp.get_editor_property("implemented_interfaces")
    except Exception:
        return names
    for entry in entries or []:
        try:
            interface = getattr(entry, "interface", None)
            names.append(str(interface.get_name()) if interface else "")
        except Exception:
            continue
    return [name for name in names if name]


def _compile_state(bp):
    raw = None
    try:
        raw = bp.get_editor_property("status")
    except Exception:
        raw = None
    name = str(getattr(raw, "name", raw) or "").upper().replace("_", "")
    if "UPTODATE" in name:
        status = "up_to_date"
    elif "DIRTY" in name:
        status = "dirty"
    elif "ERROR" in name:
        status = "error"
    else:
        status = "unknown"
    return {"status": status, "errors": 0, "warnings": 0}


def _read_nodes(graph, limit):
    unreal = get_unreal()
    nodes = graph.get_editor_property("nodes")
    output = []
    for node in list(nodes or [])[:limit]:
        guid = ""
        try:
            guid = str(node.get_editor_property("node_guid"))
        except Exception:
            pass
        x = 0
        y = 0
        try:
            x = int(node.get_editor_property("node_pos_x"))
            y = int(node.get_editor_property("node_pos_y"))
        except Exception:
            pass
        title = ""
        try:
            title = str(node.get_editor_property("node_comment") or "")
        except Exception:
            title = ""
        if not title:
            try:
                title = str(node.get_name())
            except Exception:
                title = ""
        class_name = ""
        try:
            class_name = str(node.get_class().get_name())
        except Exception:
            pass

        pins = []
        try:
            raw_pins = node.get_editor_property("pins") or []
        except Exception:
            raw_pins = []
        for pin in raw_pins:
            pin_name = ""
            try:
                pin_name = str(pin.get_editor_property("pin_name"))
            except Exception:
                pass
            direction_raw = None
            try:
                direction_raw = pin.get_editor_property("direction")
            except Exception:
                pass
            direction_text = str(getattr(direction_raw, "name", direction_raw)).lower()
            direction = "input" if "input" in direction_text else "output"
            pin_type_text = ""
            try:
                pin_type_text = _pin_type_string(pin.get_editor_property("pin_type"))
            except Exception:
                pass
            linked = []
            try:
                for linked_pin in pin.get_editor_property("linked_to") or []:
                    try:
                        linked.append(str(linked_pin.get_owning_node().get_name()))
                    except Exception:
                        continue
            except Exception:
                pass
            pins.append(
                {
                    "name": pin_name,
                    "direction": direction,
                    "type": pin_type_text,
                    "linkedTo": linked,
                }
            )

        output.append(
            {
                "guid": guid,
                "class": class_name,
                "title": title,
                "x": x,
                "y": y,
                "pins": pins,
            }
        )
    return output


def _save_asset(path):
    try:
        unreal = get_unreal()
        return bool(
            unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_asset(
                path, False
            )
        )
    except Exception:
        return False


def handle(server, params):
    action = params.get("action")
    if action in EDIT_ACTIONS:
        raise RpcError(
            "CAPABILITY_UNAVAILABLE",
            "Blueprint node editing is not available in UE 5.4 Python",
            {
                "capability": "blueprintNodeEdit",
                "action": action,
                "suggestion": "需要 C++ 辅助模块（P2）",
            },
        )

    check_keys(
        params,
        {
            "action",
            "blueprintPath",
            "include",
            "graphName",
            "includeNodes",
            "nodeLimit",
            "save",
        },
    )
    action = get_enum(params, "action", ALL_ACTIONS, required=True)
    blueprint_path = get_str(
        params, "blueprintPath", max_length=512, required=True
    )
    include = get_list(
        params, "include", default=DEFAULT_INCLUDE, max_items=len(INCLUDE_VALUES),
        item_type=str,
    )
    for index, value in enumerate(include):
        if value not in INCLUDE_VALUES:
            raise RpcError(
                "INVALID_ARGUMENT",
                "include[%d] must be one of %s"
                % (index, ", ".join(sorted(INCLUDE_VALUES))),
                {
                    "issues": [
                        {
                            "path": "include[%d]" % index,
                            "code": "invalid_enum_value",
                            "message": "must be one of %s" % ", ".join(sorted(INCLUDE_VALUES)),
                        }
                    ]
                },
            )
    graph_name = get_str(params, "graphName", max_length=256)
    include_nodes = get_bool(params, "includeNodes", default=False)
    node_limit = get_int(params, "nodeLimit", default=500, minimum=1, maximum=2000)
    save = get_bool(params, "save", default=False)

    if save and not server.settings.allow_write:
        raise RpcError(
            "PERMISSION_DENIED",
            "Saving is disabled (allowWrite=false)",
            {"gate": "bridge.allowWrite"},
        )

    blueprint = _load_blueprint(blueprint_path)
    unreal = get_unreal()
    warnings = []

    if action == "compile":
        try:
            unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
        except Exception as exc:
            raise RpcError(
                "COMPILE_FAILED",
                "Blueprint compilation raised: %s" % exc,
                {"blueprintPath": blueprint_path, "errors": [str(exc)], "warnings": []},
            )
        state = _compile_state(blueprint)
        if state["status"] == "error":
            raise RpcError(
                "COMPILE_FAILED",
                "Blueprint still has compile errors: %s" % blueprint_path,
                {"blueprintPath": blueprint_path, "errors": [], "warnings": []},
            )
        saved = False
        if save:
            saved = _save_asset(blueprint_path)
            if not saved:
                warnings.append("SAVE_FAILED: save_asset returned false")
        return HandlerResult(
            {
                "blueprintPath": blueprint_path,
                "compileState": state,
                "saved": saved,
            },
            warnings,
        )

    # action == "query"
    data = {"blueprintPath": blueprint_path}
    structure_errors = {}

    if "parent" in include:
        try:
            parent = blueprint.get_editor_property("parent_class")
            data["parentClass"] = str(parent.get_name()) if parent else ""
        except Exception as exc:
            data["parentClass"] = ""
            warnings.append("PARENT_CLASS_UNAVAILABLE")
            structure_errors["parent_class"] = _describe_exception(exc)

    if "variables" in include:
        data["variables"] = _variables(blueprint)

    if "components" in include:
        data["components"] = _components(blueprint)
        warnings.append("COMPONENT_HIERARCHY_NOT_EXPOSED")

    events, functions, macros = _graphs(blueprint)
    graph_entries = _graph_entries(events, functions, macros)

    selected_graphs = []
    if "graphs" in include or include_nodes:
        selected_graphs = [(graph, kind) for graph, kind in zip(
            events + functions + macros,
            ["event"] * len(events) + ["function"] * len(functions) + ["macro"] * len(macros),
        )]

    if graph_name is not None:
        matching = [
            (graph, kind)
            for graph, kind in selected_graphs
            if str(graph.get_name()) == graph_name
        ]
        if not matching:
            raise RpcError(
                "GRAPH_NOT_FOUND",
                "Graph not found: %s" % graph_name,
                {"blueprintPath": blueprint_path, "graphName": graph_name},
            )
        selected_graphs = matching

    if "graphs" in include:
        data["graphs"] = graph_entries

    # An "empty success" is worse than an error: callers cannot tell a blueprint
    # with no structure from one we failed to introspect. When parent class,
    # variables and graphs all came back empty, report what the API actually
    # did instead of returning a hollow payload.
    if (
        not data.get("parentClass")
        and not data.get("variables")
        and not data.get("graphs")
    ):
        raise RpcError(
            "UNSUPPORTED",
            "Blueprint structure introspection returned nothing for %s: the editor "
            "Python API did not expose parent class, variables or graphs for this asset"
            % blueprint_path,
            {
                "blueprintPath": blueprint_path,
                "diagnostics": _structure_diagnostics(blueprint),
                "observedErrors": structure_errors,
                "hint": "This is an engine Python API limitation, not a missing asset. "
                        "Compile action and asset search still work.",
            },
        )

    if "interfaces" in include:
        data["interfaces"] = _interfaces(blueprint)

    if "compileState" in include:
        data["compileState"] = _compile_state(blueprint)

    if include_nodes:
        target_graphs = selected_graphs
        if not target_graphs and events:
            target_graphs = [(events[0], "event")]
        nodes = []
        try:
            for graph, _kind in target_graphs:
                nodes.extend(_read_nodes(graph, node_limit))
            server.capabilities["blueprintNodeRead"] = True
        except Exception as exc:
            nodes = []
            warnings.append("NODE_INSPECTION_UNSTABLE: %s" % exc)
            server.capabilities["blueprintNodeRead"] = False
        data["nodes"] = nodes[:node_limit]

    saved = False
    if save:
        saved = _save_asset(blueprint_path)
        data["saved"] = saved
        if not saved:
            warnings.append("SAVE_FAILED: save_asset returned false")

    return HandlerResult(data, warnings)
