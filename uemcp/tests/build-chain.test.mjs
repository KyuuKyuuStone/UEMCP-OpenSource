/**
 * 构建链回归守卫（DEF-1，任务 ac394016）：干净树 typecheck 必须不依赖 dist。
 * 复现的历史回归：packages/shared 的 main/types 指向 ./dist，干净检出（无
 * node_modules、无各包 dist 目录）下 `pnpm install && pnpm typecheck` exit 2
 * （17× TS2307 Cannot find module '@uemcp/shared' + 3× TS2366）。
 * 修复：server 的 typecheck 配置（tsconfig.json）把 @uemcp/shared paths 到
 * shared 源码（不再依赖 shared dist）；tsup 构建走不含 paths 的 tsconfig.build.json，
 * 产物与修复前逐字节一致。
 * 本测试在临时副本（剔除 node_modules/dist/logs）里实跑 install → typecheck，
 * 断言不先 build 即 exit 0。
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { cpSync, rmSync, existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname, relative } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const IS_WIN = process.platform === "win32";

function pnpm(args, cwd) {
  return spawnSync(IS_WIN ? "cmd" : "pnpm", IS_WIN ? ["/c", "pnpm", ...args] : args, {
    cwd,
    encoding: "utf8",
  });
}

function tail(text, n) {
  return String(text ?? "").split("\n").filter(Boolean).slice(-n).join("\n");
}

test(
  "build-chain: clean tree (no node_modules, no packages/*/dist) passes install + typecheck without prior build (DEF-1)",
  { timeout: 240000 },
  () => {
    const dst = mkdtempSync(join(tmpdir(), "uemcp-buildchain-"));
    try {
      cpSync(ROOT, dst, {
        recursive: true,
        filter: (src) => {
          const rel = relative(ROOT, src);
          if (rel === "") return true;
          const parts = rel.split(/[\\/]/);
          // 剔除构建产物、依赖与运行期日志：只检验"源码可自证类型正确"
          return !parts.some((p) => p === "node_modules" || p === "dist" || p === "logs");
        },
      });
      assert.equal(existsSync(join(dst, "node_modules")), false, "fixture must exclude node_modules");
      assert.equal(existsSync(join(dst, "packages", "server", "dist")), false, "fixture must exclude server dist");
      assert.equal(existsSync(join(dst, "packages", "shared", "dist")), false, "fixture must exclude shared dist");

      const ins = pnpm(["install"], dst);
      assert.equal(
        ins.status,
        0,
        `pnpm install failed in clean copy:\n${tail(ins.stdout, 8)}\n${tail(ins.stderr, 8)}`,
      );

      const tc = pnpm(["typecheck"], dst);
      assert.equal(
        tc.status,
        0,
        `typecheck must pass on a clean tree WITHOUT prior build (DEF-1 regression):\n${tail(tc.stdout, 12)}\n${tail(tc.stderr, 12)}`,
      );
    } finally {
      try {
        rmSync(dst, { recursive: true, force: true });
      } catch {
        /* best effort */
      }
    }
  },
);
