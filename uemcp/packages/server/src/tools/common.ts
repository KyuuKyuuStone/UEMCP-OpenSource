/**
 * 工具公共封装：返回封装（§5.0.1）、错误形态（§2.9）、策略门、审计。
 */
import { randomUUID } from "node:crypto";
import type { z } from "zod";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import {
  toolErrorRetryable,
  type PolicyMode,
  type ToolErrorShape,
  type ToolMeta,
  type ToolName,
} from "@uemcp/shared";
import type { Audit } from "../audit.js";
import type { BridgeClient, BridgeCallResult } from "../bridge/client.js";
import type { BridgeWatchdog } from "../bridge/watchdog.js";
import type { Logger } from "../logger.js";
import type { PolicyState } from "../policy.js";
import type { ElicitFn } from "../confirm.js";

export interface ToolContext {
  policy: PolicyState;
  bridge: BridgeClient;
  watchdog: BridgeWatchdog;
  audit: Audit;
  log: Logger;
  transport: string;
  sessionId?: string;
  clientInfo?: { name: string; version?: string };
  elicit: ElicitFn;
}

export function makeMeta(ctx: ToolContext, started: number): ToolMeta {
  const w = ctx.watchdog.state;
  return {
    requestId: "req_" + randomUUID(),
    durationMs: Date.now() - started,
    ...(w.ueVersion ? { ueVersion: w.ueVersion } : {}),
    ...(w.pluginVersion ? { pluginVersion: w.pluginVersion } : {}),
  };
}

export function okResult(
  tool: ToolName,
  summary: string,
  data: unknown,
  warnings: string[],
  meta: ToolMeta,
  extraContent?: CallToolResult["content"],
): CallToolResult {
  return {
    content: [
      { type: "text", text: summary },
      ...(extraContent ?? []),
    ],
    structuredContent: { ok: true, data, warnings, meta },
    isError: false,
  };
}

export function errResult(
  error: ToolErrorShape,
  meta: ToolMeta,
): CallToolResult {
  const text = `${error.code}: ${error.message}`;
  return {
    content: [{ type: "text", text }],
    structuredContent: { ok: false, error, meta },
    isError: true,
  };
}

export function toolError(
  code: ToolErrorShape["code"],
  message: string,
  details?: Record<string, unknown>,
): ToolErrorShape {
  return {
    code,
    message,
    retryable: toolErrorRetryable(code),
    ...(details !== undefined ? { details } : {}),
  };
}

/** zod 校验失败 → INVALID_ARGUMENT（details.issues，§2.9.4） */
export function invalidArgument(
  zerr: z.ZodError,
): ToolErrorShape {
  return toolError("INVALID_ARGUMENT", firstIssueMessage(zerr), {
    issues: zerr.issues.map((i) => ({
      path: i.path,
      code: i.code,
      message: i.message,
    })),
  });
}

function firstIssueMessage(zerr: z.ZodError): string {
  const i = zerr.issues[0];
  if (!i) return "Invalid arguments";
  const path = i.path.length ? `${i.path.map(String).join(".")}: ` : "";
  return `${path}${i.message}`;
}

/** P1/P2 审计（§6.5） */
export async function auditCall(
  ctx: ToolContext,
  args: {
    tool: ToolName;
    rpcMethod: string;
    requestId: string;
    durationMs: number;
    ok: boolean;
    errorCode: string | null;
    decision: "allowed" | "denied";
    confirmationMode?: "elicitation" | "policy" | "none";
    confirmationSwitch?: string;
    argsSummary: Record<string, unknown>;
  },
): Promise<void> {
  const w = ctx.watchdog.state;
  await ctx.audit.record({
    ts: new Date().toISOString(),
    requestId: args.requestId,
    sessionId: ctx.sessionId,
    client: ctx.clientInfo,
    transport: ctx.transport,
    tool: args.tool,
    rpcMethod: args.rpcMethod,
    policyMode: ctx.policy.mode as PolicyMode,
    decision: args.decision,
    ...(args.confirmationMode ? { confirmationMode: args.confirmationMode } : {}),
    ...(args.confirmationSwitch ? { confirmationSwitch: args.confirmationSwitch } : {}),
    argsSummary: args.argsSummary,
    durationMs: args.durationMs,
    ok: args.ok,
    errorCode: args.errorCode,
    ...(w.ueVersion ? { ueVersion: w.ueVersion } : {}),
    ...(w.pluginVersion ? { pluginVersion: w.pluginVersion } : {}),
  });
}

export function summarizeOut(
  tool: ToolName,
  data: Record<string, unknown> | undefined,
  warnings: string[],
): string {
  const suffix = warnings.length ? ` (warnings: ${warnings.join(", ")})` : "";
  const d = data ?? {};
  switch (tool) {
    case "ue_actor_query":
      return `ue_actor_query: ${d.returned ?? 0} actors returned (total ${d.total ?? 0})${suffix}`;
    case "ue_asset_search":
      return `ue_asset_search: ${d.returned ?? 0} assets returned (total ${d.total ?? 0})${suffix}`;
    case "ue_viewport_capture":
      return `ue_viewport_capture: ${String(d.format ?? "png")} ${d.width ?? 0}x${d.height ?? 0} saved to ${String(d.path ?? "")}${suffix}`;
    case "ue_console_command":
      return `ue_console_command: dispatched=${String(d.dispatched ?? false)}, outputAvailable=${String(d.outputAvailable ?? false)}${suffix}`;
    case "ue_python_exec":
      return `ue_python_exec: mode=${String(d.mode ?? "exec")} completed${suffix}`;
    default: {
      const head = Object.keys(d)
        .slice(0, 6)
        .map((k) => `${k}=${preview(d[k])}`)
        .join(", ");
      return `${tool}: ${head || "ok"}${suffix}`;
    }
  }
}

function preview(v: unknown): string {
  if (v === null || v === undefined) return "null";
  if (typeof v === "string") return v.length > 60 ? v.slice(0, 57) + "..." : v;
  if (typeof v === "object") return Array.isArray(v) ? `[${v.length} items]` : "{...}";
  return String(v);
}

export type { BridgeCallResult };

export interface ToolDef {
  name: ToolName;
  rpcMethod: string;
  title: string;
  description: string;
  /** 当前策略下注册用的 zod schema（read-only 收窄，§5.11） */
  schemaFor(p: PolicyState): z.ZodTypeAny;
  /** 发往桥接的默认超时（§2.6：默认 30s，单工具最高 120s） */
  timeoutMs: number;
  handle(ctx: ToolContext, args: Record<string, unknown>): Promise<CallToolResult>;
}
