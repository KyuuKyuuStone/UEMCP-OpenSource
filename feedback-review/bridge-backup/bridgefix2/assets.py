"""``asset.search`` handler (architecture doc section 5.5)."""

import time

from ..errors import RpcError
from . import (
    HandlerResult,
    asset_ref,
    check_keys,
    get_bool,
    get_enum,
    get_int,
    get_list,
    get_obj,
    get_str,
    get_unreal,
)

_MAX_BFS_NODES = 1000
_MAX_SEEDS = 50


def _registry():
    unreal = get_unreal()
    return unreal.AssetRegistryHelpers.get_asset_registry()


def _check_registry_ready(registry):
    loading = False
    try:
        if hasattr(registry, "is_loading_assets"):
            loading = bool(registry.is_loading_assets())
    except Exception:
        loading = False
    if loading:
        raise RpcError(
            "ASSET_REGISTRY_UNAVAILABLE",
            "Asset registry is still loading",
            {"loading": True},
        )


_MAX_WARNINGS = 20
_asset_search_ensured = False


def _ensure_asset_search(registry):
    """Make sure the AssetRegistry dependency graph is populated.

    In -run=pythonscript commandlets the registry may report
    ``is_loading_assets() == False`` while dependency queries still return
    ``None`` until a synchronous search has run.  Run it once per process.
    """
    global _asset_search_ensured
    if _asset_search_ensured:
        return
    try:
        if hasattr(registry, "wait_for_completion"):
            registry.wait_for_completion()
    except Exception:
        pass
    try:
        if hasattr(registry, "search_all_assets"):
            registry.search_all_assets(True)
    except Exception:
        pass
    _asset_search_ensured = True


def _set_dependency_option(options, name, value, warnings):
    """Set a dependency option, skipping properties absent in this engine."""
    if not hasattr(options, name):
        warnings.append("DEPENDENCY_OPTION_UNAVAILABLE: %s" % name)
        return False
    try:
        options.set_editor_property(name, bool(value))
        return True
    except Exception as exc:
        warnings.append(
            "DEPENDENCY_OPTION_FAILED: %s (%s)" % (name, type(exc).__name__)
        )
        return False


def _dependency_options(flags):
    """Build UE5.4 AssetRegistryDependencyOptions.

    UE 5.4 exposes ``include_hard_management_references`` and
    ``include_soft_management_references``; ``include_management_references``
    does not exist and must never be set unconditionally (DEFECT-6).
    """
    unreal = get_unreal()
    options = unreal.AssetRegistryDependencyOptions()
    warnings = []
    _set_dependency_option(
        options, "include_hard_package_references", flags.get("hard", True), warnings
    )
    _set_dependency_option(
        options, "include_soft_package_references", flags.get("soft", True), warnings
    )
    management = bool(flags.get("management", False))
    hard_ok = _set_dependency_option(
        options, "include_hard_management_references", management, warnings
    )
    soft_ok = _set_dependency_option(
        options, "include_soft_management_references", management, warnings
    )
    if management and not (hard_ok or soft_ok):
        # Legacy engines use a single management flag.
        _set_dependency_option(
            options, "include_management_references", True, warnings
        )
    _set_dependency_option(
        options, "include_searchable_names", flags.get("searchableName", False), warnings
    )
    return options, warnings


def _names(values):
    result = []
    for value in values or []:
        result.append(str(value))
    return result


def _collect_relations(
    registry,
    options,
    package_name,
    include_dependencies,
    include_referencers,
    warnings,
):
    dependencies = []
    referencers = []
    if include_dependencies:
        try:
            dependencies = _names(registry.get_dependencies(package_name, options))
        except Exception as exc:
            if len(warnings) < _MAX_WARNINGS:
                warnings.append(
                    "DEPENDENCY_QUERY_FAILED: %s (%s)"
                    % (package_name, type(exc).__name__)
                )
    if include_referencers:
        try:
            referencers = _names(registry.get_referencers(package_name, options))
        except Exception as exc:
            if len(warnings) < _MAX_WARNINGS:
                warnings.append(
                    "REFERENCER_QUERY_FAILED: %s (%s)"
                    % (package_name, type(exc).__name__)
                )
    return dependencies, referencers


def _bfs(
    registry,
    options,
    seeds,
    depth,
    include_dependencies,
    include_referencers,
    deadline,
    warnings,
    max_nodes=_MAX_BFS_NODES,
    timeout_ms=None,
):
    """Breadth-first expansion with a hard node budget and a deadline.

    ``max_nodes`` caps how many related nodes are enqueued for expansion;
    hitting the cap truncates the relation graph and appends a warning
    instead of silently dropping nodes. ``timeout_ms`` is the configured
    search budget reported in SEARCH_TIMEOUT details (always positive).
    """
    collected = {}
    visited = set()
    frontier = list(seeds[:_MAX_SEEDS])
    if len(seeds) > _MAX_SEEDS:
        warnings.append(
            "BFS_SEEDS_TRUNCATED: %d seed assets exceed the %d-seed cap; "
            "only the first %d are expanded"
            % (len(seeds), _MAX_SEEDS, _MAX_SEEDS)
        )
    for seed in frontier:
        visited.add(seed)

    total_nodes = 0
    budget_hit = False
    for level in range(max(1, depth)):
        if not frontier:
            break
        next_frontier = []
        for package_name in frontier:
            if time.monotonic() > deadline:
                raise RpcError(
                    "SEARCH_TIMEOUT",
                    "Asset relation search exceeded the deadline",
                    {
                        "timeoutMs": int(timeout_ms or 0),
                        "partial": {
                            "total": len(collected),
                            "returned": len(collected),
                            "assets": [],
                        },
                    },
                )
            dependencies, referencers = _collect_relations(
                registry,
                options,
                package_name,
                include_dependencies,
                include_referencers,
                warnings,
            )
            if include_dependencies and dependencies:
                collected[package_name] = dependencies
            if include_referencers and referencers:
                collected.setdefault(package_name + "__referencers", referencers)
            for related in dependencies + referencers:
                if related in visited:
                    continue
                if total_nodes >= max_nodes:
                    budget_hit = True
                    continue
                visited.add(related)
                next_frontier.append(related)
                total_nodes += 1
        frontier = next_frontier
    if budget_hit:
        warnings.append(
            "BFS_BUDGET_TRUNCATED: relation expansion stopped at maxNodes=%d "
            "(%d nodes visited); increase maxNodes or narrow the query"
            % (max_nodes, len(visited))
        )
    return collected


def handle(server, params):
    check_keys(
        params,
        {
            "query",
            "path",
            "classNames",
            "recursive",
            "includeRedirectors",
            "includeDependencies",
            "includeReferencers",
            "dependencyDepth",
            "dependencyFlags",
            "limit",
            "offset",
            "sortBy",
            "maxNodes",
        },
    )
    query = get_str(params, "query", default="", max_length=256) or ""
    path = get_str(params, "path", default="/Game", max_length=512) or "/Game"
    class_names = get_list(params, "classNames", default=[], max_items=20, item_type=str)
    recursive = get_bool(params, "recursive", default=True)
    include_redirectors = get_bool(params, "includeRedirectors", default=False)
    include_dependencies = get_bool(params, "includeDependencies", default=False)
    include_referencers = get_bool(params, "includeReferencers", default=False)
    depth = get_int(params, "dependencyDepth", default=1, minimum=1, maximum=3)
    flags = get_obj(
        params,
        "dependencyFlags",
        allowed_keys={"hard", "soft", "management", "searchableName"},
    ) or {}
    limit = get_int(params, "limit", default=100, minimum=1, maximum=500)
    offset = get_int(params, "offset", default=0, minimum=0)
    sort_by = get_enum(
        params, "sortBy", {"path", "class", "name"}, default="path"
    )
    max_nodes = get_int(
        params, "maxNodes", default=_MAX_BFS_NODES, minimum=1, maximum=10000
    )

    unreal = get_unreal()
    registry = _registry()
    _check_registry_ready(registry)
    _ensure_asset_search(registry)

    deadline = time.monotonic() + (server.settings.search_timeout_ms / 1000.0)

    try:
        assets = registry.get_assets_by_path(unreal.Name(path), recursive)
    except Exception as exc:
        raise RpcError(
            "INTERNAL", "Asset registry query failed: %s" % exc, {"reason": str(exc)}
        )

    query_lower = query.lower()
    class_filter = [item.lower() for item in class_names]

    filtered = []
    for index, asset in enumerate(assets):
        if index % 256 == 0 and time.monotonic() > deadline:
            raise RpcError(
                "SEARCH_TIMEOUT",
                "Asset search exceeded the deadline",
                {
                    "timeoutMs": server.settings.search_timeout_ms,
                    "partial": {
                        "total": len(filtered),
                        "returned": len(filtered),
                        "assets": [asset_ref(item) for item in filtered[:limit]],
                    },
                },
            )
        if not include_redirectors:
            try:
                if unreal.AssetRegistryHelpers.is_redirector(asset):
                    continue
            except Exception:
                pass
        package_name = str(getattr(asset, "package_name", "")).lower()
        asset_name = str(getattr(asset, "asset_name", "")).lower()
        if query_lower and query_lower not in asset_name and query_lower not in package_name:
            continue
        if class_filter:
            class_name = ""
            try:
                class_name = str(asset.asset_class_path.asset_name).lower()
            except Exception:
                class_name = str(getattr(asset, "asset_class", "")).lower()
            if class_name not in class_filter:
                continue
        filtered.append(asset)

    def sort_key(asset):
        if sort_by == "class":
            try:
                return str(asset.asset_class_path.asset_name)
            except Exception:
                return ""
        if sort_by == "name":
            return str(getattr(asset, "asset_name", ""))
        return str(getattr(asset, "package_name", ""))

    filtered.sort(key=sort_key)

    total = len(filtered)
    window = filtered[offset : offset + limit]
    truncated = offset + len(window) < total

    data = {
        "total": total,
        "returned": len(window),
        "truncated": truncated,
        # Cursor for the next page; explicit null on the last page so callers
        # can loop on `nextOffset` instead of recomputing offset+returned.
        "nextOffset": (offset + len(window)) if truncated else None,
        "assets": [asset_ref(item) for item in window],
    }

    warnings = []
    if include_dependencies or include_referencers:
        options, option_warnings = _dependency_options(flags)
        warnings.extend(option_warnings)
        seeds = [str(getattr(item, "package_name", "")) for item in window if getattr(item, "package_name", "")]
        relations = _bfs(
            registry,
            options,
            seeds,
            depth,
            include_dependencies,
            include_referencers,
            deadline,
            warnings,
            max_nodes=max_nodes,
            timeout_ms=server.settings.search_timeout_ms,
        )
        data["relationsTruncated"] = any(
            item.startswith("BFS_BUDGET_TRUNCATED") for item in warnings
        )
        if include_dependencies:
            data["dependencies"] = {
                key: value
                for key, value in relations.items()
                if not key.endswith("__referencers")
            }
        if include_referencers:
            data["referencers"] = {
                key[: -len("__referencers")]: value
                for key, value in relations.items()
                if key.endswith("__referencers")
            }

    return HandlerResult(data, warnings[: _MAX_WARNINGS])
