/**
 * 危险操作确认（§5.0.3 / §6.3）：elicitation 优先，否则策略开关。
 */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

export type ElicitOutcome = "approved" | "declined" | "unsupported";

export type ElicitFn = (message: string) => Promise<ElicitOutcome>;

export function makeElicit(mcpServer: McpServer): ElicitFn {
  return async (message: string): Promise<ElicitOutcome> => {
    let caps: Record<string, unknown> | undefined;
    try {
      caps = mcpServer.server.getClientCapabilities() as Record<string, unknown> | undefined;
    } catch {
      caps = undefined;
    }
    if (!caps || !("elicitation" in caps)) return "unsupported";
    try {
      const lowLevel = mcpServer.server as unknown as {
        sendElicitation?: (p: {
          message: string;
          requestedSchema: Record<string, unknown>;
        }) => Promise<{
          action?: string;
          content?: { type?: string; text?: string };
        }>;
      };
      if (typeof lowLevel.sendElicitation !== "function") return "unsupported";
      const res = await lowLevel.sendElicitation({
        message,
        requestedSchema: {
          type: "object",
          properties: {
            approve: { type: "boolean", title: "Approve" },
          },
          required: ["approve"],
        },
      });
      if (res.action === "decline" || res.action === "cancel") return "declined";
      if (res.action === "accept") {
        const text = res.content?.text;
        if (typeof text === "string") {
          try {
            const parsed = JSON.parse(text) as { approve?: unknown };
            if (parsed.approve === true) return "approved";
            return "declined";
          } catch {
            /* 文本形态 */
          }
        }
        return "approved";
      }
      return "declined";
    } catch {
      return "unsupported";
    }
  };
}
