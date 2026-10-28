import { z } from "zod";

/** §5.8 ue_console_command */
export const ConsoleCommandInput = z
  .object({
    command: z.string().min(1).max(2000),
    worldContext: z.enum(["editor", "pie"]).default("editor"),
    timeoutMs: z.number().int().min(1000).max(30000).default(5000),
    captureOutput: z.boolean().default(false),
  })
  .strict();

export type ConsoleCommandInputT = z.infer<typeof ConsoleCommandInput>;

// 白名单与永久拒绝表的单一来源在 Bridge 侧（架构 §5.8；Server 不维护第二份）。
