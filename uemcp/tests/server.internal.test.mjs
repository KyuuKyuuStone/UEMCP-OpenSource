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
import { mkdtempSync, existsSync, statSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  Audit,
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
