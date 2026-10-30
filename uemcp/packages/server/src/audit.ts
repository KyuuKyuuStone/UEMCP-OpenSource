/**
 * 审计日志（§6.5）：~/.uemcp/audit/YYYY-MM-DD.jsonl，JSON Lines。
 * - 永不记录 token / 完整 Python 源码（仅 codeSha256 与 codeLength）/ base64（§6.5 红线）。
 * - 写入失败不阻塞工具调用；连续 3 次失败 → auditDegraded。
 * - 按天轮转；启动时清理 30 天前的文件。
 */
import { mkdir, readdir, unlink, open } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { createHash } from "node:crypto";
import type { AuditRecord } from "@uemcp/shared";
import type { Logger } from "./logger.js";

const RETENTION_DAYS = 30;

export class Audit {
  private dir: string;
  private log: Logger;
  private consecutiveFailures = 0;

  constructor(log: Logger, dirOverride?: string) {
    this.dir = dirOverride ?? join(homedir(), ".uemcp", "audit");
    this.log = log;
  }

  get degraded(): boolean {
    return this.consecutiveFailures >= 3;
  }

  async init(): Promise<void> {
    try {
      // 0o700：目录仅属主可进入（POSIX 生效；Windows 忽略）
      await mkdir(this.dir, { recursive: true, mode: 0o700 });
      await this.cleanup();
    } catch (err) {
      this.log.warn("audit_init_failed", { error: String(err) });
    }
  }

  private async cleanup(): Promise<void> {
    if (!existsSync(this.dir)) return;
    const cutoff = new Date(Date.now() - RETENTION_DAYS * 24 * 3600 * 1000);
    let files: string[];
    try {
      files = await readdir(this.dir);
    } catch {
      return;
    }
    for (const f of files) {
      const m = /^(\d{4}-\d{2}-\d{2})\.jsonl$/.exec(f);
      if (!m) continue;
      const d = new Date(m[1]! + "T00:00:00Z");
      if (!Number.isNaN(d.getTime()) && d < cutoff) {
        await unlink(join(this.dir, f)).catch(() => {});
      }
    }
  }

  async record(rec: AuditRecord): Promise<void> {
    const file = join(this.dir, `${new Date().toISOString().slice(0, 10)}.jsonl`);
    try {
      await mkdir(this.dir, { recursive: true, mode: 0o700 });
      // 0600：文件创建时生效（§6.5 红线；Windows 下记录为 ACL 近似）
      const fh = await open(file, "a", 0o600);
      try {
        await fh.write(JSON.stringify(rec) + "\n");
      } finally {
        await fh.close();
      }
      this.consecutiveFailures = 0;
    } catch (err) {
      this.consecutiveFailures++;
      this.log.warn("audit_write_failed", {
        consecutiveFailures: this.consecutiveFailures,
        error: String(err),
      });
    }
  }
}

/** 参数摘要（脱敏规则 §6.5）：按工具生成摘要而非原文；Python 永远只记 hash 与长度。 */
export function summarizeArgs(
  tool: string,
  args: Record<string, unknown>,
): Record<string, unknown> {
  const summary: Record<string, unknown> = {};
  switch (tool) {
    case "ue_actor_edit": {
      const ops = (args.operations as Array<Record<string, unknown>>) ?? [];
      summary.operationCount = ops.length;
      summary.ops = ops.map((o) => o.op);
      summary.dryRun = args.dryRun === true;
      break;
    }
    case "ue_level_control":
      summary.action = args.action;
      summary.levelPath = args.levelPath;
      summary.allowDiscardUnsaved = args.allowDiscardUnsaved === true;
      summary.confirm = args.confirm === true;
      break;
    case "ue_material_params":
      summary.action = args.action;
      summary.materialPath = args.materialPath;
      summary.instancePath = args.instancePath;
      summary.parameterCount = Array.isArray(args.parameters) ? args.parameters.length : 0;
      summary.save = args.save === true;
      break;
    case "ue_blueprint":
      summary.action = args.action;
      summary.blueprintPath = args.blueprintPath;
      summary.save = args.save === true;
      break;
    case "ue_console_command":
      // §6.5：控制台记录完整命令（可在配置中关闭 hash；MVP 记全文，不含敏感数据）
      summary.command = args.command;
      summary.worldContext = args.worldContext;
      break;
    case "ue_python_exec": {
      const code = typeof args.code === "string" ? args.code : "";
      summary.codeSha256 = sha256Hex(code);
      summary.codeLength = code.length;
      summary.mode = args.mode;
      break;
    }
    case "ue_pie_control":
      summary.action = args.action;
      summary.waitReadyMs = args.waitReadyMs;
      summary.simulate = args.simulate === true;
      break;
    case "ue_viewport_capture":
      summary.target = args.target;
      summary.returnMode = args.returnMode;
      summary.width = args.width;
      summary.height = args.height;
      break;
    default:
      summary.keys = Object.keys(args);
      break;
  }
  return summary;
}

function sha256Hex(s: string): string {
  return createHash("sha256").update(s, "utf8").digest("hex");
}
