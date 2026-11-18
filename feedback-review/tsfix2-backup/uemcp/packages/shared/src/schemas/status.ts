import { z } from "zod";

/** §5.1 ue_editor_status */
export const StatusInput = z
  .object({
    sections: z
      .array(
        z.enum(["editor", "level", "selection", "viewport", "capabilities", "policies"]),
      )
      .default(["editor", "level", "selection", "capabilities"]),
    selectionLimit: z.number().int().min(0).max(200).default(20),
  })
  .strict();

export type StatusInputT = z.infer<typeof StatusInput>;
