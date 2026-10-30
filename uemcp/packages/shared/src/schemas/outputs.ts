/**
 * 工具输出 Schema（架构 §5.0.1/§5.0.2/§10.2、附录 A：全部工具注册 outputSchema）。
 *
 * 设计约束（2026-10-28 任务 4248c955 裁决）：
 * - MCP 客户端（含 SDK 1.32 的 Ajv 校验器）对「存在的 structuredContent」一律按
 *   outputSchema 校验，包括 isError=true 的结果（client/index.js callTool）。
 *   因此每个工具的 outputSchema 必须是 成功/失败 两种封套的 anyOf 并集。
 * - 成功封套：{ ok:true, data, warnings, meta }（tools/common.ts okResult）。
 * - 失败封套：{ ok:false, error, meta }（tools/common.ts errResult，isError=true）。
 * - data 按架构 §5.x 输出表声明字段，但保持 passthrough 且不强制必填
 *   （除 Server 侧必然注入的 status.policies）：桥接侧字段演进不应被客户端
 *   schema 校验打回；封套本身（ok/warnings/meta/error）是强约束部分。
 */
import { z } from "zod";
import { TOOL_ERROR_CODES } from "../errors.js";
import type { ToolName } from "../toolNames.js";

/** §5.0.1 ToolMeta（成功/失败共用） */
export const ToolMetaOutput = z
  .object({
    requestId: z.string(),
    durationMs: z.number(),
    ueVersion: z.string().optional(),
    pluginVersion: z.string().optional(),
  })
  .strict();

/** §2.9.3 工具级错误对象（code 为 §2.9.3 全表枚举） */
export const ToolErrorOutput = z
  .object({
    code: z.enum(TOOL_ERROR_CODES),
    message: z.string(),
    retryable: z.boolean(),
    details: z.record(z.unknown()).optional(),
  })
  .strict();

/** passthrough 对象：声明字段但允许桥接侧扩展字段（向前兼容） */
function looseObject(shape: Parameters<typeof z.object>[0]) {
  return z.object(shape).passthrough();
}

/** 成功/失败双形态并集（§5.0.1 两种 structuredContent 形态） */
function outputUnion(dataSchema: z.ZodTypeAny) {
  return z.union([
    z
      .object({
        ok: z.literal(true),
        data: dataSchema,
        warnings: z.array(z.string()),
        meta: ToolMetaOutput,
      })
      .strict(),
    z
      .object({
        ok: z.literal(false),
        error: ToolErrorOutput,
        meta: ToolMetaOutput,
      })
      .strict(),
  ]);
}

// ---------- §5.1 ue_editor_status ----------

const StatusData = looseObject({
  editor: looseObject({
    ueVersion: z.string().optional(),
    pluginVersion: z.string().optional(),
    bridgeProtocol: z.number().optional(),
    processId: z.number().optional(),
    isPieRunning: z.boolean().optional(),
    isSimulating: z.boolean().optional(),
    isCompiling: z.boolean().optional(),
    isAssetRegistryLoading: z.boolean().optional(),
  }).optional(),
  level: looseObject({
    path: z.string().optional(),
    name: z.string().optional(),
    isDirty: z.boolean().optional(),
    isPartitioned: z.boolean().optional(),
    dirtyPackageCount: z.number().optional(),
  }).optional(),
  selection: looseObject({
    count: z.number().optional(),
    actors: z.array(z.record(z.unknown())).optional(),
    truncated: z.boolean().optional(),
  }).optional(),
  viewport: looseObject({}).optional(),
  capabilities: looseObject({
    python: z.boolean().optional(),
    screenshot: z.boolean().optional(),
    blueprintRead: z.boolean().optional(),
    blueprintNodeRead: z.boolean().optional(),
    blueprintCompile: z.boolean().optional(),
    animBlueprintEdit: z.boolean().optional(),
    assetRegistry: z.boolean().optional(),
    console: z.boolean().optional(),
  }).optional(),
  // Server 侧在成功路径必然注入（tools/status.ts data.policies）
  policies: z
    .object({
      mode: z.enum(["read-only", "standard", "full"]),
      write: z.boolean(),
      exec: z.boolean(),
      destructive: z.boolean(),
    })
    .strict(),
});

export const StatusOutput = outputUnion(StatusData);

// ---------- §5.2 ue_actor_query ----------

const ActorQueryData = looseObject({
  total: z.number().optional(),
  returned: z.number().optional(),
  truncated: z.boolean().optional(),
  actors: z
    .array(
      looseObject({
        actorPath: z.string().optional(),
        objectPath: z.string().optional(),
        name: z.string().optional(),
        label: z.string().optional(),
        class: z.string().optional(),
        classPath: z.string().optional(),
        levelPath: z.string().optional(),
      }),
    )
    .optional(),
});

export const ActorQueryOutput = outputUnion(ActorQueryData);

// ---------- §5.3 ue_actor_edit ----------

const ActorEditData = looseObject({
  dryRun: z.boolean().optional(),
  results: z.array(z.record(z.unknown())).optional(),
  summary: looseObject({
    requested: z.number().optional(),
    succeeded: z.number().optional(),
    failed: z.number().optional(),
    rolledBack: z.boolean().optional(),
  }).optional(),
});

export const ActorEditOutput = outputUnion(ActorEditData);

// ---------- §5.4 ue_level_control（data 随 action 变化，字段全可选） ----------

const LevelControlData = looseObject({
  path: z.string().optional(),
  name: z.string().optional(),
  previousPath: z.string().optional(),
  isDirty: z.boolean().optional(),
  isPartitioned: z.boolean().optional(),
  dirtyPackageCount: z.number().optional(),
  packages: z.array(z.record(z.unknown())).optional(),
  saved: z.boolean().optional(),
});

export const LevelControlOutput = outputUnion(LevelControlData);

// ---------- §5.5 ue_asset_search ----------

const AssetSearchData = looseObject({
  total: z.number().optional(),
  returned: z.number().optional(),
  truncated: z.boolean().optional(),
  assets: z
    .array(
      looseObject({
        packageName: z.string().optional(),
        objectPath: z.string().optional(),
        assetName: z.string().optional(),
        class: z.string().optional(),
        classPath: z.string().optional(),
        packagePath: z.string().optional(),
        isRedirector: z.boolean().optional(),
        diskSize: z.number().optional(),
      }),
    )
    .optional(),
  dependencies: z.record(z.array(z.string())).optional(),
  referencers: z.record(z.array(z.string())).optional(),
});

export const AssetSearchOutput = outputUnion(AssetSearchData);

// ---------- §5.6 ue_material_params（data 随 action 变化） ----------

const MaterialParamsData = looseObject({
  parameters: z.array(z.record(z.unknown())).optional(),
  saved: z.boolean().optional(),
  created: z.boolean().optional(),
});

export const MaterialParamsOutput = outputUnion(MaterialParamsData);

// ---------- §5.7 ue_viewport_capture ----------

const ViewportCaptureData = looseObject({
  path: z.string().optional(),
  width: z.number().optional(),
  height: z.number().optional(),
  format: z.enum(["png", "jpeg"]).optional(),
  bytes: z.number().optional(),
  capturedAt: z.string().optional(),
  // 向前兼容：桥接直接返回 base64 时（tools/viewportCapture.ts CaptureData）
  base64Data: z.string().optional(),
});

export const ViewportCaptureOutput = outputUnion(ViewportCaptureData);

// ---------- §5.8 ue_console_command ----------

const ConsoleCommandData = looseObject({
  command: z.string().optional(),
  dispatched: z.boolean().optional(),
  output: z.unknown().optional(),
  outputAvailable: z.boolean().optional(),
});

export const ConsoleCommandOutput = outputUnion(ConsoleCommandData);

// ---------- §5.9 ue_python_exec ----------

const PythonExecData = looseObject({
  mode: z.enum(["exec", "eval"]).optional(),
  result: z.unknown().optional(),
  stdout: z.string().optional(),
  stderr: z.string().optional(),
  durationMs: z.number().optional(),
  timedOut: z.boolean().optional(),
});

export const PythonExecOutput = outputUnion(PythonExecData);

// ---------- §5.10 ue_blueprint（data 随 action 变化） ----------

const BlueprintData = looseObject({
  blueprintPath: z.string().optional(),
  parentClass: z.string().optional(),
  variables: z.array(z.record(z.unknown())).optional(),
  components: z.array(z.record(z.unknown())).optional(),
  graphs: z.array(z.record(z.unknown())).optional(),
  interfaces: z.array(z.record(z.unknown())).optional(),
  nodes: z.array(z.record(z.unknown())).optional(),
  compiled: z.boolean().optional(),
  compileState: looseObject({
    status: z.string().optional(),
    errors: z.number().optional(),
    warnings: z.number().optional(),
  }).optional(),
});

export const BlueprintOutput = outputUnion(BlueprintData);

// ---------- ue_pie_control（§pie.control；data 形态与 Bridge 契约对齐） ----------

const PieControlData = looseObject({
  action: z.enum(["start", "stop", "restart", "status"]).optional(),
  isPieRunning: z.boolean().optional(),
  isSimulating: z.boolean().optional(),
  world: z.string().nullable().optional(),
  startedAt: z.string().nullable().optional(),
  durationMs: z.number().optional(),
});

export const PieControlOutput = outputUnion(PieControlData);

// ---------- ue_policy_explain（纯服务端信息，data 为可见性矩阵 + bridge 状态） ----------

const PolicyExplainData = looseObject({
  mode: z.enum(["read-only", "standard", "full"]).optional(),
  allowDestructive: z.boolean().optional(),
  allowConsole: z.boolean().optional(),
  allowExec: z.boolean().optional(),
  tools: z
    .array(
      looseObject({
        name: z.string().optional(),
        visible: z.boolean().optional(),
        gate: z.string().optional(),
        reason: z.string().optional(),
        allowedActions: z.array(z.string()).optional(),
      }),
    )
    .optional(),
  bridge: looseObject({
    connected: z.boolean().optional(),
    url: z.string().optional(),
    ueVersion: z.string().optional(),
    pluginVersion: z.string().optional(),
    projectDir: z.string().optional(),
    note: z.string().optional(),
  }).optional(),
});

export const PolicyExplainOutput = outputUnion(PolicyExplainData);

/** 全目录 data schema（供 Server 侧构造 MCP 规范要求的根层级 type:"object" outputSchema，
 *  见 packages/server/src/mcp/outputSchema.ts；新增工具缺 data schema 会编译失败） */
export const TOOL_OUTPUT_DATA_SCHEMAS: Record<ToolName, z.ZodTypeAny> = {
  ue_editor_status: StatusData,
  ue_actor_query: ActorQueryData,
  ue_actor_edit: ActorEditData,
  ue_level_control: LevelControlData,
  ue_asset_search: AssetSearchData,
  ue_material_params: MaterialParamsData,
  ue_viewport_capture: ViewportCaptureData,
  ue_console_command: ConsoleCommandData,
  ue_python_exec: PythonExecData,
  ue_blueprint: BlueprintData,
  ue_pie_control: PieControlData,
  ue_policy_explain: PolicyExplainData,
};

/** 全目录 outputSchema（成功/失败双形态 union，parse 级真值供测试使用）。
 *  注意：不能直接把该 union 作为 tools/list 的 outputSchema 发布——MCP 规范与
 *  SDK ToolSchema 要求 outputSchema 根层级 type:"object"（anyOf 顶层会被
 *  ListToolsResultSchema 打回）。发布形态由 Server 侧 toolOutputJsonSchema 构造。 */
export const TOOL_OUTPUT_SCHEMAS: Record<ToolName, z.ZodTypeAny> = Object.fromEntries(
  (Object.keys(TOOL_OUTPUT_DATA_SCHEMAS) as ToolName[]).map((n) => [
    n,
    outputUnion(TOOL_OUTPUT_DATA_SCHEMAS[n]),
  ]),
) as unknown as Record<ToolName, z.ZodTypeAny>;
