/**
 * server 包内部单元测试（node:test，零依赖）。
 * 被测对象：packages/server/dist/internal.js（测试专用导出，tsup 独立入口）。
 * 覆盖（任务 4248c955）：
 *  - N-2：审计目录/文件权限（mkdir mode 0o700 / open 0o600，POSIX 生效，Windows 跳过 mode 断言）
 *  - N-3：equalProjectDirOn 平台语义（win32 不敏感 / POSIX 敏感）与 projectHash 规范化
 *  - B  ：narrowedActions 与 shared READ_ONLY_* 常量单一来源、isToolVisible/toolDisabledGate 口径
 */
import { test, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, statSync, readdirSync, rmSync } from "node:fs";
import http from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  Audit,
  auditCall,
  acceptDiscovery,
  resolveBridge,
  BridgeWatchdog,
  loadConfig,
  summarizeArgs,
  viewportCaptureTool,
  pythonExecTool,
  equalProjectDirOn,
  normalizeProjectDir,
  projectHash,
  isToolVisible,
  narrowedActions,
  toolDisabledGate,
} from "../packages/server/dist/internal.js";
import {
  READ_ONLY_LEVEL_ACTIONS,
  READ_ONLY_MATERIAL_ACTIONS,
  READ_ONLY_BLUEPRINT_ACTIONS,
} from "../packages/shared/dist/index.js";

const IS_WIN = process.platform === "win32";

function nullLogger() {
  return { debug() {}, info() {}, warn() {}, error() {}, file: () => undefined };
}

const RO = { mode: "read-only", allowDestructive: false, allowConsole: false, allowExec: false };
const STD = { mode: "standard", allowDestructive: false, allowConsole: false, allowExec: false };
const FULL = { mode: "full", allowDestructive: true, allowConsole: true, allowExec: true };

// ---------- N-2：审计目录/文件权限 ----------

const auditHomes = [];

test("audit N-2: init+record create jsonl under override dir; POSIX mode 0700/0600", async () => {
  const home = mkdtempSync(join(tmpdir(), "uemcp-audit-"));
  auditHomes.push(home);
  const dir = join(home, "audit");
  const audit = new Audit(nullLogger(), dir);
  await audit.init();
  await audit.record({
    ts: new Date().toISOString(),
    requestId: "req_n2",
    tool: "ue_editor_status",
    rpcMethod: "editor.status",
    policyMode: "read-only",
    decision: "allowed",
    argsSummary: {},
    durationMs: 1,
    ok: true,
    errorCode: null,
  });
  assert.ok(existsSync(dir), "audit dir must be created");
  const files = readdirSync(dir);
  assert.ok(files.length === 1 && files[0].endsWith(".jsonl"), `exactly one jsonl expected, got ${files.join(",")}`);
  if (!IS_WIN) {
    const dirMode = statSync(dir).mode & 0o777;
    const fileMode = statSync(join(dir, files[0])).mode & 0o777;
    assert.equal(dirMode, 0o700, `audit dir mode must be 0700, got ${dirMode.toString(8)}`);
    assert.equal(fileMode, 0o600, `audit file mode must be 0600, got ${fileMode.toString(8)}`);
  } else {
    // Windows 忽略 mode（ACL 近似，§6.5 记录在案）：仅验证目录/文件落盘
    assert.equal(statSync(dir).isDirectory(), true);
  }
});

after(() => {
  for (const h of auditHomes) {
    try {
      rmSync(h, { recursive: true, force: true });
    } catch { /* best effort */ }
  }
});

// ---------- N-3：工程目录比较的平台语义 ----------

test("discovery N-3: win32 compare is case-insensitive with slash/trailing normalization", () => {
  assert.equal(equalProjectDirOn("win32", "C:\\A\\B", "c:/a/b"), true);
  assert.equal(equalProjectDirOn("win32", "C:/A/B/", "C:/A/B"), true);
  assert.equal(equalProjectDirOn("win32", "C:/A/B", "C:/A/C"), false);
});

test("discovery N-3: POSIX compare is case-sensitive (distinct dirs are distinct projects)", () => {
  assert.equal(equalProjectDirOn("linux", "/a/b", "/a/b"), true);
  assert.equal(equalProjectDirOn("linux", "/a/B", "/a/b"), false, "case-sensitive FS must not merge two projects differing by case");
  assert.equal(equalProjectDirOn("linux", "/a/b/", "/a/b"), true, "trailing slash normalization still applies on POSIX");
});

test("discovery N-3: normalizeProjectDir unifies backslashes and trailing slashes; projectHash is normalization-stable", () => {
  assert.equal(normalizeProjectDir("C:\\A\\B\\"), "C:/A/B");
  assert.equal(normalizeProjectDir("/a/b//"), "/a/b");
  assert.equal(projectHash("C:\\A\\B\\"), projectHash("C:/A/B"), "hash must match across slash styles");
  assert.match(projectHash("C:/A/B"), /^[0-9a-f]{16}$/);
});

// ---------- B：策略口径单一来源与一致性 ----------

test("policy B: narrowedActions is exactly the shared READ_ONLY_* constants (single source)", () => {
  assert.deepEqual([...(narrowedActions("ue_level_control", RO) ?? [])].sort(), [...READ_ONLY_LEVEL_ACTIONS].sort());
  assert.deepEqual([...(narrowedActions("ue_material_params", RO) ?? [])].sort(), [...READ_ONLY_MATERIAL_ACTIONS].sort());
  assert.deepEqual([...(narrowedActions("ue_blueprint", RO) ?? [])].sort(), [...READ_ONLY_BLUEPRINT_ACTIONS].sort());
  assert.equal(narrowedActions("ue_actor_query", RO), undefined, "P0 tools are not narrowed");
  assert.equal(narrowedActions("ue_level_control", STD), undefined, "narrowing only applies under read-only");
});

test("policy B: isToolVisible/toolDisabledGate stay consistent (P1 gate=server.policy, P2 gate=own switch)", () => {
  // read-only：P1 不注册，直调 gate=server.policy；混合工具恒注册
  assert.equal(isToolVisible("ue_actor_edit", RO), false);
  assert.equal(isToolVisible("ue_level_control", RO), true);
  assert.equal(isToolVisible("ue_blueprint", RO), true);
  // standard：P1 注册，P2 仍隐藏
  assert.equal(isToolVisible("ue_actor_edit", STD), true);
  assert.equal(isToolVisible("ue_python_exec", STD), false);
  assert.equal(isToolVisible("ue_console_command", STD), false);
  // full + 开关：P2 注册；gate 固定为对应开关（SEC-01(c)）
  assert.equal(isToolVisible("ue_python_exec", FULL), true);
  assert.equal(isToolVisible("ue_console_command", FULL), true);
  assert.equal(toolDisabledGate("ue_python_exec", FULL), "server.allowExec");
  assert.equal(toolDisabledGate("ue_console_command", FULL), "server.allowConsole");
  for (const p of [RO, STD, FULL]) {
    assert.equal(toolDisabledGate("ue_actor_edit", p), "server.policy", "P1 gate must be server.policy in every mode");
  }
});

// ---------- tsfix（f72451d4）：B1/B4 看门狗 /health 保留与断连降级 ----------

function tsfixLogger() {
  const warns = [];
  return {
    log: { debug() {}, info() {}, warn: (m, d) => warns.push({ m, d }), error() {}, file: () => undefined },
    warns,
  };
}

async function tsfixHealthServer(body) {
  const srv = http.createServer((_req, res) => {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(body));
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  return { srv, url: `http://127.0.0.1:${srv.address().port}` };
}

function tsfixFakeClient(url, discovery = { schemaVersion: 1 }) {
  const cached = { url, token: "t", source: "test", discovery };
  return { getCached: () => cached, ensureDiscovered: async () => cached, invalidate() {} };
}

async function tsfixWaitState(wd, pred, ms = 3000) {
  const t0 = Date.now();
  while (!pred(wd.state) && Date.now() - t0 < ms) await new Promise((r) => setTimeout(r, 50));
  return pred(wd.state);
}

test("tsfix B1: watchdog retains /health build identity + capabilities/policies/rateLimit/protocol/schemaVersion", async () => {
  const body = {
    app: "uemcp-bridge", ok: true, ueVersion: "5.4.4", pluginVersion: "0.1.5",
    projectDir: "C:/MockProject", startedAt: "2026-11-18T00:00:00Z", pid: 4321,
    instanceId: "inst-tsfix", buildHash: "a".repeat(64), buildTime: "2026-11-18T00:00:00Z",
    sourcePath: "C:/MockProject/UEMCPBridge", bridgeProtocol: 1, schemaVersion: 1,
    capabilities: { pixelStreaming: true }, rateLimit: { rpcPerMinute: 600 },
    policies: { allowWrite: true, allowExec: false, allowConsole: false },
  };
  const { srv, url } = await tsfixHealthServer(body);
  const wd = new BridgeWatchdog(tsfixFakeClient(url, { schemaVersion: 1, pid: 4321, startedAt: body.startedAt }), nullLogger());
  try {
    wd.start();
    assert.ok(await tsfixWaitState(wd, (s) => s.connected), "watchdog must connect to a healthy /health");
    assert.equal(wd.state.instanceId, "inst-tsfix");
    assert.equal(wd.state.buildHash, "a".repeat(64));
    assert.equal(wd.state.buildTime, body.buildTime);
    assert.equal(wd.state.sourcePath, body.sourcePath);
    assert.equal(wd.state.bridgeProtocol, 1);
    assert.equal(wd.state.schemaVersion, 1);
    assert.deepEqual(wd.state.capabilities, { pixelStreaming: true });
    assert.deepEqual(wd.state.rateLimit, { rpcPerMinute: 600 });
    assert.deepEqual(wd.state.policies, body.policies);
  } finally {
    wd.stop();
    srv.close();
  }
});

test("tsfix B1/B9: minimal /health (new fields absent) tolerated — connected, new fields undefined", async () => {
  const { srv, url } = await tsfixHealthServer({ app: "uemcp-bridge", ok: true });
  const wd = new BridgeWatchdog(tsfixFakeClient(url), nullLogger());
  try {
    wd.start();
    assert.ok(await tsfixWaitState(wd, (s) => s.connected));
    for (const k of ["instanceId", "buildHash", "buildTime", "sourcePath", "capabilities", "rateLimit", "policies", "bridgeProtocol", "schemaVersion"]) {
      assert.equal(wd.state[k], undefined, `${k} must stay undefined when /health omits it (transition tolerance)`);
    }
  } finally {
    wd.stop();
    srv.close();
  }
});

test("tsfix B4: disconnect clears every retained field (state === {connected:false}, invalidate called)", async () => {
  let invalidated = 0;
  const cached = { url: "http://127.0.0.1:1", token: "t", source: "test", discovery: { schemaVersion: 1 } };
  const client = { getCached: () => cached, ensureDiscovered: async () => cached, invalidate() { invalidated++; } };
  const wd = new BridgeWatchdog(client, nullLogger());
  wd.state = {
    connected: true, url: cached.url, instanceId: "old", buildHash: "old", buildTime: "old", sourcePath: "old",
    capabilities: { pixelStreaming: true }, policies: { allowWrite: true }, rateLimit: { rpcPerMinute: 600 },
    bridgeProtocol: 1, schemaVersion: 1,
  };
  try {
    wd.start();
    assert.ok(await tsfixWaitState(wd, (s) => !s.connected), "probe failure must mark down");
    assert.deepEqual(wd.state, { connected: false }, "B4: no stale field may survive a disconnect");
    assert.equal(invalidated, 1);
  } finally {
    wd.stop();
  }
});

// ---------- tsfix B-3.1/3.7/3.9：auditCall 新字段（构建身份/origin/stage/策略快照/schemaVersion/client） ----------

function tsfixAuditCtx(wstate, opts = {}) {
  const records = [];
  const ctx = {
    policy: { mode: "full", source: "cli", allowDestructive: true, allowConsole: true, allowExec: true },
    bridge: {
      getCached: () => opts.cached ?? null,
      ensureDiscovered: async () => opts.cached ?? null,
      invalidate() {},
      call: async () => ({ ok: true, data: {}, warnings: [] }),
    },
    watchdog: { state: wstate },
    audit: { record: async (r) => { records.push(r); }, degraded: false },
    log: nullLogger(),
    transport: "http",
    sessionId: "sess-tsfix",
    clientInfo: { name: "code-test", version: "0" },
    elicit: async () => "unsupported",
  };
  return { ctx, records };
}

const TSFIX_BUILD_STATE = {
  connected: true, url: "http://127.0.0.1:18778",
  instanceId: "i-tsfix", buildHash: "b".repeat(64), buildTime: "2026-11-18T01:00:00Z", sourcePath: "C:/P/UEMCPBridge",
  schemaVersion: 1, bridgeProtocol: 1,
  capabilities: { pixelStreaming: true },
  policies: { allowWrite: true, allowExec: false }, rateLimit: { rpcPerMinute: 600 },
};

const TSFIX_AUDIT_ARGS = {
  tool: "ue_python_exec", rpcMethod: "python.exec", requestId: "req_tsfix", durationMs: 5,
  ok: false, errorCode: "PYTHON_ERROR", decision: "allowed",
  argsSummary: { codeSha256: "c".repeat(64), codeLength: 4, mode: "exec" },
  errorDetails: { origin: "bridge", stage: "python_exec", traceback: "SECRET-FULL-TEXT" },
};

test("tsfix audit: connected → build identity + schemaVersion + policySnapshot(ts+bridge) + origin/stage + client/session/transport", async () => {
  const cached = { url: "http://127.0.0.1:18778", token: "SECRET-TOKEN", source: "bridge-json", discovery: { schemaVersion: 1 } };
  const { ctx, records } = tsfixAuditCtx({ ...TSFIX_BUILD_STATE }, { cached });
  await auditCall(ctx, TSFIX_AUDIT_ARGS);
  assert.equal(records.length, 1);
  const r = records[0];
  assert.equal(r.instanceId, "i-tsfix");
  assert.equal(r.buildHash, "b".repeat(64));
  assert.equal(r.buildTime, TSFIX_BUILD_STATE.buildTime);
  assert.equal(r.sourcePath, TSFIX_BUILD_STATE.sourcePath);
  assert.equal(r.schemaVersion, 1);
  assert.equal(r.origin, "bridge");
  assert.equal(r.stage, "python_exec");
  assert.equal(r.policyMode, "full");
  assert.equal(r.transport, "http");
  assert.equal(r.sessionId, "sess-tsfix");
  assert.deepEqual(r.client, { name: "code-test", version: "0" });
  assert.deepEqual(r.policySnapshot.ts, { mode: "full", source: "cli", allowWrite: true, allowConsole: true, allowExec: true, allowDestructive: true });
  assert.deepEqual(r.policySnapshot.bridge, { policies: { allowWrite: true, allowExec: false }, rateLimit: { rpcPerMinute: 600 } });
  const s = JSON.stringify(r);
  assert.ok(!s.includes("SECRET-FULL-TEXT"), "privacy: errorDetails full text must never enter the audit record");
  assert.ok(!s.includes("SECRET-TOKEN"), "privacy: bridge token must never enter the audit record");
  assert.ok(!("errorDetails" in r) && !("details" in r), "details object itself must not be recorded");
});

test("tsfix audit: disconnected → no build/schemaVersion/bridge snapshot; origin/stage still recorded from details", async () => {
  const { ctx, records } = tsfixAuditCtx({ connected: false });
  await auditCall(ctx, TSFIX_AUDIT_ARGS);
  const r = records[0];
  for (const k of ["instanceId", "buildHash", "buildTime", "sourcePath", "schemaVersion"]) {
    assert.ok(!(k in r), `${k} must be absent when disconnected (no stale impersonation)`);
  }
  assert.equal(r.policySnapshot.bridge, undefined);
  assert.deepEqual(r.policySnapshot.ts, { mode: "full", source: "cli", allowWrite: true, allowConsole: true, allowExec: true, allowDestructive: true });
  assert.equal(r.origin, "bridge");
  assert.equal(r.stage, "python_exec");
});

test("tsfix audit: m-2 phase fallback → stage; schemaVersion falls back to cached discovery when /health omits it", async () => {
  const cached = { url: "http://127.0.0.1:18778", source: "bridge-json", discovery: { schemaVersion: 1 } };
  const { ctx, records } = tsfixAuditCtx({ connected: true, url: cached.url }, { cached });
  await auditCall(ctx, { ...TSFIX_AUDIT_ARGS, errorCode: "BRIDGE_TIMEOUT", errorDetails: { timeoutMs: 1000, phase: "game_thread" } });
  const r = records[0];
  assert.equal(r.stage, "game_thread", "BRIDGE_TIMEOUT details.phase must map to stage");
  assert.ok(!("origin" in r), "origin absent when details carry no origin");
  assert.equal(r.schemaVersion, 1, "schemaVersion must fall back to cached discovery while connected");
});

// ---------- tsfix B9：discovery schemaVersion 硬门 + stale 尊重 ----------

const TSFIX_VALID_DISCOVERY = {
  schemaVersion: 1, pid: process.pid, url: "http://127.0.0.1:18778",
  startedAt: "2026-11-18T00:00:00Z", token: "t", host: "127.0.0.1", port: 18778,
};

test("tsfix B9: acceptDiscovery schemaVersion===1 accepted silently; mismatch rejected with expected/actual warn", () => {
  const okLog = tsfixLogger();
  assert.equal(acceptDiscovery({ ...TSFIX_VALID_DISCOVERY }, "ok.json", okLog.log), true);
  assert.equal(okLog.warns.length, 0);
  const badLog = tsfixLogger();
  assert.equal(acceptDiscovery({ schemaVersion: 2 }, "bad.json", badLog.log), false);
  assert.equal(badLog.warns.length, 1);
  assert.equal(badLog.warns[0].m, "bridge_discovery_schema_version");
  assert.equal(badLog.warns[0].d.expected, 1);
  assert.equal(badLog.warns[0].d.actual, 2);
  assert.equal(badLog.warns[0].d.file, "bad.json");
});

test("tsfix B9: stale:true discovery respected (rejected + bridge_discovery_stale warn)", () => {
  const { log, warns } = tsfixLogger();
  const raw = { ...TSFIX_VALID_DISCOVERY, stale: true, staleReason: "editor-exited", staleAt: "2026-11-18T02:00:00Z" };
  assert.equal(acceptDiscovery(raw, "stale.json", log), false);
  assert.equal(warns.length, 1);
  assert.equal(warns[0].m, "bridge_discovery_stale");
  assert.equal(warns[0].d.staleReason, "editor-exited");
  assert.equal(warns[0].d.staleAt, "2026-11-18T02:00:00Z");
});

test("tsfix B9: resolveBridge rejects stale discovery end-to-end (temp HOME, no live bridge)", async () => {
  const home = mkdtempSync(join(tmpdir(), "uemcp-tsfix-disc-"));
  const prevHome = process.env.HOME;
  const prevProfile = process.env.USERPROFILE;
  const prevPort = process.env.UEMCP_BRIDGE_PORT;
  try {
    process.env.HOME = home;
    process.env.USERPROFILE = home;
    process.env.UEMCP_BRIDGE_PORT = "1"; // default-port fallback must fail fast (connection refused)
    const projectDir = join(home, "Proj");
    const raw = { ...TSFIX_VALID_DISCOVERY, url: "http://127.0.0.1:1", stale: true, staleReason: "editor-exited", staleAt: "2026-11-18T02:00:00Z" };
    mkdirSync(join(home, ".uemcp", "bridges"), { recursive: true });
    writeFileSync(join(home, ".uemcp", "bridges", `${projectHash(projectDir)}.json`), JSON.stringify(raw));
    writeFileSync(join(home, ".uemcp", "bridge.json"), JSON.stringify(raw));
    const { log, warns } = tsfixLogger();
    const resolved = await resolveBridge({ projectDir }, log);
    assert.equal(resolved, null, "stale discovery must not resolve to a bridge");
    assert.ok(warns.some((w) => w.m === "bridge_discovery_stale"), "stale warn must be emitted on the discovery path");
  } finally {
    if (prevHome === undefined) delete process.env.HOME; else process.env.HOME = prevHome;
    if (prevProfile === undefined) delete process.env.USERPROFILE; else process.env.USERPROFILE = prevProfile;
    if (prevPort === undefined) delete process.env.UEMCP_BRIDGE_PORT; else process.env.UEMCP_BRIDGE_PORT = prevPort;
    rmSync(home, { recursive: true, force: true });
  }
});

// ---------- tsfix B3：viewport 20s 上限 + pixelStreaming 能力预检 ----------

test("tsfix B3: viewport schema timeoutMs max 20000 (default 15000) and ToolDef timeout 20000", () => {
  const schema = viewportCaptureTool.schemaFor(FULL);
  assert.equal(schema.safeParse({ timeoutMs: 20000 }).success, true);
  assert.equal(schema.safeParse({ timeoutMs: 20001 }).success, false, "B3: schema max must be 20000, not 30000");
  const d = schema.safeParse({});
  assert.equal(d.success, true);
  assert.equal(d.data.timeoutMs, 15000, "default stays 15000");
  assert.equal(viewportCaptureTool.timeoutMs, 20000, "B3: ToolDef timeout must be 20000, not 45000");
});

test("tsfix B3: pixelStreaming:false → CAPABILITY_UNAVAILABLE (audited); absent → proceeds with 20s call timeout", async () => {
  const calls = [];
  const bridge = {
    getCached: () => null, ensureDiscovered: async () => null, invalidate() {},
    call: async (method, _params, timeoutMs) => {
      calls.push({ method, timeoutMs });
      return { ok: true, data: { filePath: "C:/mock.png", width: 64, height: 64 }, warnings: [] };
    },
  };
  const mk = (capabilities) => {
    const records = [];
    return {
      records,
      ctx: {
        policy: FULL, bridge,
        watchdog: { state: { connected: true, ...(capabilities ? { capabilities } : {}) } },
        audit: { record: async (r) => records.push(r), degraded: false },
        log: nullLogger(), transport: "stdio", elicit: async () => "unsupported",
      },
    };
  };
  const off = mk({ pixelStreaming: false });
  const res = await viewportCaptureTool.handle(off.ctx, { returnMode: "file" });
  assert.equal(res.isError, true);
  assert.equal(res.structuredContent.error.code, "CAPABILITY_UNAVAILABLE");
  assert.equal(off.records.length, 1, "capability rejection must be audited");
  assert.equal(off.records[0].ok, false);
  assert.equal(off.records[0].errorCode, "CAPABILITY_UNAVAILABLE");
  assert.equal(calls.length, 0, "precheck must short-circuit before bridge.call");
  const absent = mk(undefined);
  const res2 = await viewportCaptureTool.handle(absent.ctx, { returnMode: "file" });
  assert.equal(res2.isError, false, "missing capabilities must be tolerated (transition period)");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].method, "viewport.capture");
  assert.equal(calls[0].timeoutMs, 20000, "bridge.call must receive the 20s ToolDef timeout");
  assert.equal(absent.records.length, 1);
  assert.equal(absent.records[0].ok, true);
});

// ---------- tsfix B6：pythonExec 审计 argsSummary 回填 zod 生效 mode ----------

test("tsfix B6: pythonExec audit argsSummary carries effective mode (default exec / explicit eval), hash-only", async () => {
  const records = [];
  const ctx = {
    policy: FULL,
    bridge: { getCached: () => null, ensureDiscovered: async () => null, invalidate() {}, call: async () => ({ ok: true, data: { stdout: "" }, warnings: [] }) },
    watchdog: { state: { connected: false } },
    audit: { record: async (r) => records.push(r), degraded: false },
    log: nullLogger(), transport: "stdio", elicit: async () => "unsupported",
  };
  const r1 = await pythonExecTool.handle(ctx, { code: "pass" });
  assert.equal(r1.isError, false);
  const r2 = await pythonExecTool.handle(ctx, { code: "1+1", mode: "eval" });
  assert.equal(r2.isError, false);
  assert.equal(records.length, 2);
  assert.equal(records[0].argsSummary.mode, "exec", "omitted mode must backfill the zod default exec (B6)");
  assert.equal(records[0].argsSummary.codeLength, 4);
  assert.equal(typeof records[0].argsSummary.codeSha256, "string");
  assert.equal(records[1].argsSummary.mode, "eval");
  assert.equal(records[0].confirmationMode, "policy", "no client elicitation capability → policy confirmation");
  const s = JSON.stringify(records);
  assert.ok(!s.includes("1+1"), "privacy: python source text must not enter the audit record");
  assert.ok(!s.includes("pass"), "privacy: python source text must not enter the audit record");
});

// ---------- tsfix B5：审计降级（连续 3 次写失败触发一次 audit_degraded） ----------

test("tsfix B5: audit write failures → degraded at 3rd consecutive failure, single transition warn", async () => {
  const home = mkdtempSync(join(tmpdir(), "uemcp-tsfix-audit-"));
  const blocker = join(home, "not-a-dir");
  writeFileSync(blocker, "x"); // a FILE where the audit dir should be → every mkdir/write fails
  const { log, warns } = tsfixLogger();
  const audit = new Audit(log, blocker);
  try {
    for (let i = 0; i < 4; i++) {
      await audit.record({ ts: new Date().toISOString(), requestId: `req_${i}`, tool: "ue_editor_status" });
    }
    assert.equal(audit.degraded, true);
    const degraded = warns.filter((w) => w.m === "audit_degraded");
    assert.equal(degraded.length, 1, "transition warn must fire exactly once, at the 3rd failure");
    assert.equal(degraded[0].d.consecutiveFailures, 3);
    assert.equal(warns.filter((w) => w.m === "audit_write_failed").length, 4);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

// ---------- tsfix B-3.9：policySource（cli > env > default） ----------

test("tsfix B-3.9: loadConfig policySource cli > env > default; env read-only not accepted", () => {
  const prev = process.env.UEMCP_POLICY;
  try {
    delete process.env.UEMCP_POLICY;
    let c = loadConfig([]);
    assert.equal(c.policy, "read-only");
    assert.equal(c.policySource, "default");
    c = loadConfig(["--policy", "standard"]);
    assert.equal(c.policy, "standard");
    assert.equal(c.policySource, "cli");
    process.env.UEMCP_POLICY = "full";
    c = loadConfig([]);
    assert.equal(c.policy, "full");
    assert.equal(c.policySource, "env");
    c = loadConfig(["--policy", "read-only"]);
    assert.equal(c.policy, "read-only");
    assert.equal(c.policySource, "cli", "CLI must win over env");
    process.env.UEMCP_POLICY = "read-only";
    c = loadConfig([]);
    assert.equal(c.policy, "read-only");
    assert.equal(c.policySource, "default", "env read-only is not a valid env policy → falls back to default");
  } finally {
    if (prev === undefined) delete process.env.UEMCP_POLICY; else process.env.UEMCP_POLICY = prev;
  }
});

// ---------- tsfix B7：读工具 argsSummary 仅键名/哈希（隐私） ----------

test("tsfix B7: summarizeArgs for read tools exposes keys only; python stays hash-only with mode", () => {
  assert.deepEqual(summarizeArgs("ue_actor_query", { scope: "level", limit: 50 }), { keys: ["scope", "limit"] });
  assert.deepEqual(summarizeArgs("ue_asset_search", { query: "Test" }), { keys: ["query"] });
  assert.deepEqual(summarizeArgs("ue_log_query", { pattern: "Error" }), { keys: ["pattern"] });
  const py = summarizeArgs("ue_python_exec", { code: "1+1", mode: "eval" });
  assert.equal(py.mode, "eval");
  assert.equal(py.codeLength, 3);
  assert.equal(typeof py.codeSha256, "string");
  assert.ok(!JSON.stringify(py).includes("1+1"));
});
