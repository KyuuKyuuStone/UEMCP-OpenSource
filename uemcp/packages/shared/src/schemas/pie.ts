import { z } from "zod";

/** §5.11 ue_pie_control；read-only 下 action enum 收窄为 status（与 level/material/blueprint 同机制） */
export const PIE_ACTIONS = ["start", "stop", "restart", "status"] as const;
export const READ_ONLY_PIE_ACTIONS = ["status"] as const;

export function pieInputSchema(actions: readonly string[] = PIE_ACTIONS) {
  return z
    .object({
      action: z.enum(actions as [string, ...string[]]),
      waitReadyMs: z.number().int().min(0).max(120000).default(15000),
      simulate: z.boolean().default(false),
    })
    .strict();
}

export const PieControlInput = pieInputSchema();

export type PieControlInputT = z.infer<typeof PieControlInput>;

/** start/stop/restart 为写操作（需 server policy != read-only 且 bridge allowWrite）；status 恒可用 */
export const PIE_WRITE_ACTIONS: ReadonlySet<string> = new Set(["start", "stop", "restart"]);
