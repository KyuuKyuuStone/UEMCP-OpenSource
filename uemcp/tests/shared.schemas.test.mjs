/**
 * shared 包单元测试（node:test，零依赖）。
 * 被测对象：packages/shared/dist（构建产物，tsc 每文件输出）。
 * 覆盖：zod schema 校验与默认值、read-only action 收窄、错误码表一致性、
 *       工具目录与 RPC 方法映射。
 * 运行：pnpm test（= node --test tests/）
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ViewportCaptureInput,
  ActorQueryInput,
  LevelControlInput,
  levelInputSchema,
  LEVEL_ACTIONS,
  READ_ONLY_LEVEL_ACTIONS,
  LEVEL_WRITE_ACTIONS,
  TOOL_NAMES,
  FULL_TOOL_CATALOG,
  TOOL_RPC_METHOD,
  PROTOCOL_ERROR,
  TOOL_ERROR_TABLE,
  isToolErrorCode,
  toolCodeFromJsonRpc,
} from "../packages/shared/dist/index.js";

// ---------- ue_viewport_capture schema ----------

test("viewport: defaults are target=level_viewport/1280x720/png/camera=current", () => {
  const r = ViewportCaptureInput.parse({});
  assert.equal(r.target, "level_viewport");
  assert.equal(r.width, 1280);
  assert.equal(r.height, 720);
  assert.equal(r.format, "png");
  assert.equal(r.jpegQuality, 90);
  assert.deepEqual(r.camera, { mode: "current" });
  assert.equal(r.returnMode, "image");
  assert.equal(r.hideEditorUI, true);
});

test("viewport: explicit camera accepted (location+rotation)", () => {
  const r = ViewportCaptureInput.parse({
    camera: {
      mode: "explicit",
      location: { x: 400, y: -400, z: 300 },
      rotation: { pitch: -19.5, yaw: 135, roll: 0 },
    },
  });
  assert.equal(r.camera.mode, "explicit");
});

test("viewport: explicit camera rejects unknown key fov (strict)", () => {
  const r = ViewportCaptureInput.safeParse({
    camera: {
      mode: "explicit",
      location: { x: 0, y: 0, z: 0 },
      rotation: { pitch: 0, yaw: 0, roll: 0 },
      fov: 90,
    },
  });
  assert.equal(r.success, false, "fov is not part of the explicit camera schema");
});

test("viewport: width/height outside 64..7680/64..4320 rejected", () => {
  assert.equal(ViewportCaptureInput.safeParse({ width: 0 }).success, false);
  assert.equal(ViewportCaptureInput.safeParse({ width: 7681 }).success, false);
  assert.equal(ViewportCaptureInput.safeParse({ height: 63 }).success, false);
  assert.equal(ViewportCaptureInput.safeParse({ width: 12.5 }).success, false);
});

test("viewport: unknown top-level key rejected (strict)", () => {
  assert.equal(ViewportCaptureInput.safeParse({ nope: 1 }).success, false);
});

// ---------- ue_actor_query schema ----------

test("actor.query: defaults scope/fields/limit/offset/sortBy", () => {
  const r = ActorQueryInput.parse({});
  assert.equal(r.scope, "level");
  assert.deepEqual(r.fields, ["identity", "transform", "tags"]);
  assert.equal(r.limit, 50);
  assert.equal(r.offset, 0);
  assert.equal(r.sortBy, "name");
});

test("actor.query: filter strict rejects unknown key", () => {
  assert.equal(ActorQueryInput.safeParse({ filter: { klass: "Actor" } }).success, false);
});

test("actor.query: limit bounds 1..1000", () => {
  assert.equal(ActorQueryInput.safeParse({ limit: 0 }).success, false);
  assert.equal(ActorQueryInput.safeParse({ limit: 1001 }).success, false);
  assert.equal(ActorQueryInput.safeParse({ limit: 1000 }).success, true);
});

test("actor.query: tags refine caps at 20 properties", () => {
  const tags = Object.fromEntries(Array.from({ length: 21 }, (_, i) => [`k${i}`, "v"]));
  assert.equal(ActorQueryInput.safeParse({ filter: { tags } }).success, false);
  const tags20 = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`k${i}`, "v"]));
  assert.equal(ActorQueryInput.safeParse({ filter: { tags: tags20 } }).success, true);
});

// ---------- ue_level_control schema 与 read-only 收窄 ----------

test("level: full action enum and boolean defaults", () => {
  const r = LevelControlInput.parse({ action: "save_current" });
  assert.equal(r.action, "save_current");
  assert.equal(r.partitioned, false);
  assert.equal(r.allowDiscardUnsaved, false);
  assert.equal(r.confirm, false);
});

test("level: unknown action rejected", () => {
  assert.equal(LevelControlInput.safeParse({ action: "destroy_everything" }).success, false);
});

test("level: narrowed schema (read-only) rejects write actions, accepts read actions", () => {
  const ro = levelInputSchema(READ_ONLY_LEVEL_ACTIONS);
  assert.equal(ro.safeParse({ action: "save_current" }).success, false);
  assert.equal(ro.safeParse({ action: "open" }).success, false);
  assert.equal(ro.safeParse({ action: "get_current" }).success, true);
  assert.equal(ro.safeParse({ action: "list_dirty" }).success, true);
});

test("level: READ_ONLY_LEVEL_ACTIONS matches policy.ts narrowing and is disjoint from write set", () => {
  assert.deepEqual([...READ_ONLY_LEVEL_ACTIONS].sort(), ["get_current", "list_dirty"]);
  for (const a of READ_ONLY_LEVEL_ACTIONS) {
    assert.equal(LEVEL_WRITE_ACTIONS.has(a), false, `${a} must not be a write action`);
  }
  for (const a of LEVEL_ACTIONS) {
    assert.equal(LEVEL_WRITE_ACTIONS.has(a), ["open", "save_current", "save_all", "new"].includes(a));
  }
});

// ---------- 工具目录 ----------

test("toolNames: full catalog has exactly 10 tools and RPC mapping is total", () => {
  assert.equal(TOOL_NAMES.length, 10);
  assert.equal(FULL_TOOL_CATALOG.size, 10);
  for (const t of TOOL_NAMES) {
    assert.equal(typeof TOOL_RPC_METHOD[t], "string", `missing RPC method for ${t}`);
  }
  assert.equal(TOOL_RPC_METHOD.ue_actor_edit, "actor.edit");
  assert.equal(TOOL_RPC_METHOD.ue_editor_status, "editor.status");
});

// ---------- 错误码表 ----------

test("protocol error table: key mappings per §2.9.2", () => {
  assert.deepEqual(PROTOCOL_ERROR.INVALID_PARAMS, { jsonRpc: -32602, http: 400 });
  assert.deepEqual(PROTOCOL_ERROR.SESSION_NOT_FOUND, { jsonRpc: -32001, http: 404 });
  assert.deepEqual(PROTOCOL_ERROR.PARSE_ERROR, { jsonRpc: -32700, http: 400 });
  assert.deepEqual(PROTOCOL_ERROR.METHOD_NOT_FOUND, { jsonRpc: -32601, http: 404 });
  assert.deepEqual(PROTOCOL_ERROR.RATE_LIMITED, { jsonRpc: -32012, http: 429 });
});

test("tool error table: security/bridge codes have documented meta", () => {
  assert.deepEqual(TOOL_ERROR_TABLE.BRIDGE_UNAVAILABLE, {
    bridgeJsonRpc: -32000,
    bridgeHttp: 503,
    retryable: true,
  });
  assert.deepEqual(TOOL_ERROR_TABLE.TOOL_DISABLED, {
    bridgeJsonRpc: -32004,
    bridgeHttp: 403,
    retryable: false,
  });
  assert.equal(TOOL_ERROR_TABLE.EXEC_DISABLED.retryable, false);
  assert.equal(TOOL_ERROR_TABLE.PERMISSION_DENIED.retryable, false);
  assert.equal(TOOL_ERROR_TABLE.BRIDGE_TIMEOUT.retryable, true);
});

test("tool error table: TIMEOUT is retired from §2.9.3", () => {
  assert.equal(isToolErrorCode("TIMEOUT"), false);
  assert.equal(isToolErrorCode("BRIDGE_TIMEOUT"), true);
});

test("tool error table: bridgeJsonRpc codes are unique and exclude protocol -32001", () => {
  const seen = new Map();
  for (const [code, meta] of Object.entries(TOOL_ERROR_TABLE)) {
    assert.equal(seen.has(meta.bridgeJsonRpc), false, `duplicate bridgeJsonRpc ${meta.bridgeJsonRpc} on ${code}`);
    seen.set(meta.bridgeJsonRpc, code);
  }
  assert.equal(seen.has(-32001), false, "-32001 is reserved for protocol SESSION_NOT_FOUND");
});

test("toolCodeFromJsonRpc: reverse lookup and unknown code", () => {
  assert.equal(toolCodeFromJsonRpc(-32000), "BRIDGE_UNAVAILABLE");
  assert.equal(toolCodeFromJsonRpc(-32004), "TOOL_DISABLED");
  assert.equal(toolCodeFromJsonRpc(-32001), undefined);
});
