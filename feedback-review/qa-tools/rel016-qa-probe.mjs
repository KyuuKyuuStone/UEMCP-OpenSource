// rel016-qa-probe.mjs — 同次会话内 server 侧 initialize + 桥侧往返实测探针
// 用法: node rel016-qa-probe.mjs <serverEntry>
// 输出: RAW_INITIALIZE / RAW_TOOLS_CALL / 提取行 / PROBE_RESULT
import { spawn } from "node:child_process";

const entry = process.argv[2];
if (!entry) { console.log("USAGE: node rel016-qa-probe.mjs <dist/index.js>"); process.exit(2); }

const child = spawn(process.execPath, [entry, "--transport", "stdio"], { stdio: ["pipe", "pipe", "pipe"] });
const send = (o) => child.stdin.write(JSON.stringify(o) + "\n");

const pending = new Map();
let nextId = 1;
function rpc(method, params, timeoutMs = 30000) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`TIMEOUT waiting ${method}`)), timeoutMs);
    pending.set(id, { resolve, reject, t });
    send({ jsonrpc: "2.0", id, method, params });
  });
}

let buf = "";
child.stdout.on("data", (d) => {
  buf += d.toString();
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    let msg; try { msg = JSON.parse(line); } catch { console.log("NONJSON: " + line); continue; }
    console.log("RAW_STDOUT: " + line);
    if (msg.id != null && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      clearTimeout(p.t); pending.delete(msg.id);
      p.resolve(msg);
    }
  }
});
child.stderr.on("data", (d) => process.stderr.write("[server stderr] " + d));

const fail = (code, why) => { console.log("PROBE_RESULT FAIL " + why); child.kill(); process.exit(code); };

try {
  const init = await rpc("initialize", {
    protocolVersion: "2025-03-26",
    capabilities: {},
    clientInfo: { name: "rel016-qa-probe", version: "0.0.1" },
  }, 20000);
  const si = init.result?.serverInfo ?? {};
  console.log(`serverInfo.name    = ${si.name}`);
  console.log(`serverInfo.version = ${si.version}`);
  console.log(`protocolVersion    = ${init.result?.protocolVersion}`);
  send({ jsonrpc: "2.0", method: "notifications/initialized" });

  await rpc("tools/list", {}, 20000); // policy default read-only -> 13 tools, log line above

  const call = await rpc("tools/call", { name: "ue_editor_status", arguments: { sections: ["editor", "policies"] } }, 60000);
  const full = JSON.stringify(call.result ?? {}) + "\n" + (call.result?.content ?? []).map((c) => c.text ?? "").join("\n");
  const m = full.match(/"pluginVersion"\s*:\s*"([^"]+)"/);
  console.log(`tools_call.isError = ${call.result?.isError ?? false}`);
  console.log(`pluginVersion(from ue_editor_status via live bridge) = ${m ? m[1] : "NOT-FOUND"}`);

  const bridgeInText = !!(m && m[1] === "0.1.6");
  const ok = si.version === "0.1.6" && (call.result?.isError !== true);
  console.log("PROBE_RESULT " + (ok ? "PASS serverInfo=0.1.6 roundtrip-live" : "FAIL see lines above")
    + " | pluginVersion-in-tool-text=" + bridgeInText);
  child.stdin.end();
  child.kill();
  process.exit(ok ? 0 : 3);
} catch (e) {
  fail(4, e.message);
}
