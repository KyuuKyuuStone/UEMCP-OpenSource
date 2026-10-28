import type { ToolErrorCode } from "./errors.js";

/** 架构文档 §10.1 关键类型 */
export type PolicyMode = "read-only" | "standard" | "full";

export interface ToolMeta {
  requestId: string;
  durationMs: number;
  ueVersion?: string;
  pluginVersion?: string;
}

export interface ToolErrorShape {
  code: ToolErrorCode;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown>;
}

export interface ToolOk<T> {
  ok: true;
  data: T;
  warnings: string[];
  meta: ToolMeta;
}

export interface ToolErr {
  ok: false;
  error: ToolErrorShape;
  meta: ToolMeta;
}

export type ToolResult<T> = ToolOk<T> | ToolErr;

/** 桥接 RPC 成功响应（§2.8） */
export interface BridgeRpcOk<T = unknown> {
  ok: true;
  data: T;
  warnings: string[];
  meta: Record<string, unknown>;
}

/** 桥接发现文件（§2.4） */
export interface BridgeDiscoveryFile {
  schemaVersion: number;
  pid: number;
  projectDir: string;
  projectFile: string;
  host: string;
  port: number;
  url: string;
  token: string;
  ueVersion: string;
  pluginVersion: string;
  bridgeProtocol: number;
  capabilities: {
    python: boolean;
    screenshot: boolean;
    blueprintRead: boolean;
    blueprintNodeRead: boolean;
    blueprintCompile: boolean;
    animBlueprintEdit: boolean;
    assetRegistry: boolean;
    console: boolean;
  };
  startedAt: string;
}

/** 审计记录（§6.5） */
export interface AuditRecord {
  ts: string;
  requestId: string;
  sessionId?: string;
  client?: { name: string; version?: string };
  transport?: string;
  tool: string;
  rpcMethod: string;
  policyMode: PolicyMode;
  decision: "allowed" | "denied";
  confirmationMode?: "elicitation" | "policy" | "none";
  confirmationSwitch?: string;
  argsSummary: Record<string, unknown>;
  durationMs: number;
  ok: boolean;
  errorCode: string | null;
  ueVersion?: string;
  pluginVersion?: string;
}
