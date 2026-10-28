/**
 * tools/list 发布用 outputSchema 构造（附录 A / 任务 4248c955-A）。
 *
 * MCP 规范（2025-06-18 Tools；SDK ToolSchema 同口径）要求 outputSchema 根层级
 * type:"object"，因此不能直接发布成功/失败 union（anyOf 顶层会被 SDK 的
 * ListToolsResultSchema 打回）。发布形态：根 object 声明全部封套键并禁扩展，
 * anyOf 分支做判别（ok const + 条件 required + not 排他）：
 *   成功：{ ok:true, data, warnings, meta }（okResult，§5.0.1）
 *   失败：{ ok:false, error, meta }（errResult，isError=true；SDK 对存在的
 *         structuredContent 一律校验，含错误结果 → 双形态必须同 schema 兼容）
 */
import { zodToJsonSchema } from "zod-to-json-schema";
import {
  TOOL_OUTPUT_DATA_SCHEMAS,
  ToolErrorOutput,
  ToolMetaOutput,
  type ToolName,
} from "@uemcp/shared";

/** 去掉内嵌子 schema 的根 $schema（嵌入 properties 时属噪音；方言由根声明承担） */
function stripRootDialect(schema: Record<string, unknown>): Record<string, unknown> {
  const { $schema: _drop, ...rest } = schema;
  void _drop;
  return rest;
}

function toEmbedded(schema: { readonly _def?: unknown } & object): Record<string, unknown> {
  return stripRootDialect(
    zodToJsonSchema(schema as never, { $refStrategy: "none" }) as Record<string, unknown>,
  );
}

export function toolOutputJsonSchema(name: ToolName): Record<string, unknown> {
  return {
    type: "object",
    description:
      "UEMCP envelope (§5.0.1): success = { ok:true, data, warnings, meta }, failure = { ok:false, error, meta }; validated for both isError values.",
    properties: {
      ok: { type: "boolean", description: "true on success, false on tool failure" },
      data: toEmbedded(TOOL_OUTPUT_DATA_SCHEMAS[name]),
      warnings: { type: "array", items: { type: "string" } },
      error: toEmbedded(ToolErrorOutput),
      meta: toEmbedded(ToolMetaOutput),
    },
    required: ["ok", "meta"],
    additionalProperties: false,
    anyOf: [
      {
        // 成功分支：ok 恒为 true，必须携带 data 与 warnings，且不得携带 error
        properties: { ok: { const: true } },
        required: ["data", "warnings"],
        not: { required: ["error"] },
      },
      {
        // 失败分支：ok 恒为 false，必须携带 error，且不得携带 data
        properties: { ok: { const: false } },
        required: ["error"],
        not: { required: ["data"] },
      },
    ],
  };
}
