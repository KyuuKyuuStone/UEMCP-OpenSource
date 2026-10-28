import { ActorEditInput } from "@uemcp/shared";
import { isToolVisible, toolDisabledGate, type PolicyState } from "../policy.js";
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
import { summarizeArgs } from "../audit.js";

export const actorEditTool: ToolDef = {
  name: "ue_actor_edit",
  rpcMethod: "actor.edit",
  title: "Edit Unreal Actors",
  description:
    "Batch edit actors: spawn, delete, set_transform, set_properties (whitelist only), duplicate, select. Runs in an editor transaction (atomic by default). delete requires confirmation (elicitation or --allow-destructive); dryRun requires none. Rejected while PIE is running.",
  timeoutMs: 30000,
  schemaFor(_p: PolicyState) {
    return ActorEditInput;
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    if (!isToolVisible(actorEditTool.name, ctx.policy)) {
      return errResult(
        toolError("TOOL_DISABLED", "Tool not available under current policy", {
          gate: toolDisabledGate(actorEditTool.name, ctx.policy),
        }),
        makeMeta(ctx, started),
      );
    }
    const parsed = ActorEditInput.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const args = parsed.data;
    const ops = args.operations as Array<{ op: string; confirm?: boolean }>;

    // §5.3 确认要求：delete（未逐 op confirm、非 dryRun）需要确认
    const needsConfirm =
      !args.dryRun && ops.some((o) => o.op === "delete" && o.confirm !== true);
    let confirmationMode: "elicitation" | "policy" | "none" = "none";
    let confirmationSwitch: string | undefined;
    if (needsConfirm) {
      const outcome = await ctx.elicit(
        `UEMCP requests a destructive operation: delete ${ops.filter((o) => o.op === "delete" && o.confirm !== true).length} actor(s). Allow?`,
      );
      if (outcome === "declined") {
        const meta = makeMeta(ctx, started);
        await auditCall(ctx, {
          tool: actorEditTool.name,
          rpcMethod: actorEditTool.rpcMethod,
          requestId: meta.requestId,
          durationMs: meta.durationMs,
          ok: false,
          errorCode: "CONFIRMATION_DENIED",
          decision: "denied",
          confirmationMode: "elicitation",
          argsSummary: summarizeArgs(actorEditTool.name, rawArgs),
        });
        return errResult(
          toolError("CONFIRMATION_DENIED", "User declined the destructive operation"),
          meta,
        );
      }
      if (outcome === "unsupported" && !ctx.policy.allowDestructive) {
        const meta = makeMeta(ctx, started);
        await auditCall(ctx, {
          tool: actorEditTool.name,
          rpcMethod: actorEditTool.rpcMethod,
          requestId: meta.requestId,
          durationMs: meta.durationMs,
          ok: false,
          errorCode: "CONFIRMATION_REQUIRED",
          decision: "denied",
          argsSummary: summarizeArgs(actorEditTool.name, rawArgs),
        });
        return errResult(
          toolError(
            "CONFIRMATION_REQUIRED",
            "Destructive operation requires confirmation: client elicitation not available and --allow-destructive is off",
          ),
          meta,
        );
      }
      confirmationMode = outcome === "approved" ? "elicitation" : "policy";
      if (confirmationMode === "policy") confirmationSwitch = "--allow-destructive";
    }

    const res = await ctx.bridge.call("actor.edit", args as unknown as Record<string, unknown>, actorEditTool.timeoutMs) /* 写方法：不自动重试 */;
    const meta = makeMeta(ctx, started);
    await auditCall(ctx, {
      tool: actorEditTool.name,
      rpcMethod: actorEditTool.rpcMethod,
      requestId: meta.requestId,
      durationMs: meta.durationMs,
      ok: res.ok,
      errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
      decision: "allowed",
      ...(needsConfirm ? { confirmationMode, confirmationSwitch } : {}),
      argsSummary: summarizeArgs(actorEditTool.name, rawArgs),
    });
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      actorEditTool.name,
      summarizeOut(actorEditTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};
