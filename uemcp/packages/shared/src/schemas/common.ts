import { z } from "zod";

/** 共享类型（§5.0.2 $defs） */
export const Vec3 = z
  .object({
    x: z.number(),
    y: z.number(),
    z: z.number(),
  })
  .strict();

export const Rotator = z
  .object({
    pitch: z.number(),
    yaw: z.number(),
    roll: z.number(),
  })
  .strict();

export const Selector = z
  .object({
    kind: z.enum(["actorPath", "objectPath", "name", "label"]),
    value: z.string().min(1).max(512),
  })
  .strict();

export const ActorRef = z
  .object({
    actorPath: z.string().describe("关卡内路径，例如 PersistentLevel.SM_Chair_2"),
    objectPath: z.string().optional(),
    name: z.string(),
    label: z.string().optional(),
    class: z.string(),
    classPath: z.string().optional(),
    levelPath: z.string().optional(),
  })
  .strict();

export const AssetRef = z
  .object({
    packageName: z.string(),
    objectPath: z.string(),
    assetName: z.string(),
    class: z.string(),
    classPath: z.string().optional(),
    packagePath: z.string().optional(),
    isRedirector: z.boolean().optional(),
    diskSize: z.number().int().nonnegative().optional(),
  })
  .strict();

export const Transform = z
  .object({
    location: Vec3.optional(),
    rotation: Rotator.optional(),
    scale: Vec3.optional(),
  })
  .strict();

export const ErrorShape = z.object({
  code: z.string(),
  message: z.string(),
  retryable: z.boolean(),
  details: z.record(z.unknown()).optional(),
});
