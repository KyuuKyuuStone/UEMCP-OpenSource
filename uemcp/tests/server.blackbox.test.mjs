/**
 * server 包黑盒集成测试（node:test，零依赖）。
 * 被测对象：packages/server/dist/index.js（构建产物）+ scripts/mock-bridge.mjs（fake transport）。
 * 不依赖真实 UE / 真实桥接。端口规划：本文件 Server 用 19101..19199，
 * mock bridge 用 --port 0（随机），与真实服务（18777/18778）、smoke（18999/19001-19008）隔离。
 * 覆盖：settings 加载与默认值（CLI > env > 默认）、策略门控（server.policy /
 *       server.allowExec / bridge.allowExec / bridge.allowWrite / schema 收窄）、
 *       dispatcher 路由与错误码形态、RPC 请求-响应封装、桥接不可达 / 非 JSON / 401 映射、
 *       outputSchema 发布与成功/错误双形态客户端校验（附录 A / 任务 4248c955-A）、
 *       m-3 超时语义（默认 10s 贯通）、m-13 blueprint query+save 写门与审计、
 *       BRIDGE_TIMEOUT 分类（挂起桥接，TimeoutError → BRIDGE_TIMEOUT）。
 * 已知未测：更长超时档位（30s/45s/60s 工具超时与 clamp 120s）——测试时长不可接受，
 *           BRIDGE_TIMEOUT 用 1s 档（m-3 后用户可调下限 1000ms）验证分类路径。
 */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import http from "node:http";
import { validate, outputSchemaBranches } from "../scripts/output-schema-validator.mjs";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const SERVER = join(ROOT, "packages", "server", "dist", "index.js");
const MOCK = join(ROOT, "scripts", "mock-bridge.mjs");

// ---------- 基础设施 ----------

const homes = [];
function newHome() {
  const h = mkdtempSync(join(tmpdir(), "uemcp-test-"));
  homes.push(h);
  return h;
}

function startBridge(home, flags = []) {
  return new Promise((resolve, reject) => {
    const p = spawn(process.execPath, [MOCK, "--port", "0", "--home", home, ...flags], {
      stdio: ["ignore", "pipe", "pipe"],
    });
    let out = "";
    const timer = setTimeout(() => reject(new Error("mock bridge did not start")), 10000);
    p.stdout.on("data", (c) => {
      out += c;
      const nl = out.indexOf("\n");
      if (nl >= 0) {
        clearTimeout(timer);
        resolve({ proc: p, info: JSON.parse(out.slice(0, nl)) });
      }
    });
    p.on("exit", (code) => reject(new Error(`mock bridge exited early: ${code}`)));
  });
}

function serverEnv(home, extra = {}) {
  return {
    USERPROFILE: home,
    UEMCP_AUDIT_DIR: join(home, "audit"),
    UEMCP_BRIDGE_PORT: "18999", // 隔离默认发现：本机真实桥接在 18778
    ...extra,
  };
}

function startServer(args, env, port) {
  const p = spawn(process.execPath, [SERVER, "--transport", "http", ...args], { env });
  p.stderr.resume();
  return { proc: p, port };
}

async function waitHealth(port, timeoutMs = 12000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`);
      if (res.ok) return await res.json();
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`server on ${port} did not become healthy`);
}

function stop(p) {
  return new Promise((resolve) => {
    if (!p || p.exitCode !== null) return resolve();
    p.once("exit", resolve);
    p.kill();
    setTimeout(() => {
      try { p.kill("SIGKILL"); } catch { /* already gone */ }
      resolve();
    }, 3000);
  });
}

async function initSession(port) {
  const res = await fetch(`http://127.0.0.1:${port}/mcp`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "code-test", version: "0" } },
    }),
  });
  const sid = res.headers.get("mcp-session-id");
  assert.ok(sid, "initialize must return mcp-session-id");
  await fetch(`http://127.0.0.1:${port}/mcp`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid },
    body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
  });
  return sid;
}

async function rpc(port, sid, name, argsObject, id = 9) {
  const res = await fetch(`http://127.0.0.1:${port}/mcp`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      accept: "application/json, text/event-stream",
      ...(sid ? { "mcp-session-id": sid } : {}),
    },
    body: JSON.stringify({ jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: argsObject } }),
  });
  const text = await res.text();
  const json = JSON.parse(text.match(/^data: (.*)$/m)?.[1] ?? text);
  return { http: res.status, body: json };
}

async function listTools(port, sid) {
  const res = await fetch(`http://127.0.0.1:${port}/mcp`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid },
    body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }),
  });
  const text = await res.text();
  const json = JSON.parse(text.match(/^data: (.*)$/m)?.[1] ?? text);
  return json.result.tools.map((t) => t.name);
}

const SC = (r) => r.body.result?.structuredContent;

// ---------- settings：加载与默认值（CLI > env > 默认） ----------

test("settings: no args and no env → default read-only policy exposes 9 tools", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19101"], serverEnv(home));
  try {
    await waitHealth(19101);
    const sid = await initSession(19101);
    const names = await listTools(19101, sid);
    assert.equal(names.length, 9);
    assert.ok(names.includes("ue_editor_status"));
    assert.ok(!names.includes("ue_actor_edit"), "read-only must hide P1 ue_actor_edit");
    assert.ok(!names.includes("ue_python_exec"), "read-only must hide P2 tools");
  } finally {
    await stop(srv.proc);
  }
});

test("settings: UEMCP_POLICY env=standard → 10 tools (env used when no CLI flag)", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19102"], serverEnv(home, { UEMCP_POLICY: "standard" }));
  try {
    await waitHealth(19102);
    const sid = await initSession(19102);
    const names = await listTools(19102, sid);
    assert.equal(names.length, 10);
    assert.ok(names.includes("ue_actor_edit"));
    assert.ok(!names.includes("ue_python_exec"));
  } finally {
    await stop(srv.proc);
  }
});

test("settings: CLI --policy overrides UEMCP_POLICY env", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19103", "--policy", "read-only"], serverEnv(home, { UEMCP_POLICY: "standard" }));
  try {
    await waitHealth(19103);
    const sid = await initSession(19103);
    const names = await listTools(19103, sid);
    assert.equal(names.length, 9, "CLI read-only must win over env standard");
  } finally {
    await stop(srv.proc);
  }
});

test("settings: UEMCP_HTTP_PORT env is honored when --port absent", async () => {
  const home = newHome();
  const srv = startServer([], serverEnv(home, { UEMCP_HTTP_PORT: "19104" }));
  try {
    const health = await waitHealth(19104);
    assert.ok(health.ok !== false);
  } finally {
    await stop(srv.proc);
  }
});

test("settings: unknown option --audit-python-source → fatal exit 1 with Unknown option", async () => {
  const home = newHome();
  const p = spawn(process.execPath, [SERVER, "--transport", "http", "--port", "19105", "--audit-python-source"], {
    env: serverEnv(home),
  });
  let errText = "";
  p.stderr.on("data", (c) => (errText += c));
  const code = await new Promise((resolve) => {
    const t = setTimeout(() => {
      try { p.kill("SIGKILL"); } catch { /* ignore */ }
      resolve(null);
    }, 8000);
    p.on("exit", (c) => {
      clearTimeout(t);
      resolve(c);
    });
  });
  assert.equal(code, 1, "unknown option must exit 1");
  assert.ok(errText.includes("Unknown option: --audit-python-source"), `stderr: ${errText}`);
  const fatal = errText.split("\n").find((l) => l.includes('"event":"fatal"'));
  assert.ok(fatal, "stderr must contain fatal JSON log line");
  assert.equal(JSON.parse(fatal).event, "fatal");
});

// ---------- security 门控 ----------

test("security: hidden P1 tool direct call → TOOL_DISABLED gate=server.policy", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19110", "--policy", "read-only"], serverEnv(home));
  try {
    await waitHealth(19110);
    const sid = await initSession(19110);
    const r = await rpc(19110, sid, "ue_actor_edit", { operations: [{ op: "spawn", class: "Cube" }] });
    assert.equal(r.http, 200);
    assert.equal(r.body.result.isError, true);
    assert.equal(SC(r).error.code, "TOOL_DISABLED");
    assert.equal(SC(r).error.details?.gate, "server.policy");
    assert.ok((r.body.result.content?.[0]?.text ?? "").startsWith("TOOL_DISABLED:"), "content[0].text must be prefixed with CODE:");
  } finally {
    await stop(srv.proc);
  }
});

test("security: read-only narrowing rejects write action at schema layer, read action passes", async () => {
  const home = newHome();
  const bridge = await startBridge(home);
  const srv = startServer(
    ["--port", "19111", "--policy", "read-only", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19111);
    const sid = await initSession(19111);
    const bad = await rpc(19111, sid, "ue_level_control", { action: "save_current" });
    assert.equal(bad.http, 200);
    assert.equal(bad.body.result.isError, true);
    assert.equal(SC(bad).error.code, "INVALID_ARGUMENT");
    assert.ok(Array.isArray(SC(bad).error.details?.issues) && SC(bad).error.details.issues.length > 0, "details.issues[] must be present (§2.9.4)");
    const good = await rpc(19111, sid, "ue_level_control", { action: "get_current" }, 10);
    assert.equal(good.http, 200);
    assert.equal(good.body.result.isError, false, "successful tool call is isError:false");
    assert.equal(SC(good).ok, true);
    assert.equal(SC(good).data.name, "L_TestUEMCP");
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

test("security: full+allowExec but bridge denies exec → EXEC_DISABLED gate=bridge.allowExec", async () => {
  const home = newHome();
  const bridge = await startBridge(home, ["--deny-exec"]);
  const srv = startServer(
    ["--port", "19112", "--policy", "full", "--allow-exec", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19112);
    const sid = await initSession(19112);
    const r = await rpc(19112, sid, "ue_python_exec", { mode: "eval", code: "1+1" });
    assert.equal(r.http, 200);
    assert.equal(SC(r).error.code, "EXEC_DISABLED");
    assert.equal(SC(r).error.details?.gate, "bridge.allowExec");
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

test("security: standard + spawn via bridge without --allow-write → PERMISSION_DENIED gate=bridge.allowWrite", async () => {
  const home = newHome();
  const bridge = await startBridge(home);
  const srv = startServer(
    ["--port", "19113", "--policy", "standard", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19113);
    const sid = await initSession(19113);
    const r = await rpc(19113, sid, "ue_actor_edit", {
      operations: [{ op: "spawn", class: "StaticMeshActor" }],
    });
    assert.equal(r.http, 200);
    assert.equal(SC(r).error.code, "PERMISSION_DENIED");
    assert.equal(SC(r).error.details?.gate, "bridge.allowWrite");
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

test("security: full + allowed bridge → python eval ok (meta.durationMs) and console stat dispatched", async () => {
  const home = newHome();
  const bridge = await startBridge(home, ["--allow-write", "--allow-exec", "--allow-console"]);
  const srv = startServer(
    ["--port", "19114", "--policy", "full", "--allow-console", "--allow-exec", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19114);
    const sid = await initSession(19114);
    const py = await rpc(19114, sid, "ue_python_exec", { mode: "eval", code: "1+1" });
    assert.equal(py.http, 200);
    assert.equal(py.body.result.isError, false, "successful tool call is isError:false");
    assert.equal(SC(py).ok, true);
    assert.equal(SC(py).data.result, 2);
    assert.equal(typeof SC(py).meta.durationMs, "number");
    const con = await rpc(19114, sid, "ue_console_command", { command: "stat fps" }, 10);
    assert.equal(con.http, 200);
    assert.equal(SC(con).data.dispatched, true);
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

// ---------- dispatcher 路由与错误码形态 ----------

test("dispatcher: unknown bridge class filter → CLASS_NOT_FOUND with details.className", async () => {
  const home = newHome();
  const bridge = await startBridge(home);
  const srv = startServer(
    ["--port", "19120", "--policy", "standard", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19120);
    const sid = await initSession(19120);
    const r = await rpc(19120, sid, "ue_actor_query", { filter: { class: "FooBar" } });
    assert.equal(r.http, 200);
    assert.equal(r.body.result.isError, true);
    assert.equal(SC(r).error.code, "CLASS_NOT_FOUND");
    assert.equal(SC(r).error.details?.className, "FooBar");
    assert.ok((r.body.result.content?.[0]?.text ?? "").startsWith("CLASS_NOT_FOUND:"));
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

test("dispatcher: happy-path RPC round-trip returns ok envelope with data/warnings/meta", async () => {
  const home = newHome();
  const bridge = await startBridge(home);
  const srv = startServer(
    ["--port", "19121", "--policy", "standard", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19121);
    const sid = await initSession(19121);
    const r = await rpc(19121, sid, "ue_actor_query", { filter: { class: "StaticMeshActor" } });
    assert.equal(r.http, 200);
    const sc = SC(r);
    assert.equal(sc.ok, true);
    assert.equal(sc.data.total, 2);
    assert.equal(sc.data.returned, 2);
    assert.equal(sc.data.truncated, false);
    assert.ok(Array.isArray(sc.warnings));
    assert.equal(typeof sc.meta.durationMs, "number");
    assert.equal(sc.meta.requestId ? typeof sc.meta.requestId : "string", typeof sc.meta.requestId, "meta present");
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

test("dispatcher: bridge maps viewport pie target → PIE_NOT_RUNNING", async () => {
  const home = newHome();
  const bridge = await startBridge(home);
  const srv = startServer(
    ["--port", "19122", "--policy", "standard", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19122);
    const sid = await initSession(19122);
    const r = await rpc(19122, sid, "ue_viewport_capture", { target: "pie", returnMode: "file" });
    assert.equal(r.http, 200);
    assert.equal(r.body.result.isError, true);
    assert.equal(SC(r).error.code, "PIE_NOT_RUNNING");
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

// ---------- 桥接不可达 / 非 JSON / 401（fake bridge 直连） ----------

test("bridge: dead --bridge-url read tool → BRIDGE_UNAVAILABLE retryable, server stays healthy", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19130", "--policy", "standard", "--bridge-url", "http://127.0.0.1:19139"], serverEnv(home));
  try {
    await waitHealth(19130);
    const sid = await initSession(19130);
    const r = await rpc(19130, sid, "ue_editor_status", {});
    assert.equal(r.http, 200);
    assert.equal(SC(r).error.code, "BRIDGE_UNAVAILABLE");
    assert.equal(SC(r).error.retryable, true);
    const health = await (await fetch("http://127.0.0.1:19130/health")).json();
    assert.equal(health.ok !== false, true, "server must stay alive after bridge loss");
  } finally {
    await stop(srv.proc);
  }
});

test("bridge: dead --bridge-url write tool → BRIDGE_UNAVAILABLE with explicit not-auto-retried note", async () => {
  const home = newHome();
  const srv = startServer(
    ["--port", "19131", "--policy", "full", "--allow-destructive", "--bridge-url", "http://127.0.0.1:19139"],
    serverEnv(home),
  );
  try {
    await waitHealth(19131);
    const sid = await initSession(19131);
    const r = await rpc(19131, sid, "ue_actor_edit", { operations: [{ op: "spawn", class: "Cube" }] });
    assert.equal(SC(r).error.code, "BRIDGE_UNAVAILABLE");
    assert.ok(
      String(SC(r).error.message).includes("not auto-retried"),
      "non-idempotent methods must state they are not auto-retried",
    );
  } finally {
    await stop(srv.proc);
  }
});

test("bridge: non-JSON 200 response → INTERNAL with bridgeHttpStatus detail", async () => {
  const home = newHome();
  const fake = http.createServer((req, res) => {
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ app: "uemcp-bridge", ok: true, pid: process.pid, startedAt: new Date().toISOString() }));
      return;
    }
    res.writeHead(200, { "content-type": "text/plain" });
    res.end("hello-not-json");
  });
  await new Promise((r) => fake.listen(19140, "127.0.0.1", r));
  const srv = startServer(
    ["--port", "19141", "--policy", "standard", "--bridge-url", "http://127.0.0.1:19140"],
    serverEnv(home),
  );
  try {
    await waitHealth(19141);
    const sid = await initSession(19141);
    const r = await rpc(19141, sid, "ue_editor_status", {});
    assert.equal(SC(r).error.code, "INTERNAL");
    assert.equal(SC(r).error.details?.bridgeHttpStatus, 200);
  } finally {
    await stop(srv.proc);
    fake.close();
  }
});

test("bridge: HTTP 401 → BRIDGE_UNAVAILABLE (retriable) so discovery can re-run", async () => {
  const home = newHome();
  const fake = http.createServer((req, res) => {
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ app: "uemcp-bridge", ok: true, pid: process.pid, startedAt: new Date().toISOString() }));
      return;
    }
    res.writeHead(401, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "unauthorized" }));
  });
  await new Promise((r) => fake.listen(19142, "127.0.0.1", r));
  const srv = startServer(
    ["--port", "19143", "--policy", "standard", "--bridge-url", "http://127.0.0.1:19142", "--bridge-token", "bad-token"],
    serverEnv(home),
  );
  try {
    await waitHealth(19143);
    const sid = await initSession(19143);
    const r = await rpc(19143, sid, "ue_editor_status", {});
    assert.equal(SC(r).error.code, "BRIDGE_UNAVAILABLE", "401 must map to BRIDGE_UNAVAILABLE, not INTERNAL");
    assert.equal(SC(r).error.retryable, true);
    assert.equal(SC(r).error.details?.bridgeHttpStatus, 401);
  } finally {
    await stop(srv.proc);
    fake.close();
  }
});

// ---------- outputSchema（附录 A / 任务 4248c955-A）----------

test("outputSchema: every visible tool publishes a dual-shape (success|failure) schema", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19150", "--policy", "standard"], serverEnv(home));
  try {
    await waitHealth(19150);
    const sid = await initSession(19150);
    const res = await fetch(`http://127.0.0.1:19150/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid },
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }),
    });
    const text = await res.text();
    const json = JSON.parse(text.match(/^data: (.*)$/m)?.[1] ?? text);
    const tools = json.result.tools;
    assert.equal(tools.length, 10);
    for (const t of tools) {
      // MCP 规范/SDK ToolSchema：根层级必须 type:"object"
      assert.equal(t.outputSchema?.type, "object", `${t.name}: outputSchema root must be type object`);
      assert.ok(Array.isArray(t.outputSchema.required) && t.outputSchema.required.includes("ok") && t.outputSchema.required.includes("meta"),
        `${t.name}: root must require ok/meta`);
      const b = outputSchemaBranches(t);
      assert.ok(b, `${t.name}: outputSchema must carry a success|failure anyOf union`);
      assert.ok(b.success.properties.ok.const === true && ["data", "warnings"].every((k) => b.success.required.includes(k)),
        `${t.name}: success branch must demand ok=true + data + warnings`);
      assert.ok(b.failure.properties.ok.const === false && b.failure.required.includes("error"),
        `${t.name}: failure branch must demand ok=false + error`);
      assert.deepEqual(b.success.not?.required ?? [], ["error"], `${t.name}: success branch must exclude error`);
      assert.deepEqual(b.failure.not?.required ?? [], ["data"], `${t.name}: failure branch must exclude data`);
    }
  } finally {
    await stop(srv.proc);
  }
});

test("outputSchema: success AND error structuredContent pass the published schema for all 12 tools", async () => {
  const home = newHome();
  const bridge = await startBridge(home, ["--allow-write", "--allow-exec", "--allow-console"]);
  const srv = startServer(
    ["--port", "19151", "--policy", "full", "--allow-console", "--allow-exec", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19151);
    const sid = await initSession(19151);
    const lres = await fetch(`http://127.0.0.1:19151/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid },
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }),
    });
    const ltext = await lres.text();
    const ljson = JSON.parse(ltext.match(/^data: (.*)$/m)?.[1] ?? ltext);
    const tools = ljson.result.tools;
    assert.equal(tools.length, 12, "full+switches exposes the full catalog");
    const schemas = new Map(tools.map((t) => [t.name, t.outputSchema]));

    const successes = [
      ["ue_editor_status", {}],
      ["ue_actor_query", { filter: { class: "StaticMeshActor" } }],
      ["ue_asset_search", { query: "M_Test" }],
      ["ue_actor_edit", { operations: [{ op: "spawn", class: "Cube" }] }],
      ["ue_level_control", { action: "get_current" }],
      ["ue_material_params", { action: "list", materialPath: "/Game/Materials/M_Test" }],
      ["ue_viewport_capture", { returnMode: "file" }],
      ["ue_console_command", { command: "stat fps" }],
      ["ue_python_exec", { code: "1+1", mode: "eval" }],
      ["ue_blueprint", { action: "query", blueprintPath: "/Game/BP_Test" }],
      ["ue_pie_control", { action: "status" }],
      ["ue_policy_explain", {}],
    ];
    for (const [i, [name, args]] of successes.entries()) {
      const r = await rpc(19151, sid, name, args, 100 + i);
      assert.equal(r.http, 200, `${name} http`);
      assert.equal(r.body.result.isError, false, `${name} expected success`);
      const sc = SC(r);
      const v = validate(schemas.get(name), sc);
      assert.equal(v.valid, true, `${name} success structuredContent must match its outputSchema: ${v.errors.join("; ")}`);
    }

    const failures = [
      ["ue_level_control", { action: "definitely_not_an_action" }, "INVALID_ARGUMENT"],
      ["ue_actor_query", { filter: { class: "FooBar" } }, "CLASS_NOT_FOUND"],
      ["ue_console_command", { command: "quit" }, "COMMAND_NOT_ALLOWED"],
    ];
    for (const [i, [name, args, code]] of failures.entries()) {
      const r = await rpc(19151, sid, name, args, 200 + i);
      assert.equal(r.http, 200, `${name} tool-layer error must be HTTP 200`);
      assert.equal(r.body.result.isError, true, `${name} expected isError=true`);
      const sc = SC(r);
      assert.equal(sc.error.code, code, `${name} error code`);
      const v = validate(schemas.get(name), sc);
      assert.equal(v.valid, true, `${name} error structuredContent must match the failure branch of its outputSchema: ${v.errors.join("; ")}`);
    }
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

// ---------- m-13：blueprint query+save 计入写操作 ----------

test("m-13: read-only ue_blueprint {action:query, save:true} → PERMISSION_DENIED (write to disk blocked)", async () => {
  const home = newHome();
  const bridge = await startBridge(home);
  const srv = startServer(
    ["--port", "19152", "--policy", "read-only", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19152);
    const sid = await initSession(19152);
    const lres = await fetch(`http://127.0.0.1:19152/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid },
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }),
    });
    const ltext = await lres.text();
    const ljson = JSON.parse(ltext.match(/^data: (.*)$/m)?.[1] ?? ltext);
    const bp = ljson.result.tools.find((t) => t.name === "ue_blueprint");
    const bpSchema = bp.outputSchema;

    const denied = await rpc(19152, sid, "ue_blueprint", { action: "query", save: true }, 3);
    assert.equal(denied.body.result.isError, true);
    assert.equal(SC(denied).error.code, "PERMISSION_DENIED", "save:true is a disk write and must be denied under read-only");
    assert.equal(SC(denied).error.details?.gate, "server.policy");
    const dv = validate(bpSchema, SC(denied));
    assert.equal(dv.valid, true, `failure shape must match outputSchema: ${dv.errors.join("; ")}`);

    const plain = await rpc(19152, sid, "ue_blueprint", { action: "query" }, 4);
    assert.equal(plain.body.result.isError, false, "plain query without save stays read-only-allowed");
    const pv = validate(bpSchema, SC(plain));
    assert.equal(pv.valid, true, `success shape must match outputSchema: ${pv.errors.join("; ")}`);
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

test("m-13: standard ue_blueprint {action:query, save:true} → audited as write, plain query not audited", async () => {
  const home = newHome();
  const bridge = await startBridge(home, ["--allow-write"]);
  const srv = startServer(
    ["--port", "19153", "--policy", "standard", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19153);
    const sid = await initSession(19153);
    const plain = await rpc(19153, sid, "ue_blueprint", { action: "query" }, 3);
    assert.equal(plain.body.result.isError, false);
    const saved = await rpc(19153, sid, "ue_blueprint", { action: "query", save: true }, 4);
    assert.equal(saved.body.result.isError, false, "standard mode allows the disk write");
    await new Promise((r) => setTimeout(r, 300));
    const auditDir = join(home, "audit");
    let lines = "";
    if (existsSync(auditDir)) {
      for (const f of readdirSync(auditDir)) lines += readFileSync(join(auditDir, f), "utf8");
    }
    const bpRecords = lines.split("\n").flatMap((l) => {
      try { const j = JSON.parse(l); return j.tool === "ue_blueprint" ? [j] : []; } catch { return []; }
    });
    assert.equal(bpRecords.length, 1, "exactly the save:true call must be audited (plain query stays unaudited)");
    assert.equal(bpRecords[0].argsSummary?.save, true);
    assert.equal(bpRecords[0].decision, "allowed");
    assert.equal(bpRecords[0].ok, true);
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

// ---------- m-3：pythonExec 超时语义贯通（schema 默认 10s，用户可调） ----------

test("m-3: ue_python_exec timeoutMs semantics flow to the bridge (default 10000, explicit 5000 honored)", async () => {
  const home = newHome();
  const bridge = await startBridge(home, ["--allow-write", "--allow-exec", "--allow-console"]);
  const srv = startServer(
    ["--port", "19154", "--policy", "full", "--allow-exec", "--bridge-url", `http://127.0.0.1:${bridge.info.port}`, "--bridge-token", bridge.info.token],
    serverEnv(home),
  );
  try {
    await waitHealth(19154);
    const sid = await initSession(19154);
    const omitted = await rpc(19154, sid, "ue_python_exec", { code: "1+1", mode: "eval" }, 3);
    assert.equal(omitted.body.result.isError, false);
    assert.equal(SC(omitted).data.timeoutMsReceived, 10000, "omitted timeoutMs must use the §5.9 schema default 10000, not a server-side 30s floor");
    const explicit = await rpc(19154, sid, "ue_python_exec", { code: "1+1", mode: "eval", timeoutMs: 5000 }, 4);
    assert.equal(SC(explicit).data.timeoutMsReceived, 5000, "user-set 5s must not be raised to 30s anymore (m-3)");
  } finally {
    await stop(srv.proc);
    bridge.proc.kill();
  }
});

// ---------- m-2 / BRIDGE_TIMEOUT：挂起桥接的 abort 分类 ----------

test("bridge: hung /rpc with timeoutMs=1000 → BRIDGE_TIMEOUT phase=game_thread (abort classification)", async () => {
  const home = newHome();
  const fake = http.createServer((req, res) => {
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ app: "uemcp-bridge", ok: true, pid: process.pid, startedAt: new Date().toISOString() }));
      return;
    }
    // /rpc：接受连接但永不响应 → 客户端 AbortSignal.timeout(timeoutMs+5s) 触发 TimeoutError
  });
  await new Promise((r) => fake.listen(19158, "127.0.0.1", r));
  const srv = startServer(
    ["--port", "19159", "--policy", "full", "--allow-exec", "--bridge-url", "http://127.0.0.1:19158"],
    serverEnv(home),
  );
  try {
    await waitHealth(19159);
    const sid = await initSession(19159);
    const r = await rpc(19159, sid, "ue_python_exec", { code: "pass", mode: "exec", timeoutMs: 1000 }, 3);
    assert.equal(r.http, 200);
    assert.equal(SC(r).error.code, "BRIDGE_TIMEOUT", "TimeoutError must classify as BRIDGE_TIMEOUT, not BRIDGE_UNAVAILABLE");
    assert.equal(SC(r).error.retryable, true);
    assert.equal(SC(r).error.details?.phase, "game_thread");
    assert.equal(SC(r).error.details?.timeoutMs, 1000);
  } finally {
    await stop(srv.proc);
    fake.close();
    fake.closeAllConnections?.(); // 挂起的 /rpc 连接会让 close 回调挂起，直接断开
  }
});

// ---------- charset=utf-8（外部报告建议项）----------

test("http: /mcp JSON+error, /mcp SSE and /health content-type carry explicit charset=utf-8", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19160", "--policy", "standard"], serverEnv(home));
  try {
    await waitHealth(19160);
    const H = { "content-type": "application/json", accept: "application/json, text/event-stream" };

    // /health（express res.json 路径）
    const health = await fetch("http://127.0.0.1:19160/health");
    assert.ok(
      (health.headers.get("content-type") ?? "").includes("charset=utf-8"),
      `/health content-type missing charset: ${health.headers.get("content-type")}`,
    );

    // /mcp 正常响应（SDK 1.32 默认 SSE 响应模式：JSON-RPC 帧在 event-stream 里回）
    const init = await fetch("http://127.0.0.1:19160/mcp", {
      method: "POST",
      headers: H,
      body: JSON.stringify({
        jsonrpc: "2.0", id: 1, method: "initialize",
        params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "charset-test", version: "0" } },
      }),
    });
    const initCt = init.headers.get("content-type") ?? "";
    assert.ok(initCt.includes("text/event-stream") && initCt.includes("charset=utf-8"), `/mcp POST (SSE mode) content-type: ${initCt}`);
    const sid = init.headers.get("mcp-session-id");
    assert.ok(sid, "initialize must establish a session");

    // /mcp JSON 形态（协议层 JSON 错误：Accept 缺 text/event-stream → 406 createJsonErrorResponse）
    const json406 = await fetch("http://127.0.0.1:19160/mcp", {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 2, method: "initialize",
        params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "charset-test", version: "0" } },
      }),
    });
    const json406Ct = json406.headers.get("content-type") ?? "";
    assert.equal(json406.status, 406);
    assert.ok(json406Ct.includes("application/json") && json406Ct.includes("charset=utf-8"), `/mcp JSON 406 content-type: ${json406Ct}`);

    // /mcp SSE 流（text/event-stream 也要带 charset）
    const ac = new AbortController();
    try {
      const sse = await fetch("http://127.0.0.1:19160/mcp", {
        method: "GET",
        headers: { accept: "text/event-stream", "mcp-session-id": sid },
        signal: ac.signal,
      });
      const sseCt = sse.headers.get("content-type") ?? "";
      assert.ok(sseCt.includes("text/event-stream") && sseCt.includes("charset=utf-8"), `/mcp SSE content-type: ${sseCt}`);
    } catch (e) {
      if ((e && e.name) !== "AbortError") throw e;
    } finally {
      ac.abort(); // 释放流连接
    }

    // 协议层错误（sendRpcError，未知会话 404 -32001）
    const bad = await fetch("http://127.0.0.1:19160/mcp", {
      method: "POST",
      headers: { ...H, "mcp-session-id": "00000000-0000-0000-0000-000000000000" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 9, method: "tools/list", params: {} }),
    });
    assert.equal(bad.status, 404);
    assert.ok(
      (bad.headers.get("content-type") ?? "").includes("charset=utf-8"),
      `sendRpcError 404 content-type: ${bad.headers.get("content-type")}`,
    );

    // Host 不合法 421（fetch 不能改 Host，用 node:http 原始请求）
    await new Promise((resolve) => {
      const req = http.request(
        { host: "127.0.0.1", port: 19160, path: "/health", method: "GET", headers: { Host: "evil.example.com" } },
        (res) => {
          assert.equal(res.statusCode, 421);
          assert.ok(
            String(res.headers["content-type"]).includes("charset=utf-8"),
            `421 content-type: ${res.headers["content-type"]}`,
          );
          res.resume();
          res.on("end", resolve);
        },
      );
      req.on("error", (e) => { assert.fail(`request error: ${e.message}`); resolve(); });
      req.end();
    });
  } finally {
    await stop(srv.proc);
  }
});

// ---------- 会话池加固（P1-5）：满仓 LRU 逐出 + 失效可预期 ----------

const initializeOn = async (port, id, headers = {}) => {
  const res = await fetch(`http://127.0.0.1:${port}/mcp`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream", ...headers },
    body: JSON.stringify({
      jsonrpc: "2.0", id, method: "initialize",
      params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "pool-test", version: "0" } },
    }),
  });
  return res;
};

test("sessions: maxSessions=2 LRU-evicts the oldest idle session — 3 initializes all succeed, first sid 404s with hint+ttlMs and expires header", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19165", "--policy", "standard", "--max-sessions", "2"], serverEnv(home));
  try {
    await waitHealth(19165);
    const init1 = await initializeOn(19165, 1);
    const sid1 = init1.headers.get("mcp-session-id");
    const init2 = await initializeOn(19165, 2);
    const sid2 = init2.headers.get("mcp-session-id");
    const init3 = await initializeOn(19165, 3);
    const sid3 = init3.headers.get("mcp-session-id");
    assert.ok(sid1 && sid2 && sid3, "all three initializes must succeed (no 429 under LRU eviction)");
    assert.notEqual(sid1, sid2); assert.notEqual(sid2, sid3);

    // initialize 响应头声明空闲 TTL（默认 30min = 1800000ms）
    assert.equal(init3.headers.get("mcp-session-expires-in-ms"), String(30 * 60 * 1000));

    // 最老的 sid1 被逐出 → 404 -32001 + data.hint/ttlMs（自愈契约）
    const gone = await fetch(`http://127.0.0.1:19165/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid1 },
      body: JSON.stringify({ jsonrpc: "2.0", id: 10, method: "tools/list", params: {} }),
    });
    const goneBody = await gone.json();
    assert.equal(gone.status, 404);
    assert.equal(goneBody?.error?.code, -32001);
    assert.equal(goneBody?.error?.data?.errorCode, "SESSION_NOT_FOUND");
    assert.equal(goneBody?.error?.data?.hint, "reinitialize");
    assert.equal(goneBody?.error?.data?.ttlMs, 30 * 60 * 1000);

    // 幸存者仍可用：sid2（较新）与 sid3
    const list2 = await fetch(`http://127.0.0.1:19165/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid2 },
      body: JSON.stringify({ jsonrpc: "2.0", id: 11, method: "tools/list", params: {} }),
    });
    assert.equal(list2.status, 200);
    const list3 = await fetch(`http://127.0.0.1:19165/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid3 },
      body: JSON.stringify({ jsonrpc: "2.0", id: 12, method: "tools/list", params: {} }),
    });
    assert.equal(list3.status, 200);
  } finally {
    await stop(srv.proc);
  }
});

test("sessions: eviction prefers bare-POST sessions over live SSE sessions; a pool of live SSE streams returns 429 with retryAfterMs", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19166", "--policy", "standard", "--max-sessions", "2"], serverEnv(home));
  const aborts = [];
  try {
    await waitHealth(19166);
    // A：initialize + 打开 standalone GET /mcp SSE 流（活跃流会话）
    const initA = await initializeOn(19166, 1);
    const sidA = initA.headers.get("mcp-session-id");
    const acA = new AbortController();
    aborts.push(acA);
    const sseA = await fetch(`http://127.0.0.1:19166/mcp`, {
      method: "GET",
      headers: { accept: "text/event-stream", "mcp-session-id": sidA },
      signal: acA.signal,
    });
    assert.equal(sseA.status, 200, "standalone SSE stream must open");
    // B：裸 POST 会话（无任何流）
    const initB = await initializeOn(19166, 2);
    const sidB = initB.headers.get("mcp-session-id");
    // C：满仓 → 逐出对象必须是 B（裸 POST），而不是持活跃流的 A
    const initC = await initializeOn(19166, 3);
    const sidC = initC.headers.get("mcp-session-id");
    assert.ok(sidC, "initC must succeed by evicting the bare-POST session B");
    const goneB = await fetch(`http://127.0.0.1:19166/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sidB },
      body: JSON.stringify({ jsonrpc: "2.0", id: 10, method: "tools/list", params: {} }),
    });
    assert.equal(goneB.status, 404, "evicted session must be B (bare-POST), not the SSE session A");    const aliveA = await fetch(`http://127.0.0.1:19166/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sidA },
      body: JSON.stringify({ jsonrpc: "2.0", id: 11, method: "tools/list", params: {} }),
    });
    assert.equal(aliveA.status, 200, "the live-SSE session A must survive eviction");

    // C 上也开 SSE → 两个会话都持活跃流 → 再 initialize 只能 429（带 retryAfterMs / sessions / maxSessions）
    const acC = new AbortController();
    aborts.push(acC);
    const sseC = await fetch(`http://127.0.0.1:19166/mcp`, {
      method: "GET",
      headers: { accept: "text/event-stream", "mcp-session-id": sidC },
      signal: acC.signal,
    });
    assert.equal(sseC.status, 200);
    const initD = await initializeOn(19166, 4);
    assert.equal(initD.status, 429);
    const initDBody = await initD.json();
    assert.equal(initDBody?.error?.code, -32012);
    assert.equal(initDBody?.error?.data?.errorCode, "RATE_LIMITED");
    assert.equal(initDBody?.error?.data?.sessions, 2, "429 body must carry the current pool size");
    assert.equal(initDBody?.error?.data?.maxSessions, 2);
    assert.equal(typeof initDBody?.error?.data?.retryAfterMs, "number");
    assert.ok(initDBody.error.data.retryAfterMs > 0);

    // A 仍然存活（从未被逐出）
    const aliveA2 = await fetch(`http://127.0.0.1:19166/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sidA },
      body: JSON.stringify({ jsonrpc: "2.0", id: 12, method: "tools/list", params: {} }),
    });
    assert.equal(aliveA2.status, 200);
  } finally {
    for (const ac of aborts) ac.abort(); // 关闭 SSE 流连接
    await stop(srv.proc);
  }
});

test("sessions: UEMCP_MAX_SESSIONS env is honored like --max-sessions (C. configurability)", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19167", "--policy", "standard"], serverEnv(home, { UEMCP_MAX_SESSIONS: "2" }));
  try {
    await waitHealth(19167);
    const i1 = await initializeOn(19167, 1);
    const sid1 = i1.headers.get("mcp-session-id");
    const i2 = await initializeOn(19167, 2);
    const sid2 = i2.headers.get("mcp-session-id");
    const i3 = await initializeOn(19167, 3);
    const sid3 = i3.headers.get("mcp-session-id");
    assert.ok(sid1 && sid2 && sid3, "env-configured cap=2 must LRU-evict, not 429");
    const gone = await fetch(`http://127.0.0.1:19167/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "mcp-session-id": sid1 },
      body: JSON.stringify({ jsonrpc: "2.0", id: 10, method: "tools/list", params: {} }),
    });
    assert.equal(gone.status, 404);
    const goneBody = await gone.json();
    assert.equal(goneBody?.error?.data?.hint, "reinitialize");
  } finally {
    await stop(srv.proc);
  }
});

after(async () => {
  for (const h of homes) {
    try {
      await import("node:fs").then((fs) => fs.rmSync(h, { recursive: true, force: true }));
    } catch { /* best effort */ }
  }
});
