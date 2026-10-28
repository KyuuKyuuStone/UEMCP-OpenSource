/**
 * Bridge JSON-RPC client（§2.8 内部协议 + §2.9.5 转换规则）。
 * - 连接拒绝/不可达/短时失败（非超时异常）→ BRIDGE_UNAVAILABLE（retryable）
 * - 等待超时（AbortSignal TimeoutError）→ BRIDGE_TIMEOUT（phase=game_thread）
 * - 合法 JSON-RPC error → 按 data.errorCode 映射；未知 → INTERNAL
 * - 非 JSON / 5xx 无合法 body → INTERNAL（details.bridgeHttpStatus）
 * - token 轮换自愈：401/BRIDGE_UNAVAILABLE 时重新发现一次再重试
 */
import { randomUUID } from "node:crypto";
import {
  isToolErrorCode,
  toolErrorRetryable,
  type ToolErrorShape,
} from "@uemcp/shared";
import type { Logger } from "../logger.js";
import { resolveBridge, type DiscoveryOptions, type ResolvedBridge } from "./discovery.js";

export interface BridgeCallResult<T = unknown> {
  ok: boolean;
  data?: T;
  warnings: string[];
  meta: Record<string, unknown>;
  error?: ToolErrorShape;
}

const MAX_TIMEOUT_MS = 120000; // §2.6：单工具超时上限 120s

export interface CallOptions {
  /**
   * Major-4：仅只读/幂等方法允许 BRIDGE_UNAVAILABLE 自动重试（重新发现一次）；
   * 写方法必须传 false（或省略，默认 false），直接返回可重试错误由用户确认后重发，
   * 避免桥接已执行但响应丢失时的重复执行。
   */
  retriable?: boolean;
}

export class BridgeClient {
  private current: ResolvedBridge | null = null;
  private log: Logger;
  private discoveryOpts: DiscoveryOptions;
  private onEndpointChange?: (b: ResolvedBridge | null) => void;

  constructor(
    log: Logger,
    discoveryOpts: DiscoveryOptions,
    onEndpointChange?: (b: ResolvedBridge | null) => void,
  ) {
    this.log = log;
    this.discoveryOpts = discoveryOpts;
    this.onEndpointChange = onEndpointChange;
  }

  getCached(): ResolvedBridge | null {
    return this.current;
  }

  async ensureDiscovered(): Promise<ResolvedBridge | null> {
    if (!this.current) {
      this.current = await resolveBridge(this.discoveryOpts, this.log);
      this.onEndpointChange?.(this.current);
      if (this.current) {
        this.log.info("bridge_connected", {
          url: this.current.url,
          source: this.current.source,
        });
      }
    }
    return this.current;
  }

  invalidate(): void {
    this.current = null;
    this.onEndpointChange?.(null);
  }

  async call<T = unknown>(
    method: string,
    params: Record<string, unknown>,
    timeoutMs: number = 30000,
    opts: CallOptions = {},
  ): Promise<BridgeCallResult<T>> {
    const t = Math.min(Math.max(1000, timeoutMs), MAX_TIMEOUT_MS);
    const first = await this.attempt<T>(method, params, t);
    if (
      !first.ok &&
      opts.retriable === true &&
      first.error?.code === "BRIDGE_UNAVAILABLE" &&
      first.error.retryable
    ) {
      // 仅只读/幂等方法：token 轮换 / 桥接重启自愈，重新发现一次
      this.log.debug("bridge_retry_readonly", { method });
      this.invalidate();
      return this.attempt<T>(method, params, t);
    }
    if (
      !first.ok &&
      first.error?.code === "BRIDGE_UNAVAILABLE" &&
      opts.retriable !== true
    ) {
      return {
        ...first,
        error: {
          ...first.error!,
          message:
            first.error!.message +
            " (not auto-retried: non-idempotent method; confirm and retry)",
        },
      };
    }
    return first;
  }

  private async attempt<T>(
    method: string,
    params: Record<string, unknown>,
    timeoutMs: number,
  ): Promise<BridgeCallResult<T>> {
    const endpoint = await this.ensureDiscovered();
    if (!endpoint) {
      return err("BRIDGE_UNAVAILABLE", "Bridge not discovered (no reachable bridge)");
    }
    const id = randomUUID();
    const started = Date.now();
    try {
      const res = await fetch(endpoint.url + "/rpc", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(endpoint.token ? { "X-UEMCP-Token": endpoint.token } : {}),
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id,
          method,
          params,
          meta: { timeoutMs, traceId: "trc_" + randomUUID() },
        }),
        signal: AbortSignal.timeout(timeoutMs + 5000),
      });
      const text = await res.text();
      if (res.status === 401) {
        // token 被拒：发现信息（token/来源）已失效 → BRIDGE_UNAVAILABLE（retriable，
        // 调用侧按 retriable 策略重新发现），而不是 INTERNAL
        return err(
          "BRIDGE_UNAVAILABLE",
          `Bridge rejected token (HTTP 401) at ${endpoint.url}`,
          { bridgeHttpStatus: 401 },
        );
      }
      let body: unknown;
      try {
        body = JSON.parse(text);
      } catch {
        return err(
          "INTERNAL",
          `Bridge returned non-JSON response (HTTP ${res.status})`,
          { bridgeHttpStatus: res.status },
        );
      }
      const b = body as {
        result?: { ok?: boolean; data?: T; warnings?: string[]; meta?: Record<string, unknown> };
        error?: { code?: number; message?: string; data?: { errorCode?: string; retryable?: boolean; details?: Record<string, unknown> } };
      };
      if (b.error) {
        const ec = b.error.data?.errorCode;
        if (typeof ec === "string" && isToolErrorCode(ec)) {
          return err(
            ec,
            b.error.message ?? ec,
            b.error.data?.details,
            b.error.data?.retryable ?? toolErrorRetryable(ec),
          );
        }
        return err("INTERNAL", b.error.message ?? "Unknown bridge error", {
          bridgeErrorCode: b.error.code,
        });
      }
      if (b.result && b.result.ok === true) {
        return {
          ok: true,
          data: b.result.data,
          warnings: b.result.warnings ?? [],
          meta: { ...(b.result.meta ?? {}), durationMs: Date.now() - started },
        };
      }
      return err("INTERNAL", "Bridge result missing ok:true envelope", {
        bridgeResult: b.result as unknown as Record<string, unknown> | undefined,
      });
    } catch (e) {
      // m-2（审查报告）：按异常类型区分——TimeoutError（AbortSignal.timeout
      // 触发，elapsed 恒 ≥ timeoutMs+5s）→ BRIDGE_TIMEOUT；连接拒绝等其他异常
      // （快速失败）→ BRIDGE_UNAVAILABLE。原 CONNECT_WINDOW_MS「elapsed<3s →
      // 连接层失败」分支不可达（abort 时 elapsed 必 ≥ 6s），已删除。
      const isAbort = e instanceof Error && e.name === "TimeoutError";
      if (isAbort) {
        return err(
          "BRIDGE_TIMEOUT",
          `Game-thread job timed out after ${timeoutMs}ms (method ${method})`,
          { timeoutMs, phase: "game_thread" },
        );
      }
      return err("BRIDGE_UNAVAILABLE", `Bridge unreachable: ${String(e)}`);
    }
  }
}

function err(
  code: ToolErrorShape["code"],
  message: string,
  details?: Record<string, unknown>,
  retryable?: boolean,
): BridgeCallResult<never> {
  return {
    ok: false,
    warnings: [],
    meta: {},
    error: {
      code,
      message,
      retryable: retryable ?? toolErrorRetryable(code),
      ...(details !== undefined ? { details } : {}),
    },
  };
}
