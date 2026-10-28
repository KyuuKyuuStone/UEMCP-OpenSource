import { BLUEPRINT_WRITE_ACTIONS, blueprintInputSchema } from "@uemcp/shared";
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

type BlueprintArgs = z.infer<ReturnType<typeof blueprintInputSchema>>;

export const blueprintTool: ToolDef = {
  name: "ue_blueprint",
  rpcMethod: "blueprint.query",
  title: "Blueprint Query / Compile",
  description:
    "Read blueprint structure (parent class, variables, components, graphs, interfaces, compile state; node read is experimental) and trigger compilation. Node creation/wiring is not supported (CAPABILITY_UNAVAILABLE in P2).",
  timeoutMs: 60000,
  schemaFor(p: PolicyState) {
    return blueprintInputSchema(narrowedActions(blueprintTool.name, p) ?? undefined);
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const schema = blueprintInputSchema(narrowedActions(blueprintTool.name, ctx.policy));
    const parsed = schema.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const args = parsed.data as BlueprintArgs;
    // m-13（审查报告）：query + save:true 会写盘（保存蓝图包），必须计入写操作——
    // 否则 read-only 下静默写盘、standard/full 下不审计且可自动重试。
    // BLUEPRINT_WRITE_ACTIONS（action 维度，与 Bridge 端 WRITE_ACTIONS={compile} 同口径）
    // 保持不变；此处补上参数维度的 save===true。
    const isWrite =
      BLUEPRINT_WRITE_ACTIONS.has(args.action) ||
      (args.action === "query" && args.save === true);

    if (ctx.policy.mode === "read-only" && isWrite) {
      return errResult(
        toolError("PERMISSION_DENIED", "Write action not allowed under read-only policy", {
          gate: "server.policy",
        }),
        makeMeta(ctx, started),
      );
    }

    const res = await ctx.bridge.call("blueprint.query", args as unknown as Record<string, unknown>, blueprintTool.timeoutMs, { retriable: !isWrite });
    const meta = makeMeta(ctx, started);
    if (isWrite) {
      await auditCall(ctx, {
        tool: blueprintTool.name,
        rpcMethod: blueprintTool.rpcMethod,
        requestId: meta.requestId,
        durationMs: meta.durationMs,
        ok: res.ok,
        errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
        decision: "allowed",
        argsSummary: summarizeArgs(blueprintTool.name, rawArgs),
      });
    }
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      blueprintTool.name,
      summarizeOut(blueprintTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};
