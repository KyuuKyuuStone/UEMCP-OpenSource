/**
 * 策略矩阵（§5.0.3 / §5.11 / §6.3）。
 */
import type { PolicyMode, ToolName } from "@uemcp/shared";
import {
  READ_ONLY_BLUEPRINT_ACTIONS,
  READ_ONLY_LEVEL_ACTIONS,
  READ_ONLY_MATERIAL_ACTIONS,
  READ_ONLY_PIE_ACTIONS,
} from "@uemcp/shared";

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
    case "ue_pie_control":
      return true; // 恒注册（read-only 收窄为 status；写动作另有 policy/allowWrite 双门）
    case "ue_policy_explain":
      return true; // 纯只读信息工具恒可见（无副作用、无 RPC）
    case "ue_actor_edit":
      return p.mode !== "read-only"; // P1：read-only 不注册
    case "ue_console_command":
      return p.mode === "full" && p.allowConsole; // P2
    case "ue_python_exec":
      return p.mode === "full" && p.allowExec; // P2
  }
}

/** read-only 下混合工具收窄的 action enum（§5.11）
 *  单一来源：直接引用 shared 的 READ_ONLY_* 常量（Major-5 白名单单一来源口径），
 *  与 levelInputSchema/materialInputSchema/blueprintInputSchema 的收窄枚举同源。 */
export function narrowedActions(
  tool: ToolName,
  p: PolicyState,
): readonly string[] | undefined {
  if (p.mode !== "read-only") return undefined;
  switch (tool) {
    case "ue_level_control":
      return READ_ONLY_LEVEL_ACTIONS;
    case "ue_material_params":
      return READ_ONLY_MATERIAL_ACTIONS;
    case "ue_blueprint":
      return READ_ONLY_BLUEPRINT_ACTIONS;
    case "ue_pie_control":
      return READ_ONLY_PIE_ACTIONS;
    default:
      return undefined;
  }
}

/** 未注册工具被直接调用时的 gate 来源（§2.9.6 TOOL_DISABLED gate）。
 *  P2 工具的 gate 固定为对应开关（SEC-01(c)/SEC-15）；P1 为 server.policy。 */
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
