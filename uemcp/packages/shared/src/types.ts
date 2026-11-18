import type { ToolErrorCode } from "./errors.js";

/** 架构文档 §10.1 关键类型 */
export type PolicyMode = "read-only" | "standard" | "full";

/** 策略来源（B-3.9 policySnapshot.ts.source）：CLI 参数 > 环境变量 > 默认 read-only */
export type PolicySource = "cli" | "env" | "default";

export interface ToolMeta {
  requestId: string;
  durationMs: number;
  ueVersion?: string;
  pluginVersion?: string;
}

export interface ToolErrorShape {
  code: ToolErrorCode;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown>;
}

export interface ToolOk<T> {
  ok: true;
  data: T;
  warnings: string[];
  meta: ToolMeta;
}

export interface ToolErr {
  ok: false;
  error: ToolErrorShape;
  meta: ToolMeta;
}

export type ToolResult<T> = ToolOk<T> | ToolErr;

/** 桥接 RPC 成功响应（§2.8） */
export interface BridgeRpcOk<T = unknown> {
  ok: true;
  data: T;
  warnings: string[];
  meta: Record<string, unknown>;
}

/** 桥接发现文件（§2.4） */
export interface BridgeDiscoveryFile {
  schemaVersion: number;
  pid: number;
  projectDir: string;
  projectFile: string;
  host: string;
  port: number;
  url: string;
  token: string;
  ueVersion: string;
  pluginVersion: string;
  bridgeProtocol: number;
  capabilities: {
    python: boolean;
    screenshot: boolean;
    blueprintRead: boolean;
    blueprintNodeRead: boolean;
    blueprintCompile: boolean;
    animBlueprintEdit: boolean;
    assetRegistry: boolean;
    console: boolean;
    /** 桥接并行新增能力位（B-3.3）；旧桥接缺失时容忍，TS 预检优雅跳过 */
    pixelStreaming?: boolean;
  };
  startedAt: string;
  /** B-3.9：桥接自标记陈旧（如编辑器已退出）；TS 发现时尊重，拒绝采用 */
  stale?: boolean;
  staleReason?: string;
  staleAt?: string;
}

/** 审计记录（§6.5） */
export interface AuditRecord {
  ts: string;
  requestId: string;
  sessionId?: string;
  client?: { name: string; version?: string };
  transport?: string;
  tool: string;
  rpcMethod: string;
  policyMode: PolicyMode;
  decision: "allowed" | "denied";
  confirmationMode?: "elicitation" | "policy" | "none";
  confirmationSwitch?: string;
  argsSummary: Record<string, unknown>;
  durationMs: number;
  ok: boolean;
  errorCode: string | null;
  ueVersion?: string;
  pluginVersion?: string;
  /** B-3.1 构建身份四字段：仅当看门狗已连接且 /health 实际返回时记录，断连/缺失不伪造 */
  instanceId?: string;
  buildHash?: string;
  buildTime?: string;
  sourcePath?: string;
  /** B-3.9：看门狗保留的 /health schemaVersion（缺失时回退发现文件值；断连不记录） */
  schemaVersion?: number;
  /** B-3.7：PYTHON_ERROR details 的 origin/stage 关键字段（容忍缺失；不记录 details 全文） */
  origin?: string;
  stage?: string;
  /** B-3.9 策略快照：ts 侧生效策略＋来源；bridge 侧按 /health 收到的键原样记录、不伪造 */
  policySnapshot?: {
    ts: {
      mode: PolicyMode;
      source?: PolicySource;
      allowWrite: boolean;
      allowConsole: boolean;
      allowExec: boolean;
      allowDestructive: boolean;
    };
    bridge?: {
      policies?: Record<string, unknown>;
      rateLimit?: Record<string, unknown>;
    };
  };
}
