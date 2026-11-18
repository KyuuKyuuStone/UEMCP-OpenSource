/**
 * 轻量 JSON logger（§3.2/§7.3）——stderr + 可选文件双写。
 * stdio 模式下 stdout 只允许 MCP 帧，日志走 stderr；
 * 文件日志（主管要求）：logs/server-YYYY-MM-DD.log，按天切换。
 * 同步追加（量小），写入失败静默（日志失败不崩服务）。
 */
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

type Level = "debug" | "info" | "warn" | "error";

export interface Logger {
  debug(event: string, fields?: Record<string, unknown>): void;
  info(event: string, fields?: Record<string, unknown>): void;
  warn(event: string, fields?: Record<string, unknown>): void;
  error(event: string, fields?: Record<string, unknown>): void;
  /** 当前日志文件路径（/health 的 logPath 用） */
  file(): string | undefined;
}

export function createLogger(minLevel: Level = "info", logDir?: string): Logger {
  const order: Record<Level, number> = { debug: 0, info: 1, warn: 2, error: 3 };
  let cachedFile: string | undefined;
  if (logDir) {
    try {
      mkdirSync(logDir, { recursive: true });
    } catch {
      /* 目录创建失败：仅 stderr */
    }
  }
  const today = () => new Date().toISOString().slice(0, 10);
  const write = (level: Level, event: string, fields?: Record<string, unknown>) => {
    const line = JSON.stringify({ level, event, ts: new Date().toISOString(), ...fields });
    process.stderr.write(line + "\n");
    if (!logDir) return;
    try {
      const f = join(logDir, `server-${today()}.log`);
      appendFileSync(f, line + "\n", "utf8");
      cachedFile = f;
    } catch {
      /* 文件写入失败不阻塞 */
    }
  };
  return {
    debug: (e, f) => {
      if (order.debug >= order[minLevel]) write("debug", e, f);
    },
    info: (e, f) => {
      if (order.info >= order[minLevel]) write("info", e, f);
    },
    warn: (e, f) => {
      if (order.warn >= order[minLevel]) write("warn", e, f);
    },
    error: (e, f) => {
      if (order.error >= order[minLevel]) write("error", e, f);
    },
    file: () => cachedFile,
  };
}

/** 默认日志目录：<uemcp 包根>/logs（由 dist/index.js 位置推导），UEMCP_LOG_DIR 可覆盖 */
export function defaultLogDir(): string {
  if (process.env.UEMCP_LOG_DIR) return process.env.UEMCP_LOG_DIR;
  try {
    // dist/index.js → packages/server/dist → packages/server → packages → <uemcp 根>
    const here = new URL(".", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
    return join(here, "..", "..", "..", "logs");
  } catch {
    return join(process.cwd(), "logs");
  }
}
