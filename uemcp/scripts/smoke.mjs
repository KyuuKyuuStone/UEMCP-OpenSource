#!/usr/bin/env node
/**
 * UEMCP Server 自测（任务要求的最小验证集）：
 * 启动成功 / /health / initialize / 三种策略 tools/list 集合（PROTO-03）
 * tools/call 正常与错误路径（PROTO-04/10/11/12/12b/12c、SEC-01、TOOL-05(c)）
 * 桥接不可达 BRIDGE_UNAVAILABLE（RES-03）/ 端口占用 exit 2（RES-06）/ stdio（PROTO-16）
 * Host/Origin 校验（SEC-04/05）、DELETE 会话（PROTO-07）、审计（SEC-12 红线抽查）
 * 临时 HOME 清理（DEF-2）：默认 try/finally 删除本次 uemcp-smoke-* 目录（含失败/崩溃
 * 路径，先兜底回收全部子进程）；--keep-artifacts 或 UEMCP_KEEP_ARTIFACTS=1 保留现场。
 */
import { spawn } from "node:child_process";
import { request as httpRequest } from "node:http";
import { mkdtempSync, readdirSync, readFileSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validate, outputSchemaBranches } from "./output-schema-validator.mjs";

const SERVER = new URL("../packages/server/dist/index.js", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const MOCK = new URL("./mock-bridge.mjs", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

const results = [];
const smokeChildren = new Set(); // 本次 smoke 启动的全部子进程（DEF-2：finally 兜底回收）
let current = "";
function check(name, cond, detail = "") {
  results.push({ name, pass: cond === true, detail });
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}${detail && !cond ? `  -- ${detail}` : ""}`);
}
function section(s) {
  current = s;
  console.log(`\n== ${s} ==`);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseBody(text, contentType) {
  if (contentType && contentType.includes("text/event-stream")) {
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        try {
          return JSON.parse(line.slice(6));
        } catch {
          /* continue */
        }
      }
    }
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function rpc(port, body, opts = {}) {
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
    ...(opts.headers ?? {}),
  };
  const res = await fetch(`http://127.0.0.1:${port}/mcp`, {
    method: "POST",
    headers,
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
  const sid = res.headers.get("mcp-session-id") ?? undefined;
  const text = await res.text();
  return {
    status: res.status,
    sid,
    contentType: res.headers.get("content-type") ?? "",
    text,
    json: parseBody(text, res.headers.get("content-type") ?? ""),
  };
}

async function waitHealth(port, timeoutMs = 10000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`);
      if (res.ok) return await res.json();
    } catch {
      /* not yet */
    }
    await sleep(150);
  }
  throw new Error(`server on ${port} did not become healthy`);
}

function spawnServer(args, env) {
  const child = spawn(process.execPath, [SERVER, ...args], {
    env: { ...process.env, ...env },
    stdio: ["pipe", "pipe", "pipe"],
  });
  smokeChildren.add(child);
  return child;
}

function collectStderr(child) {
  const chunks = [];
  child.stderr.on("data", (c) => chunks.push(c.toString()));
  return chunks;
}

async function main() {
  // DEF-2：默认清理本次临时 HOME（try/finally 兜底失败/崩溃路径）；
  // --keep-artifacts（argv）或 UEMCP_KEEP_ARTIFACTS=1 保留现场供排查。
  const keepArtifacts = process.argv.includes("--keep-artifacts") || process.env.UEMCP_KEEP_ARTIFACTS === "1";
  const home = mkdtempSync(join(tmpdir(), "uemcp-smoke-"));
  try {
    await runSuite(home);
  } finally {
    // 兜底回收子进程（正常路径多数已退出；崩溃/超时路径必须回收才能安全删目录）
    for (const c of smokeChildren) {
      try { c.kill(); } catch { /* already gone */ }
    }
    await sleep(600); // 等句柄释放（Windows 上立即删目录可能 EBUSY）
    for (const c of smokeChildren) {
      try { c.kill("SIGKILL"); } catch { /* already gone */ }
    }
    if (keepArtifacts) {
      console.log(`\nINFO  --keep-artifacts: temp HOME preserved for inspection: ${home}`);
    } else {
      let cleaned = false;
      try {
        rmSync(home, { recursive: true, force: true });
        cleaned = !existsSync(home);
      } catch (e) {
        console.error(`WARN  temp HOME cleanup failed: ${String(e)}`);
      }
      check("temp HOME cleaned up after run (DEF-2, no uemcp-smoke-* leak)", cleaned, home);
    }
  }
  const failed = results.filter((r) => !r.pass);
  console.log(`\n========== SMOKE RESULT: ${results.length - failed.length}/${results.length} passed ==========`);
  if (failed.length) {
    console.log("FAILED:");
    for (const f of failed) console.log(`  - ${f.name}: ${f.detail}`);
    process.exitCode = 1;
  }
}

async function runSuite(home) {
  // 隔离默认桥接端口：避免本机真实 UEMCPBridge（18778）影响"全部发现来源失败"类断言
  const env = { USERPROFILE: home, UEMCP_AUDIT_DIR: join(home, "audit"), UEMCP_BRIDGE_PORT: "18999" };

  // ---- 启动 mock bridge ----
  section("mock bridge");
  const bridgeStdout = [];
  const bridge = spawn(process.execPath, [MOCK, "--port", "0", "--home", home], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  smokeChildren.add(bridge);
  bridge.stdout.on("data", (c) => bridgeStdout.push(c.toString()));
  let bridgeInfo;
  for (let i = 0; i < 50 && !bridgeInfo; i++) {
    await sleep(100);
    const raw = bridgeStdout.join("");
    const line = raw.split("\n").find((l) => l.trim().startsWith("{"));
    if (line) {
      try {
        bridgeInfo = JSON.parse(line);
      } catch {
        /* wait */
      }
    }
  }
  check("mock bridge started + discovery written", !!bridgeInfo, "no stdout json");
  check("discovery bridge.json exists", existsSync(join(home, ".uemcp", "bridge.json")));
  const bridgeHealth = await (await fetch(`http://127.0.0.1:${bridgeInfo?.port}/health`)).json();
  check("bridge /health app=uemcp-bridge", bridgeHealth.app === "uemcp-bridge" && bridgeHealth.ok === true);

  // ---- HTTP server (standard) ----
  section("HTTP server: startup & health");
  const PORT = 19001;
  const srv = spawnServer(["--transport", "http", "--port", String(PORT), "--policy", "standard"], env);
  const srvErr = collectStderr(srv);
  let health;
  try {
    health = await waitHealth(PORT);
  } catch (e) {
    console.error("server failed:", srvErr.join(""));
    throw e;
  }
  check("server /health ok", health.ok === true && health.name === "uemcp");
  await sleep(300);
  const health2 = await (await fetch(`http://127.0.0.1:${PORT}/health`)).json();
  check("/health bridge.connected=true (discovery + watchdog)", health2.bridge.connected === true, JSON.stringify(health2.bridge));
  check("/health no token leak", !JSON.stringify(health2).includes(bridgeInfo.token));

  // ---- initialize / initialized ----
  section("MCP protocol (PROTO-01/02/17)");
  const init = await rpc(PORT, {
    jsonrpc: "2.0", id: 1, method: "initialize",
    params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "smoke", version: "0" } },
  });
  check("initialize 200 + session header (PROTO-01)", init.status === 200 && !!init.sid, `status=${init.status}`);
  check("initialize protocolVersion negotiated (PROTO-17)", init.json?.result?.protocolVersion === "2025-06-18", init.text.slice(0, 120));
  check("serverInfo.name=uemcp", init.json?.result?.serverInfo?.name === "uemcp");
  const SID = init.sid;
  const H = { "Mcp-Session-Id": SID, "MCP-Protocol-Version": "2025-06-18" };

  const initOld = await rpc(PORT, {
    jsonrpc: "2.0", id: 90, method: "initialize",
    params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "smoke", version: "0" } },
  });
  check("initialize 2024-11-05 echo (PROTO-17)", initOld.json?.result?.protocolVersion === "2024-11-05");
  const initFuture = await rpc(PORT, {
    jsonrpc: "2.0", id: 91, method: "initialize",
    params: { protocolVersion: "2999-01-01", capabilities: {}, clientInfo: { name: "smoke", version: "0" } },
  });
  check("initialize future version falls back (PROTO-17)", ["2025-06-18", "2025-03-26", "2024-11-05"].includes(initFuture.json?.result?.protocolVersion));

  const notified = await fetch(`http://127.0.0.1:${PORT}/mcp`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream", "Mcp-Session-Id": SID },
    body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
  });
  check("notifications/initialized 202 empty (PROTO-02)", notified.status === 202 && (await notified.text()).length === 0);

  // ---- tools/list standard ----
  section("tools/list: policy matrix (PROTO-03)");
  const listStd = await rpc(PORT, { jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }, { headers: H });
  const namesStd = (listStd.json?.result?.tools ?? []).map((t) => t.name).sort();
  check("standard = exactly 10 tools", namesStd.length === 10 && JSON.stringify(namesStd) === JSON.stringify([
    "ue_actor_edit", "ue_actor_query", "ue_asset_search", "ue_blueprint",
    "ue_editor_status", "ue_level_control", "ue_material_params", "ue_pie_control",
    "ue_policy_explain", "ue_viewport_capture",
  ]), JSON.stringify(namesStd));
  const stdTool = (n) => listStd.json.result.tools.find((t) => t.name === n);
  check("standard: ue_editor_status readOnlyHint=true (§5.0.4)", stdTool("ue_editor_status").annotations?.readOnlyHint === true);
  check("standard: ue_level_control readOnlyHint=false", stdTool("ue_level_control").annotations?.readOnlyHint === false);
  check("standard: no P2 tools", !namesStd.includes("ue_console_command") && !namesStd.includes("ue_python_exec"));
  check("every tool has inputSchema", listStd.json.result.tools.every((t) => t.inputSchema && t.inputSchema.type === "object"));
  check(
    "every tool has dual-shape outputSchema (success|failure union, 附录 A / 4248c955-A)",
    listStd.json.result.tools.every((t) => outputSchemaBranches(t) !== null),
  );
  const stOut = listStd.json.result.tools.find((t) => t.name === "ue_editor_status").outputSchema;

  // ---- tools/call success ----
  section("tools/call success (PROTO-04)");
  const call = await rpc(PORT, { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "ue_editor_status", arguments: {} } }, { headers: H });
  const sc = call.json?.result;
  check("status call 200, no top-level error", call.status === 200 && call.json.error === undefined);
  check("isError=false, structuredContent.ok=true", sc?.isError !== true && sc?.structuredContent?.ok === true);
  check("data has editor/level/selection/capabilities", ["editor", "level", "selection", "capabilities"].every((k) => k in (sc.structuredContent.data ?? {})), JSON.stringify(Object.keys(sc.structuredContent?.data ?? {})));
  check("meta requestId/durationMs/ueVersion", !!sc.structuredContent?.meta?.requestId && typeof sc.structuredContent?.meta?.durationMs === "number" && sc.structuredContent?.meta?.ueVersion === "5.4.4");
  check("data.policies.mode=standard (server-side)", sc.structuredContent.data.policies?.mode === "standard");
  {
    const v = validate(stOut, sc.structuredContent);
    check("status structuredContent validates against outputSchema (client-side)", v.valid, v.errors.join("; "));
  }
  check("content[0].type=text", sc.content?.[0]?.type === "text");

  // ---- protocol-layer errors ----
  section("protocol-layer errors (PROTO-05/06/10/11/12b/12c)");
  const badJson = await rpc(PORT, "{invalid", { headers: H });
  check("invalid JSON → 400 -32700 (PROTO-10)", badJson.status === 400 && badJson.json?.error?.code === -32700);
  const unknownMethod = await rpc(PORT, { jsonrpc: "2.0", id: 4, method: "foo/bar", params: {} }, { headers: H });
  check("unknown method → 404 -32601 (PROTO-11)", unknownMethod.status === 404 && unknownMethod.json?.error?.code === -32601);
  const envelopeErr = await rpc(PORT, { jsonrpc: "2.0", id: 5, method: "tools/call", params: { name: "ue_editor_status", arguments: ["not", "an", "object"] } }, { headers: H });
  check("arguments array → 400 -32602 INVALID_PARAMS (PROTO-12b)", envelopeErr.status === 400 && envelopeErr.json?.error?.code === -32602 && envelopeErr.json?.error?.data?.errorCode === "INVALID_PARAMS" && envelopeErr.json.result === undefined);
  const unknownTool = await rpc(PORT, { jsonrpc: "2.0", id: 6, method: "tools/call", params: { name: "ue_no_such_tool", arguments: {} } }, { headers: H });
  check("unknown tool → 400 -32602 (PROTO-12c)", unknownTool.status === 400 && unknownTool.json?.error?.code === -32602);
  const noSession = await rpc(PORT, { jsonrpc: "2.0", id: 7, method: "tools/list", params: {} });
  check("missing session → 400 (PROTO-05)", noSession.status === 400);
  const badSession = await rpc(PORT, { jsonrpc: "2.0", id: 8, method: "tools/list", params: {} }, { headers: { "Mcp-Session-Id": "00000000-0000-0000-0000-000000000000" } });
  check("unknown session → 404 -32001 (PROTO-06)", badSession.status === 404 && badSession.json?.error?.code === -32001 && String(badSession.json?.error?.message).includes("Session not found"));

  // ---- tool-layer errors ----
  section("tool-layer errors (PROTO-12 / TOOL-05c)");
  const badEnum = await rpc(PORT, { jsonrpc: "2.0", id: 9, method: "tools/call", params: { name: "ue_editor_status", arguments: { sections: ["nope"] } } }, { headers: H });
  const be = badEnum.json?.result;
  check("schema violation → 200 + isError (PROTO-12)", badEnum.status === 200 && badEnum.json?.error === undefined && be?.isError === true && be?.structuredContent?.ok === false);
  check("error.code=INVALID_ARGUMENT + issues[]", be?.structuredContent?.error?.code === "INVALID_ARGUMENT" && Array.isArray(be?.structuredContent?.error?.details?.issues) && be.structuredContent.error.details.issues.length > 0);
  check("content[0].text starts with 'INVALID_ARGUMENT: '", String(be?.content?.[0]?.text).startsWith("INVALID_ARGUMENT: "));
  {
    const v = validate(stOut, be?.structuredContent);
    check("INVALID_ARGUMENT structuredContent validates against outputSchema failure branch", v.valid, v.errors.join("; "));
  }

  const classNf = await rpc(PORT, { jsonrpc: "2.0", id: 10, method: "tools/call", params: { name: "ue_actor_query", arguments: { scope: "level", filter: { class: "NoSuchClassXYZ" } } } }, { headers: H });
  const cn = classNf.json?.result;
  check("CLASS_NOT_FOUND + details.className (TOOL-05c)", classNf.status === 200 && cn?.isError === true && cn?.structuredContent?.error?.code === "CLASS_NOT_FOUND" && cn?.structuredContent?.error?.details?.className === "NoSuchClassXYZ");

  // ---- P2 tools with full policy (same server? need new) ----
  section("policy matrix: read-only / full (PROTO-03 ①③⑤)");
  const PORT2 = 19002, PORT3 = 19003;
  const srv2 = spawnServer(["--transport", "http", "--port", String(PORT2), "--policy", "read-only"], env);
  const srv3 = spawnServer(["--transport", "http", "--port", String(PORT3), "--policy", "full", "--allow-console", "--allow-exec"], env);
  collectStderr(srv2); collectStderr(srv3);
  await waitHealth(PORT2);
  await waitHealth(PORT3);
  async function toolNames(port) {
    const i = await rpc(port, { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "smoke", version: "0" } } });
    const l = await rpc(port, { jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }, { headers: { "Mcp-Session-Id": i.sid } });
    return { sid: i.sid, tools: l.json.result.tools };
  }
  const ro = await toolNames(PORT2);
  const roNames = ro.tools.map((t) => t.name).sort();
  check("read-only = exactly 9 tools", roNames.length === 9 && JSON.stringify(roNames) === JSON.stringify([
    "ue_actor_query", "ue_asset_search", "ue_blueprint", "ue_editor_status",
    "ue_level_control", "ue_material_params", "ue_pie_control", "ue_policy_explain",
    "ue_viewport_capture",
  ]), JSON.stringify(roNames));
  const roLevel = ro.tools.find((t) => t.name === "ue_level_control");
  check("read-only ue_level_control action enum narrowed", JSON.stringify(roLevel.inputSchema.properties.action.enum) === JSON.stringify(["get_current", "list_dirty"]), JSON.stringify(roLevel.inputSchema.properties.action));
  const roMat = ro.tools.find((t) => t.name === "ue_material_params");
  check("read-only ue_material_params action enum narrowed", JSON.stringify(roMat.inputSchema.properties.action.enum) === JSON.stringify(["list", "get"]));
  const roBp = ro.tools.find((t) => t.name === "ue_blueprint");
  check("read-only ue_blueprint action enum narrowed", JSON.stringify(roBp.inputSchema.properties.action.enum) === JSON.stringify(["query"]));
  const roPie = ro.tools.find((t) => t.name === "ue_pie_control");
  check("read-only ue_pie_control action enum narrowed to status", JSON.stringify(roPie?.inputSchema?.properties?.action?.enum) === JSON.stringify(["status"]), JSON.stringify(roPie?.inputSchema?.properties?.action));
  check("read-only ue_pie_control readOnlyHint=true (status only)", roPie?.annotations?.readOnlyHint === true);
  check("read-only mixed tools readOnlyHint=true/destructiveHint=false", ["ue_level_control", "ue_material_params", "ue_blueprint"].every((n) => ro.tools.find((t) => t.name === n).annotations.readOnlyHint === true && ro.tools.find((t) => t.name === n).annotations.destructiveHint === false));
  check("read-only every tool has dual-shape outputSchema", ro.tools.every((t) => outputSchemaBranches(t) !== null));

  const full = await toolNames(PORT3);
  const fullNames = full.tools.map((t) => t.name).sort();
  check("full + both switches = exactly 12 tools", fullNames.length === 12 && fullNames.includes("ue_console_command") && fullNames.includes("ue_python_exec"));
  check("ue_policy_explain visible in read-only, standard and full", [roNames, namesStd, fullNames].every((n) => n.includes("ue_policy_explain")), JSON.stringify({ ro: roNames.includes("ue_policy_explain"), std: namesStd.includes("ue_policy_explain"), full: fullNames.includes("ue_policy_explain") }));

  // SEC-01: hidden tool direct call
  const roEdit = await rpc(PORT2, { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "ue_actor_edit", arguments: { operations: [{ op: "spawn", class: "StaticMeshActor" }] } } }, { headers: { "Mcp-Session-Id": ro.sid } });
  const roe = roEdit.json?.result;
  check("read-only ue_actor_edit → TOOL_DISABLED gate=server.policy (SEC-01b)", roEdit.status === 200 && roe?.structuredContent?.error?.code === "TOOL_DISABLED" && roe?.structuredContent?.error?.details?.gate === "server.policy");
  const roExec = await rpc(PORT2, { jsonrpc: "2.0", id: 4, method: "tools/call", params: { name: "ue_python_exec", arguments: { code: "1+1", mode: "eval" } } }, { headers: { "Mcp-Session-Id": ro.sid } });
  const rox = roExec.json?.result;
  check("read-only ue_python_exec → TOOL_DISABLED gate=server.allowExec (SEC-01c)", roExec.status === 200 && rox?.structuredContent?.error?.code === "TOOL_DISABLED" && rox?.structuredContent?.error?.details?.gate === "server.allowExec");
  const roSave = await rpc(PORT2, { jsonrpc: "2.0", id: 5, method: "tools/call", params: { name: "ue_level_control", arguments: { action: "save_current" } } }, { headers: { "Mcp-Session-Id": ro.sid } });
  const ros = roSave.json?.result;
  check("read-only save_current → INVALID_ARGUMENT (SEC-01d)", roSave.status === 200 && ros?.structuredContent?.error?.code === "INVALID_ARGUMENT");
  {
    const v = validate(ro.tools.find((t) => t.name === "ue_level_control").outputSchema, ros?.structuredContent);
    check("read-only INVALID_ARGUMENT error validates against failure branch", v.valid, v.errors.join("; "));
  }

  // ---- P2 exec path with mock bridge (deny-exec default) ----
  section("P2 tools via bridge (SEC-11 / TOOL-32)");
  const execDenied = await rpc(PORT3, { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "ue_python_exec", arguments: { code: "1+1", mode: "eval" } } }, { headers: { "Mcp-Session-Id": full.sid } });
  const exd = execDenied.json?.result;
  check("bridge allowExec=false → EXEC_DISABLED gate=bridge.allowExec (SEC-11)", execDenied.status === 200 && exd?.structuredContent?.error?.code === "EXEC_DISABLED" && exd?.structuredContent?.error?.details?.gate === "bridge.allowExec");
  const consoleDenied = await rpc(PORT3, { jsonrpc: "2.0", id: 4, method: "tools/call", params: { name: "ue_console_command", arguments: { command: "stat fps" } } }, { headers: { "Mcp-Session-Id": full.sid } });
  const ccd = consoleDenied.json?.result;
  check("bridge allowConsole=false → PERMISSION_DENIED gate=bridge.allowConsole (SEC-11c)", consoleDenied.status === 200 && ccd?.structuredContent?.error?.code === "PERMISSION_DENIED" && ccd?.structuredContent?.error?.details?.gate === "bridge.allowConsole");

  // spawn allow-all bridge on second port and point server3 at it
  const PORT4 = 19004;
  const bridge2Out = [];
  const bridge2 = spawn(process.execPath, [MOCK, "--port", "0", "--home", home, "--allow-write", "--allow-exec", "--allow-console"], { stdio: ["ignore", "pipe", "pipe"] });
  smokeChildren.add(bridge2);
  bridge2.stdout.on("data", (c) => bridge2Out.push(c.toString()));
  let bridge2Info;
  for (let i = 0; i < 50 && !bridge2Info; i++) {
    await sleep(100);
    const line = bridge2Out.join("").split("\n").find((l) => l.trim().startsWith("{"));
    if (line) { try { bridge2Info = JSON.parse(line); } catch { /* wait */ } }
  }
  const PORT5 = 19005;
  const srv5 = spawnServer(["--transport", "http", "--port", String(PORT5), "--policy", "full", "--allow-console", "--allow-exec", "--bridge-url", `http://127.0.0.1:${bridge2Info.port}`, "--bridge-token", bridge2Info.token], env);
  collectStderr(srv5);
  await waitHealth(PORT5);
  const i5 = await rpc(PORT5, { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "smoke", version: "0" } } });
  const H5 = { "Mcp-Session-Id": i5.sid };
  const execOk = await rpc(PORT5, { jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "ue_python_exec", arguments: { code: "1+1", mode: "eval" } } }, { headers: H5 });
  check("python eval 1+1 → result=2 (TOOL-32)", execOk.json?.result?.structuredContent?.data?.result === 2 && execOk.json?.result?.isError !== true);
  check("python exec: timeoutMsReceived=10000 (m-3 schema default flows through)", execOk.json?.result?.structuredContent?.data?.timeoutMsReceived === 10000, JSON.stringify(execOk.json?.result?.structuredContent?.data));
  {
    const v = validate(full.tools.find((t) => t.name === "ue_python_exec").outputSchema, execOk.json?.result?.structuredContent);
    check("python exec structuredContent validates against outputSchema success branch", v.valid, v.errors.join("; "));
  }
  const cmdDenied = await rpc(PORT5, { jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "ue_console_command", arguments: { command: "quit" } } }, { headers: H5 });
  check("console 'quit' → COMMAND_NOT_ALLOWED (TOOL-31)", cmdDenied.json?.result?.structuredContent?.error?.code === "COMMAND_NOT_ALLOWED");
  {
    const v = validate(full.tools.find((t) => t.name === "ue_console_command").outputSchema, cmdDenied.json?.result?.structuredContent);
    check("COMMAND_NOT_ALLOWED error validates against failure branch", v.valid, v.errors.join("; "));
  }
  const cmdOk = await rpc(PORT5, { jsonrpc: "2.0", id: 4, method: "tools/call", params: { name: "ue_console_command", arguments: { command: "stat fps" } } }, { headers: H5 });
  const cdo = cmdOk.json?.result;
  check("console 'stat fps' dispatched, outputAvailable=false", cdo?.structuredContent?.data?.dispatched === true && cdo?.structuredContent?.data?.outputAvailable === false);

  // ---- viewport.capture: Server 读文件编码内联 / 超 8MiB 降级 (TOOL-26) ----
  section("viewport.capture inline & fallback (TOOL-26)");
  const capSmall = await rpc(PORT5, { jsonrpc: "2.0", id: 5, method: "tools/call", params: { name: "ue_viewport_capture", arguments: { target: "level_viewport", width: 640, height: 480, format: "png", returnMode: "image" } } }, { headers: H5 });
  const cs = capSmall.json?.result;
  const imgBlock = cs?.content?.find((c) => c.type === "image");
  check(
    "small PNG → image content block (base64, image/png)",
    capSmall.status === 200 && cs?.isError !== true && !!imgBlock && imgBlock.mimeType === "image/png" && typeof imgBlock.data === "string" && imgBlock.data.length > 0,
    capSmall.text.slice(0, 200),
  );
  check(
    "small PNG: base64 decodes to non-empty PNG bytes",
    (() => { try { const b = Buffer.from(imgBlock?.data ?? "", "base64"); return b.length > 8 && b.subarray(0, 4).toString("hex") === "89504e47"; } catch { return false; } })(),
  );
  check("small PNG: data.path returned in structuredContent", typeof cs?.structuredContent?.data?.path === "string" && cs.structuredContent.data.path.length > 0);
  const capBig = await rpc(PORT5, { jsonrpc: "2.0", id: 6, method: "tools/call", params: { name: "ue_viewport_capture", arguments: { target: "level_viewport", width: 7680, height: 4320, format: "png", returnMode: "image" } } }, { headers: H5 });
  const cb = capBig.json?.result;
  check(
    ">8MiB → no image block + warning IMAGE_TOO_LARGE_FOR_INLINE, still ok",
    capBig.status === 200 && cb?.isError !== true && !cb?.content?.some((c) => c.type === "image") && (cb?.structuredContent?.warnings ?? []).includes("IMAGE_TOO_LARGE_FOR_INLINE") && typeof cb?.structuredContent?.data?.path === "string",
    capBig.text.slice(0, 200),
  );

  // ---- --project discovery（Critical-2）----
  section("--project discovery (Critical-2)");
  const PORT6 = 19006, PORT7 = 19007, PORT8 = 19008;
  const PROJ = "UEMCP-TestProject"; // mock bridge 写发现文件用的 projectDir
  const projectServers = [];
  async function probeProject(port, projectDir) {
    const s = spawnServer(["--transport", "http", "--port", String(port), "--policy", "standard", "--project", projectDir], env);
    projectServers.push(s); // 必须清理：持有输出管道会阻塞上游 tail/EOF
    collectStderr(s);
    await waitHealth(port);
    const i = await rpc(port, { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "smoke", version: "0" } } });
    const c = await rpc(port, { jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "ue_editor_status", arguments: {} } }, { headers: { "Mcp-Session-Id": i.sid } });
    return { health: await (await fetch(`http://127.0.0.1:${port}/health`)).json(), call: c };
  }
  const projTail = await probeProject(PORT6, PROJ + "/");
  check(
    "--project with trailing slash discovers bridge (normalizeProjectDir)",
    projTail.health.bridge.connected === true && projTail.call.json?.result?.structuredContent?.ok === true,
    JSON.stringify(projTail.health.bridge),
  );
  const projCase = await probeProject(PORT8, PROJ.toLowerCase());
  check(
    "--project case-insensitive match (content compare)",
    projCase.health.bridge.connected === true && projCase.call.json?.result?.structuredContent?.ok === true,
    JSON.stringify(projCase.health.bridge),
  );
  // 不匹配工程：必须硬失败 BRIDGE_UNAVAILABLE，不得回退到 ~/.uemcp/bridge.json（home 里存在且指向活着的 mock bridge）
  const projBad = await probeProject(PORT7, "C:/Some/Other/Project");
  const pb = projBad.call.json?.result;
  check(
    "--project mismatch → hard fail BRIDGE_UNAVAILABLE, no fallback to bridge.json",
    projBad.call.status === 200 && pb?.structuredContent?.error?.code === "BRIDGE_UNAVAILABLE" && projBad.health.bridge.connected === false,
    projBad.call.text.slice(0, 200),
  );

  // ---- Host / Origin ----
  section("Host/Origin validation (SEC-04/05)");
  // fetch 禁止覆盖 Host 头，用 node:http 原始请求
  const hostBad = await new Promise((resolve) => {
    const req = httpRequest(
      { host: "127.0.0.1", port: PORT, path: "/health", headers: { Host: "evil.example.com" }, method: "GET" },
      (res) => {
        let t = "";
        res.on("data", (c) => (t += c));
        res.on("end", () => resolve({ status: res.statusCode, text: t }));
      },
    );
    req.on("error", () => resolve({ status: 0, text: "" }));
    req.end();
  });
  check(
    "bad Host → 421 INVALID_REQUEST (SEC-04)",
    hostBad.status === 421 && JSON.parse(hostBad.text).error?.data?.errorCode === "INVALID_REQUEST",
    `status=${hostBad.status} body=${hostBad.text.slice(0, 120)}`,
  );
  const originBad = await fetch(`http://127.0.0.1:${PORT}/mcp`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", Origin: "http://evil.example.com" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "x", version: "0" } } }),
  });
  check("bad Origin → 403 (SEC-05)", originBad.status === 403);

  // ---- 速率限制（Major-6 / SEC-14）----
  section("rate limit (Major-6 / SEC-14)");
  {
    const i = await rpc(PORT, { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "smoke", version: "0" } } });
    const hs = { "Mcp-Session-Id": i.sid };
    const codes = [];
    // 并发突发，确保超过突发桶 40 且期间补充的令牌不足以吸收
    const burst = await Promise.all(
      Array.from({ length: 100 }, (_, n) =>
        rpc(PORT, { jsonrpc: "2.0", id: n + 10, method: "tools/list", params: {} }, { headers: hs }),
      ),
    );
    for (const r of burst) codes.push({ status: r.status, json: r.json });
    const limited = codes.filter((c) => c.status === 429);
    check(
      "burst > 40 → some 429, protocol-layer shape (no result, -32012 RATE_LIMITED)",
      limited.length > 0 && limited.every((c) => c.json?.error?.code === -32012 && c.json?.error?.data?.errorCode === "RATE_LIMITED" && c.json.result === undefined),
      `429 count=${limited.length}`,
    );
    check("pre-limit requests still 200", codes[0].status === 200 && codes[39].status === 200);
    await sleep(1300); // 20/s 恢复
    const recovered = await rpc(PORT, { jsonrpc: "2.0", id: 99, method: "tools/list", params: {} }, { headers: hs });
    check("recovers after backoff", recovered.status === 200, `status=${recovered.status}`);
  }

  // ---- DELETE session ----
  section("DELETE /mcp (PROTO-07)");
  const del = await fetch(`http://127.0.0.1:${PORT}/mcp`, { method: "DELETE", headers: { "Mcp-Session-Id": SID } });
  check("DELETE → 204", del.status === 204);
  const afterDel = await rpc(PORT, { jsonrpc: "2.0", id: 20, method: "tools/list", params: {} }, { headers: H });
  check("session gone → 404 -32001", afterDel.status === 404 && afterDel.json?.error?.code === -32001);

  // ---- audit ----
  section("audit log (SEC-12 spot check)");
  const auditDir = join(home, "audit");
  await sleep(200);
  let auditLines = "";
  if (existsSync(auditDir)) {
    for (const f of readdirSync(auditDir)) auditLines += readFileSync(join(auditDir, f), "utf8");
  }
  const hasExecRecord = auditLines.split("\n").some((l) => { try { const j = JSON.parse(l); return j.tool === "ue_python_exec" && j.argsSummary?.codeSha256 && !l.includes("1+1"); } catch { return false; } });
  check("P2 exec audited with codeSha256, no source text", hasExecRecord, auditLines.slice(0, 200));
  check("audit has no token", !auditLines.includes(bridgeInfo.token) && !auditLines.includes(bridge2Info.token));

  // ---- bridge unavailable ----
  section("bridge unavailable (RES-03)");
  bridge2.kill();
  bridge.kill();
  await sleep(6200); // 等 watchdog 下线 + 缓存失效
  const unavailable = await rpc(PORT5, { jsonrpc: "2.0", id: 5, method: "tools/call", params: { name: "ue_editor_status", arguments: {} } }, { headers: H5 });
  const un = unavailable.json?.result;
  check("bridge down → BRIDGE_UNAVAILABLE retryable (RES-03)", unavailable.status === 200 && un?.isError === true && un?.structuredContent?.error?.code === "BRIDGE_UNAVAILABLE" && un?.structuredContent?.error?.retryable === true, unavailable.text.slice(0, 200));
  {
    const v = validate(stOut, un?.structuredContent);
    check("BRIDGE_UNAVAILABLE error validates against failure branch", v.valid, v.errors.join("; "));
  }
  const healthAlive = await fetch(`http://127.0.0.1:${PORT5}/health`);
  check("server still alive after bridge loss", healthAlive.status === 200 && (await healthAlive.json()).ok === true);

  // ---- port conflict exit 2 ----
  section("port conflict exit 2 (RES-06)");
  const conflict = await new Promise((resolve) => {
    const child = spawnServer(["--transport", "http", "--port", String(PORT), "--policy", "read-only"], env);
    const err = collectStderr(child);
    const t0 = Date.now();
    child.on("exit", (code) => resolve({ code, err: err.join(""), ms: Date.now() - t0 }));
  });
  check("EADDRINUSE → exit code 2", conflict.code === 2, `code=${conflict.code} err=${conflict.err.slice(0, 200)}`);
  check("stderr has http_bind_failed JSON (§2.3)", (() => { const line = conflict.err.split("\n").find((l) => l.includes("http_bind_failed")); if (!line) return false; try { const j = JSON.parse(line); return j.event === "http_bind_failed" && j.port === PORT && j.code === "EADDRINUSE"; } catch { return false; } })());
  check("exit within 2s", conflict.ms < 2000, `${conflict.ms}ms`);

  // ---- stdio ----
  section("stdio transport (PROTO-16)");
  const stdioResult = await new Promise((resolve) => {
    const child = spawnServer(["--transport", "stdio", "--policy", "standard"], env);
    let out = "", errOut = "";
    child.stdout.on("data", (c) => (out += c.toString()));
    child.stderr.on("data", (c) => (errOut += c.toString()));
    const lines = [
      JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "smoke", version: "0" } } }),
      JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
      JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }),
    ];
    for (const l of lines) child.stdin.write(l + "\n");
    const finish = () => resolve({ out, errOut });
    const timer = setTimeout(() => {
      child.kill();
      finish();
    }, 8000);
    child.on("exit", () => {
      clearTimeout(timer);
      finish();
    });
    // 收到两个响应后优雅结束 stdin，让进程自然退出（避免 Windows 上 kill 触发 libuv 断言）
    const maybeDone = () => {
      const parsed = out.split("\n").filter((l) => l.trim());
      if (parsed.length >= 2) child.stdin.end();
    };
    child.stdout.on("data", maybeDone);
  });
  const stdioLines = stdioResult.out.split("\n").filter((l) => l.trim());
  check("stdio stdout: every line valid JSON-RPC (PROTO-16)", stdioLines.length >= 2 && stdioLines.every((l) => { try { const j = JSON.parse(l); return j.jsonrpc === "2.0"; } catch { return false; } }), stdioResult.out.slice(0, 200));
  const stdioTools = (() => { for (const l of stdioLines) { try { const j = JSON.parse(l); if (j.id === 2) return j.result?.tools?.length; } catch { /* skip */ } } return undefined; })();
  check("stdio tools/list = 10 (standard)", stdioTools === 10, `got ${stdioTools}`);
  check("stdio stderr has JSON log", (() => stdioResult.errOut.split("\n").some((l) => { try { const j = JSON.parse(l); return typeof j.event === "string"; } catch { return false; } }))());

  // ---- cleanup ----
  for (const s of [srv, srv2, srv3, srv5, ...projectServers]) s.kill();
  for (const s of [srv, srv2, srv3, srv5]) {
    s.stdout?.removeAllListeners?.();
  }
}
// 临时 HOME 的最终删除与结果汇总在 main() 的 finally 之后（DEF-2）。

main().catch((e) => {
  console.error("SMOKE CRASH:", e);
  process.exit(2);
});
