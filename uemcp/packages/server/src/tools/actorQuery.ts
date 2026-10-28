import { ActorQueryInput } from "@uemcp/shared";
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
