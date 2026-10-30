/**
 * ue_reflect（§object.reflect，2026-10-30 通用原语）：
 * 列出目标对象上可从 Python 调用的函数（只读）。
 * 用途：替代「grep 源码才知道某个 handler 有哪些命令」——例如业务方的
 * CustomDomainCmdHandler 上暴露的 fly_to_monitor_point 等。
 */
import { reflectInputSchema } from "@uemcp/shared";
import { makeMeta, okResult, errResult, toolError, type ToolContext, type ToolDef } from "./common.js";

export const reflectTool: ToolDef = {
  name: "ue_reflect",
  rpcMethod: "object.reflect",
  title: "Reflect Object Functions",
  description:
    "List the functions exposed by an object (BlueprintCallable UFUNCTIONs mapped to Python attributes) plus their parameter counts. target may be an asset/actor path ('/Game/...:MyActor') or a class name (first matching instance is used). Read-only.",
  timeoutMs: 30000,
  schemaFor() {
    return reflectInputSchema();
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const parsed = reflectInputSchema().safeParse(rawArgs);
    if (!parsed.success) {
      const meta = makeMeta(ctx, started);
      return errResult(
        toolError("INVALID_ARGUMENT", "target must be a non-empty string (max 512 chars)", {
          issues: parsed.error.issues,
        }),
        meta,
      );
    }
    const res = await ctx.bridge.call("object.reflect", parsed.data as Record<string, unknown>, reflectTool.timeoutMs);
    const meta = makeMeta(ctx, started);
    if (!res.ok) return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    return okResult(
      reflectTool.name,
      `reflected ${Array.isArray((res.data as { functions?: unknown[] }).functions) ? (res.data as { functions: unknown[] }).functions.length : 0} function(s)`,
      res.data,
      res.warnings,
      meta,
    );
  },
};
