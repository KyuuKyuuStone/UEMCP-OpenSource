/**
 * Bridge 探活（§3.3）：每 5s GET /health（超时 1s），维护 /health 的 bridge.connected
 * 与缓存元数据（ueVersion/pluginVersion/projectDir/startedAt）。
 * B-3.1/B-3.9（看门狗第一刀）：同时保留 /health 的构建身份四字段
 * （instanceId/buildHash/buildTime/sourcePath）与 capabilities/rateLimit/policies/
 * bridgeProtocol/schemaVersion——本文件是这些字段的唯一丢弃点，保留后解锁
 * 审计构建身份、策略快照与 pixelStreaming 能力位预检。
 * B-3.4：断连（markDown/无缓存）时 state 整体重置为 {connected:false}，
 * 全部字段置空——绝不以旧缓存冒充现值、绝不伪造。
 */
import type { BridgeDiscoveryFile } from "@uemcp/shared";
import type { Logger } from "../logger.js";
import type { BridgeClient } from "./client.js";

export interface BridgeWatchState {
  connected: boolean;
  url?: string;
  ueVersion?: string;
  pluginVersion?: string;
  projectDir?: string;
  startedAt?: string;
  pid?: number;
  /** B-3.1 构建身份：仅记录 /health 实际返回的字符串值（缺失→undefined，不伪造） */
  instanceId?: string;
  buildHash?: string;
  buildTime?: string;
  sourcePath?: string;
  /** B-3.3/B-3.9：/health 返回的能力位/限流/策略/协议版本（对象/数字守卫，按收到的键原样保留） */
  capabilities?: BridgeDiscoveryFile["capabilities"];
  rateLimit?: Record<string, unknown>;
  policies?: Record<string, unknown>;
  bridgeProtocol?: number;
  /** B-3.9：/health schemaVersion（过渡期桥接可能缺失；缺失→undefined） */
  schemaVersion?: number;
}

export class BridgeWatchdog {
  private timer: NodeJS.Timeout | null = null;
  state: BridgeWatchState = { connected: false };

  constructor(
    private client: BridgeClient,
    private log: Logger,
  ) {}

  start(): void {
    const probe = async () => {
      let cached = this.client.getCached();
      if (!cached) {
        // 首次（或桥接失效后）主动发现，让 /health 尽快反映真实状态
        cached = await this.client.ensureDiscovered();
        if (cached) this.log.info("bridge_connected", { url: cached.url, source: cached.source });
      }
      if (!cached) {
        // 未连接时不主动写日志（每 5s 一条太吵），仅维护状态
        this.state = { connected: false };
        return;
      }
      try {
        const res = await fetch(cached.url + "/health", {
          signal: AbortSignal.timeout(1000),
        });
        const body = res.ok
          ? ((await res.json()) as Record<string, unknown>)
          : null;
        if (body && body.app === "uemcp-bridge" && body.ok === true) {
          const wasConnected = this.state.connected;
          this.state = {
            connected: true,
            url: cached.url,
            ueVersion:
              typeof body.ueVersion === "string" ? body.ueVersion : cached.discovery?.ueVersion,
            pluginVersion:
              typeof body.pluginVersion === "string"
                ? body.pluginVersion
                : cached.discovery?.pluginVersion,
            projectDir:
              typeof body.projectDir === "string"
                ? body.projectDir
                : cached.discovery?.projectDir,
            startedAt:
              typeof body.startedAt === "string" ? body.startedAt : cached.discovery?.startedAt,
            pid: typeof body.pid === "number" ? body.pid : cached.discovery?.pid,
            // B-3.1/B-3.9 新增保留字段：只取 /health 实际返回值（不回退发现文件、不伪造）；
            // 旧桥接缺失这些键时保持 undefined，消费侧（审计/status/预检）容忍缺失。
            instanceId: typeof body.instanceId === "string" ? body.instanceId : undefined,
            buildHash: typeof body.buildHash === "string" ? body.buildHash : undefined,
            buildTime: typeof body.buildTime === "string" ? body.buildTime : undefined,
            sourcePath: typeof body.sourcePath === "string" ? body.sourcePath : undefined,
            capabilities:
              typeof body.capabilities === "object" && body.capabilities !== null
                ? (body.capabilities as BridgeDiscoveryFile["capabilities"])
                : undefined,
            rateLimit:
              typeof body.rateLimit === "object" && body.rateLimit !== null
                ? (body.rateLimit as Record<string, unknown>)
                : undefined,
            policies:
              typeof body.policies === "object" && body.policies !== null
                ? (body.policies as Record<string, unknown>)
                : undefined,
            bridgeProtocol:
              typeof body.bridgeProtocol === "number" ? body.bridgeProtocol : undefined,
            schemaVersion:
              typeof body.schemaVersion === "number" ? body.schemaVersion : undefined,
          };
          if (!wasConnected) this.log.info("bridge_watchdog_up", { url: cached.url });
        } else {
          this.markDown(cached.url);
        }
      } catch {
        this.markDown(cached.url);
      }
    };
    void probe();
    this.timer = setInterval(probe, 5000);
    this.timer.unref?.();
  }

  private markDown(url: string): void {
    if (this.state.connected) {
      this.log.warn("bridge_watchdog_down", { url });
      // 桥接疑似关闭：失效缓存，下次调用重新发现
      this.client.invalidate();
    }
    // B-3.4：整体重置——构建身份/能力位/策略等保留字段一并置空，不以旧缓存冒充现值
    this.state = { connected: false };
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}
