import { LEVEL_WRITE_ACTIONS, levelInputSchema } from "@uemcp/shared";
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

type LevelArgs = z.infer<ReturnType<typeof levelInputSchema>>;

export const levelControlTool: ToolDef = {
  name: "ue_level_control",
  rpcMethod: "level.control",
  title: "Control Level",
  description:
    "Query current level and dirty packages; open, save, create levels. open discards unsaved changes only with allowDiscardUnsaved+confirm; save_all requires confirmation (elicitation or --allow-destructive).",
  timeoutMs: 30000,
  schemaFor(p: PolicyState) {
    return levelInputSchema(narrowedActions(levelControlTool.name, p) ?? undefined);
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const schema = levelInputSchema(narrowedActions(levelControlTool.name, ctx.policy));
    const parsed = schema.safeParse(rawArgs);
    if (!parsed.success) {
      // read-only 收窄的写 action → INVALID_ARGUMENT（§5.11 调用语义）
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const args = parsed.data as LevelArgs;
    const isWrite = LEVEL_WRITE_ACTIONS.has(args.action);

    // 防御：read-only 下绕过 Schema 直达 handler 的写 action（§5.11）
    if (ctx.policy.mode === "read-only" && isWrite) {
      return errResult(
        toolError("PERMISSION_DENIED", "Write action not allowed under read-only policy", {
          gate: "server.policy",
        }),
        makeMeta(ctx, started),
      );
    }

    let confirmationMode: "elicitation" | "policy" | "none" = "none";
    let confirmationSwitch: string | undefined;

    if (isWrite) {
      if (args.action === "save_all" && !args.confirm) {
        // §2.9.7：save_all confirm=false → CONFIRMATION_REQUIRED
        const outcome = await ctx.elicit(
          "UEMCP requests a destructive operation: save_all (batch overwrite dirty packages on disk). Allow?",
        );
        if (outcome === "declined") {
          return denied(ctx, started, "CONFIRMATION_DENIED", rawArgs, "elicitation");
        }
        if (outcome === "unsupported" && !ctx.policy.allowDestructive) {
          return denied(ctx, started, "CONFIRMATION_REQUIRED", rawArgs);
        }
        confirmationMode = outcome === "approved" ? "elicitation" : "policy";
        if (confirmationMode === "policy") confirmationSwitch = "--allow-destructive";
        args.confirm = true; // 策略级确认等价（§2.9.7 执行打开/保存）
      } else if (
        args.action === "open" &&
        args.allowDiscardUnsaved &&
        !args.confirm &&
        ctx.policy.allowDestructive
      ) {
        // §2.9.7：--allow-destructive 已满足破坏性确认 → 执行打开
        confirmationMode = "policy";
        confirmationSwitch = "--allow-destructive";
        args.confirm = true;
      }
    }

    const res = await ctx.bridge.call("level.control", args as unknown as Record<string, unknown>, levelControlTool.timeoutMs, { retriable: !isWrite });
    const meta = makeMeta(ctx, started);
    if (isWrite) {
      await auditCall(ctx, {
        tool: levelControlTool.name,
        rpcMethod: levelControlTool.rpcMethod,
        requestId: meta.requestId,
        durationMs: meta.durationMs,
        ok: res.ok,
        errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
        decision: "allowed",
        ...(confirmationMode !== "none" ? { confirmationMode, confirmationSwitch } : {}),
        argsSummary: summarizeArgs(levelControlTool.name, rawArgs),
      });
    }
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      levelControlTool.name,
      summarizeOut(levelControlTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};

async function denied(
  ctx: ToolContext,
  started: number,
  code: "CONFIRMATION_REQUIRED" | "CONFIRMATION_DENIED",
  rawArgs: Record<string, unknown>,
  confirmationMode?: "elicitation",
) {
  const meta = makeMeta(ctx, started);
  await auditCall(ctx, {
    tool: levelControlTool.name,
    rpcMethod: levelControlTool.rpcMethod,
    requestId: meta.requestId,
    durationMs: meta.durationMs,
    ok: false,
    errorCode: code,
    decision: "denied",
    ...(confirmationMode ? { confirmationMode } : {}),
    argsSummary: summarizeArgs(levelControlTool.name, rawArgs),
  });
  return errResult(
    toolError(
      code,
      code === "CONFIRMATION_REQUIRED"
        ? "Confirmation required: client elicitation not available and --allow-destructive is off"
        : "User declined the destructive operation",
    ),
    meta,
  );
}
