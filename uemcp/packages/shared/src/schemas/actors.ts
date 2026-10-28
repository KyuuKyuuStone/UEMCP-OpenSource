import { z } from "zod";
import { Rotator, Selector, Vec3 } from "./common.js";

/** §5.2 ue_actor_query */
export const ActorQueryInput = z
  .object({
    scope: z.enum(["level", "selection"]).default("level"),
    filter: z
      .object({
        class: z.string().max(256).describe("类名或类路径，匹配派生类"),
        nameContains: z.string().max(200),
        labelContains: z.string().max(200),
        tags: z
          .record(z.string())
          .refine((v) => Object.keys(v).length <= 20, "maxProperties 20"),
        folders: z.array(z.string()).max(10),
        hasComponentClass: z.string().max(256),
      })
      .strict()
      .partial()
      .optional(),
    fields: z
      .array(
        z.enum([
          "identity",
          "transform",
          "bounds",
          "tags",
          "components",
          "mobility",
          "folder",
        ]),
      )
      .default(["identity", "transform", "tags"]),
    limit: z.number().int().min(1).max(1000).default(50),
    offset: z.number().int().min(0).max(100000).default(0),
    sortBy: z.enum(["name", "label", "class", "path"]).default("name"),
  })
  .strict();

export type ActorQueryInputT = z.infer<typeof ActorQueryInput>;

const transformFields = z
  .object({
    location: Vec3.optional(),
    rotation: Rotator.optional(),
    scale: Vec3.optional(),
  })
  .strict();

/** §5.3 ue_actor_edit 操作（oneOf 六种） */
const SpawnOp = z
  .object({
    op: z.literal("spawn"),
    class: z.string().max(256),
    assetPath: z.string().max(512).optional(),
    location: Vec3.optional(),
    rotation: Rotator.optional(),
    scale: Vec3.optional(),
    label: z.string().max(128).optional(),
    tags: z.array(z.string()).max(20).optional(),
    folderPath: z.string().max(256).optional(),
    selectAfterSpawn: z.boolean().default(false),
  })
  .strict();

const DeleteOp = z
  .object({
    op: z.literal("delete"),
    selector: Selector,
    confirm: z.boolean().default(false),
  })
  .strict();

const SetTransformOp = z
  .object({
    op: z.literal("set_transform"),
    selector: Selector,
    location: Vec3.optional(),
    rotation: Rotator.optional(),
    scale: Vec3.optional(),
    snapToGrid: z.boolean().default(false),
  })
  .strict();

const SetPropertiesOp = z
  .object({
    op: z.literal("set_properties"),
    selector: Selector,
    properties: z
      .object({
        label: z.string().max(128),
        hidden: z.boolean(),
        mobility: z.enum(["static", "stationary", "movable"]),
        folderPath: z.string().max(256),
        tags: z.array(z.string()).max(20),
        staticMesh: z.string().max(512),
        materials: z
          .record(z.string())
          .refine((v) => Object.keys(v).length <= 20, "maxProperties 20"),
      })
      .strict()
      .partial(),
  })
  .strict();

const DuplicateOp = z
  .object({
    op: z.literal("duplicate"),
    selector: Selector,
    count: z.number().int().min(1).max(50).default(1),
    offset: Vec3.optional(),
    labelSuffix: z.string().max(64).default("_copy"),
  })
  .strict();

const SelectOp = z
  .object({
    op: z.literal("select"),
    selector: Selector,
    mode: z.enum(["replace", "add", "remove"]).default("replace"),
  })
  .strict();

export const ActorEditOperation = z.union([
  SpawnOp,
  DeleteOp,
  SetTransformOp,
  SetPropertiesOp,
  DuplicateOp,
  SelectOp,
]);

export type ActorEditOperationT = z.infer<typeof ActorEditOperation>;

export const ActorEditInput = z
  .object({
    operations: z.array(ActorEditOperation).min(1).max(50),
    atomic: z.boolean().default(true).describe("失败时通过事务取消回滚"),
    dryRun: z.boolean().default(false),
    transactionName: z.string().max(128).default("UEMCP Actor Edit"),
  })
  .strict();

export type ActorEditInputT = z.infer<typeof ActorEditInput>;

export const ACTOR_TRANSFORM_FIELDS = transformFields;
