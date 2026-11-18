/**
 * 工具注解（§5.0.4）：随策略模式变化。
 * （唯一实现：policy.ts 中的旧 toolAnnotations(tool, PolicyState) 重复实现已删除——
 *   无人引用且签名口径不同，见审查 m 系列与任务 4248c955-B。）
 */
import type { PolicyMode, ToolName } from "@uemcp/shared";

export interface ToolAnnotationSet {
  title?: string;
  readOnlyHint: boolean;
  destructiveHint: boolean;
  idempotentHint: boolean;
  openWorldHint: boolean;
}

/** §5.0.4 注解表；混合工具 read-only 下 readOnlyHint=true、destructiveHint=false */
export function toolAnnotations(tool: ToolName, mode: PolicyMode): ToolAnnotationSet {
  const ro = mode === "read-only";
  switch (tool) {
    case "ue_editor_status":
      return { title: "Get Unreal Editor Status", readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
    case "ue_actor_query":
      return { title: "Query Unreal Actors", readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
    case "ue_asset_search":
      return { title: "Search Unreal Assets", readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
    case "ue_viewport_capture":
      return { title: "Capture Viewport Screenshot", readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false };
    case "ue_actor_edit":
      return { title: "Edit Unreal Actors", readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false };
    case "ue_console_command":
      return { title: "Execute Console Command", readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false };
    case "ue_python_exec":
      return { title: "Execute Python in Editor", readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true };
    case "ue_level_control":
      return ro
        ? { title: "Control Level (read-only actions)", readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false }
        : { title: "Control Level", readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false };
    case "ue_material_params":
      return ro
        ? { title: "Material Parameters (read-only actions)", readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false }
        : { title: "Material Parameters", readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false };
    case "ue_blueprint":
      return ro
        ? { title: "Blueprint Query", readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false }
        : { title: "Blueprint Query / Compile", readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false };
    case "ue_pie_control":
      // 契约（2026-10-30）：readOnlyHint=false / destructiveHint=false / idempotentHint=false；
      // read-only 下仅剩 status，与混合工具口径一致 readOnlyHint=true。
      return ro
        ? { title: "PIE Control (status only)", readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false }
        : { title: "PIE Control", readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false };
    case "ue_policy_explain":
      return { title: "Explain Policy & Tool Visibility", readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
    case "ue_reflect":
      return { title: "Reflect Object Functions", readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
    case "ue_call_function":
      return { title: "Call Object Function", readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false };
    case "ue_log_query":
      return { title: "Query Editor Log", readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
  }
}
