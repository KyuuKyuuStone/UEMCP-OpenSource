"""Static undefined-name guard (no editor required).

Catches the DEFECT-1 class of bug (a name used but never imported/defined),
for example ``get_enum`` missing from ``handlers/assets.py``'s import block.

The analysis is deliberately module-wide: it unions every binding (imports,
assignments, function/class definitions, parameters, comprehension targets,
exception names) and reports loaded names that are neither bound nor builtin.
That catches missing imports/definitions; it does not attempt full scope
resolution (a name bound only in another function would be a false negative).

Exit code 0 = PASS, 1 = FAIL.
"""

import ast
import builtins
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")

_BUILTINS = set(dir(builtins)) | {
    "__file__",
    "__name__",
    "__doc__",
    "__package__",
    "__builtins__",
}


class _BindingCollector(ast.NodeVisitor):
    def __init__(self):
        self.bound = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.bound.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name != "*":
                self.bound.add(alias.asname or alias.name)

    def _bind_arguments(self, args):
        for argument in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            self.bound.add(argument.arg)
        if args.vararg is not None:
            self.bound.add(args.vararg.arg)
        if args.kwarg is not None:
            self.bound.add(args.kwarg.arg)

    def visit_FunctionDef(self, node):
        self.bound.add(node.name)
        self._bind_arguments(node.args)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.bound.add(node.name)
        self._bind_arguments(node.args)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        self._bind_arguments(node.args)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.bound.add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bound.add(node.id)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.bound.add(node.name)
        self.generic_visit(node)

    def visit_Global(self, node):
        self.bound.update(node.names)

    def visit_Nonlocal(self, node):
        self.bound.update(node.names)


def _collect_bound(tree):
    collector = _BindingCollector()
    collector.visit(tree)
    return collector.bound


def _loaded_names(tree):
    loaded = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.append((node.id, node.lineno))
    return loaded


def main():
    failures = []
    checked_files = 0
    for root, _dirs, files in os.walk(PYTHON_DIR):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            checked_files += 1
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            bound = _collect_bound(tree)
            for identifier, line in _loaded_names(tree):
                if identifier in bound or identifier in _BUILTINS:
                    continue
                failures.append(
                    "%s:%d: name %r is used but never imported/defined"
                    % (os.path.relpath(path, PYTHON_DIR), line, identifier)
                )

    print("HANDLER_NAME_CHECK files=%d undefined=%d" % (checked_files, len(failures)))
    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("HANDLER_NAME_RESULT FAIL")
        return 1
    print("HANDLER_NAME_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
