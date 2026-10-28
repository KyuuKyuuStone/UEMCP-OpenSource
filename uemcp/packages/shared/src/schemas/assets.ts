import { z } from "zod";

/** §5.5 ue_asset_search */
export const AssetSearchInput = z
  .object({
    query: z
      .string()
      .max(256)
      .describe("匹配资产名或包路径，不区分大小写"),
    path: z.string().max(512).default("/Game"),
    classNames: z.array(z.string().max(128)).max(20).optional(),
    recursive: z.boolean().default(true),
    includeRedirectors: z.boolean().default(false),
    includeDependencies: z.boolean().default(false),
    includeReferencers: z.boolean().default(false),
    dependencyDepth: z.number().int().min(1).max(3).default(1),
    dependencyFlags: z
      .object({
        hard: z.boolean().default(true),
        soft: z.boolean().default(true),
        management: z.boolean().default(false),
        searchableName: z.boolean().default(false),
      })
      .strict()
      .partial()
      .optional(),
    limit: z.number().int().min(1).max(500).default(100),
    offset: z.number().int().min(0).default(0),
    sortBy: z.enum(["path", "class", "name"]).default("path"),
  })
  .strict();

export type AssetSearchInputT = z.infer<typeof AssetSearchInput>;
