/**
 * ue_pie_control（§pie.control，2026-10-30 需求 #1）：
 * Play-In-Editor 的 start/stop/restart/status。
 * - 恒注册；read-only 下 action 收窄为 status（narrowedActions → READ_ONLY_PIE_ACTIONS）；
 * - start/stop/restart 为写操作：server policy != read-only（schema 收窄 + 兜底门）
 *   且 bridge allowWrite=true（bridge 侧 PERMISSION_DENIED gate=bridge.allowWrite）；
 * - 写动作进审计（与 actor.edit 一致，decision=allowed + argsSummary）；
 * - 错误码沿用现有表：PIE_NOT_RUNNING（stop 无 PIE）、CONFLICT（start 已在 PIE）等由
 *   bridge 侧映射，server 透传（client.ts 按 data.errorCode 反查）；
 * - timeout 60000ms（契约值）。注意 waitReadyMs 契约上限 120000 > 60000：
 *   用户传大 waitReadyMs 而 PIE 未按时就绪时，server 侧会先到 60s 超时（BRIDGE_TIMEOUT）。
 */
import { PIE_WRITE_ACTIONS, pieInputSchema } from "@uemcp/shared";
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

type PieArgs = z.infer<ReturnType<typeof pieInputSchema>>;

export const pieControlTool: ToolDef = {
  name: "ue_pie_control",
  rpcMethod: "pie.control",
  title: "PIE Control",
  description:
    "Start / stop / restart Play-In-Editor (PIE) or query its status. start/stop/restart are write actions (server policy != read-only AND bridge allowWrite); status is always allowed. waitReadyMs bounds how long the bridge waits for PIE readiness (0..120000, default 15000); the server-side bridge timeout for this tool is 60s.",
  timeoutMs: 60000,
  schemaFor(p: PolicyState) {
    return pieInputSchema(narrowedActions(pieControlTool.name, p) ?? undefined);
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const schema = pieInputSchema(narrowedActions(pieControlTool.name, ctx.policy));
    const parsed = schema.safeParse(rawArgs);
    if (!parsed.success) {
      // read-only 收窄的写 action → INVALID_ARGUMENT（§5.11 调用语义，同 level/material/blueprint）
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const args = parsed.data as PieArgs;
    const isWrite = PIE_WRITE_ACTIONS.has(args.action);

    // 防御：read-only 下绕过 Schema 直达 handler 的写 action（§5.11）
    if (ctx.policy.mode === "read-only" && isWrite) {
      return errResult(
        toolError("PERMISSION_DENIED", "Write action not allowed under read-only policy", {
          gate: "server.policy",
        }),
        makeMeta(ctx, started),
      );
    }

    const res = await ctx.bridge.call("pie.control", args as unknown as Record<string, unknown>, pieControlTool.timeoutMs, { retriable: !isWrite });
    const meta = makeMeta(ctx, started);
    if (isWrite) {
      await auditCall(ctx, {
        tool: pieControlTool.name,
        rpcMethod: pieControlTool.rpcMethod,
        requestId: meta.requestId,
        durationMs: meta.durationMs,
        ok: res.ok,
        errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
        decision: "allowed",
        argsSummary: summarizeArgs(pieControlTool.name, rawArgs),
      });
    }
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    return okResult(
      pieControlTool.name,
      summarizeOut(pieControlTool.name, res.data as Record<string, unknown>, res.warnings),
      res.data,
      res.warnings,
      meta,
    );
  },
};
