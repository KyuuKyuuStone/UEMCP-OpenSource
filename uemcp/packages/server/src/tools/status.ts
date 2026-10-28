import { z } from "zod";
import { StatusInput } from "@uemcp/shared";
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
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    // §5.1：policies 段为 Server 侧信息（桥接不知道 MCP 策略）
    const data = (res.data ?? {}) as Record<string, unknown>;
    data.policies = {
      mode: ctx.policy.mode,
      write: ctx.policy.mode !== "read-only",
      exec: ctx.policy.mode === "full" && ctx.policy.allowExec,
      destructive: ctx.policy.allowDestructive,
    };
    return okResult(
      statusTool.name,
      summarizeOut(statusTool.name, data, res.warnings),
      data,
      res.warnings,
      meta,
    );
  },
};
