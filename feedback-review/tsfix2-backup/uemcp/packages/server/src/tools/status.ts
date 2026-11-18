import { z } from "zod";
import { StatusInput } from "@uemcp/shared";
import { summarizeArgs } from "../audit.js";
import type { PolicyState } from "../policy.js";
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

export const statusTool: ToolDef = {
  name: "ue_editor_status",
  rpcMethod: "editor.status",
  title: "Get Unreal Editor Status",
  description:
    "Return editor status: engine version, current level, selection, viewport camera, capabilities and active policy. Read-only. First entry point for any client.",
  timeoutMs: 30000,
  schemaFor(_p: PolicyState) {
    return StatusInput;
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const parsed = StatusInput.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const res = await ctx.bridge.call("editor.status", parsed.data as Record<string, unknown>, statusTool.timeoutMs, { retriable: true });
    const meta = makeMeta(ctx, started);
    // B-3.7：读工具统一纳入审计（argsSummary 仅摘要，隐私红线不变；
    // invalidArgument 早退不审计，与写工具口径一致）
    const auditBase = {
      tool: statusTool.name,
      rpcMethod: statusTool.rpcMethod,
      requestId: meta.requestId,
      durationMs: meta.durationMs,
      decision: "allowed" as const,
      argsSummary: summarizeArgs(statusTool.name, parsed.data as Record<string, unknown>),
    };
    if (!res.ok) {
      const error = res.error ?? toolError("INTERNAL", "bridge call failed");
      await auditCall(ctx, { ...auditBase, ok: false, errorCode: error.code, errorDetails: error.details });
      return errResult(error, meta);
    }
    // §5.1：policies 段为 Server 侧信息（桥接不知道 MCP 策略）；B2 裁决保留此覆盖口径
    const data = (res.data ?? {}) as Record<string, unknown>;
    data.policies = {
      mode: ctx.policy.mode,
      write: ctx.policy.mode !== "read-only",
      exec: ctx.policy.mode === "full" && ctx.policy.allowExec,
      destructive: ctx.policy.allowDestructive,
    };
    // B-3.1/B2：构建身份由 TS 从 watchdog 保留的 /health 实际值注入——
    // 仅连接且字段存在时注入；断连/缺失不注入，绝不以旧缓存冒充现值。
    const w = ctx.watchdog.state;
    if (w.connected) {
      const build: Record<string, string> = {};
      if (w.instanceId !== undefined) build.instanceId = w.instanceId;
      if (w.buildHash !== undefined) build.buildHash = w.buildHash;
      if (w.buildTime !== undefined) build.buildTime = w.buildTime;
      if (w.sourcePath !== undefined) build.sourcePath = w.sourcePath;
      if (Object.keys(build).length > 0) data.build = build;
    }
    await auditCall(ctx, { ...auditBase, ok: true, errorCode: null });
    return okResult(
      statusTool.name,
      summarizeOut(statusTool.name, data, res.warnings),
      data,
      res.warnings,
      meta,
    );
  },
};
