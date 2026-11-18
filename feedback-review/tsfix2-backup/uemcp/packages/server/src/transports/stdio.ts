/**
 * stdio 传输（§3.2）：stdout 只允许 MCP 帧；所有日志写 stderr。
 */
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import type { ToolContext } from "../tools/common.js";
import { buildMcpServer } from "../mcp/buildServer.js";
import type { Logger } from "../logger.js";

export async function startStdio(ctx: ToolContext, log: Logger): Promise<void> {
  const transport = new StdioServerTransport();
  const server = buildMcpServer(ctx);
  await server.connect(transport);
  log.info("stdio_started", { policy: ctx.policy.mode });
}
