import { ConsoleCommandInput } from "@uemcp/shared";
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

export const consoleCommandTool: ToolDef = {
  name: "ue_console_command",
  rpcMethod: "console.command",
  title: "Execute Console Command",
  description:
    "Execute an Unreal console command in the editor or PIE world. P2: requires --policy full + --allow-console (server) AND bridge allowConsole. Bridge enforces allowlist and a permanent deny table (quit/exec/py/...). Output capture is not supported in MVP (outputAvailable=false).",
  timeoutMs: 30000,
  schemaFor(_p: PolicyState) {
    return ConsoleCommandInput;
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    if (!isToolVisible(consoleCommandTool.name, ctx.policy)) {
      return errResult(
        toolError("TOOL_DISABLED", "Tool not available under current policy/switches", {
          gate: toolDisabledGate(consoleCommandTool.name, ctx.policy),
        }),
        makeMeta(ctx, started),
      );
    }
    const parsed = ConsoleCommandInput.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    // §5.8/§6.3-5 确认（Major-2）：elicitation 优先；客户端不支持时
    // --allow-console 兼作策略级确认（工具可见本身已要求该开关）。
    const outcome = await ctx.elicit(
      `UEMCP requests executing a console command in the editor: "${String(parsed.data.command)}". Allow?`,
    );
    if (outcome === "declined") {
      const meta = makeMeta(ctx, started);
      await auditCall(ctx, {
        tool: consoleCommandTool.name,
        rpcMethod: consoleCommandTool.rpcMethod,
        requestId: meta.requestId,
        durationMs: meta.durationMs,
        ok: false,
        errorCode: "CONFIRMATION_DENIED",
        decision: "denied",
        confirmationMode: "elicitation",
        argsSummary: summarizeArgs(consoleCommandTool.name, rawArgs),
      });
      return errResult(
        toolError("CONFIRMATION_DENIED", "User declined the console command"),
        meta,
      );
    }
    const confirmationMode = outcome === "approved" ? "elicitation" : "policy";
    const res = await ctx.bridge.call("console.command", parsed.data as Record<string, unknown>, consoleCommandTool.timeoutMs) /* 副作用：不自动重试 */;
    const meta = makeMeta(ctx, started);
    await auditCall(ctx, {
      tool: consoleCommandTool.name,
      rpcMethod: consoleCommandTool.rpcMethod,
      requestId: meta.requestId,
      durationMs: meta.durationMs,
      ok: res.ok,
      errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
      decision: "allowed",
      confirmationMode,
      ...(confirmationMode === "policy" ? { confirmationSwitch: "--allow-console" } : {}),
      argsSummary: summarizeArgs(consoleCommandTool.name, rawArgs),
    });
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      consoleCommandTool.name,
      summarizeOut(consoleCommandTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};
