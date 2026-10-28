/**
 * 错误码枚举与映射 —— 架构文档 §2.9。
 * 协议层错误码（§2.9.2）与工具级错误码（§2.9.3）分层；
 * TIMEOUT 已退役（§2.9.3 命名规则）。
 */

export const PROTOCOL_ERROR = {
  PARSE_ERROR: { jsonRpc: -32700, http: 400 },
  INVALID_REQUEST: { jsonRpc: -32600, http: 400 },
  METHOD_NOT_FOUND: { jsonRpc: -32601, http: 404 },
  INVALID_PARAMS: { jsonRpc: -32602, http: 400 },
  SESSION_NOT_FOUND: { jsonRpc: -32001, http: 404 },
  UNAUTHORIZED: { jsonRpc: -32019, http: 401 },
  PAYLOAD_TOO_LARGE: { jsonRpc: -32011, http: 413 },
  RATE_LIMITED: { jsonRpc: -32012, http: 429 },
  INTERNAL: { jsonRpc: -32603, http: 500 },
} as const;

export type ProtocolErrorCode = keyof typeof PROTOCOL_ERROR;

/** 工具级错误码（§2.9.3 全表） */
export const TOOL_ERROR_CODES = [
  "INVALID_ARGUMENT",
  "INTERNAL",
  "ACTOR_NOT_FOUND",
  "AMBIGUOUS_SELECTOR",
  "CLASS_NOT_FOUND",
  "ASSET_NOT_FOUND",
  "TRANSACTION_FAILED",
  "LEVEL_NOT_FOUND",
  "LEVEL_LOAD_FAILED",
  "UNSAVED_CHANGES",
  "SEARCH_TIMEOUT",
  "ASSET_REGISTRY_UNAVAILABLE",
  "MATERIAL_NOT_FOUND",
  "NOT_A_MATERIAL",
  "NOT_AN_INSTANCE",
  "PARAM_NOT_FOUND",
  "TYPE_MISMATCH",
  "ALREADY_EXISTS",
  "CAPTURE_FAILED",
  "CAPTURE_TIMEOUT",
  "PIE_NOT_RUNNING",
  "BLUEPRINT_NOT_FOUND",
  "NOT_A_BLUEPRINT",
  "GRAPH_NOT_FOUND",
  "COMPILE_FAILED",
  "EXEC_DISABLED",
  "BRIDGE_UNAVAILABLE",
  "BRIDGE_TIMEOUT",
  "BRIDGE_BUSY",
  "PERMISSION_DENIED",
  "TOOL_DISABLED",
  "CONFIRMATION_REQUIRED",
  "NOT_FOUND",
  "CONFLICT",
  "UNSUPPORTED",
  "EXECUTION_ERROR",
  "EDITOR_UNSAFE_STATE",
  "PAYLOAD_TOO_LARGE",
  "RATE_LIMITED",
  "SAVE_FAILED",
  "PYTHON_ERROR",
  "RESULT_NOT_SERIALIZABLE",
  "CAPABILITY_UNAVAILABLE",
  "COMMAND_NOT_ALLOWED",
  "CONFIRMATION_DENIED",
] as const;

export type ToolErrorCode = (typeof TOOL_ERROR_CODES)[number];

export interface ToolErrorMeta {
  bridgeJsonRpc: number;
  bridgeHttp: number;
  retryable: boolean;
}

/** §2.9.3 错误码表：字符串码 → 桥接 JSON-RPC 数字码 / 桥接 HTTP / retryable */
export const TOOL_ERROR_TABLE: Record<ToolErrorCode, ToolErrorMeta> = {
  INVALID_ARGUMENT: { bridgeJsonRpc: -32602, bridgeHttp: 400, retryable: false },
  INTERNAL: { bridgeJsonRpc: -32603, bridgeHttp: 500, retryable: false },
  ACTOR_NOT_FOUND: { bridgeJsonRpc: -32044, bridgeHttp: 404, retryable: false },
  AMBIGUOUS_SELECTOR: { bridgeJsonRpc: -32021, bridgeHttp: 409, retryable: false },
  CLASS_NOT_FOUND: { bridgeJsonRpc: -32022, bridgeHttp: 404, retryable: false },
  ASSET_NOT_FOUND: { bridgeJsonRpc: -32023, bridgeHttp: 404, retryable: false },
  TRANSACTION_FAILED: { bridgeJsonRpc: -32024, bridgeHttp: 409, retryable: false },
  LEVEL_NOT_FOUND: { bridgeJsonRpc: -32025, bridgeHttp: 404, retryable: false },
  LEVEL_LOAD_FAILED: { bridgeJsonRpc: -32026, bridgeHttp: 500, retryable: false },
  UNSAVED_CHANGES: { bridgeJsonRpc: -32027, bridgeHttp: 409, retryable: false },
  SEARCH_TIMEOUT: { bridgeJsonRpc: -32028, bridgeHttp: 504, retryable: true },
  ASSET_REGISTRY_UNAVAILABLE: { bridgeJsonRpc: -32029, bridgeHttp: 503, retryable: true },
  MATERIAL_NOT_FOUND: { bridgeJsonRpc: -32030, bridgeHttp: 404, retryable: false },
  NOT_A_MATERIAL: { bridgeJsonRpc: -32031, bridgeHttp: 400, retryable: false },
  NOT_AN_INSTANCE: { bridgeJsonRpc: -32032, bridgeHttp: 409, retryable: false },
  PARAM_NOT_FOUND: { bridgeJsonRpc: -32033, bridgeHttp: 404, retryable: false },
  TYPE_MISMATCH: { bridgeJsonRpc: -32034, bridgeHttp: 400, retryable: false },
  ALREADY_EXISTS: { bridgeJsonRpc: -32035, bridgeHttp: 409, retryable: false },
  CAPTURE_FAILED: { bridgeJsonRpc: -32036, bridgeHttp: 500, retryable: false },
  CAPTURE_TIMEOUT: { bridgeJsonRpc: -32037, bridgeHttp: 504, retryable: true },
  PIE_NOT_RUNNING: { bridgeJsonRpc: -32038, bridgeHttp: 409, retryable: false },
  BLUEPRINT_NOT_FOUND: { bridgeJsonRpc: -32039, bridgeHttp: 404, retryable: false },
  NOT_A_BLUEPRINT: { bridgeJsonRpc: -32040, bridgeHttp: 400, retryable: false },
  GRAPH_NOT_FOUND: { bridgeJsonRpc: -32041, bridgeHttp: 404, retryable: false },
  COMPILE_FAILED: { bridgeJsonRpc: -32042, bridgeHttp: 500, retryable: false },
  EXEC_DISABLED: { bridgeJsonRpc: -32043, bridgeHttp: 403, retryable: false },
  BRIDGE_UNAVAILABLE: { bridgeJsonRpc: -32000, bridgeHttp: 503, retryable: true },
  BRIDGE_TIMEOUT: { bridgeJsonRpc: -32020, bridgeHttp: 504, retryable: true },
  BRIDGE_BUSY: { bridgeJsonRpc: -32002, bridgeHttp: 429, retryable: true },
  PERMISSION_DENIED: { bridgeJsonRpc: -32003, bridgeHttp: 403, retryable: false },
  TOOL_DISABLED: { bridgeJsonRpc: -32004, bridgeHttp: 403, retryable: false },
  CONFIRMATION_REQUIRED: { bridgeJsonRpc: -32005, bridgeHttp: 428, retryable: false },
  NOT_FOUND: { bridgeJsonRpc: -32006, bridgeHttp: 404, retryable: false },
  CONFLICT: { bridgeJsonRpc: -32007, bridgeHttp: 409, retryable: false },
  UNSUPPORTED: { bridgeJsonRpc: -32008, bridgeHttp: 501, retryable: false },
  EXECUTION_ERROR: { bridgeJsonRpc: -32009, bridgeHttp: 500, retryable: false },
  EDITOR_UNSAFE_STATE: { bridgeJsonRpc: -32010, bridgeHttp: 409, retryable: true },
  PAYLOAD_TOO_LARGE: { bridgeJsonRpc: -32011, bridgeHttp: 413, retryable: false },
  RATE_LIMITED: { bridgeJsonRpc: -32012, bridgeHttp: 429, retryable: true },
  SAVE_FAILED: { bridgeJsonRpc: -32013, bridgeHttp: 500, retryable: false },
  PYTHON_ERROR: { bridgeJsonRpc: -32014, bridgeHttp: 500, retryable: false },
  RESULT_NOT_SERIALIZABLE: { bridgeJsonRpc: -32015, bridgeHttp: 500, retryable: false },
  CAPABILITY_UNAVAILABLE: { bridgeJsonRpc: -32016, bridgeHttp: 501, retryable: false },
  COMMAND_NOT_ALLOWED: { bridgeJsonRpc: -32017, bridgeHttp: 403, retryable: false },
  CONFIRMATION_DENIED: { bridgeJsonRpc: -32018, bridgeHttp: 403, retryable: false },
};

export function isToolErrorCode(code: string): code is ToolErrorCode {
  return Object.prototype.hasOwnProperty.call(TOOL_ERROR_TABLE, code);
}

export function toolErrorRetryable(code: ToolErrorCode): boolean {
  return TOOL_ERROR_TABLE[code].retryable;
}

/**
 * 桥接错误码 → 数字码反查（mock/测试与桥接端映射用）。
 * 数字码在表中唯一（-32001 专用于协议层 SESSION_NOT_FOUND，不在本表）。
 */
const JSONRPC_TO_CODE = new Map<number, ToolErrorCode>(
  (Object.keys(TOOL_ERROR_TABLE) as ToolErrorCode[]).map((c) => [
    TOOL_ERROR_TABLE[c].bridgeJsonRpc,
    c,
  ]),
);

export function toolCodeFromJsonRpc(code: number): ToolErrorCode | undefined {
  return JSONRPC_TO_CODE.get(code);
}
