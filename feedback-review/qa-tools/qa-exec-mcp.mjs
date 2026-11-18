#!/usr/bin/env node
// QA exec tool (task cc433d95, supervisor q3 authorization). NOT product code; feedback-review/qa-tools/ only.
// Minimal MCP client over stdio against the REAL TS server (packages/server/dist/index.js).
// usage: node qa-exec-mcp.mjs --policy standard|full [--allow-gates] [--out transcript.jsonl] <cases.json>
// cases.json = array of {call:"initialize"|"tools/list"|"tools/call", name?, args?, elicitation?:"accept"|"decline"}
// Server->client requests supported: elicitation/create (answered per case elicitation mode), ping.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const REPO = "C:\\UE5_P\\5.4\\UEMCP";
const SERVER = path.join(REPO, "uemcp", "packages", "server", "dist", "index.js");

function arg(name, dflt) {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : dflt;
}
const policy = arg("--policy", "standard");
const allowGates = process.argv.includes("--allow-gates");
const out = arg("--out", path.join(REPO, "feedback-review", "logs", "qasmoke-exec-mcp-transcript-" + Date.now() + ".jsonl"));
const casesFile = process.argv[process.argv.length - 1];
if (!casesFile || casesFile.startsWith("--")) {
  console.error("missing cases.json path");
  process.exit(2);
}
const cases = JSON.parse(fs.readFileSync(casesFile, "utf8"));
const fh = fs.openSync(out, "w");
function transcript(dir, msg) {
  fs.writeSync(fh, JSON.stringify({ ts: new Date().toISOString(), dir, msg }) + "\n");
}

const serverArgs = [SERVER, "--transport", "stdio", "--policy", policy];
if (allowGates) serverArgs.push("--allow-console", "--allow-exec");
const child = spawn(process.execPath, serverArgs, { stdio: ["pipe", "pipe", "pipe"] });
let stderrBuf = "";
child.stderr.on("data", (d) => { stderrBuf += d.toString(); });

let nextId = 1;
const pending = new Map(); // id -> {resolve, reject}
const serverRequests = []; // queued server reqs (elicitation) awaiting current case mode
let currentElicitMode = "accept";
let buf = "";

child.stdout.on("data", (d) => {
  buf += d.toString("utf8");
  let idx;
  while ((idx = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, idx).trim();
    buf = buf.slice(idx + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { transcript("recv-raw", line); continue; }
    transcript("recv", msg);
    if (msg.id !== undefined && msg.method) {
      handleServerRequest(msg);
      continue;
    }
    if (msg.id !== undefined && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      p.resolve(msg);
    }
  }
});

function handleServerRequest(msg) {
  if (msg.method === "ping") {
    const resp = { jsonrpc: "2.0", id: msg.id, result: {} };
    transcript("send", resp);
    child.stdin.write(JSON.stringify(resp) + "\n");
    return;
  }
  if (msg.method === "elicitation/create") {
    const action = currentElicitMode === "accept" ? "accept" : "decline";
    const resp = action === "accept"
      ? { jsonrpc: "2.0", id: msg.id, result: { action, content: {} } }
      : { jsonrpc: "2.0", id: msg.id, result: { action } };
    transcript("send", resp);
    child.stdin.write(JSON.stringify(resp) + "\n");
    serverRequests.push({ msg, resp });
    return;
  }
  const resp = { jsonrpc: "2.0", id: msg.id, error: { code: -32601, message: "qa client: unsupported server request " + msg.method } };
  transcript("send", resp);
  child.stdin.write(JSON.stringify(resp) + "\n");
}

function send(method, params, id) {
  const msg = { jsonrpc: "2.0", id, method, params };
  transcript("send", msg);
  child.stdin.write(JSON.stringify(msg) + "\n");
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error("timeout waiting for " + method + " id=" + id)); } }, 120000);
  });
}

child.on("exit", (code) => { transcript("server-exit", { code, stderrTail: stderrBuf.slice(-1500) }); });

(async () => {
  const results = [];
  for (const c of cases) {
    if (c.call === "initialize") {
      const id = nextId++;
      const r = await send("initialize", {
        protocolVersion: "2025-06-18",
        capabilities: { elicitation: {} },
        clientInfo: { name: "qa-exec-mcp-client", version: "0.0.0" },
      }, id);
      results.push({ call: "initialize", result: r.result });
      const nt = { jsonrpc: "2.0", method: "notifications/initialized" };
      transcript("send", nt);
      child.stdin.write(JSON.stringify(nt) + "\n");
    } else if (c.call === "tools/list") {
      const id = nextId++;
      const r = await send("tools/list", {}, id);
      const names = (r.result && r.result.tools ? r.result.tools : []).map((t) => t.name);
      results.push({ call: "tools/list", count: names.length, names });
    } else if (c.call === "tools/call") {
      currentElicitMode = c.elicitation || "accept";
      serverRequests.length = 0;
      const id = nextId++;
      const t0 = Date.now();
      const r = await send("tools/call", { name: c.name, arguments: c.args || {} }, id);
      results.push({
        call: "tools/call",
        name: c.name,
        args: c.args || {},
        elicitationMode: currentElicitMode,
        isError: r.result ? !!r.result.isError : null,
        contentText: r.result && r.result.content && r.result.content[0] ? String(r.result.content[0].text).slice(0, 800) : null,
        error: r.error || null,
        serverElicitations: serverRequests.map((s) => ({ params: s.msg.params, answered: s.resp.result })),
        durationMs: Date.now() - t0,
      });
    } else {
      results.push({ call: c.call, skipped: "unknown" });
    }
  }
  fs.writeFileSync(out + ".summary.json", JSON.stringify({ policy, allowGates, startedCases: cases.length, results }, null, 2), "utf8");
  console.log(JSON.stringify({ transcript: out, cases: results.length, lastError: results.filter((r) => r.error).length }));
  child.stdin.end();
  child.kill();
  process.exit(0);
})().catch((e) => {
  transcript("fatal", { error: e.message });
  console.error("QA-EXEC-MCP ERROR: " + e.message + " stderrTail=" + stderrBuf.slice(-800));
  try { child.kill(); } catch {}
  process.exit(1);
});
