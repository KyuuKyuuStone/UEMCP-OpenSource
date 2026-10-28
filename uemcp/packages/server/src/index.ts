/**
 * UEMCP Server CLI 入口（§3.2/§3.3）。
 * 用法：uemcp --transport http|stdio [--port N] [--policy read-only|standard|full]
 *       [--allow-destructive] [--allow-console] [--allow-exec]
 *       [--bridge-url URL] [--bridge-token T] [--project DIR] [--auth-token TOKEN]
 *       [--disable-legacy-sse] [--session-ttl-ms N] [--session-sweep-ms N]
 * 进程健壮性（主管要求）：uncaughtException/unhandledRejection/SIGINT/SIGTERM/SIGBREAK
 * 统一记录（stderr + logs/server-YYYY-MM-DD.log 双写）后可控退出/继续；
 * 部署请用 scripts/start-server.ps1（分离进程，不随调用方终端退出）。
 */
import { loadConfig } from "./config.js";
import { createLogger, defaultLogDir } from "./logger.js";
import { Audit } from "./audit.js";
import { BridgeClient } from "./bridge/client.js";
import { BridgeWatchdog } from "./bridge/watchdog.js";
import type { PolicyState } from "./policy.js";
import { startHttp, type HttpTransportHandles } from "./transports/http.js";
import { startStdio } from "./transports/stdio.js";
import type { ToolContext } from "./tools/common.js";

async function main(): Promise<void> {
  const opts = loadConfig(process.argv.slice(2));
  const log = createLogger("info", defaultLogDir());

  // —— 进程级兜底（先于业务启动注册）——
  process.on("uncaughtException", (err) => {
    log.error("uncaught_exception", {
      pid: process.pid,
      message: err?.message,
      stack: err?.stack,
      ts: new Date().toISOString(),
    });
    process.exit(1);
  });
  process.on("unhandledRejection", (reason) => {
    // 记录但不退出：瞬态 rejection 不应打断本地服务（已双写日志可追溯）
    log.error("unhandled_rejection", { pid: process.pid, reason: String(reason) });
  });

  log.info("server_start", {
    pid: process.pid,
    argv: process.argv.slice(2),
    transport: opts.transport,
    port: opts.transport === "http" ? opts.port : undefined,
    policy: opts.policy,
    allowDestructive: opts.allowDestructive,
    allowConsole: opts.allowConsole,
    allowExec: opts.allowExec,
  });

  const policy: PolicyState = {
    mode: opts.policy,
    allowDestructive: opts.allowDestructive,
    allowConsole: opts.allowConsole,
    allowExec: opts.allowExec,
  };

  const audit = new Audit(log, opts.auditDir);
  await audit.init();

  const bridge = new BridgeClient(
    log,
    { bridgeUrl: opts.bridgeUrl, bridgeToken: opts.bridgeToken, projectDir: opts.projectDir },
    (b) => log.info("bridge_endpoint_changed", { url: b?.url ?? null }),
  );
  const watchdog = new BridgeWatchdog(bridge, log);
  watchdog.start();

  const ctx: ToolContext = {
    policy,
    bridge,
    watchdog,
    audit,
    log,
    transport: opts.transport === "stdio" ? "stdio" : "streamable-http",
    elicit: async () => "unsupported", // 由 buildMcpServer 内部按实例覆盖
  };

  let handles: HttpTransportHandles | null = null;
  let shuttingDown = false;
  const shutdown = (reason: string) => {
    if (shuttingDown) return;
    shuttingDown = true;
    log.info("server_shutdown", { pid: process.pid, reason, ts: new Date().toISOString() });
    void (async () => {
      await handles?.close().catch(() => {});
      watchdog.stop();
      process.exit(0);
    })();
  };
  const onSignal = (signal: string) => {
    log.info("signal_received", { pid: process.pid, signal, ts: new Date().toISOString() });
    shutdown(`signal:${signal}`);
  };
  for (const sig of ["SIGINT", "SIGTERM", "SIGBREAK"] as const) {
    try {
      process.on(sig, () => onSignal(sig));
    } catch {
      /* 平台不支持该信号 */
    }
  }

  if (opts.transport === "stdio") {
    await startStdio(ctx, log);
    return;
  }

  handles = await startHttp(opts, ctx, log, audit);
}

main().catch((err) => {
  process.stderr.write(
    JSON.stringify({
      level: "error",
      event: "fatal",
      ts: new Date().toISOString(),
      message: String((err as Error)?.stack ?? err),
    }) + "\n",
  );
  process.exit(1);
});
