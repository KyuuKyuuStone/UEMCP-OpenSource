/**
 * server 包黑盒集成测试（node:test，零依赖）。
 * 被测对象：packages/server/dist/index.js（构建产物）+ scripts/mock-bridge.mjs（fake transport）。
 * 不依赖真实 UE / 真实桥接。端口规划：本文件 Server 用 19101..19199，
 * mock bridge 用 --port 0（随机），与真实服务（18777/18778）、smoke（18999/19001-19008）隔离。
 * 覆盖：settings 加载与默认值（CLI > env > 默认）、策略门控（server.policy /
 *       server.allowExec / bridge.allowExec / bridge.allowWrite / schema 收窄）、
 *       dispatcher 路由与错误码形态、RPC 请求-响应封装、桥接不可达 / 非 JSON / 401 映射。
 * 已知未测：BRIDGE_TIMEOUT（工具最小超时 30s + fetch 余量 5s，测试时长不可接受；
 *           abort < 3s 分支由“bridge unreachable”用例覆盖）。
 */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import http from "node:http";

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

test("settings: no args and no env → default read-only policy exposes 7 tools", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19101"], serverEnv(home));
  try {
    await waitHealth(19101);
    const sid = await initSession(19101);
    const names = await listTools(19101, sid);
    assert.equal(names.length, 7);
    assert.ok(names.includes("ue_editor_status"));
    assert.ok(!names.includes("ue_actor_edit"), "read-only must hide P1 ue_actor_edit");
    assert.ok(!names.includes("ue_python_exec"), "read-only must hide P2 tools");
  } finally {
    await stop(srv.proc);
  }
});

test("settings: UEMCP_POLICY env=standard → 8 tools (env used when no CLI flag)", async () => {
  const home = newHome();
  const srv = startServer(["--port", "19102"], serverEnv(home, { UEMCP_POLICY: "standard" }));
  try {
    await waitHealth(19102);
    const sid = await initSession(19102);
    const names = await listTools(19102, sid);
    assert.equal(names.length, 8);
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
    assert.equal(names.length, 7, "CLI read-only must win over env standard");
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

after(async () => {
  for (const h of homes) {
    try {
      await import("node:fs").then((fs) => fs.rmSync(h, { recursive: true, force: true }));
    } catch { /* best effort */ }
  }
});
