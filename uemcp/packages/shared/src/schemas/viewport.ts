import { z } from "zod";
import { Rotator, Vec3 } from "./common.js";

/** §5.7 ue_viewport_capture */
export const ViewportCaptureInput = z
  .object({
    target: z.enum(["level_viewport", "pie"]).default("level_viewport"),
    width: z.number().int().min(64).max(7680).default(1280),
    height: z.number().int().min(64).max(4320).default(720),
    format: z.enum(["png", "jpeg"]).default("png"),
    jpegQuality: z.number().int().min(1).max(100).default(90),
    camera: z
      .union([
        z
          .object({ mode: z.literal("current") })
          .strict(),
        z
          .object({
            mode: z.literal("actor"),
            actorPath: z.string().max(512),
            distanceMultiplier: z.number().min(0.5).max(10).default(2.5),
          })
          .strict(),
        z
          .object({
            mode: z.literal("explicit"),
            location: Vec3,
            rotation: Rotator,
          })
          .strict(),
      ])
      .default({ mode: "current" }),
    returnMode: z.enum(["image", "file"]).default("image"),
    hideEditorUI: z.boolean().default(true),
    timeoutMs: z.number().int().min(1000).max(30000).default(15000),
  })
  .strict();

export type ViewportCaptureInputT = z.infer<typeof ViewportCaptureInput>;
