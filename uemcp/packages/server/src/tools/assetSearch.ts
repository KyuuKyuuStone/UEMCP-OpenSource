import { AssetSearchInput } from "@uemcp/shared";
import type { PolicyState } from "../policy.js";
import {
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
