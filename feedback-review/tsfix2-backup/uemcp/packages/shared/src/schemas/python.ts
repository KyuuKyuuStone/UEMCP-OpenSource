import { z } from "zod";

/** §5.9 ue_python_exec */
export const PythonExecInput = z
  .object({
    code: z.string().min(1).max(65536),
    mode: z.enum(["exec", "eval"]).default("exec"),
    resultExpression: z
      .string()
      .max(4096)
      .describe("exec 执行后可选求值，结果作为 result 返回")
      .optional(),
    timeoutMs: z.number().int().min(1000).max(120000).default(10000),
    captureOutput: z.boolean().default(true),
  })
  .strict();

export type PythonExecInputT = z.infer<typeof PythonExecInput>;
