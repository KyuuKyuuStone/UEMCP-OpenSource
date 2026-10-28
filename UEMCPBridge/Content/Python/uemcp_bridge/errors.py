"""Bridge error model (architecture doc section 2.9).

Every failure raised by a handler is an :class:`RpcError` carrying the
string ``errorCode`` used by the MCP server, the JSON-RPC numeric code and the
bridge HTTP status.  The MCP server maps ``data.errorCode`` to tool errors.
"""

import json
import logging
import warnings

_LOGGER = logging.getLogger("uemcp_bridge.errors")

# (jsonrpc_code, http_status, retryable)
ERROR_TABLE = {
    # Tool-level argument/validation failure.  JSON-RPC -32602 is used in the
    # bridge-internal channel only; the MCP server maps it to a tool error
    # (HTTP 200 + isError) on its own boundary.
    "INVALID_ARGUMENT": (-32602, 400, False),
    "INTERNAL": (-32603, 500, False),
    # Protocol/envelope-level codes used by the bridge HTTP layer (2.9.2).
    "INVALID_PARAMS": (-32602, 400, False),
    "INVALID_REQUEST": (-32600, 400, False),
    "METHOD_NOT_FOUND": (-32601, 404, False),
    "PARSE_ERROR": (-32700, 400, False),
    "BRIDGE_UNAVAILABLE": (-32000, 503, True),
    "SESSION_NOT_FOUND": (-32001, 404, False),
    "BRIDGE_BUSY": (-32002, 429, True),
    "PERMISSION_DENIED": (-32003, 403, False),
    "TOOL_DISABLED": (-32004, 403, False),
    "CONFIRMATION_REQUIRED": (-32005, 428, False),
    "NOT_FOUND": (-32006, 404, False),
    "CONFLICT": (-32007, 409, False),
    "UNSUPPORTED": (-32008, 501, False),
    "EXECUTION_ERROR": (-32009, 500, False),
    "EDITOR_UNSAFE_STATE": (-32010, 409, True),
    "PAYLOAD_TOO_LARGE": (-32011, 413, False),
    "RATE_LIMITED": (-32012, 429, True),
    "SAVE_FAILED": (-32013, 500, False),
    "PYTHON_ERROR": (-32014, 500, False),
    "RESULT_NOT_SERIALIZABLE": (-32015, 500, False),
    "CAPABILITY_UNAVAILABLE": (-32016, 501, False),
    "COMMAND_NOT_ALLOWED": (-32017, 403, False),
    "CONFIRMATION_DENIED": (-32018, 403, False),
    "BRIDGE_TIMEOUT": (-32020, 504, True),
    "AMBIGUOUS_SELECTOR": (-32021, 409, False),
    "CLASS_NOT_FOUND": (-32022, 404, False),
    "ASSET_NOT_FOUND": (-32023, 404, False),
    "TRANSACTION_FAILED": (-32024, 409, False),
    "LEVEL_NOT_FOUND": (-32025, 404, False),
    "LEVEL_LOAD_FAILED": (-32026, 500, False),
    "UNSAVED_CHANGES": (-32027, 409, False),
    "SEARCH_TIMEOUT": (-32028, 504, True),
    "ASSET_REGISTRY_UNAVAILABLE": (-32029, 503, True),
    "MATERIAL_NOT_FOUND": (-32030, 404, False),
    "NOT_A_MATERIAL": (-32031, 400, False),
    "NOT_AN_INSTANCE": (-32032, 409, False),
    "PARAM_NOT_FOUND": (-32033, 404, False),
    "TYPE_MISMATCH": (-32034, 400, False),
    "ALREADY_EXISTS": (-32035, 409, False),
    "CAPTURE_FAILED": (-32036, 500, False),
    "CAPTURE_TIMEOUT": (-32037, 504, True),
    "PIE_NOT_RUNNING": (-32038, 409, False),
    "BLUEPRINT_NOT_FOUND": (-32039, 404, False),
    "NOT_A_BLUEPRINT": (-32040, 400, False),
    "GRAPH_NOT_FOUND": (-32041, 404, False),
    "COMPILE_FAILED": (-32042, 500, False),
    "EXEC_DISABLED": (-32043, 403, False),
    "ACTOR_NOT_FOUND": (-32044, 404, False),
}

# JSON-RPC envelope-level codes (not tool errors).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

MAX_DETAILS_BYTES = 16 * 1024
MAX_MESSAGE_CHARS = 1024


class RpcError(Exception):
    """A bridge-side failure with a contract error code."""

    __slots__ = ("code", "message", "details", "rpc_code", "http_status", "retryable")

    def __init__(self, code, message, details=None, rpc_code=None, http_status=None, retryable=None):
        super(RpcError, self).__init__(message)
        if not isinstance(code, str):
            code = str(code)
        meta = ERROR_TABLE.get(code)
        if meta is None:
            # Never rewrite a caller-supplied code: preserving it keeps the
            # error diagnosable.  Only the metadata (JSON-RPC/HTTP/retryable)
            # falls back to the generic internal-error triple, and the event
            # is logged loudly so missing table entries are noticed.
            _warn_unknown_code(code)
            meta = (INTERNAL_ERROR, 500, False)
        self.code = code
        self.message = _truncate_message(str(message))
        self.details = _truncate_details(details or {})
        self.rpc_code = meta[0] if rpc_code is None else rpc_code
        self.http_status = meta[1] if http_status is None else http_status
        self.retryable = meta[2] if retryable is None else bool(retryable)

    def to_jsonrpc_error(self):
        return {
            "code": self.rpc_code,
            "message": self.message,
            "data": {
                "errorCode": self.code,
                "retryable": self.retryable,
                "details": self.details,
            },
        }

    def __repr__(self):
        return "RpcError(%s, %s)" % (self.code, self.message)


def _warn_unknown_code(code):
    message = (
        "unknown bridge error code %r; preserving it and using default "
        "metadata (INTERNAL/-32603/500)" % (code,)
    )
    try:
        import unreal  # type: ignore

        if hasattr(unreal, "log_warning"):
            unreal.log_warning("[UEMCP] " + message)
            return
    except Exception:
        pass
    _LOGGER.warning(message)
    try:
        warnings.warn(message, RuntimeWarning, stacklevel=3)
    except Exception:
        pass


def _truncate_message(message):
    if len(message) <= MAX_MESSAGE_CHARS:
        return message
    return message[: MAX_MESSAGE_CHARS - 3] + "..."


def _truncate_details(details):
    if not isinstance(details, dict):
        details = {"value": details}
    try:
        encoded = json.dumps(details, ensure_ascii=False, default=str)
    except Exception:
        return {"detailsTruncated": True, "reason": "not serializable"}
    if len(encoded.encode("utf-8")) <= MAX_DETAILS_BYTES:
        return details
    return {
        "detailsTruncated": True,
        "reason": "details exceeded 16 KiB",
    }


def invalid_argument(issues, message=None):
    """Convenience constructor for INVALID_ARGUMENT with ``details.issues``."""
    if isinstance(issues, dict):
        issues = [issues]
    first = issues[0] if issues else {}
    text = message or "%s: %s" % (
        first.get("path", "<arguments>"),
        first.get("message", "invalid arguments"),
    )
    return RpcError("INVALID_ARGUMENT", text, {"issues": issues})


def rpc_error_response(request_id, code, message, rpc_code, details=None):
    """Build a JSON-RPC error envelope for envelope-level failures."""
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": rpc_code,
            "message": message,
            "data": {"errorCode": code, "retryable": False, "details": details or {}},
        },
    }
    return payload
