import { AssetSearchInput } from "@uemcp/shared";
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

export const assetSearchTool: ToolDef = {
  name: "ue_asset_search",
  rpcMethod: "asset.search",
  title: "Search Unreal Assets",
  description:
    "Search assets by path/name/class via AssetRegistry; optional dependency and referencer queries (BFS depth <= 3). Read-only, paginated.",
  timeoutMs: 30000,
  schemaFor(_p: PolicyState) {
    return AssetSearchInput;
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const parsed = AssetSearchInput.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const res = await ctx.bridge.call("asset.search", parsed.data as Record<string, unknown>, assetSearchTool.timeoutMs, { retriable: true });
    const meta = makeMeta(ctx, started);
    // B-3.7：读工具统一纳入审计（仅摘要；invalidArgument 早退不审计，与写工具口径一致）
    await auditCall(ctx, {
      tool: assetSearchTool.name,
      rpcMethod: assetSearchTool.rpcMethod,
      requestId: meta.requestId,
      durationMs: meta.durationMs,
      ok: res.ok,
      errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
      decision: "allowed",
      argsSummary: summarizeArgs(assetSearchTool.name, parsed.data as Record<string, unknown>),
      errorDetails: res.error?.details,
    });
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      assetSearchTool.name,
      summarizeOut(assetSearchTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};
