import { z } from "zod";

/** §5.4 ue_level_control；read-only 下 action enum 收窄（§5.11） */
export const LEVEL_ACTIONS = [
  "get_current",
  "list_dirty",
  "open",
  "save_current",
  "save_all",
  "new",
] as const;

export const READ_ONLY_LEVEL_ACTIONS = ["get_current", "list_dirty"] as const;

export function levelInputSchema(actions: readonly string[] = LEVEL_ACTIONS) {
  return z
    .object({
      action: z.enum(actions as [string, ...string[]]),
      levelPath: z.string().max(512).describe("如 /Game/Maps/Demo").optional(),
      templatePath: z.string().max(512).optional(),
      partitioned: z.boolean().default(false),
      allowDiscardUnsaved: z.boolean().default(false),
      confirm: z.boolean().default(false),
    })
    .strict();
}

export const LevelControlInput = levelInputSchema();

export type LevelControlInputT = z.infer<typeof LevelControlInput>;

export const LEVEL_WRITE_ACTIONS: ReadonlySet<string> = new Set([
  "open",
  "save_current",
  "save_all",
  "new",
]);
