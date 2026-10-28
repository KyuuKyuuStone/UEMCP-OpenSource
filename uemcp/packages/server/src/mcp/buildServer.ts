/**
 * 构建共享的 McpServer（三种传输共用，§3.1）。
 * 每个传输/会话 connect 一个实例；elicitation 封装绑定到该实例
 * （客户端 capability 存在于实例上）。
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { makeElicit } from "../confirm.js";
import type { ToolContext } from "../tools/common.js";
import { registerTools } from "./registerTools.js";

export const SERVER_NAME = "uemcp";
export const SERVER_VERSION = "0.1.0";
export const PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"];

export function buildMcpServer(baseCtx: ToolContext): McpServer {
  const server = new McpServer(
    { name: SERVER_NAME, version: SERVER_VERSION },
    { capabilities: { tools: { listChanged: false } } },
  );
  const ctx: ToolContext = { ...baseCtx, elicit: makeElicit(server) };
  registerTools(server, ctx);
  return server;
}
