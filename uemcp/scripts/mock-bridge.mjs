#!/usr/bin/env node
/**
 * UEMCP mock bridge —— Server 自测用（Bridge 尚未就绪）。
 * 本地 HTTP JSON-RPC：GET /health、POST /rpc（X-UEMCP-Token）。
 * 行为按架构文档 §2.4/§2.8/§2.9.5 模拟，可注入错误路径。
 *
 * 用法：
 *   node scripts/mock-bridge.mjs [--port 0] [--home <dir>] [--project <dir>]
 *        [--allow-write] [--deny-exec] [--deny-console] [--fail-python] [--dirty]
 * stdout 首行输出 JSON：{ port, token, home }（供测试脚本读取）。
 */
import http from "node:http";
import { createHash, randomBytes } from "node:crypto";
import { mkdirSync, writeFileSync, renameSync, existsSync, statSync } from "node:fs";
import { join, dirname } from "node:path";

const args = new Map();
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith("--")) {
    const next = process.argv[i + 1];
    if (next && !next.startsWith("--")) {
      args.set(a, next);
      i++;
    } else args.set(a, true);
  }
}

const portArg = Number(args.get("--port") ?? 0);
const home = args.get("--home") ?? process.env.USERPROFILE ?? process.env.HOME ?? ".";
const projectDir = (args.get("--project") ?? "UEMCP-TestProject").replaceAll("\\", "/");
const token = randomBytes(32).toString("base64url");
const startedAt = new Date().toISOString();
const flags = {
  allowWrite: args.has("--allow-write"),
  // 与真实桥接一致（§4.4）：默认只读、禁止 exec/console；--allow-exec/--allow-console 打开
  allowExec: args.has("--allow-exec"),
  allowConsole: args.has("--allow-console"),
  failPython: args.has("--fail-python"),
  dirty: args.has("--dirty"),
};

const CONSOLE_DENIED = ["quit", "exit", "restart", "shutdown", "reconnect", "open", "exec", "py", "python", "delete", "rm", "crash", "bugit"];
const CONSOLE_ALLOW = ["stat", "show", "r.", "sg.", "viewmode", "log", "help", "dumpticks", "obj", "memreport", "camera"];

const ACTORS = [
  { actorPath: "PersistentLevel.StaticMeshActor_1", name: "StaticMeshActor_1", label: "Chair", class: "StaticMeshActor", transform: { location: { x: 0, y: 0, z: 0 } } },
  { actorPath: "PersistentLevel.StaticMeshActor_2", name: "StaticMeshActor_2", label: "Table", class: "StaticMeshActor", transform: { location: { x: 100, y: 0, z: 0 } } },
  { actorPath: "PersistentLevel.Light_1", name: "Light_1", label: "Light", class: "PointLight", transform: { location: { x: 0, y: 0, z: 300 } } },
];

// 1x1 PNG
const PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

function ok(data, warnings = [], meta = {}) {
  return { ok: true, data, warnings, meta };
}

function rpcErr(id, rpcCode, errorCode, message, details, retryable = false) {
  return {
    jsonrpc: "2.0",
    id,
    error: { code: rpcCode, message, data: { errorCode, retryable, details } },
  };
}

function dispatch(method, params, meta = {}) {
  switch (method) {
    case "bridge.ping":
    case "bridge.capabilities":
      return ok({
        python: true,
        screenshot: true,
        blueprintRead: true,
        blueprintNodeRead: false,
        blueprintCompile: true,
        animBlueprintEdit: false,
        assetRegistry: true,
        console: true,
      });
    case "editor.status":
      return ok({
        editor: {
          ueVersion: "5.4.4",
          pluginVersion: "0.1.0",
          bridgeProtocol: 1,
          processId: process.pid,
          isPieRunning: false,
          isSimulating: false,
          isCompiling: false,
          isAssetRegistryLoading: false,
        },
        level: { path: "/Game/Maps/L_TestUEMCP", name: "L_TestUEMCP", isDirty: flags.dirty, isPartitioned: false, dirtyPackageCount: flags.dirty ? 1 : 0 },
        selection: { count: 0, actors: [], truncated: false },
        capabilities: { python: true, screenshot: true, blueprintRead: true, blueprintNodeRead: false, blueprintCompile: true, animBlueprintEdit: false, assetRegistry: true, console: true },
      });
    case "actor.query": {
      const cls = params.filter?.class;
      if (cls && cls !== "StaticMeshActor" && cls !== "PointLight" && cls !== "Actor") {
        return { __err: rpcErrTemplate("CLASS_NOT_FOUND", -32022, `Class not found: ${cls}`, { className: cls }) };
      }
      let list = ACTORS;
      if (cls) list = list.filter((a) => a.class === cls || cls === "Actor");
      if (params.filter?.nameContains) list = list.filter((a) => a.name.includes(params.filter.nameContains));
      if (params.filter?.labelContains) list = list.filter((a) => a.label.includes(params.filter.labelContains));
      const sortBy = params.sortBy ?? "name";
      list = [...list].sort((a, b) => String(a[sortBy === "path" ? "actorPath" : sortBy] ?? "").localeCompare(String(b[sortBy === "path" ? "actorPath" : sortBy] ?? "")));
      const total = list.length;
      const offset = params.offset ?? 0;
      const limit = params.limit ?? 50;
      const page = list.slice(offset, offset + limit);
      return ok({ total, returned: page.length, truncated: offset + page.length < total, actors: page });
    }
    case "actor.edit": {
      if (!flags.allowWrite) {
        return { __err: rpcErrTemplate("PERMISSION_DENIED", -32003, "Bridge allowWrite=false", { gate: "bridge.allowWrite" }) };
      }
      const results = (params.operations ?? []).map((op, i) => {
        if (op.op === "set_transform" && op.selector?.value === "NoSuchActor") {
          return { index: i, op: op.op, ok: false, error: { code: "ACTOR_NOT_FOUND", message: "Actor not found", retryable: false, details: { selector: op.selector, matches: [] } } };
        }
        return {
          index: i,
          op: op.op,
          ok: true,
          ...(op.op === "spawn" ? { created: [{ actorPath: `PersistentLevel.${op.class}_new`, name: `${op.class}_new`, class: op.class }] } : {}),
          ...(op.op === "set_transform" ? { modified: [op.selector.value] } : {}),
          ...(op.op === "delete" ? { deleted: [op.selector.value] } : {}),
        };
      });
      const failed = results.filter((r) => !r.ok).length;
      return ok({
        dryRun: params.dryRun === true,
        results,
        summary: {
          requested: results.length,
          succeeded: results.length - failed,
          failed,
          rolledBack: failed > 0 && params.atomic !== false,
        },
      });
    }
    case "level.control": {
      const action = params.action;
      if (action === "get_current")
        return ok({ path: "/Game/Maps/L_TestUEMCP", name: "L_TestUEMCP", isDirty: flags.dirty, isPartitioned: false });
      if (action === "list_dirty")
        return ok({ packages: flags.dirty ? [{ path: "/Game/Maps/L_TestUEMCP", name: "L_TestUEMCP", isMap: true }] : [] });
      if (action === "open") {
        if (flags.dirty && params.allowDiscardUnsaved !== true)
          return { __err: rpcErrTemplate("UNSAVED_CHANGES", -32027, "Unsaved changes exist", { dirtyPackages: ["/Game/Maps/L_TestUEMCP"] }) };
        if (params.allowDiscardUnsaved === true && params.confirm !== true)
          return { __err: rpcErrTemplate("CONFIRMATION_REQUIRED", -32005, "Confirmation required to discard unsaved changes") };
        return ok({ path: params.levelPath, name: String(params.levelPath ?? "").split("/").pop() ?? "", previousPath: "/Game/Maps/L_TestUEMCP" });
      }
      if (action === "save_current") return ok({ saved: true });
      if (action === "save_all") {
        if (params.confirm !== true)
          return { __err: rpcErrTemplate("CONFIRMATION_REQUIRED", -32005, "save_all requires confirm") };
        return ok({ saved: true });
      }
      if (action === "new") return ok({ path: params.levelPath, name: String(params.levelPath ?? "").split("/").pop() ?? "" });
      return { __err: rpcErrTemplate("INVALID_ARGUMENT", -32602, `Unknown action: ${action}`) };
    }
    case "asset.search":
      return ok({
        total: 2,
        returned: 2,
        truncated: false,
        assets: [
          { packageName: "/Game/Materials/M_Test", objectPath: "/Game/Materials/M_Test.M_Test", assetName: "M_Test", class: "Material" },
          { packageName: "/Game/Materials/MI_Test", objectPath: "/Game/Materials/MI_Test.MI_Test", assetName: "MI_Test", class: "MaterialInstanceConstant" },
        ],
        dependencies: params.includeDependencies ? { "/Game/Materials/MI_Test": ["/Game/Materials/M_Test"] } : undefined,
      });
    case "material.params": {
      const action = params.action;
      if (action === "list" || action === "get")
        return ok({
          parameters: [
            { name: "Param1", type: "scalar", value: 0.5, editable: true },
            { name: "Color", type: "vector", value: { r: 1, g: 0, b: 0, a: 1 }, editable: true },
          ],
        });
      if (action === "set") {
        if (params.materialPath && !params.instancePath)
          return { __err: rpcErrTemplate("NOT_AN_INSTANCE", -32032, "Target is not a MaterialInstanceConstant", { path: params.materialPath, actualClass: "Material" }) };
        if (!flags.allowWrite)
          return { __err: rpcErrTemplate("PERMISSION_DENIED", -32003, "Bridge allowWrite=false", { gate: "bridge.allowWrite" }) };
        return ok({ saved: params.save === true });
      }
      if (action === "create_instance") {
        if (params.instancePath === "/Game/Materials/MI_Test")
          return { __err: rpcErrTemplate("ALREADY_EXISTS", -32035, "Asset already exists", { path: params.instancePath }) };
        return ok({ created: true });
      }
      return { __err: rpcErrTemplate("INVALID_ARGUMENT", -32602, `Unknown action: ${action}`) };
    }
    case "viewport.capture": {
      if (params.target === "pie")
        return { __err: rpcErrTemplate("PIE_NOT_RUNNING", -32038, "PIE is not running", { target: "pie" }) };
      // 写真实文件供 Server 端读取编码（当前桥接契约：只返回 path，不返回 base64）
      const capDir = join(home, "captures");
      mkdirSync(capDir, { recursive: true });
      const w = params.width ?? 1280;
      const h = params.height ?? 720;
      let file, bytes;
      if (w * h >= 7680 * 4320) {
        // 触发 >8MiB 降级路径
        file = join(capDir, "mock-big.png");
        if (!existsSync(file) || statSync(file).size <= 8 * 1024 * 1024) {
          writeFileSync(file, Buffer.alloc(9 * 1024 * 1024, 1));
        }
        bytes = statSync(file).size;
      } else {
        const buf = Buffer.from(PNG_BASE64, "base64");
        file = join(capDir, "mock-small.png");
        writeFileSync(file, buf);
        bytes = buf.length;
      }
      return ok({
        path: file,
        width: w,
        height: h,
        format: params.format ?? "png",
        bytes,
        capturedAt: new Date().toISOString(),
      });
    }
    case "console.command": {
      if (!flags.allowConsole)
        return { __err: rpcErrTemplate("PERMISSION_DENIED", -32003, "Bridge allowConsole=false", { gate: "bridge.allowConsole" }) };
      const cmd = String(params.command ?? "").trim().toLowerCase();
      const first = cmd.split(/\s+/)[0] ?? "";
      if (CONSOLE_DENIED.includes(first))
        return { __err: rpcErrTemplate("COMMAND_NOT_ALLOWED", -32017, `Command not allowed: ${params.command}`) };
      if (!CONSOLE_ALLOW.some((p) => first === p || first.startsWith(p)))
        return { __err: rpcErrTemplate("COMMAND_NOT_ALLOWED", -32017, `Command not in allowlist: ${params.command}`) };
      const warnings = params.captureOutput ? ["OUTPUT_CAPTURE_UNSUPPORTED"] : [];
      return ok({ command: params.command, dispatched: true, output: null, outputAvailable: false, warnings }, warnings);
    }
    case "python.exec": {
      if (!flags.allowExec)
        return { __err: rpcErrTemplate("EXEC_DISABLED", -32043, "Bridge allowExec=false", { gate: "bridge.allowExec" }) };
      if (flags.failPython)
        return { __err: rpcErrTemplate("PYTHON_ERROR", -32014, "Traceback (most recent call last):\n  ValueError: uemcp-test") };
      if (params.mode === "eval" && params.code === "1+1")
        return ok({ mode: "eval", result: 2, stdout: "", stderr: "", durationMs: 1, timedOut: false, timeoutMsReceived: meta.timeoutMs });
      return ok({ mode: params.mode ?? "exec", result: null, stdout: "", stderr: "", durationMs: 1, timedOut: false, timeoutMsReceived: meta.timeoutMs });
    }
    case "blueprint.query": {
      const action = params.action;
      if (action === "query")
        return ok({
          blueprintPath: params.blueprintPath,
          parentClass: "Actor",
          variables: [{ name: "Speed", type: "float", defaultValue: "0.0", instanceEditable: true, exposeOnSpawn: false, replicated: false }],
          components: [{ name: "StaticMesh", class: "StaticMeshComponent", parent: null }],
          graphs: [{ name: "EventGraph", kind: "event", nodeCount: 3 }],
          interfaces: [],
          compileState: { status: "up_to_date", errors: 0, warnings: 0 },
        });
      if (action === "compile") {
        if (!flags.allowWrite)
          return { __err: rpcErrTemplate("PERMISSION_DENIED", -32003, "Bridge allowWrite=false", { gate: "bridge.allowWrite" }) };
        return ok({ compiled: true, compileState: { status: "up_to_date", errors: 0, warnings: 0 } });
      }
      return { __err: rpcErrTemplate("INVALID_ARGUMENT", -32602, `Unknown action: ${action}`) };
    }
    default:
      return { __err: { errorCode: "INTERNAL", rpcCode: -32603, message: `Unknown method: ${method}` } };
  }
}

function rpcErrTemplate(errorCode, rpcCode, message, details) {
  return { errorCode, rpcCode, message, details };
}

function writeDiscovery(actualPort) {
  const hash = createHash("sha1").update(projectDir).digest("hex").slice(0, 16);
  const payload = {
    schemaVersion: 1,
    pid: process.pid,
    projectDir,
    projectFile: "XQHCPP_54.uproject",
    host: "127.0.0.1",
    port: actualPort,
    url: `http://127.0.0.1:${actualPort}`,
    token,
    ueVersion: "5.4.4",
    pluginVersion: "0.1.0",
    bridgeProtocol: 1,
    capabilities: {
      python: true, screenshot: true, blueprintRead: true, blueprintNodeRead: false,
      blueprintCompile: true, animBlueprintEdit: false, assetRegistry: true, console: true,
    },
    startedAt,
  };
  const dir = join(home, ".uemcp");
  const bridgesDir = join(dir, "bridges");
  mkdirSync(bridgesDir, { recursive: true });
  // 原子写（先 .tmp 再 rename）
  for (const [file, obj] of [
    [join(bridgesDir, `${hash}.json`), payload],
    [join(dir, "bridge.json"), payload],
  ]) {
    const tmp = file + ".tmp";
    writeFileSync(tmp, JSON.stringify(obj));
    renameSync(tmp, file);
  }
}

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ app: "uemcp-bridge", ok: true, pid: process.pid, startedAt, ueVersion: "5.4.4", pluginVersion: "0.1.0", projectDir }));
    return;
  }
  if (req.method === "POST" && req.url === "/rpc") {
    const remote = req.socket.remoteAddress ?? "";
    if (remote !== "127.0.0.1" && remote !== "::1" && remote !== "::ffff:127.0.0.1") {
      res.writeHead(403).end();
      return;
    }
    const got = req.headers["x-uemcp-token"];
    if (got !== token) {
      res.writeHead(401, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "unauthorized" }));
      return;
    }
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      res.writeHead(200, { "Content-Type": "application/json" });
      let msg;
      try {
        msg = JSON.parse(body);
      } catch {
        res.end(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Invalid JSON", data: { errorCode: "PARSE_ERROR" } } }));
        return;
      }
      const r = dispatch(msg.method, msg.params ?? {}, msg.meta ?? {});
      if (r && typeof r === "object" && "__err" in r) {
        const e = r.__err;
        res.end(JSON.stringify(rpcErr(msg.id, e.rpcCode, e.errorCode, e.message, e.details)));
        return;
      }
      res.end(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: r }));
    });
    return;
  }
  res.writeHead(404).end();
});

server.listen(portArg, "127.0.0.1", () => {
  const actual = server.address().port;
  writeDiscovery(actual);
  process.stdout.write(JSON.stringify({ port: actual, token, home }) + "\n");
});
