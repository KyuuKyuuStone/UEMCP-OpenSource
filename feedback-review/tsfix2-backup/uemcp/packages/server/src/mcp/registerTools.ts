/**
 * 工具注册（§5.0.3/§5.11）。
 * 使用低层 setRequestHandler 自控 tools/call 与 tools/list：
 * - tools/call：完整目录存在性 → 策略门（TOOL_DISABLED）→ zod（INVALID_ARGUMENT）
 *   → handler；错误形态严格按 §2.9（200 + isError + structuredContent.error）。
 *   （不用 registerTool 的 zod 自动校验：其错误形态无法携带 structuredContent.error。）
 * - tools/list：只返回当前策略可见的工具；read-only 下混合工具 inputSchema 收窄。
 */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  McpError,
  ErrorCode,
  type CallToolResult,
  type CallToolRequest,
} from "@modelcontextprotocol/sdk/types.js";
import { zodToJsonSchema } from "zod-to-json-schema";
import { isToolVisible } from "../policy.js";
import { toolAnnotations } from "./annotations.js";
import { toolOutputJsonSchema } from "./outputSchema.js";
import { ALL_TOOLS } from "../tools/index.js";
import type { ToolContext } from "../tools/common.js";

export function registerTools(server: McpServer, ctx: ToolContext): void {
  const defs = ALL_TOOLS.map((def) => {
    const inputSchema = zodToJsonSchema(def.schemaFor(ctx.policy), {
      $refStrategy: "none",
    }) as Record<string, unknown>;
    // 附录 A：根层级 type:"object" + 成功/失败双形态 anyOf（§5.0.1）。
    // 客户端（SDK Ajv）对存在的 structuredContent 一律校验，含 isError=true 的结果。
    const outputSchema = toolOutputJsonSchema(def.name);
    return { def, inputSchema, outputSchema };
  });
  const byName = new Map<string, (typeof defs)[number]>(
    defs.map((e) => [e.def.name as string, e]),
  );

  server.server.setRequestHandler(
    CallToolRequestSchema,
    async (req: CallToolRequest, extra): Promise<CallToolResult> => {
      const name = req.params.name as string;
      const entry = byName.get(name);
      if (!entry) {
        // 完整目录中不存在 → 协议层 INVALID_PARAMS（§2.9.4）
        throw new McpError(ErrorCode.InvalidParams, `Unknown tool: ${name}`);
      }
      const args =
        req.params.arguments !== undefined &&
        typeof req.params.arguments === "object" &&
        req.params.arguments !== null &&
        !Array.isArray(req.params.arguments)
          ? (req.params.arguments as Record<string, unknown>)
          : {};
      const reqCtx: ToolContext = { ...ctx, sessionId: extra.sessionId };
      return entry.def.handle(reqCtx, args);
    },
  );

  server.server.setRequestHandler(ListToolsRequestSchema, async () => {
    const visible = defs.filter((e) => isToolVisible(e.def.name, ctx.policy));
    return {
      tools: visible.map(({ def, inputSchema, outputSchema }) => ({
        name: def.name,
        title: def.title,
        description: def.description,
        inputSchema: inputSchema as never,
        outputSchema: outputSchema as never,
        annotations: {
          ...toolAnnotations(def.name, ctx.policy.mode),
          title: def.title,
        } as never,
      })),
    };
  });
}
