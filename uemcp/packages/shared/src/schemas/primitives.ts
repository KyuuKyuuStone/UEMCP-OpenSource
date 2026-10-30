/**
 * 通用原语输入 Schema（2026-10-30，P0-3 通用化改造）：
 * - ue_reflect：列出目标对象上可从 Python 调用的函数（只读）
 * - ue_call_function：按名调用 BlueprintCallable 函数（写类，需 allowWrite）
 * - ue_log_query：检索本工程日志（只读，限制在 Saved/Logs 下）
 */
import { z } from "zod";

/** 目标对象：`/Game/...:MyActor` 路径、关卡 Actor 路径，或类名（取首个匹配实例） */
export const REFLECT_MAX_FUNCTIONS = 200;

export function reflectInputSchema() {
  return z
    .object({
      target: z.string().min(1).max(512),
    })
    .strict();
}

export const ReflectInput = reflectInputSchema();
export type ReflectInputT = z.infer<typeof ReflectInput>;

export const CALL_MAX_ARGS = 32;
export const CALL_MAX_WAIT_MS = 60000;

export function callFunctionInputSchema() {
  return z
    .object({
      target: z.string().min(1).max(512),
      function: z.string().min(1).max(256),
      args: z.array(z.unknown()).max(CALL_MAX_ARGS).default([]),
      waitMs: z.number().int().min(0).max(CALL_MAX_WAIT_MS).default(5000),
    })
    .strict();
}

export const CallFunctionInput = callFunctionInputSchema();
export type CallFunctionInputT = z.infer<typeof CallFunctionInput>;

export const LOG_LEVELS = ["Error", "Warning", "Log", "Display"] as const;
export const LOG_MAX_PATTERN = 200;
export const LOG_MAX_LIMIT = 2000;

export function logQueryInputSchema() {
  return z
    .object({
      pattern: z.string().max(LOG_MAX_PATTERN).optional(),
      levels: z.array(z.enum(LOG_LEVELS)).optional(),
      since: z.string().max(64).optional(),
      limit: z.number().int().min(1).max(LOG_MAX_LIMIT).default(200),
      offset: z.number().int().min(0).default(0),
    })
    .strict();
}

export const LogQueryInput = logQueryInputSchema();
export type LogQueryInputT = z.infer<typeof LogQueryInput>;
