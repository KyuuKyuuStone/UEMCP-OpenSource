import { z } from "zod";

/** §5.10 ue_blueprint；read-only 下 action enum 收窄（§5.11） */
export const BLUEPRINT_ACTIONS = ["query", "compile"] as const;
export const READ_ONLY_BLUEPRINT_ACTIONS = ["query"] as const;

export function blueprintInputSchema(
  actions: readonly string[] = BLUEPRINT_ACTIONS,
) {
  return z
    .object({
      action: z.enum(actions as [string, ...string[]]),
      blueprintPath: z.string().max(512).optional(),
      include: z
        .array(
          z.enum([
            "parent",
            "variables",
            "components",
            "graphs",
            "interfaces",
            "compileState",
          ]),
        )
        .default(["parent", "variables", "graphs", "compileState"]),
      graphName: z.string().max(256).optional(),
      includeNodes: z.boolean().default(false),
      nodeLimit: z.number().int().min(1).max(2000).default(500),
      save: z.boolean().default(false),
    })
    .strict();
}

export const BlueprintInput = blueprintInputSchema();

export type BlueprintInputT = z.infer<typeof BlueprintInput>;

export const BLUEPRINT_WRITE_ACTIONS: ReadonlySet<string> = new Set(["compile"]);
