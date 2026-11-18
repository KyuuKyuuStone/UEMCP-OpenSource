"""Stub regression test for DEFECT-6 (dependency options + query failures)."""

import os
import sys
import types

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

UE54_OPTIONS = {
    "include_hard_package_references",
    "include_soft_package_references",
    "include_hard_management_references",
    "include_soft_management_references",
    "include_searchable_names",
}
LEGACY_OPTIONS = {
    "include_hard_package_references",
    "include_soft_package_references",
    "include_management_references",
    "include_searchable_names",
}


class FakeOptions(object):
    def __init__(self, known):
        self._known = set(known)
        self.values = {}

    def __getattr__(self, name):
        if name in self._known:
            return None
        raise AttributeError(name)

    def set_editor_property(self, name, value):
        if name not in self._known:
            raise Exception("Failed to find property %r" % name)
        self.values[name] = value


_OPTIONS_KNOWN = [UE54_OPTIONS]


def _make_options():
    return FakeOptions(_OPTIONS_KNOWN[0])


unreal_stub = types.ModuleType("unreal")
unreal_stub.AssetRegistryDependencyOptions = _make_options
sys.modules["unreal"] = unreal_stub

if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge.handlers import assets  # noqa: E402


class _FakeRegistry(object):
    def __init__(self, mode="raise"):
        self.mode = mode

    def get_dependencies(self, _package, _options):
        if self.mode == "raise":
            raise RuntimeError("dependencies exploded")
        return None

    def get_referencers(self, _package, _options):
        if self.mode == "raise":
            raise RuntimeError("referencers exploded")
        return None


def main():
    failures = []

    # UE 5.4 shape: hard/soft management flags, no legacy management flag.
    _OPTIONS_KNOWN[0] = UE54_OPTIONS
    options, warnings = assets._dependency_options(
        {"hard": True, "soft": True, "management": True, "searchableName": False}
    )
    if warnings:
        failures.append("UE54 options produced warnings: %r" % warnings)
    for name in (
        "include_hard_package_references",
        "include_soft_package_references",
        "include_hard_management_references",
        "include_soft_management_references",
    ):
        if options.values.get(name) is not True:
            failures.append("UE54 option %s = %r" % (name, options.values.get(name)))
    if "include_management_references" in options.values:
        failures.append("legacy management flag was set on UE54 options")
    print("UE54_OPTIONS warnings=0 hardManagement=%s softManagement=%s" % (
        options.values.get("include_hard_management_references"),
        options.values.get("include_soft_management_references"),
    ))

    # Legacy engine: only the single management flag exists.
    _OPTIONS_KNOWN[0] = LEGACY_OPTIONS
    options, warnings = assets._dependency_options(
        {"hard": True, "soft": True, "management": True, "searchableName": False}
    )
    if options.values.get("include_management_references") is not True:
        failures.append("legacy management fallback not applied")
    if not any("DEPENDENCY_OPTION_UNAVAILABLE" in warning for warning in warnings):
        failures.append("missing warning for absent management properties: %r" % warnings)
    print("LEGACY_OPTIONS warnings=%r legacy=%s" % (
        warnings, options.values.get("include_management_references")))

    # Missing searchable flag must be skipped, not raised.
    _OPTIONS_KNOWN[0] = {"include_hard_package_references"}
    options, warnings = assets._dependency_options(
        {"hard": True, "soft": False, "management": False, "searchableName": True}
    )
    if not any("include_searchable_names" in warning for warning in warnings):
        failures.append("missing searchable warning: %r" % warnings)
    print("MISSING_PROPERTY_SKIPPED warnings=%r" % warnings)

    # Query errors degrade to empty lists with warnings, never exceptions.
    warnings = []
    dependencies, referencers = assets._collect_relations(
        _FakeRegistry("raise"), object(), "pkg", True, True, warnings
    )
    if dependencies or referencers:
        failures.append("failed queries did not degrade to empty lists")
    if not any("DEPENDENCY_QUERY_FAILED" in warning for warning in warnings):
        failures.append("missing dependency failure warning: %r" % warnings)
    if not any("REFERENCER_QUERY_FAILED" in warning for warning in warnings):
        failures.append("missing referencer failure warning: %r" % warnings)
    print("QUERY_FAILURE_DEGRADED warnings=%d" % len(warnings))

    # None results must become empty lists.
    warnings = []
    dependencies, referencers = assets._collect_relations(
        _FakeRegistry("none"), object(), "pkg", True, True, warnings
    )
    if dependencies or referencers or warnings:
        failures.append("None results mishandled: %r %r %r" % (
            dependencies, referencers, warnings))
    print("NONE_RESULTS_OK")

    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("DEPENDENCY_OPTIONS_RESULT FAIL")
        return 1
    print("DEPENDENCY_OPTIONS_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
