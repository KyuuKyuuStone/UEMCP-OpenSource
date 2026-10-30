/**
 * ue_policy_explain（2026-10-30 需求 #4，P1-4）：
 * 解释当前策略下每个工具的可见性——解决「--policy standard 下工具静默消失，
 * 用户要翻源码才知道为什么」的痛点。
 * - 纯服务端信息：不发 RPC、无副作用、恒可见（isToolVisible 恒 true）；
 * - 每工具一条 { name, visible, gate, reason, allowedActions? }：
 *   gate 取现有 toolDisabledGate()（server.policy / server.allowConsole / server.allowExec）；
 *   reason 为中英双语各一句；allowedActions 仅为 read-only 收窄的混合工具输出
 *   （narrowedActions()，含 ue_pie_control 的 ["status"]）；
 * - bridge 状态取自 watchdog 缓存的 /health（不可达时 connected=false 并在 note 说明）。
 *   注：watchdog/health 缓存中没有 bridge 侧 policies 字段，故如实返回 watchdog
 *   实际维护的连接信息，不编造字段。
 */
import { z } from "zod";
import { TOOL_NAMES } from "@uemcp/shared";
import { isToolVisible, narrowedActions, toolDisabledGate } from "../policy.js";
import {
  makeMeta,
  okResult,
  summarizeOut,
  type ToolContext,
  type ToolDef,
} from "./common.js";

/** 无入参：空 strict object（无未知键容忍，与 StatusInput 风格一致） */
const PolicyExplainInput = z.object({}).strict();

function explainReason(visible: boolean, gate: string, mode: string, allowedActions?: readonly string[]): string {
  if (visible && allowedActions) {
    return `read-only 下 action 收窄为 [${allowedActions.join(", ")}] / actions narrowed to [${allowedActions.join(", ")}] under read-only policy`;
  }
  if (visible) {
    return `当前策略可见 / visible under current policy`;
  }
  if (gate === "server.allowConsole") {
    return `需 --policy full 且开启 --allow-console / requires full policy and --allow-console`;
  }
  if (gate === "server.allowExec") {
    return `需 --policy full 且开启 --allow-exec / requires full policy and --allow-exec`;
  }
  return `${mode} 策略下不注册 / not registered under ${mode} policy`;
}

export const policyExplainTool: ToolDef = {
  name: "ue_policy_explain",
  rpcMethod: "policy.explain", // 仅目录占位：本工具不发 RPC
  title: "Explain Policy & Tool Visibility",
  description:
    "Explain the current server policy: per-tool visibility, the gate controlling it (server.policy / server.allowConsole / server.allowExec), narrowed actions under read-only, and the bridge connection state from the watchdog health cache. Purely informational: no RPC, no side effects, always visible.",
  timeoutMs: 30000, // 不发 RPC；字段为 ToolDef 契约占位
  schemaFor(_p) {
    return PolicyExplainInput;
  },
  async handle(ctx: ToolContext, _rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const mode = ctx.policy.mode;
    const tools = TOOL_NAMES.map((name) => {
      const visible = isToolVisible(name, ctx.policy);
      const gate = toolDisabledGate(name, ctx.policy);
      const allowedActions = narrowedActions(name, ctx.policy);
      return {
        name,
        visible,
        gate,
        reason: explainReason(visible, gate, mode, allowedActions),
        ...(allowedActions ? { allowedActions: [...allowedActions] } : {}),
      };
    });
    const w = ctx.watchdog.state;
    const bridge = w.connected
      ? {
          connected: true,
          ...(w.url ? { url: w.url } : {}),
          ...(w.ueVersion ? { ueVersion: w.ueVersion } : {}),
          ...(w.pluginVersion ? { pluginVersion: w.pluginVersion } : {}),
          ...(w.projectDir ? { projectDir: w.projectDir } : {}),
        }
      : {
          connected: false,
          note:
            "bridge 未连接（未发现或 /health 失败）：需要 bridge 的工具调用将返回 BRIDGE_UNAVAILABLE / bridge not connected; tool calls will fail with BRIDGE_UNAVAILABLE",
        };
    const data = {
      mode,
      allowDestructive: ctx.policy.allowDestructive,
      allowConsole: ctx.policy.allowConsole,
      allowExec: ctx.policy.allowExec,
      tools,
      bridge,
    };
    const meta = makeMeta(ctx, started);
    return okResult(
      policyExplainTool.name,
      summarizeOut(policyExplainTool.name, data as Record<string, unknown>, []),
      data,
      [],
      meta,
    );
  },
};
