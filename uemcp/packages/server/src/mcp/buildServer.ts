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
export const SERVER_VERSION = "0.1.3";
// TODO(协议版本 2025-11-25)：维持三版本表。按 HANDOFF.md §10-6 与 README-DEV §8-1
// 裁决：SDK 1.32 已支持 2025-11-25，但放开协商需先更新架构 §3.6 三版本表（含测试
// 计划 PROTO-17 基线），文档结论归文档岗维护，Server 侧不自行动——若裁决通过，
// 在 PROTOCOL_VERSIONS 头部插入 "2025-11-25" 并同步 smoke 的回退断言。
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
