/**
 * Bridge 发现（§2.4）：解析顺序与校验规则。
 * 来源：1) --bridge-url/UEMCP_BRIDGE_URL；2) --project → bridges/<hash>.json；
 *       3) ~/.uemcp/bridge.json；4) http://127.0.0.1:18778 + UEMCP_BRIDGE_TOKEN。
 * 校验：结构合法 + schemaVersion===1 + pid 存活 + GET /health 校验 app/pid/startedAt；
 *       任一失败视为陈旧，转向下一来源；全部失败 → null（调用侧 BRIDGE_UNAVAILABLE）。
 * Critical-2：显式 --project 时硬失败（禁止回退到 bridge.json/默认端口）；
 *             路径规范化（斜杠统一/去尾）hash 与比较共用，比较大小写不敏感（Windows）。
 */
import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import type { BridgeDiscoveryFile } from "@uemcp/shared";
import type { Logger } from "../logger.js";
import { DEFAULT_BRIDGE_PORT } from "../config.js";

export interface ResolvedBridge {
  url: string;
  token?: string;
  discovery?: BridgeDiscoveryFile;
  source: string;
}

/** 目录规范化（§2.4）：统一 /、去尾斜杠；hash 与比较共用 */
export function normalizeProjectDir(dir: string): string {
  return dir.replaceAll("\\", "/").replace(/\/+$/, "");
}

/**
 * 比较按平台语义（N-3）：win32 大小写不敏感（NTFS 默认），POSIX 大小写敏感
 * （大小写敏感 FS 上仅大小写不同的两个目录是两个工程，宽松比较会错选桥接；
 * 保守方向的误差是「发现失败报 BRIDGE_UNAVAILABLE」而非「连错编辑器」）。
 * platform 参数化以便单元测试覆盖两种分支（真实分支由运行时 platform 决定）。
 */
export function equalProjectDirOn(
  platform: NodeJS.Platform,
  a: string,
  b: string,
): boolean {
  const na = normalizeProjectDir(a);
  const nb = normalizeProjectDir(b);
  return platform === "win32" ? na.toLowerCase() === nb.toLowerCase() : na === nb;
}

function equalProjectDir(a: string, b: string): boolean {
  return equalProjectDirOn(process.platform, a, b);
}

/** 发现文件名 hash：路径规范化后 sha1 前 16 位（斜杠/尾斜杠差异不影响） */
export function projectHash(dir: string): string {
  return createHash("sha1").update(normalizeProjectDir(dir), "utf8").digest("hex").slice(0, 16);
}

function pidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    // Windows: EPERM 表示进程存在但无权限；ESRCH 表示不存在
    const code = (err as NodeJS.ErrnoException).code;
    return code === "EPERM";
  }
}

function validStructure(f: unknown): f is BridgeDiscoveryFile {
  if (typeof f !== "object" || f === null) return false;
  const o = f as Record<string, unknown>;
  return (
    o.schemaVersion === 1 &&
    typeof o.pid === "number" &&
    typeof o.url === "string" &&
    typeof o.startedAt === "string" &&
    typeof o.token === "string" &&
    typeof o.host === "string" &&
    typeof o.port === "number"
  );
}

async function readJson(file: string): Promise<unknown> {
  try {
    return JSON.parse(await readFile(file, "utf8"));
  } catch {
    return null;
  }
}

/** GET <url>/health，校验 app=uemcp-bridge 且 pid/startedAt 与文件一致（§2.4） */
async function healthCheck(
  url: string,
  f?: BridgeDiscoveryFile,
): Promise<boolean> {
  try {
    const res = await fetch(url + "/health", {
      signal: AbortSignal.timeout(2000),
    });
    if (!res.ok) return false;
    const body = (await res.json()) as Record<string, unknown>;
    if (body.app !== "uemcp-bridge" || body.ok !== true) return false;
    if (f) {
      if (typeof body.pid === "number" && body.pid !== f.pid) return false;
      if (typeof body.startedAt === "string" && body.startedAt !== f.startedAt)
        return false;
    }
    return true;
  } catch {
    return false;
  }
}

export interface DiscoveryOptions {
  bridgeUrl?: string;
  bridgeToken?: string;
  projectDir?: string;
}

export async function resolveBridge(
  opts: DiscoveryOptions,
  log: Logger,
): Promise<ResolvedBridge | null> {
  const home = homedir();

  // 来源 1：显式 URL
  if (opts.bridgeUrl) {
    const url = opts.bridgeUrl.replace(/\/+$/, "");
    if (await healthCheck(url)) {
      return { url, token: opts.bridgeToken, source: "bridge-url" };
    }
    log.warn("bridge_url_unreachable", { url });
  }

  // 来源 2：--project → bridges/<hash>.json（显式指定工程时硬失败，禁止回退到 bridge.json/默认端口）
  if (opts.projectDir) {
    const bridgesDir = join(home, ".uemcp", "bridges");
    const hashFile = join(bridgesDir, `${projectHash(opts.projectDir)}.json`);
    const hashRaw = await readJson(hashFile);
    let raw: BridgeDiscoveryFile | null = validStructure(hashRaw) ? hashRaw : null;
    let matchedBy = "project-hash";
    if (!validStructure(raw) || !equalProjectDir(raw.projectDir, opts.projectDir)) {
      // hash 文件未命中（如大小写差异导致 hash 不同）→ 扫描目录按 projectDir 内容匹配
      raw = null;
      try {
        const files = await readdir(bridgesDir);
        for (const f of files) {
          if (!f.endsWith(".json")) continue;
          const cand = await readJson(join(bridgesDir, f));
          if (validStructure(cand) && equalProjectDir(cand.projectDir, opts.projectDir)) {
            raw = cand;
            matchedBy = "project-scan";
            break;
          }
        }
      } catch {
        /* 目录不存在或不可读 */
      }
    }
    if (!raw) {
      log.warn("bridge_discovery_project_failed", {
        file: hashFile,
        reason: "no-matching-project-bridge",
      });
      return null;
    }
    if (!pidAlive(raw.pid)) {
      log.warn("bridge_discovery_stale_pid", { file: hashFile, pid: raw.pid });
      return null;
    }
    if (!(await healthCheck(raw.url, raw))) {
      log.warn("bridge_discovery_health_failed", { file: hashFile, url: raw.url });
      return null;
    }
    return { url: raw.url, token: raw.token, discovery: raw, source: matchedBy };
  }

  // 来源 3：~/.uemcp/bridge.json（未指定 --project 时才使用）
  const bridgeJsonFile = join(home, ".uemcp", "bridge.json");
  {
    const raw = await readJson(bridgeJsonFile);
    if (validStructure(raw)) {
      if (!pidAlive(raw.pid)) {
        log.warn("bridge_discovery_stale_pid", { file: bridgeJsonFile, pid: raw.pid });
      } else if (!(await healthCheck(raw.url, raw))) {
        log.warn("bridge_discovery_health_failed", { file: bridgeJsonFile, url: raw.url });
      } else {
        return { url: raw.url, token: raw.token, discovery: raw, source: "bridge-json" };
      }
    } else {
      log.warn("bridge_discovery_invalid", { file: bridgeJsonFile });
    }
  }

  // 来源 4：默认端口 + env token
  const url = `http://127.0.0.1:${process.env.UEMCP_BRIDGE_PORT ? Number(process.env.UEMCP_BRIDGE_PORT) : DEFAULT_BRIDGE_PORT}`;
  if (await healthCheck(url)) {
    return { url, token: opts.bridgeToken, source: "default-port" };
  }

  return null;
}
