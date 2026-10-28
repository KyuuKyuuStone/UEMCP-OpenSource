/**
 * 版本无关化回归守卫（任务 4248c955-D）：
 * Server/shared 的对外包描述不得写死引擎版本（引擎版本由 bridge /health 上报，
 * 见 watchdog.state.ueVersion → ToolMeta.ueVersion / /health bridge.ueVersion）。
 * 注意：shared 源码注释中的 "§5.4" 是架构文档章节号，不是引擎版本，不受此约束。
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const ROOT = join(fileURLToPath(new URL("..", import.meta.url)));

function readPackage(rel) {
  return JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
}

test("metadata D: package descriptions are engine-agnostic (no hardcoded 5.4)", () => {
  for (const rel of ["package.json", "packages/server/package.json", "packages/shared/package.json"]) {
    const pkg = readPackage(rel);
    const desc = String(pkg.description ?? "");
    assert.equal(/5\.4/.test(desc), false, `${rel} description must not hardcode engine version: "${desc}"`);
  }
});
