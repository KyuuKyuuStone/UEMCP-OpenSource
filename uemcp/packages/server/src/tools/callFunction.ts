/**
 * ue_call_function（§object.call，2026-10-30 通用原语）：
 * 按名调用任意对象上的 BlueprintCallable 函数（写类）。
 *
 * 设计要点：
 * - **通用**：不对接任何具体业务框架；业务侧的 CustomDomainCmdHandler 只是普通对象，
 *   调它的 FlyToMonitorPoint 与调任何函数走同一条路径。
 * - 写门：read-only 下**不注册**（与 actor.edit 一致）；standard/full 下仍需
 *   Bridge allowWrite=true（否则 bridge 返回 PERMISSION_DENIED gate=bridge.allowWrite）。
 * - 审计：与 actor.edit 同级（decision=allowed + argsSummary）。
 * - void 函数返回 returned:null + returnedVoid:true，**不是错误**。
 */
import { callFunctionInputSchema } from "@uemcp/shared";
import { summarizeArgs } from "../audit.js";
import {
  auditCall,
  errResult,
  invalidArgument,
  makeMeta,
  okResult,
  toolError,
  type ToolContext,
  type ToolDef,
} from "./common.js";

export const callFunctionTool: ToolDef = {
  name: "ue_call_function",
  rpcMethod: "object.call",
  title: "Call Object Function",
  description:
    "Call a BlueprintCallable function by name on an object or actor (target may be a path or a class name; function names are matched case-insensitively via snake_case). Arguments are passed positionally as JSON. Returns the function's return value, or returnedVoid=true when the function returns nothing. Write action: requires policy standard or higher AND bridge allowWrite.",
  timeoutMs: 60000,
  schemaFor() {
    return callFunctionInputSchema();
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const parsed = callFunctionInputSchema().safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    if (ctx.policy.mode === "read-only") {
      // 防御：read-only 下本工具本不应注册（同 ue_actor_edit）
      return errResult(
        toolError("PERMISSION_DENIED", "ue_call_function is not available under read-only policy", {
          gate: "server.policy",
        }),
        makeMeta(ctx, started),
      );
    }
    const res = await ctx.bridge.call("object.call", parsed.data as Record<string, unknown>, callFunctionTool.timeoutMs, {
      retriable: false,
    });
    const meta = makeMeta(ctx, started);
    await auditCall(ctx, {
      tool: callFunctionTool.name,
      rpcMethod: callFunctionTool.rpcMethod,
      requestId: meta.requestId,
      durationMs: meta.durationMs,
      ok: res.ok,
      errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
      decision: "allowed",
      argsSummary: summarizeArgs(callFunctionTool.name, rawArgs),
    });
    if (!res.ok) return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    const data = res.data as { returned?: unknown; returnedVoid?: boolean; function?: string };
    const summary = data.returnedVoid
      ? `${data.function ?? "call"} returned void`
      : `${data.function ?? "call"} returned ${JSON.stringify(data.returned)}`;
    return okResult(callFunctionTool.name, summary, res.data, res.warnings, meta);
  },
};
