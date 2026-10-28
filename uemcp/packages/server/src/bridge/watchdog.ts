/**
 * Bridge 探活（§3.3）：每 5s GET /health（超时 1s），维护 /health 的 bridge.connected
 * 与缓存元数据（ueVersion/pluginVersion/projectDir/startedAt）。
 */
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
    this.state = { connected: false };
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}
