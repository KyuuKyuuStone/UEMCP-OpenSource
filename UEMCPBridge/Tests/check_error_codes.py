"""Bridge error-code self-check (no editor required).

1. Statically collects every error-code string passed to ``RpcError(...)``,
   ``rpc_error_response(...)`` and the HTTP layer's ``_send_rpc_error(...)``
   and asserts each one exists in ``ERROR_TABLE``.
2. Asserts the runtime contract for ``INVALID_ARGUMENT``: -32602 / HTTP 400 /
   non-retryable, with ``details.issues`` preserved.
3. Asserts that unknown codes are preserved (not rewritten) and only fall back
   to the generic metadata triple.

Exit code 0 = PASS, 1 = FAIL.
"""

import ast
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PYTHON_DIR = os.path.join(PLUGIN_DIR, "Content", "Python")
if PYTHON_DIR not in sys.path:
    sys.path.insert(0, PYTHON_DIR)

from uemcp_bridge.errors import (  # noqa: E402
    ERROR_TABLE,
    RpcError,
    invalid_argument,
)

# Calls whose relevant argument is an error-code string constant.
_CODE_ARG_INDEX = {
    "RpcError": 0,          # RpcError("CODE", ...)
    "rpc_error_response": 1,  # rpc_error_response(id, "CODE", ...)
    "_send_rpc_error": 1,     # self._send_rpc_error(id, "CODE", ...)
}


def _collect_codes():
    findings = []
    for root, _dirs, files in os.walk(PYTHON_DIR):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                call_name = None
                if isinstance(func, ast.Name):
                    call_name = func.id
                elif isinstance(func, ast.Attribute):
                    call_name = func.attr
                index = _CODE_ARG_INDEX.get(call_name)
                if index is None:
                    continue
                if len(node.args) <= index:
                    continue
                argument = node.args[index]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    findings.append(
                        (argument.value, os.path.relpath(path, PYTHON_DIR), node.lineno)
                    )
    return findings


def main():
    failures = []

    findings = _collect_codes()
    for code, path, line in findings:
        if code not in ERROR_TABLE:
            failures.append("missing ERROR_TABLE entry for %r at %s:%d" % (code, path, line))

    # Direct contract assertions.
    expected_entries = {
        "INVALID_ARGUMENT": (-32602, 400, False),
        "INVALID_PARAMS": (-32602, 400, False),
        "INVALID_REQUEST": (-32600, 400, False),
        "METHOD_NOT_FOUND": (-32601, 404, False),
        "PARSE_ERROR": (-32700, 400, False),
    }
    for code, expected in expected_entries.items():
        actual = ERROR_TABLE.get(code)
        if actual != expected:
            failures.append(
                "ERROR_TABLE[%r] = %r, expected %r" % (code, actual, expected)
            )

    error = invalid_argument(
        [{"path": "sections[0]", "code": "invalid_enum_value", "message": "bad"}]
    )
    if error.code != "INVALID_ARGUMENT":
        failures.append("invalid_argument().code = %r" % error.code)
    if error.rpc_code != -32602:
        failures.append("invalid_argument().rpc_code = %r" % error.rpc_code)
    if error.http_status != 400:
        failures.append("invalid_argument().http_status = %r" % error.http_status)
    issues = (error.details or {}).get("issues")
    if not isinstance(issues, list) or not issues or issues[0].get("path") != "sections[0]":
        failures.append("invalid_argument().details.issues was not preserved: %r" % (error.details,))
    envelope = error.to_jsonrpc_error()
    if envelope.get("code") != -32602:
        failures.append("to_jsonrpc_error().code = %r" % envelope.get("code"))
    if envelope.get("data", {}).get("errorCode") != "INVALID_ARGUMENT":
        failures.append("to_jsonrpc_error().data.errorCode = %r" % envelope.get("data", {}).get("errorCode"))

    unknown = RpcError("SOME_UNKNOWN_TEST_CODE", "boom")
    if unknown.code != "SOME_UNKNOWN_TEST_CODE":
        failures.append("unknown code was rewritten to %r" % unknown.code)
    if (unknown.rpc_code, unknown.http_status) != (-32603, 500):
        failures.append(
            "unknown code metadata = (%r, %r), expected (-32603, 500)"
            % (unknown.rpc_code, unknown.http_status)
        )
    if unknown.details != {}:
        failures.append("unknown code details = %r, expected {}" % (unknown.details,))

    # Emit a compact report; this script also runs inside commandlets.
    print("ERROR_CODE_CHECK scanned_calls=%d table_entries=%d" % (len(findings), len(ERROR_TABLE)))
    print("INVALID_ARGUMENT rpc_code=%d http=%d" % (error.rpc_code, error.http_status))
    print("UNKNOWN_CODE_PRESERVED %r metadata=(%d,%d)" % (unknown.code, unknown.rpc_code, unknown.http_status))
    if failures:
        for failure in failures:
            print("FAIL: %s" % failure)
        print("ERROR_CODE_RESULT FAIL")
        return 1
    print("ERROR_CODE_RESULT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
