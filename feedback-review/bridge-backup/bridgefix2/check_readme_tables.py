#!/usr/bin/env python3
"""README <-> code consistency check (batch-2 item 11: documentation generation).

The README restates four sets of facts that live in code:

* the plugin version (``settings.PLUGIN_VERSION``, also the title line),
* the RPC method set (``rpc.HANDLERS``, section 5 table),
* the self-check script set (``Tests/check_*.py`` + ``Tests/test_*.py``,
  section 10.2 table),
* the derived counts quoted in the tree / section 8 / section 10.2 headings.

Hand-maintained prose drifts from code silently; this script turns the drift
into a non-zero exit.  It parses the two Python sources with ``ast`` instead of
importing them, so it runs under a bare CPython with no ``unreal`` module and
never touches the editor.

Usage:
    python check_readme_tables.py            # verify (exit 0 pass / 1 fail)
    python check_readme_tables.py --emit      # print section 5 rows from code

``--emit`` prints one row per ``rpc.HANDLERS`` entry using the tool/permission
columns already present in the README, so adding a method and re-running
``--emit`` yields the row to paste into the table.  The tool-name and
permission columns are policy facts maintained by hand; only the method column
is generated.
"""

import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
README_PATH = os.path.join(PLUGIN_DIR, "README.md")
PKG_DIR = os.path.join(PLUGIN_DIR, "Content", "Python", "uemcp_bridge")
SETTINGS_PATH = os.path.join(PKG_DIR, "settings.py")
RPC_PATH = os.path.join(PKG_DIR, "rpc.py")

SELF_CHECK_RE = re.compile(r"^(check_|test_)")
METHOD_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z0-9_.]*)`\s*\|")
SCRIPT_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*`([A-Za-z0-9_]+\.py)`\s*\|")
NUMBERED_RE = re.compile(r"^##\s*5\.")

# (pattern, what it used to say).  These are the exact stale strings reported in
# bridge-verification.md item 11; they must not survive anywhere in the README.
STALE_PATTERNS = [
    ("v0.1.0", "title version before 0.1.5"),
    ("11/11", "self-check tally before the test set grew"),
    ("12 个 RPC", "RPC count before object.reflect/object.call/log.query"),
    ("10 个工具", "tool count before ue_reflect/ue_call_function/ue_log_query"),
    ("14 个无编辑器自检", "section 8 count"),
    ("11 个无编辑器自检", "tree count"),
    ("11 个脚本", "section 10.2 expectation"),
    ("预期 11 个", "section 10.2 expectation"),
]


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def module_constant(path, name):
    """Return the literal value of a module-level ``name = <constant>``."""
    tree = ast.parse(read_text(path), path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    return None
    return None


def dict_literal_keys(path, name):
    """Return the string keys of a module-level ``name = {...}`` dict literal."""
    tree = ast.parse(read_text(path), path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                if not isinstance(node.value, ast.Dict):
                    return None
                keys = []
                for key in node.value.keys:
                    if not isinstance(key, ast.Constant) or not isinstance(
                        key.value, str
                    ):
                        return None
                    keys.append(key.value)
                return keys
    return None


def self_check_scripts():
    names = [
        name
        for name in os.listdir(HERE)
        if name.endswith(".py") and SELF_CHECK_RE.match(name)
    ]
    return sorted(names)


def section_lines(lines, heading_prefix):
    """Return the lines of the top-level section starting with ``heading_prefix``."""
    start = None
    for index, line in enumerate(lines):
        if line.startswith(heading_prefix):
            start = index
            break
    if start is None:
        return []
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            return lines[start:index]
    return lines[start:]


def split_cells(line):
    parts = line.split("|")
    return [part.strip() for part in parts[1:-1]]


def readme_methods(section):
    """Ordered (method, tool, permission) triples from the section 5 table."""
    rows = []
    for line in section:
        match = METHOD_ROW_RE.match(line)
        if not match:
            continue
        cells = split_cells(line)
        if len(cells) < 3:
            continue
        rows.append((match.group(1), cells[1].strip("`"), cells[2]))
    return rows


def readme_scripts(section):
    """Ordered (number, script) pairs from the section 10.2 table."""
    rows = []
    for line in section:
        match = SCRIPT_ROW_RE.match(line)
        if match:
            rows.append((int(match.group(1)), match.group(2)))
    return rows


def emit(methods, methods_from_readme):
    """Print section 5 rows for every handler, reusing tool/permission columns."""
    known = {method: (tool, perm) for method, tool, perm in methods_from_readme}
    missing = []
    for method in methods:
        tool, perm = known.get(method, ("", ""))
        if not tool or not perm:
            missing.append(method)
            tool, perm = "TODO", "TODO"
        print("| `%s` | %s | %s |" % (method, tool, perm))
    print("README_TABLES_EMIT methods=%d missing=%d" % (len(methods), len(missing)))
    return 0 if not missing else 1


def main(argv):
    failures = []
    lines = read_text(README_PATH).splitlines()

    version = module_constant(SETTINGS_PATH, "PLUGIN_VERSION")
    methods = dict_literal_keys(RPC_PATH, "HANDLERS")
    scripts = self_check_scripts()

    if not version:
        print("FAIL: settings.PLUGIN_VERSION not found")
        return 1
    if not methods:
        print("FAIL: rpc.HANDLERS not a string-keyed dict literal")
        return 1

    table_rows = readme_methods(section_lines(lines, "## 5."))
    table_methods = [method for method, _tool, _perm in table_rows]
    table_scripts = readme_scripts(section_lines(lines, "### 10.2"))

    if argv and argv[0] == "--emit":
        return emit(methods, table_rows)

    # 1. Title carries the plugin version from settings.py.
    if not lines:
        failures.append("readme: empty")
    else:
        title = lines[0]
        if "v" + version not in title:
            failures.append(
                "title: %r does not carry settings.PLUGIN_VERSION=%s"
                % (title, version)
            )

    # 2. Section 5 table == rpc.HANDLERS, both directions, no duplicates.
    if len(set(table_methods)) != len(table_methods):
        failures.append("section 5: duplicate method rows")
    missing_rows = [method for method in methods if method not in set(table_methods)]
    extra_rows = [method for method in table_methods if method not in set(methods)]
    if missing_rows:
        failures.append(
            "section 5: %d handler(s) missing from table: %s"
            % (len(missing_rows), ", ".join(missing_rows))
        )
    if extra_rows:
        failures.append(
            "section 5: %d row(s) not in rpc.HANDLERS: %s"
            % (len(extra_rows), ", ".join(extra_rows))
        )
    if table_methods and table_methods != methods:
        failures.append("section 5: row order differs from rpc.HANDLERS order")

    # 3. Section 10.2 table == actual Tests/check_*.py + Tests/test_*.py.
    listed_scripts = [script for _number, script in table_scripts]
    if len(set(listed_scripts)) != len(listed_scripts):
        failures.append("section 10.2: duplicate script rows")
    missing_scripts = [name for name in scripts if name not in set(listed_scripts)]
    extra_scripts = [name for name in listed_scripts if name not in set(scripts)]
    if missing_scripts:
        failures.append(
            "section 10.2: %d script(s) missing from table: %s"
            % (len(missing_scripts), ", ".join(missing_scripts))
        )
    if extra_scripts:
        failures.append(
            "section 10.2: %d row(s) without a script on disk: %s"
            % (len(extra_scripts), ", ".join(extra_scripts))
        )
    numbers = [number for number, _script in table_scripts]
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        failures.append("section 10.2: row numbers are not 1..%d" % len(numbers))

    # 4. Every quoted count agrees with the code.
    method_count = len(methods)
    script_count = len(scripts)
    tool_count = len({tool for _method, tool, _perm in table_rows if tool != "公共"})
    print("README_TABLES method_count=%d tool_count=%d script_count=%d"
          % (method_count, tool_count, script_count))

    for number, text in enumerate(lines, start=1):
        match = re.search(r"(\d+) 个工具对应的 (\d+) 个 RPC method", text)
        if match:
            if int(match.group(1)) != tool_count:
                failures.append(
                    "line %d: %s tools, actual %d" % (number, match.group(1), tool_count)
                )
            if int(match.group(2)) != method_count:
                failures.append(
                    "line %d: %s RPC methods, actual %d"
                    % (number, match.group(2), method_count)
                )
        match = re.search(r"(\d+) 个无编辑器自检", text)
        if match and int(match.group(1)) != script_count:
            failures.append(
                "line %d: %s 无编辑器自检, actual %d"
                % (number, match.group(1), script_count)
            )
        match = re.search(r"无需编辑器的 (\d+) 个自检", text)
        if match and int(match.group(1)) != script_count:
            failures.append(
                "line %d: section 10.2 heading says %s, actual %d"
                % (number, match.group(1), script_count)
            )
        match = re.search(r"预期 (\d+) 个脚本", text)
        if match and int(match.group(1)) != script_count:
            failures.append(
                "line %d: 预期 %s 个脚本, actual %d"
                % (number, match.group(1), script_count)
            )
        match = re.search(r"(\d+)/(\d+) exit 0", text)
        if match and (
            int(match.group(1)) != script_count or int(match.group(2)) != script_count
        ):
            failures.append(
                "line %d: %s/%s exit 0, actual %d"
                % (number, match.group(1), match.group(2), script_count)
            )

    # 5. No stale strings reported by bridge-verification.md item 11.
    for pattern, reason in STALE_PATTERNS:
        for number, text in enumerate(lines, start=1):
            if pattern in text:
                failures.append(
                    "line %d: stale %r (%s)" % (number, pattern, reason)
                )

    for failure in failures:
        print("FAIL: " + failure)
    print(
        "README_TABLES_CHECK methods=%d scripts=%d %s"
        % (method_count, script_count, "PASS" if not failures else "FAIL(%d)" % len(failures))
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))