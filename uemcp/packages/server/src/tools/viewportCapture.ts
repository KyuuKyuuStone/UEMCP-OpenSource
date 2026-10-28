import { readFile } from "node:fs/promises";
import { ViewportCaptureInput } from "@uemcp/shared";
import type { PolicyState } from "../policy.js";
import {
  auditCall,
  errResult,
  invalidArgument,
  makeMeta,
  okResult,
  summarizeOut,
  toolError,
  type ToolContext,
  type ToolDef,
} from "./common.js";
import { summarizeArgs } from "../audit.js";

const INLINE_IMAGE_LIMIT = 8 * 1024 * 1024; // §3.3：图像内联上限 8 MiB 原始字节

interface CaptureData {
  path?: string;
  width?: number;
  height?: number;
  format?: "png" | "jpeg";
  bytes?: number;
  capturedAt?: string;
  /** 向前兼容：若桥接直接返回 base64 则优先使用（主管裁决：当前桥接只返回 path） */
  base64Data?: string;
}

export const viewportCaptureTool: ToolDef = {
  name: "ue_viewport_capture",
  rpcMethod: "viewport.capture",
  title: "Capture Viewport Screenshot",
  description:
    "Capture the level viewport or PIE as PNG/JPEG. returnMode=image inlines base64 (<= 8 MiB, read from the captured file on this machine) otherwise falls back to file path with a warning. Screenshots are written to <Project>/Saved/UEMCP/captures/ and audited.",
  timeoutMs: 45000,
  schemaFor(_p: PolicyState) {
    return ViewportCaptureInput;
  },
  async handle(ctx: ToolContext, rawArgs: Record<string, unknown>) {
    const started = Date.now();
    const parsed = ViewportCaptureInput.safeParse(rawArgs);
    if (!parsed.success) {
      return errResult(invalidArgument(parsed.error), makeMeta(ctx, started));
    }
    const args = parsed.data;
    const res = await ctx.bridge.call("viewport.capture", args as Record<string, unknown>, viewportCaptureTool.timeoutMs, { retriable: true });
    const meta = makeMeta(ctx, started);
    await auditCall(ctx, {
      tool: viewportCaptureTool.name,
      rpcMethod: viewportCaptureTool.rpcMethod,
      requestId: meta.requestId,
      durationMs: meta.durationMs,
      ok: res.ok,
      errorCode: res.ok ? null : (res.error?.code ?? "INTERNAL"),
      decision: "allowed",
      argsSummary: summarizeArgs(viewportCaptureTool.name, rawArgs),
    });
    if (!res.ok) {
      return errResult(res.error ?? toolError("INTERNAL", "bridge call failed"), meta);
    }
    const data = res.data as CaptureData;
    const warnings = [...res.warnings];

    if (args.returnMode === "image") {
      // 优先桥接 base64Data（向前兼容）；否则读捕获文件（同机）编码
      let base64: string | undefined = data.base64Data;
      let size = base64 ? (data.bytes ?? 0) : 0;
      if (!base64 && data.path) {
        try {
          const buf = await readFile(data.path);
          size = buf.length;
          if (size <= INLINE_IMAGE_LIMIT) base64 = buf.toString("base64");
        } catch {
          size = -1; // 读失败：与无路径同等处理（降级 file + warning）
        }
      }
      if (base64 && size <= INLINE_IMAGE_LIMIT) {
        const mime = data.format === "jpeg" ? "image/jpeg" : "image/png";
        return okResult(
          viewportCaptureTool.name,
          summarizeOut(viewportCaptureTool.name, data as Record<string, unknown>, warnings),
          data,
          warnings,
          meta,
          [{ type: "image", data: base64, mimeType: mime }],
        );
      }
      // 超过 8 MiB、无路径或读失败 → 降级 file（§5.7），附 warning
      warnings.push("IMAGE_TOO_LARGE_FOR_INLINE");
      const { base64Data: _drop, ...rest } = data;
      void _drop;
      return okResult(
        viewportCaptureTool.name,
        summarizeOut(viewportCaptureTool.name, rest as Record<string, unknown>, warnings),
        rest,
        warnings,
        meta,
      );
    }
    return okResult(
      viewportCaptureTool.name,
      summarizeOut(viewportCaptureTool.name, data as Record<string, unknown>, warnings),
      data,
      warnings,
      meta,
    );
  },
};
