"""Plugin metadata self-check (no editor required).

The bridge must not pin itself to one engine version in source:

* ``UEMCPBridge.uplugin`` has no ``EngineVersion`` (any UE5 loads it) and a
  version-agnostic ``Description``;
* ``Tools/stamp_uplugin.py`` can inject ``EngineVersion`` for packaging builds,
  reading it either from an explicit ``--engine`` or from
  ``<Engine>/Build/Build.version``;
* stamping never mutates the repository descriptor unless ``--force`` is used;
* the stamp tool is standard-library only (the plugin may not grow third-party
  dependencies).

Exit code 0 = PASS, 1 = FAIL.
"""

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
UPLUGIN_PATH = os.path.join(PLUGIN_DIR, "UEMCPBridge.uplugin")
TOOL_PATH = os.path.join(PLUGIN_DIR, "Tools", "stamp_uplugin.py")

_REQUIRED_PLUGINS = {"PythonScriptPlugin", "EditorScriptingUtilities"}


def _load_tool():
    spec = importlib.util.spec_from_file_location("uemcp_stamp_uplugin", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _check_descriptor(failures):
    with open(UPLUGIN_PATH, "r", encoding="utf-8") as handle:
        descriptor = json.load(handle)

    if "EngineVersion" in descriptor:
        failures.append(
            "uplugin pins EngineVersion=%r; keep it out of the source descriptor"
            % descriptor.get("EngineVersion")
        )

    description = str(descriptor.get("Description", ""))
    for banned in ("5.4", "5.7"):
        if banned in description:
            failures.append("Description still names engine version %s: %r" % (banned, description))
    if "Unreal Engine 5" not in description:
        failures.append("Description does not name the engine family: %r" % description)

    if descriptor.get("Modules") != []:
        failures.append("Modules must stay empty (pure Python plugin): %r" % descriptor.get("Modules"))
    if descriptor.get("Type") != "Editor":
        failures.append("Type = %r, expected 'Editor'" % descriptor.get("Type"))
    if descriptor.get("CanContainContent") is not True:
        failures.append("CanContainContent must stay true so Content/Python is scanned")

    plugins = {item.get("Name") for item in descriptor.get("Plugins", []) if isinstance(item, dict)}
    missing = _REQUIRED_PLUGINS - plugins
    if missing:
        failures.append("required plugin dependencies missing: %r" % sorted(missing))

    print(
        "UPLUGIN descriptor EngineVersion=absent description=%r modules=%r plugins=%r"
        % (description, descriptor.get("Modules"), sorted(plugins))
    )


def _check_stamp(failures, tool):
    with open(UPLUGIN_PATH, "r", encoding="utf-8") as handle:
        original = json.load(handle)

    stamped = tool.stamp_descriptor(original, "5.7.4")
    if stamped.get("EngineVersion") != "5.7.4":
        failures.append("stamp_descriptor did not set EngineVersion")
    if "EngineVersion" in original:
        failures.append("stamp_descriptor mutated its input")
    if stamped.get("Modules") != original.get("Modules"):
        failures.append("stamp_descriptor changed unrelated keys")

    for bad in ("5.7", "v5.7.4", "", "5.7.4.1", None):
        try:
            tool.stamp_descriptor(original, bad)
        except ValueError:
            continue
        except Exception as exc:
            failures.append("stamp_descriptor(%r) raised %r instead of ValueError" % (bad, exc))
        else:
            failures.append("stamp_descriptor(%r) accepted an invalid version" % (bad,))

    fake_engine = tempfile.mkdtemp(prefix="uemcp_engine_")
    os.makedirs(os.path.join(fake_engine, "Engine", "Build"), exist_ok=True)
    with open(os.path.join(fake_engine, "Engine", "Build", "Build.version"), "w", encoding="utf-8") as handle:
        json.dump({"MajorVersion": 5, "MinorVersion": 7, "PatchVersion": 4}, handle)
    resolved = tool.engine_version_from_install(fake_engine)
    if resolved != "5.7.4":
        failures.append("engine_version_from_install = %r, expected 5.7.4" % resolved)
    try:
        tool.engine_version_from_install(tempfile.mkdtemp(prefix="uemcp_no_engine_"))
    except ValueError:
        pass
    except Exception as exc:
        failures.append("missing Build.version raised %r instead of ValueError" % (exc,))
    else:
        failures.append("missing Build.version did not raise")

    # --out writes a stamped copy and leaves the source untouched.
    source_digest = _digest(UPLUGIN_PATH)
    out_dir = tempfile.mkdtemp(prefix="uemcp_stamp_out_")
    out_path = os.path.join(out_dir, "UEMCPBridge.uplugin")
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = tool.main(["--engine", "5.7.4", "--out", out_path])
    if code != 0:
        failures.append("stamp --out exit code = %r" % code)
    with open(out_path, "r", encoding="utf-8") as handle:
        written = json.load(handle)
    if written.get("EngineVersion") != "5.7.4":
        failures.append("stamped file EngineVersion = %r" % written.get("EngineVersion"))
    if written.get("Modules") != original.get("Modules"):
        failures.append("stamped file changed Modules")
    if _digest(UPLUGIN_PATH) != source_digest:
        failures.append("--out modified the repository descriptor")
    if "STAMPED" not in captured.getvalue():
        failures.append("stamp --out did not report success")

    # --inplace on the repo descriptor is refused without --force.
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            tool.main(["--engine", "5.7.4", "--inplace"])
    except SystemExit as exc:
        if exc.code not in (2,):
            failures.append("--inplace refusal exit code = %r, expected 2" % (exc.code,))
    else:
        failures.append("--inplace on the repository descriptor was not refused")
    if _digest(UPLUGIN_PATH) != source_digest:
        failures.append("refused --inplace still modified the repository descriptor")

    # --engine and --engine-root are mutually exclusive.
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            tool.main(["--engine", "5.7.4", "--engine-root", fake_engine, "--out", out_path])
    except SystemExit as exc:
        if exc.code not in (2,):
            failures.append("mutually exclusive args exit code = %r" % (exc.code,))
    else:
        failures.append("--engine with --engine-root was accepted")

    print("STAMP tool engine_from_install=%s out_file=%s" % (resolved, os.path.basename(out_path)))


def _check_stdlib_only(failures):
    with open(TOOL_PATH, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=TOOL_PATH)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    allowed = {"argparse", "json", "re", "sys", "pathlib"}
    unexpected = imported - allowed
    if unexpected:
        failures.append("stamp_uplugin imports non-stdlib modules: %r" % sorted(unexpected))
    print("STAMP_IMPORTS stdlib_only=%r" % sorted(imported))


def main():
    failures = []
    if not os.path.isfile(TOOL_PATH):
        print("FAIL: missing %s" % TOOL_PATH)
        print("UPLUGIN_METADATA_RESULT FAIL")
        return 1
    tool = _load_tool()
    _check_descriptor(failures)
    _check_stamp(failures, tool)
    _check_stdlib_only(failures)
    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("UPLUGIN_METADATA_RESULT FAIL")
        return 1
    print("UPLUGIN_METADATA_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
