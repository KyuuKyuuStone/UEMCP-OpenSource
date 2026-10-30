/**
 * ue_log_query（§log.query，2026-10-30 通用原语）：
 * 检索当前工程日志（只读）。用于替代「读文件 + grep + 猜哪份日志」的胶水。
 *
 * 边界：Bridge 侧用 realpath 限制在 `<projectDir>/Saved/Logs/` 下，
 * 不允许任意路径读取（这是本插件不开放文件读取的边界的一部分）。
 */
import { logQueryInputSchema } from "@uemcp/shared";
import { makeMeta, okResult, errResult, invalidArgument, toolError, type ToolContext, type ToolDef } from "./common.js";

export const logQueryTool: ToolDef = {
  name: "ue_log_query",
  rpcMethod: "log.query",
  title: "Query Editor Log",
  description:
    "Search the current project's editor log (Saved/Logs/<Project>.log) with an optional regex pattern, level filter (Error/Warning/Log/Display), since timestamp and pagination. Returns matched lines with line numbers. Read-only; restricted to the project's log directory.",
  timeoutMs: 30000,
  schemaFor() {
    return logQueryInputSchema();
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const parsed = logQueryInputSchema().safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const res = await ctx.bridge.call("log.query", parsed.data as Record<string, unknown>, logQueryTool.timeoutMs);
    const meta = makeMeta(ctx, started);
    if (!res.ok) return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    const data = res.data as { matched?: number; scannedLines?: number; truncated?: boolean };
    return okResult(
      logQueryTool.name,
      `matched ${data.matched ?? 0} of ${data.scannedLines ?? 0} scanned line(s)${data.truncated ? " (truncated)" : ""}`,
      res.data,
      res.warnings,
      meta,
    );
  },
};
