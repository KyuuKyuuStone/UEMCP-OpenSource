/**
 * 工具注解（§5.0.4）：随策略模式变化。
 */
import type { PolicyMode, ToolName } from "@uemcp/shared";
import type { PolicyState } from "../policy.js";

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
  }
}

export type { PolicyState };
