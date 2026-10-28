import { PythonExecInput } from "@uemcp/shared";
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

export const pythonExecTool: ToolDef = {
  name: "ue_python_exec",
  rpcMethod: "python.exec",
  title: "Execute Python in Editor",
  description:
    "Execute Python code on the editor game thread. P2: requires --policy full + --allow-exec (server) AND bridge allowExec. Enabling this equals handing the editor process to the caller; avoid infinite loops (timeouts cannot interrupt game-thread code). Audit records code hash only.",
  timeoutMs: 120000,
  schemaFor(_p: PolicyState) {
    return PythonExecInput;
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    if (!isToolVisible(pythonExecTool.name, ctx.policy)) {
      return errResult(
        toolError("TOOL_DISABLED", "Tool not available under current policy/switches", {
          gate: toolDisabledGate(pythonExecTool.name, ctx.policy),
        }),
        makeMeta(ctx, started),
      );
    }
    const parsed = PythonExecInput.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const args = parsed.data;
    // §5.9/§6.3-5 确认（Major-2）：elicitation 优先；客户端不支持时
    // --allow-exec 兼作策略级确认（工具可见本身已要求该开关）。
    const outcome = await ctx.elicit(
      "UEMCP requests executing arbitrary Python code inside the Unreal editor process. Allow?",
    );
    if (outcome === "declined") {
      const meta = makeMeta(ctx, started);
      await auditCall(ctx, {
        tool: pythonExecTool.name,
        rpcMethod: pythonExecTool.rpcMethod,
        requestId: meta.requestId,
        durationMs: meta.durationMs,
        ok: false,
        errorCode: "CONFIRMATION_DENIED",
        decision: "denied",
        confirmationMode: "elicitation",
        argsSummary: summarizeArgs(pythonExecTool.name, rawArgs),
      });
      return errResult(
        toolError("CONFIRMATION_DENIED", "User declined the Python execution"),
        meta,
      );
    }
    const confirmationMode = outcome === "approved" ? "elicitation" : "policy";
    const res = await ctx.bridge.call(
      "python.exec",
      args as unknown as Record<string, unknown>,
      Math.max(args.timeoutMs, 30000) /* 写方法：不自动重试 */,
    );
    const meta = makeMeta(ctx, started);
    // §6.3-5：审计仅 hash/长度，永不记录源码（§6.5 红线）
    await auditCall(ctx, {
      tool: pythonExecTool.name,
      rpcMethod: pythonExecTool.rpcMethod,
      requestId: meta.requestId,
      durationMs: meta.durationMs,
      ok: res.ok,
      errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
      decision: "allowed",
      confirmationMode,
      ...(confirmationMode === "policy" ? { confirmationSwitch: "--allow-exec" } : {}),
      argsSummary: summarizeArgs(pythonExecTool.name, rawArgs),
    });
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      pythonExecTool.name,
      summarizeOut(pythonExecTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};
