import { ActorQueryInput } from "@uemcp/shared";
import { summarizeArgs } from "../audit.js";
import type { PolicyState } from "../policy.js";
import {
  auditCall,
  errResult,
  invalidArgument,
  makeMeta,
  okResult,
  summarizeOut,
  toolError,
  type ToolContext,
  type ToolDef,
} from "./common.js";

export const actorQueryTool: ToolDef = {
  name: "ue_actor_query",
  rpcMethod: "actor.query",
  title: "Query Unreal Actors",
  description:
    "Query actors in the current editor level or selection. Read-only. Supports class/name/label/tag/folder/component filters, field selection, sorting and pagination.",
  timeoutMs: 30000,
  schemaFor(_p: PolicyState) {
    return ActorQueryInput;
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const parsed = ActorQueryInput.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const res = await ctx.bridge.call("actor.query", parsed.data as Record<string, unknown>, actorQueryTool.timeoutMs, { retriable: true });
    const meta = makeMeta(ctx, started);
    // B-3.7：读工具统一纳入审计（仅摘要；invalidArgument 早退不审计，与写工具口径一致）
    await auditCall(ctx, {
      tool: actorQueryTool.name,
      rpcMethod: actorQueryTool.rpcMethod,
      requestId: meta.requestId,
      durationMs: meta.durationMs,
      ok: res.ok,
      errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
      decision: "allowed",
      argsSummary: summarizeArgs(actorQueryTool.name, parsed.data as Record<string, unknown>),
      errorDetails: res.error?.details,
    });
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      actorQueryTool.name,
      summarizeOut(actorQueryTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};
