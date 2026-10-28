/**
 * 策略矩阵（§5.0.3 / §5.11 / §6.3）。
 */
import type { PolicyMode, ToolName } from "@uemcp/shared";

export interface PolicyState {
  mode: PolicyMode;
  allowDestructive: boolean;
  allowConsole: boolean;
  allowExec: boolean;
}

/** §5.11 工具与策略矩阵 */
export function isToolVisible(tool: ToolName, p: PolicyState): boolean {
  switch (tool) {
    case "ue_editor_status":
    case "ue_actor_query":
    case "ue_asset_search":
    case "ue_viewport_capture":
      return true; // P0 恒可见
    case "ue_level_control":
    case "ue_material_params":
    case "ue_blueprint":
      return true; // P0/P1 混合工具恒注册（read-only 收窄 Schema）
    case "ue_actor_edit":
      return p.mode !== "read-only"; // P1：read-only 不注册
    case "ue_console_command":
      return p.mode === "full" && p.allowConsole; // P2
    case "ue_python_exec":
      return p.mode === "full" && p.allowExec; // P2
  }
}

/** read-only 下混合工具收窄的 action enum（§5.11） */
export function narrowedActions(
  tool: ToolName,
  p: PolicyState,
): readonly string[] | undefined {
  if (p.mode !== "read-only") return undefined;
  switch (tool) {
    case "ue_level_control":
      return ["get_current", "list_dirty"];
    case "ue_material_params":
      return ["list", "get"];
    case "ue_blueprint":
      return ["query"];
    default:
      return undefined;
  }
}

/**
 * 未注册工具被直接调用时的 gate 来源（§2.9.6 TOOL_DISABLED gate）。
 * P2 工具的 gate 固定为对应开关（SEC-01(c)/SEC-15）；P1 为 server.policy。
 */
export function toolDisabledGate(tool: ToolName, p: PolicyState): string {
  switch (tool) {
    case "ue_console_command":
      return "server.allowConsole";
    case "ue_python_exec":
      return "server.allowExec";
    default:
      void p;
      return "server.policy";
  }
}

/** §5.0.4 工具注解（随策略变化） */
export function toolAnnotations(
  tool: ToolName,
  p: PolicyState,
): {
  readOnlyHint: boolean;
  destructiveHint: boolean;
  idempotentHint: boolean;
  openWorldHint: boolean;
} {
  const readOnlyMode = p.mode === "read-only";
  switch (tool) {
    case "ue_editor_status":
      return { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
    case "ue_actor_query":
      return { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
    case "ue_asset_search":
      return { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
    case "ue_viewport_capture":
      return { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false };
    case "ue_actor_edit":
      return { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false };
    case "ue_console_command":
      return { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false };
    case "ue_python_exec":
      return { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true };
    case "ue_level_control":
      return readOnlyMode
        ? { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false }
        : { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false };
    case "ue_material_params":
      return readOnlyMode
        ? { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false }
        : { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false };
    case "ue_blueprint":
      return readOnlyMode
        ? { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false }
        : { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false };
  }
}
