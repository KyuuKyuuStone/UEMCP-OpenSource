export const TOOL_NAMES = [
  "ue_editor_status",
  "ue_actor_query",
  "ue_actor_edit",
  "ue_level_control",
  "ue_asset_search",
  "ue_material_params",
  "ue_viewport_capture",
  "ue_console_command",
  "ue_python_exec",
  "ue_blueprint",
  "ue_pie_control",
  "ue_policy_explain",
  "ue_reflect",
  "ue_call_function",
  "ue_log_query",
] as const;

export type ToolName = (typeof TOOL_NAMES)[number];

/** 完整工具目录集合（§2.9.4：工具存在性按完整目录判断） */
export const FULL_TOOL_CATALOG: ReadonlySet<string> = new Set(TOOL_NAMES);

/** 工具名 → 内部 RPC method（§2.8 RPC 方法表）
 *  ue_policy_explain 为纯服务端信息工具（不发 RPC）；policy.explain 仅为目录占位。 */
export const TOOL_RPC_METHOD: Record<ToolName, string> = {
  ue_editor_status: "editor.status",
  ue_actor_query: "actor.query",
  ue_actor_edit: "actor.edit",
  ue_level_control: "level.control",
  ue_asset_search: "asset.search",
  ue_material_params: "material.params",
  ue_viewport_capture: "viewport.capture",
  ue_console_command: "console.command",
  ue_python_exec: "python.exec",
  ue_blueprint: "blueprint.query",
  ue_pie_control: "pie.control",
  ue_policy_explain: "policy.explain",
  ue_reflect: "object.reflect",
  ue_call_function: "object.call",
  ue_log_query: "log.query",
};
