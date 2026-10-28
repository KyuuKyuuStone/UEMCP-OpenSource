/**
 * SDK 客户端端到端验证（任务 4248c955-A 验收）：
 * 用真正的 MCP SDK Client（自带 AjvJsonSchemaValidator，callTool 时对存在的
 * structuredContent 按 tools/list 的 outputSchema 校验，含 isError=true 的结果）
 * 连接构建产物 + mock bridge，实测成功路径与错误路径都不被客户端校验打回。
 * 运行：pnpm --filter @uemcp/server verify:sdk（需要先 pnpm build）
 */
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const SERVER = join(HERE, "..", "dist", "index.js"); // packages/server/dist
const MOCK = join(HERE, "..", "..", "..", "scripts", "mock-bridge.mjs"); // uemcp/scripts
const PORT = 19200;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitHealth(port, timeoutMs = 10000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`);
      if (res.ok) return await res.json();
    } catch { /* not yet */ }
    await sleep(150);
  }
  throw new Error(`server on ${port} did not become healthy`);
}

// 手动累积 stdout（waitStdoutJson 里无法回读，用事件补齐）
function collect(child) {
  const chunks = [];
  child.stdout.on("data", (c) => chunks.push(c.toString()));
  return () => chunks.join("");
}

async function main() {
  const home = mkdtempSync(join(tmpdir(), "uemcp-sdkverify-"));
  const env = {
    ...process.env,
    USERPROFILE: home,
    UEMCP_AUDIT_DIR: join(home, "audit"),
    UEMCP_BRIDGE_PORT: "18999",
  };

  const bridge = spawn(process.execPath, [MOCK, "--port", "0", "--home", home, "--allow-write", "--allow-exec", "--allow-console"], { stdio: ["ignore", "pipe", "pipe"] });
  bridge.on("error", (e) => console.error("bridge spawn error:", e.message));
  const bridgeOut = collect(bridge);
  let bridgeInfo = null;
  for (let i = 0; i < 50 && !bridgeInfo; i++) {
    await sleep(100);
    const line = bridgeOut().split("\n").find((l) => l.trim().startsWith("{"));
    if (line) bridgeInfo = JSON.parse(line);
  }
  if (!bridgeInfo) throw new Error("mock bridge did not start");

  const srv = spawn(process.execPath, [SERVER, "--transport", "http", "--port", String(PORT), "--policy", "full", "--allow-console", "--allow-exec", "--bridge-url", `http://127.0.0.1:${bridgeInfo.port}`, "--bridge-token", bridgeInfo.token], { env, stdio: ["ignore", "ignore", "pipe"] });
  const srvErr = [];
  srv.stderr.on("data", (c) => srvErr.push(c.toString()));
  try {
    await waitHealth(PORT);
    const transport = new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${PORT}/mcp`));
    const client = new Client({ name: "sdk-verify", version: "0.0.0" });
    await client.connect(transport);

    const { tools } = await client.listTools(); // 缓存 outputSchema 校验器
    console.log(`tools/list: ${tools.length} tools, all with outputSchema=${tools.every((t) => !!t.outputSchema)}`);
    if (tools.length !== 10 || !tools.every((t) => !!t.outputSchema)) {
      throw new Error("expected 10 tools each with outputSchema");
    }

    // 成功路径 ×10：任一 structuredContent 不匹配 outputSchema → callTool 抛 McpError
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
    ];
    for (const [name, args] of successes) {
      const r = await client.callTool({ name, arguments: args });
      if (r.isError === true) throw new Error(`${name}: expected success, got isError=true`);
      if (!r.structuredContent?.ok) throw new Error(`${name}: expected structuredContent.ok=true`);
      console.log(`PASS  success ${name} (client-side outputSchema validation did not reject)`);
    }

    // 错误路径 ×3：isError=true 且 structuredContent 存在 → SDK 同样校验 → 必须匹配失败分支
    const failures = [
      ["ue_editor_status", { sections: ["nope"] }, "INVALID_ARGUMENT"],
      ["ue_actor_query", { filter: { class: "FooBar" } }, "CLASS_NOT_FOUND"],
      ["ue_console_command", { command: "quit" }, "COMMAND_NOT_ALLOWED"],
    ];
    for (const [name, args, code] of failures) {
      const r = await client.callTool({ name, arguments: args });
      if (r.isError !== true) throw new Error(`${name}: expected isError=true`);
      if (r.structuredContent?.error?.code !== code) {
        throw new Error(`${name}: expected error.code=${code}, got ${r.structuredContent?.error?.code}`);
      }
      console.log(`PASS  error   ${name} → ${code} (client-side outputSchema validation did not reject)`);
    }

    await client.close();
    console.log("\nSDK CLIENT VERIFICATION: all success/error calls passed the published outputSchema (no client-side rejection).");
  } catch (e) {
    console.error("SDK CLIENT VERIFICATION FAILED:", e?.message ?? e);
    console.error(srvErr.join("").slice(-2000));
    process.exitCode = 1;
  } finally {
    srv.kill();
    bridge.kill();
  }
}

main();
