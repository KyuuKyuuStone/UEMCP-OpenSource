import { MATERIAL_WRITE_ACTIONS, materialInputSchema } from "@uemcp/shared";
import type { z } from "zod";
import { narrowedActions, type PolicyState } from "../policy.js";
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

type MaterialArgs = z.infer<ReturnType<typeof materialInputSchema>>;

export const materialParamsTool: ToolDef = {
  name: "ue_material_params",
  rpcMethod: "material.params",
  title: "Material Parameters",
  description:
    "List/get material or material-instance parameters; set parameters on MaterialInstanceConstant only (base materials rejected with NOT_AN_INSTANCE); create material instances.",
  timeoutMs: 30000,
  schemaFor(p: PolicyState) {
    return materialInputSchema(narrowedActions(materialParamsTool.name, p) ?? undefined);
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const schema = materialInputSchema(narrowedActions(materialParamsTool.name, ctx.policy));
    const parsed = schema.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const args = parsed.data as MaterialArgs;
    const isWrite = MATERIAL_WRITE_ACTIONS.has(args.action);

    if (ctx.policy.mode === "read-only" && isWrite) {
      return errResult(
        toolError("PERMISSION_DENIED", "Write action not allowed under read-only policy", {
          gate: "server.policy",
        }),
        makeMeta(ctx, started),
      );
    }

    const res = await ctx.bridge.call("material.params", args as unknown as Record<string, unknown>, materialParamsTool.timeoutMs, { retriable: !isWrite });
    const meta = makeMeta(ctx, started);
    if (isWrite) {
      await auditCall(ctx, {
        tool: materialParamsTool.name,
        rpcMethod: materialParamsTool.rpcMethod,
        requestId: meta.requestId,
        durationMs: meta.durationMs,
        ok: res.ok,
        errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
        decision: "allowed",
        argsSummary: summarizeArgs(materialParamsTool.name, rawArgs),
      });
    }
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      materialParamsTool.name,
      summarizeOut(materialParamsTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};
