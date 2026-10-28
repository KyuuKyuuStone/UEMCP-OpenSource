/**
 * 配置（§2.3）：优先级 命令行参数 > 环境变量 > 发现文件 > 默认值。
 */
export interface ServerOptions {
  transport: "http" | "stdio";
  host: string;
  port: number;
  policy: "read-only" | "standard" | "full";
  allowDestructive: boolean;
  allowConsole: boolean;
  allowExec: boolean;
  bridgeUrl?: string;
  bridgeToken?: string;
  projectDir?: string;
  authToken?: string;
  disableLegacySse: boolean;
  sessionTtlMs: number;
  sessionSweepMs: number;
  auditDir?: string;
}

export const DEFAULT_HTTP_PORT = 18777;
export const DEFAULT_BRIDGE_PORT = 18778;

const KNOWN_ARGS = new Set([
  "--transport",
  "--port",
  "--policy",
  "--allow-destructive",
  "--allow-console",
  "--allow-exec",
  "--bridge-url",
  "--bridge-token",
  "--project",
  "--auth-token",
  "--disable-legacy-sse",
  "--session-ttl-ms",
  "--session-sweep-ms",
]);

function parseArgs(argv: string[]): Record<string, string | boolean> {
  const out: Record<string, string | boolean> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!;
    if (a === "--allow-destructive" || a === "--allow-console" || a === "--allow-exec" || a === "--disable-legacy-sse") {
      out[a] = true;
      continue;
    }
    if (a.startsWith("--")) {
      // 未知参数明确报错（含已删除的 --audit-python-source），不静默忽略
      if (!KNOWN_ARGS.has(a)) {
        throw new Error(`Unknown option: ${a}`);
      }
      const key = a;
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        out[key] = next;
        i++;
      } else {
        out[key] = true;
      }
    }
  }
  return out;
}

function intOr(v: string | undefined, fallback: number): number {
  if (v === undefined || v === "") return fallback;
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? n : fallback;
}

export function loadConfig(argv: string[]): ServerOptions {
  const args = parseArgs(argv);
  const env = process.env;
  const transport = args["--transport"] === "stdio" ? "stdio" : "http";
  return {
    transport,
    host: "127.0.0.1",
    port: intOr(
      typeof args["--port"] === "string" ? args["--port"] : undefined,
      intOr(env.UEMCP_HTTP_PORT, DEFAULT_HTTP_PORT),
    ),
    policy:
      args["--policy"] === "standard" || args["--policy"] === "full" || args["--policy"] === "read-only"
        ? (args["--policy"] as ServerOptions["policy"])
        : (env.UEMCP_POLICY as ServerOptions["policy"]) === "standard" ||
            (env.UEMCP_POLICY as ServerOptions["policy"]) === "full"
          ? (env.UEMCP_POLICY as ServerOptions["policy"])
          : "read-only",
    allowDestructive: args["--allow-destructive"] === true || env.UEMCP_ALLOW_DESTRUCTIVE === "1",
    allowConsole: args["--allow-console"] === true || env.UEMCP_ALLOW_CONSOLE === "1",
    allowExec: args["--allow-exec"] === true || env.UEMCP_ALLOW_EXEC === "1",
    bridgeUrl:
      (typeof args["--bridge-url"] === "string" ? args["--bridge-url"] : undefined) ??
      env.UEMCP_BRIDGE_URL ??
      undefined,
    bridgeToken:
      (typeof args["--bridge-token"] === "string" ? args["--bridge-token"] : undefined) ??
      env.UEMCP_BRIDGE_TOKEN ??
      undefined,
    projectDir:
      (typeof args["--project"] === "string" ? args["--project"] : undefined) ??
      env.UEMCP_PROJECT ??
      undefined,
    authToken:
      (typeof args["--auth-token"] === "string" ? args["--auth-token"] : undefined) ??
      env.UEMCP_AUTH_TOKEN ??
      undefined,
    disableLegacySse: args["--disable-legacy-sse"] === true || env.UEMCP_DISABLE_LEGACY_SSE === "1",
    // D4 裁决：提供 TTL 覆盖参数供 PROTO-08 测试；默认 §3.3 的 30 分钟 / 60s 清扫。
    sessionTtlMs: intOr(
      typeof args["--session-ttl-ms"] === "string" ? args["--session-ttl-ms"] : undefined,
      intOr(env.UEMCP_SESSION_TTL_MS, 30 * 60 * 1000),
    ),
    sessionSweepMs: intOr(
      typeof args["--session-sweep-ms"] === "string" ? args["--session-sweep-ms"] : undefined,
      intOr(env.UEMCP_SESSION_SWEEP_MS, 60 * 1000),
    ),
    auditDir: env.UEMCP_AUDIT_DIR ?? undefined,
  };
}
