import { z } from "zod";

/** §5.6 ue_material_params；read-only 下 action enum 收窄（§5.11） */
export const MATERIAL_ACTIONS = ["list", "get", "set", "create_instance"] as const;
export const READ_ONLY_MATERIAL_ACTIONS = ["list", "get"] as const;

const MaterialParam = z.union([
  z
    .object({
      name: z.string().max(128),
      type: z.literal("scalar"),
      value: z.number(),
    })
    .strict(),
  z
    .object({
      name: z.string().max(128),
      type: z.literal("vector"),
      value: z
        .object({
          r: z.number(),
          g: z.number(),
          b: z.number(),
          a: z.number(),
        })
        .strict(),
    })
    .strict(),
  z
    .object({
      name: z.string().max(128),
      type: z.literal("texture"),
      value: z.string().max(512),
    })
    .strict(),
  z
    .object({
      name: z.string().max(128),
      type: z.literal("staticSwitch"),
      value: z.boolean(),
    })
    .strict(),
]);

export function materialInputSchema(
  actions: readonly string[] = MATERIAL_ACTIONS,
) {
  return z
    .object({
      action: z.enum(actions as [string, ...string[]]),
      materialPath: z.string().max(512).optional(),
      instancePath: z.string().max(512).optional(),
      parameterNames: z.array(z.string().max(128)).max(100).optional(),
      parameters: z.array(MaterialParam).max(50).optional(),
      save: z.boolean().default(false),
    })
    .strict();
}

export const MaterialParamsInput = materialInputSchema();

export type MaterialParamsInputT = z.infer<typeof MaterialParamsInput>;

export const MATERIAL_WRITE_ACTIONS: ReadonlySet<string> = new Set([
  "set",
  "create_instance",
]);
