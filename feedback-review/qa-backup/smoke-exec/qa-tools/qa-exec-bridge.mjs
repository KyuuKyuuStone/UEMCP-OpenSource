#!/usr/bin/env node
// QA exec tool (task cc433d95). NOT product code; lives in feedback-review/qa-tools/.
// usage:
//   node qa-exec-bridge.mjs health
//   node qa-exec-bridge.mjs rpc <method> '<json-params>' [--id N] [--out file.json]
// Reads bridge port/token from ~/.uemcp/bridges/*.json (most recent). Emits one-line summary to stdout.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");

function findBridge() {
  const dir = path.join(os.homedir(), ".uemcp", "bridges");
  let files = [];
  try {
    files = fs.readdirSync(dir).filter((f) => f.endsWith(".json"));
  } catch {
    throw new Error("no bridges dir");
  }
  const recs = files
    .map((f) => {
      const p = path.join(dir, f);
      try {
        const r = JSON.parse(fs.readFileSync(p, "utf8"));
        r.__file = p;
        r.__mtime = fs.statSync(p).mtimeMs;
        return r;
      } catch {
        return null;
      }
    })
    .filter((r) => r && r.port && r.token)
    .sort((a, b) => b.__mtime - a.__mtime);
  if (!recs.length) throw new Error("no usable bridge discovery record");
  return recs[0];
}

function post(port, token, body, timeoutMs) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const req = http.request(
      {
        host: "127.0.0.1",
        port,
        path: "/rpc",
        method: "POST",
        timeout: timeoutMs || 60000,
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(data),
          "X-UEMCP-Token": token,
        },
      },
      (res) => {
        let buf = "";
        res.on("data", (c) => (buf += c));
        res.on("end", () => {
          let parsed = null;
          try {
            parsed = JSON.parse(buf);
          } catch {
            parsed = { raw: buf.slice(0, 2000) };
          }
          resolve({ status: res.statusCode, body: parsed });
        });
      }
    );
    req.on("timeout", () => {
      req.destroy(new Error("client-timeout"));
    });
    req.on("error", reject);
    req.end(data);
  });
}

function getJson(port, token, p, timeoutMs) {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        host: "127.0.0.1",
        port,
        path: p,
        method: "GET",
        timeout: timeoutMs || 10000,
        headers: { "X-UEMCP-Token": token },
      },
      (res) => {
        let buf = "";
        res.on("data", (c) => (buf += c));
        res.on("end", () => {
          let parsed = null;
          try {
            parsed = JSON.parse(buf);
          } catch {
            parsed = { raw: buf.slice(0, 2000) };
          }
          resolve({ status: res.statusCode, body: parsed });
        });
      }
    );
    req.on("error", reject);
    req.end();
  });
}

(async () => {
  const argv = process.argv.slice(2);
  const cmd = argv[0];
  const bridge = findBridge();
  if (cmd === "health") {
    const r = await getJson(bridge.port, bridge.token, "/health", 10000);
    const keys = Object.keys(r.body).sort();
    console.log(JSON.stringify({ ok: r.status === 200, status: r.status, keyCount: keys.length, keys, body: r.body }, null, 1));
    return;
  }
  if (cmd === "rpc") {
    const method = argv[1];
    let params = argv[2] && argv[2] !== "--params-file" ? JSON.parse(argv[2]) : {};
    const pf = argv.indexOf("--params-file");
    if (pf > 0) params = JSON.parse(fs.readFileSync(argv[pf + 1], "utf8"));
    let id = 1000 + Math.floor(Math.random() * 9000);
    let out = null;
    const iIdx = argv.indexOf("--id");
    if (iIdx > 0) id = parseInt(argv[iIdx + 1], 10);
    const oIdx = argv.indexOf("--out");
    if (oIdx > 0) out = argv[oIdx + 1];
    let tIdx = argv.indexOf("--timeout");
    const timeoutMs = tIdx > 0 ? parseInt(argv[tIdx + 1], 10) : 90000;
    const t0 = Date.now();
    const r = await post(bridge.port, bridge.token, { jsonrpc: "2.0", id, method, params }, timeoutMs);
    const dur = Date.now() - t0;
    const rec = {
      ts: new Date().toISOString(),
      tool: "qa-exec-bridge",
      bridgePort: bridge.port,
      projectDir: bridge.projectDir || null,
      request: { jsonrpc: "2.0", id, method, params },
      httpStatus: r.status,
      response: r.body,
      durationMs: dur,
    };
    if (out) fs.writeFileSync(out, JSON.stringify(rec, null, 2), "utf8");
    const err = r.body && r.body.error;
    console.log(
      JSON.stringify({
        method,
        id,
        http: r.status,
        ok: r.status === 200 && !err,
        rpcCode: err ? err.code : null,
        errorCode: err && err.data ? err.data.errorCode : null,
        retryable: err && err.data ? err.data.retryable : null,
        origin: err && err.data && err.data.details ? err.data.details.origin : null,
        stage: err && err.data && err.data.details ? err.data.details.stage : null,
        durationMs: dur,
        out,
      })
    );
    return;
  }
  console.error("unknown cmd: " + cmd);
  process.exit(2);
})().catch((e) => {
  console.error("QA-EXEC-BRIDGE ERROR: " + e.message);
  process.exit(1);
});
