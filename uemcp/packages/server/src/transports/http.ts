/**
 * Streamable HTTP + 旧版 SSE 传输（§3.3/§3.4）+ /health。
 * - 仅回环绑定；Host 校验 421 / Origin 校验 403 / OPTIONS 405
 * - 可选 Bearer 鉴权（§6.6 常量时间比较）
 * - 会话：Mcp-Session-Id、TTL、上限 32（429）、DELETE 204、未知 404/-32001
 * - EADDRINUSE：2 秒内 exit 2（§2.3/D10）
 * - 协议层错误（§2.9.2/§2.9.4）：信封/未知工具 400 -32602、未知 method 404 -32601
 */
import express, {
  type Express,
  type Request,
  type Response,
  type NextFunction,
  type RequestHandler,
} from "express";
import { Server } from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { FULL_TOOL_CATALOG } from "@uemcp/shared";
import type { ToolContext } from "../tools/common.js";
import {
  buildMcpServer,
  PROTOCOL_VERSIONS,
  SERVER_NAME,
  SERVER_VERSION,
} from "../mcp/buildServer.js";
import type { ServerOptions } from "../config.js";
import type { Logger } from "../logger.js";
import type { Audit } from "../audit.js";

const MAX_BODY_BYTES = 8 * 1024 * 1024;
const KNOWN_METHODS = new Set([
  "initialize",
  "notifications/initialized",
  "ping",
  "tools/list",
  "tools/call",
]);

// §6.7 速率限制：每会话 20 req/s、突发 40（令牌桶；协议层 429 + RATE_LIMITED；stdio 不适用）
const RATE_PER_SEC = 20;
const RATE_BURST = 40;
const rateBuckets = new Map<string, { tokens: number; last: number }>();
function rateAllow(key: string): boolean {
  const now = Date.now();
  let b = rateBuckets.get(key);
  if (!b) {
    b = { tokens: RATE_BURST, last: now };
    rateBuckets.set(key, b);
  }
  b.tokens = Math.min(RATE_BURST, b.tokens + ((now - b.last) / 1000) * RATE_PER_SEC);
  b.last = now;
  if (b.tokens < 1) return false;
  b.tokens -= 1;
  return true;
}

type SessionEntry =
  | {
      kind: "streamable";
      transport: StreamableHTTPServerTransport;
      lastSeen: number;
      /** 是否有未关闭的 standalone GET /mcp SSE 流（LRU 逐出时跳过这类活跃流会话） */
      sseOpen?: boolean;
    }
  | {
      kind: "legacy";
      transport: SSEServerTransport;
      lastSeen: number;
      heartbeat?: NodeJS.Timeout;
    };

export interface HttpTransportHandles {
  app: Express;
  server: Server;
  sessionCount(): number;
  close(): Promise<void>;
}

const asyncHandler =
  (fn: (req: Request, res: Response) => Promise<void>): RequestHandler =>
  (req, res, next) => {
    fn(req, res).catch(next);
  };

export function startHttp(
  opts: ServerOptions,
  ctx: ToolContext,
  log: Logger,
  audit: Audit,
): Promise<HttpTransportHandles> {
  const app = express();
  const sessions = new Map<string, SessionEntry>();
  const startedAt = Date.now();
  const server = new Server(app);
  app.disable("x-powered-by");

  // —— 会话池满仓的 LRU 逐出（P1-5）——
  // 逐出对象：streamable 会话里 lastSeen 最老的一个；两类会话不参与逐出：
  //   1) legacy（旧版 /sse）——它的 SSE 连接是长活流，只有连接断开（onclose）才会出 map，
  //      在 map 里即活跃；
  //   2) streamable 但 sseOpen=true ——有未关闭的 standalone GET /mcp SSE 流。
  // 优先逐出「裸 POST 会话」的理由：这类会话没有任何在途响应/流，transport.close()
  // 不会打断任何客户端正在读取的数据；SSE 活流被逐出会立刻表现为客户端读到半截事件流。
  // 若全部会话都持活跃流（无可逐出对象），才返回 429 并带 retryAfterMs / sessions 现值。
  const tryEvictOldestIdle = (): string | null => {
    let victimId: string | null = null;
    let victimLastSeen = Number.POSITIVE_INFINITY;
    for (const [id, e] of sessions) {
      if (e.kind === "legacy") continue;
      if (e.kind === "streamable" && e.sseOpen) continue;
      if (e.lastSeen < victimLastSeen) {
        victimLastSeen = e.lastSeen;
        victimId = id;
      }
    }
    if (victimId === null) return null;
    const victim = sessions.get(victimId)!;
    sessions.delete(victimId);
    rateBuckets.delete(victimId);
    log.info("session_evicted", {
      sessionId: victimId,
      kind: victim.kind,
      reason: "pool_full_lru",
      idleMs: Date.now() - victimLastSeen,
    });
    void victim.transport.close().catch(() => {});
    return victimId;
  };

  const poolFull429 = (res: Response): void => {
    sendRpcError(
      res,
      429,
      -32012,
      "RATE_LIMITED",
      `Too many concurrent sessions (max ${opts.maxSessions}); all sessions hold active SSE streams`,
      {
        retryAfterMs: opts.sessionSweepMs,
        sessions: sessions.size,
        maxSessions: opts.maxSessions,
      },
    );
  };

  const boundPort = (): number =>
    (server.address() as { port: number } | null)?.port ?? opts.port;

  // —— charset 中间件（外部报告建议项，2026-10-29）——
  // /mcp 的响应头由 SDK 传输层手写：Streamable HTTP 经 @hono/node-server 最终走
  // outgoing.writeHead(status, header)，旧版 SSE 直接 res.writeHead(200, {...})，
  // 均不经 express 的 res.set，Content-Type 不带 charset；/health 与 sendRpcError
  // 走 express res.json（express 自会补 charset）。客户端侧（如 PowerShell 5.1
  // 的 Invoke-WebRequest）在缺失 charset 时按 Latin-1 解码 UTF-8 字节，中文成乱码。
  // 此处在最先的中间件里统一包裹 res.setHeader / res.writeHead：JSON 与 SSE 两类
  // Content-Type 缺 charset 时补 "; charset=utf-8"，已带 charset 的原样放行（幂等）。
  app.use((_req: Request, res: Response, next: NextFunction) => {
    const withCharset = (type: string): string => {
      const base = type.split(";")[0]!.trim().toLowerCase();
      if ((base === "application/json" || base === "text/event-stream") && !/charset=/i.test(type)) {
        return `${type}; charset=utf-8`;
      }
      return type;
    };
    const origSetHeader = res.setHeader.bind(res) as (name: string, value: string | number | readonly string[]) => unknown;
    const origWriteHead = res.writeHead.bind(res) as (...args: unknown[]) => unknown;
    const patched = res as unknown as {
      setHeader: (name: string, value: string | number | readonly string[]) => unknown;
      writeHead: (...args: unknown[]) => unknown;
    };
    patched.setHeader = (name, value) => {
      if (typeof name === "string" && name.toLowerCase() === "content-type" && typeof value === "string") {
        return origSetHeader(name, withCharset(value));
      }
      return origSetHeader(name, value);
    };
    // writeHead 兼容三种重载：[status]、[status, reason, headers]、[status, headers]
    patched.writeHead = (...args: unknown[]) => {
      for (const arg of args) {
        if (arg !== null && typeof arg === "object" && !Array.isArray(arg)) {
          const headers = arg as Record<string, unknown>;
          for (const key of Object.keys(headers)) {
            if (key.toLowerCase() === "content-type" && typeof headers[key] === "string") {
              headers[key] = withCharset(headers[key] as string);
            }
          }
        }
      }
      return origWriteHead(...args);
    };
    next();
  });

  // —— 安全中间件（§6.2）——
  app.use((req: Request, res: Response, next: NextFunction) => {
    const remote = req.socket.remoteAddress ?? "";
    if (remote !== "127.0.0.1" && remote !== "::1" && remote !== "::ffff:127.0.0.1") {
      res.destroy();
      return;
    }
    if (req.method === "OPTIONS") {
      res.status(405).end();
      return;
    }
    const port = boundPort();
    const host = (req.headers.host ?? "").toLowerCase();
    if (host !== `127.0.0.1:${port}` && host !== `localhost:${port}`) {
      sendRpcError(res, 421, -32600, "INVALID_REQUEST", `Host header not allowed: ${host}`);
      return;
    }
    const origin = req.headers.origin;
    if (origin !== undefined) {
      const ok =
        origin === "null" ||
        origin.toLowerCase() === `http://127.0.0.1:${port}` ||
        origin.toLowerCase() === `http://localhost:${port}`;
      if (!ok) {
        sendRpcError(res, 403, -32600, "INVALID_REQUEST", `Origin not allowed: ${origin}`);
        return;
      }
    }
    if (opts.authToken) {
      const auth = req.headers.authorization ?? "";
      const m = /^Bearer (.+)$/.exec(auth);
      if (!m || !safeEqual(m[1]!, opts.authToken)) {
        sendRpcError(res, 401, -32019, "UNAUTHORIZED", "unauthorized");
        return;
      }
    }
    next();
  });

  app.use(express.json({ limit: MAX_BODY_BYTES, type: () => true }));

  // 请求体超限 / 非法 JSON / 未捕获异常（§2.9.2）
  const errorHandler = (err: unknown, _req: Request, res: Response, next: NextFunction): void => {
    if (res.headersSent) {
      next(err);
      return;
    }
    const e = err as { type?: string; status?: number; statusCode?: number };
    if (e?.type === "entity.too.large" || e?.status === 413 || e?.statusCode === 413) {
      sendRpcError(res, 413, -32011, "PAYLOAD_TOO_LARGE", "Request body exceeds 8 MiB limit");
      return;
    }
    if (e?.type === "entity.parse.failed") {
      sendRpcError(res, 400, -32700, "PARSE_ERROR", "Invalid JSON body");
      return;
    }
    sendRpcError(res, 500, -32603, "INTERNAL", String((err as Error)?.message ?? err));
  };

  // —— /health ——
  app.get("/health", (_req: Request, res: Response) => {
    const w = ctx.watchdog.state;
    res.json({
      ok: true,
      name: SERVER_NAME,
      version: SERVER_VERSION,
      protocolVersions: PROTOCOL_VERSIONS,
      transports: ["streamable-http", "sse", "stdio"],
      sessions: sessions.size,
      uptimeSec: Math.floor((Date.now() - startedAt) / 1000),
      pid: process.pid,
      ...(ctx.log.file() ? { logPath: ctx.log.file() } : {}),
      bridge: {
        connected: w.connected,
        ...(w.url ? { url: w.url } : {}),
        ...(w.ueVersion ? { ueVersion: w.ueVersion } : {}),
        ...(w.pluginVersion ? { pluginVersion: w.pluginVersion } : {}),
        ...(w.projectDir ? { projectDir: w.projectDir } : {}),
      },
      ...(audit.degraded ? { auditDegraded: true } : {}),
    });
  });

  // —— Streamable HTTP：/mcp ——
  app.post("/mcp", asyncHandler(async (req: Request, res: Response) => {
    let body = req.body;
    // 协议层预校验（§2.9.4 校验顺序：信封 → 完整目录存在性 → 策略 → zod）
    if (isJsonObject(body)) {
      const method = body.method;
      if (
        typeof method === "string" &&
        method !== "" &&
        !KNOWN_METHODS.has(method) &&
        !method.startsWith("notifications/")
      ) {
        sendRpcError(res, 404, -32601, "METHOD_NOT_FOUND", `Unknown method: ${method}`);
        return;
      }
      if (method === "tools/call") {
        const params = body.params;
        if (!isJsonObject(params)) {
          sendRpcError(res, 400, -32602, "INVALID_PARAMS", "tools/call params must be an object");
          return;
        }
        const name = params.name;
        if (typeof name !== "string" || name === "") {
          sendRpcError(res, 400, -32602, "INVALID_PARAMS", "tools/call requires string name");
          return;
        }
        const args = params.arguments;
        if (args !== undefined && !isJsonObject(args)) {
          sendRpcError(res, 400, -32602, "INVALID_PARAMS", "tools/call arguments must be an object");
          return;
        }
        if (!FULL_TOOL_CATALOG.has(name)) {
          sendRpcError(res, 400, -32602, "INVALID_PARAMS", `Unknown tool: ${name}`);
          return;
        }
      }
    }
    // 协议版本协商（§3.6/§3.3）：仅接受三版本表；其他（含 SDK 更新的
    // 2025-11-25 与未知版本）统一按 2025-06-18 处理，由 SDK 回显该版本
    if (isJsonObject(body) && body.method === "initialize") {
      const params = body.params;
      const pv =
        isJsonObject(params) && typeof params.protocolVersion === "string"
          ? params.protocolVersion
          : undefined;
      if (pv === undefined || !PROTOCOL_VERSIONS.includes(pv)) {
        const patched = { ...body } as { params: Record<string, unknown> };
        patched.params = { ...(params as object), protocolVersion: "2025-06-18" };
        body = patched;
      }
    }
    const sid = req.header("mcp-session-id");
    if (!sid) {
      if (!isInitialize(body)) {
        sendRpcError(res, 400, -32600, "INVALID_REQUEST", "Missing session: initialize required");
        return;
      }
      if (sessions.size >= opts.maxSessions) {
        // 满仓：先尝试 LRU 逐出（P1-5），无可逐出对象才 429
        if (tryEvictOldestIdle() === null) {
          poolFull429(res);
          return;
        }
      }
      // 失效可预期（P1-5）：initialize 响应头声明会话空闲 TTL（毫秒）。
      // 客户端收到 404 -32001 时应重新 initialize（data.hint=reinitialize）。
      const expiresHeader = "Mcp-Session-Expires-In-Ms";
      const origInitWriteHead = res.writeHead.bind(res) as (...args: unknown[]) => unknown;
      (res as unknown as { writeHead: (...args: unknown[]) => unknown }).writeHead = (...args: unknown[]) => {
        for (const arg of args) {
          if (arg !== null && typeof arg === "object" && !Array.isArray(arg)) {
            const headers = arg as Record<string, unknown>;
            const ctKey = Object.keys(headers).find((k) => k.toLowerCase() === "content-type");
            if (ctKey !== undefined) {
              headers[expiresHeader] = String(opts.sessionTtlMs);
              break;
            }
          }
        }
        return origInitWriteHead(...args);
      };
      const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (id) => {
          sessions.set(id, { transport, lastSeen: Date.now(), kind: "streamable" });
          log.debug("session_created", { sessionId: id, kind: "streamable" });
        },
      });
      transport.onclose = () => {
        for (const [id, e] of sessions) {
          if (e.transport === transport) sessions.delete(id);
        }
      };
      const mcp = buildMcpServer(ctx);
      await mcp.connect(transport);
      await transport.handleRequest(req, res, body);
      return;
    }
    const entry = sessions.get(sid);
    if (!entry || entry.kind !== "streamable") {
      sendRpcError(res, 404, -32001, "SESSION_NOT_FOUND", "Session not found", {
        hint: "reinitialize",
        ttlMs: opts.sessionTtlMs,
      });
      return;
    }
    if (!rateAllow(sid)) {
      sendRpcError(res, 429, -32012, "RATE_LIMITED", "Rate limit exceeded (20 req/s per session)");
      return;
    }
    entry.lastSeen = Date.now();
    await entry.transport.handleRequest(req, res, body);
  }));

  app.get("/mcp", (req: Request, res: Response) => {
    const sid = req.header("mcp-session-id") ?? "";
    const entry = sessions.get(sid);
    if (!entry || entry.kind !== "streamable") {
      sendRpcError(res, 404, -32001, "SESSION_NOT_FOUND", "Session not found", {
        hint: "reinitialize",
        ttlMs: opts.sessionTtlMs,
      });
      return;
    }
    entry.lastSeen = Date.now();
    // standalone SSE 流标记：开启期间该会话不参与 LRU 逐出，连接关闭后解除
    if (entry.kind === "streamable") {
      entry.sseOpen = true;
      res.on("close", () => {
        entry.sseOpen = false;
      });
    }
    void entry.transport.handleRequest(req, res).catch(() => {
      if (!res.headersSent) sendRpcError(res, 500, -32603, "INTERNAL", "GET /mcp failed");
    });
  });

  app.delete("/mcp", asyncHandler(async (req: Request, res: Response) => {
    const sid = req.header("mcp-session-id") ?? "";
    const entry = sessions.get(sid);
    if (!entry || entry.kind !== "streamable") {
      sendRpcError(res, 404, -32001, "SESSION_NOT_FOUND", "Session not found", {
        hint: "reinitialize",
        ttlMs: opts.sessionTtlMs,
      });
      return;
    }
    await entry.transport.close();
    rateBuckets.delete(sid);
    sessions.delete(sid);
    res.status(204).end();
  }));

  // —— 旧版 SSE：/sse + /messages（§3.4）——
  if (!opts.disableLegacySse) {
    app.get("/sse", asyncHandler(async (_req: Request, res: Response) => {
      if (sessions.size >= opts.maxSessions) {
        // 满仓：与 /mcp 相同的 LRU 逐出口径（legacy 会话本身是活跃流，不会被选为逐出对象）
        if (tryEvictOldestIdle() === null) {
          poolFull429(res);
          return;
        }
      }
      const transport = new SSEServerTransport("/messages", res);
      sessions.set(transport.sessionId, {
        transport,
        lastSeen: Date.now(),
        kind: "legacy",
        heartbeat: setInterval(() => {
          try {
            res.write(": ping\n\n");
          } catch {
            /* 连接已断开 */
          }
        }, 15000),
      });
      transport.onclose = () => {
        const e = sessions.get(transport.sessionId);
        if (e?.kind === "legacy" && e.heartbeat) clearInterval(e.heartbeat);
        sessions.delete(transport.sessionId);
      };
      const mcp = buildMcpServer(ctx);
      await mcp.connect(transport);
    }));

    app.post("/messages", asyncHandler(async (req: Request, res: Response) => {
      const sid = String(req.query.sessionId ?? "");
      const entry = sessions.get(sid);
      if (!entry || entry.kind !== "legacy") {
        res.status(404).end();
        return;
      }
      entry.lastSeen = Date.now();
      if (!rateAllow(sid)) {
        sendRpcError(res, 429, -32012, "RATE_LIMITED", "Rate limit exceeded (20 req/s per session)");
        return;
      }
      await entry.transport.handlePostMessage(req, res, req.body);
    }));
  }

  app.use((_req: Request, res: Response) => {
    res.status(404).json({ error: "not_found" });
  });
  app.use(errorHandler);

  // —— TTL 清扫（§3.3）——
  const sweeper = setInterval(() => {
    const now = Date.now();
    for (const [id, e] of sessions) {
      if (now - e.lastSeen > opts.sessionTtlMs) {
        log.info("session_expired", { sessionId: id, kind: e.kind });
        if (e.kind === "legacy" && e.heartbeat) clearInterval(e.heartbeat);
        void e.transport.close().catch(() => {});
        rateBuckets.delete(id);
        sessions.delete(id);
      }
    }
  }, opts.sessionSweepMs);
  sweeper.unref?.();

  // —— 监听：bind 失败 2 秒内 exit 2（§2.3/D10，不换端口不重试）——
  return new Promise<HttpTransportHandles>((resolve) => {
    const failTimer = setTimeout(() => {
      log.error("http_bind_failed", {
        host: opts.host,
        port: opts.port,
        code: "EBINDTIMEOUT",
        message: "bind did not complete within 2s",
      });
      process.exit(2);
    }, 2000);
    failTimer.unref?.();
    server.once("error", (err: NodeJS.ErrnoException) => {
      clearTimeout(failTimer);
      log.error("http_bind_failed", {
        host: opts.host,
        port: opts.port,
        code: err.code ?? "EADDRINUSE",
        message: err.message,
      });
      process.exit(2);
    });
    server.listen(opts.port, opts.host, () => {
      clearTimeout(failTimer);
      const addr = server.address() as { port: number };
      log.info("http_listening", { host: opts.host, port: addr.port });
      resolve({
        app,
        server,
        sessionCount: () => sessions.size,
        close: async () => {
          clearInterval(sweeper);
          for (const [, e] of sessions) {
            if (e.kind === "legacy" && e.heartbeat) clearInterval(e.heartbeat);
            await e.transport.close().catch(() => {});
          }
          sessions.clear();
          await new Promise<void>((r) => server.close(() => r()));
        },
      });
    });
  });
}

function isJsonObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isInitialize(body: unknown): boolean {
  return isJsonObject(body) && body.method === "initialize";
}

function safeEqual(a: string, b: string): boolean {
  const ha = Buffer.from(a, "utf8");
  const hb = Buffer.from(b, "utf8");
  if (ha.length !== hb.length) {
    timingSafeEqual(ha, ha); // 稳定比较时间
    return false;
  }
  return timingSafeEqual(ha, hb);
}

export function sendRpcError(
  res: Response,
  httpStatus: number,
  jsonRpcCode: number,
  errorCode: string,
  message: string,
  extraData?: Record<string, unknown>,
): void {
  if (res.headersSent) {
    res.destroy();
    return;
  }
  res.status(httpStatus).json({
    jsonrpc: "2.0",
    id: null,
    error: {
      code: jsonRpcCode,
      message,
      data: { errorCode, ...(extraData ?? {}) },
    },
  });
}
