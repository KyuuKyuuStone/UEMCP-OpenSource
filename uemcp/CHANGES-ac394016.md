# 变更说明：修 DEF-1 干净树 typecheck 与 DEF-2 smoke 临时目录泄漏（任务 ac394016）

日期：2026-10-28 ｜ 负责人：Server 工程（TypeScript / MCP 协议层）
范围：`uemcp/packages/server/tsconfig*`、`tsup.config.ts`、`scripts/smoke.mjs`、新增 2 个测试；不改 UE 侧 Python、不改文档结论、不降低既有断言强度（计数 54→55、80→81，只增不减）。

## 1. DEF-1：干净树 typecheck 必失败 → 已修复

**复现（修复前，干净副本 `%TEMP%\uemcp-clean-def1-before`，无 node_modules、无各包 dist）**：
- `cmd /c pnpm install` → exit 0（warm store，1.6s）
- `cmd /c pnpm typecheck` → **exit 2**，TS2307 `Cannot find module '@uemcp/shared'` 系列 + TS2366（switch 穷尽性失效）

**根因**：`packages/shared/package.json` 的 main/types/exports 指向 `./dist/`；server 的 tsconfig 无 paths 映射，未构建前 server 的 tsc 解析不到 shared 类型。

**修法与理由（选 QA 方案①：tsconfig paths，而非方案②）**：
- `packages/server/tsconfig.json`（typecheck/IDE 入口）：`paths: { "@uemcp/shared": ["../shared/src/index.ts"] }`，同时**不再继承 rootDir/outDir**（首版踩了 TS6059「shared src 不在 rootDir」——QA 预警的坑；`--noEmit` 下这两项本无意义，改为独立声明 `noEmit/types/paths`，`extends` base）。
- `packages/server/tsconfig.build.json`（新增）：原 tsconfig 内容原样保留，**专供 tsup**（`tsup.config.ts` 显式 `tsconfig: "tsconfig.build.json"`）。
- **为什么不用方案②（pretypecheck/build 链）**：脚本链对 `pnpm typecheck` 生效但对 QA 同样使用的 `pnpm -r typecheck`、`pnpm --filter @uemcp/server typecheck` 与 IDE 场景无效；且 typecheck 会产生 dist 副作用。方案①让 typecheck 在任何入口都"纯检查、不依赖 dist"，编辑器打开即有完整跨包类型。构建期继续按 workspace 依赖解析（pnpm -r 拓扑序保证 shared 先建），**产物逐字节不变**——实测 SHA256 前后一致：`index.js A86D774A…`、`internal.js B31D4BD0…`、`chunk-MLNHJAFL.js 82E0662D…`。
- **谁受影响**：所有在干净检出（或删 dist 后）跑 typecheck/QA 复跑的人（由失败变通过）；tsup 构建行为与产物无任何变化。

**验收硬标准证据（修复后，干净副本 `%TEMP%\uemcp-clean-def1-after`，robocopy 剔除 node_modules/dist/logs）**：
- `cmd /c pnpm install` → exit 0（1.8s）
- `cmd /c pnpm typecheck` → **exit 0（未先 build）** ← 硬标准
- `cmd /c pnpm -r build` → exit 0；`cmd /c pnpm -r typecheck` → **exit 0**（原"build 后 typecheck"顺序不破坏）

**自动化断言**：`tests/build-chain.test.mjs` —「build-chain: clean tree (no node_modules, no packages/*/dist) passes install + typecheck without prior build (DEF-1)」：临时副本实拷源码（剔除 node_modules/dist/logs）→ 实跑 install+typecheck，断言两步 exit 0；防"tsconfig/包入口改动让干净树 typecheck 重新依赖 dist"的回归。（开发注记：该文件首版因块注释里写了 `packages/*/dist` 提前闭合注释导致语法错误，已改措辞——恰好证明这类守卫值得配自动跑。）

## 2. DEF-2：smoke.mjs 不清理临时 HOME → 已修复

**修法**：`scripts/smoke.mjs` 重构——
- `main()` 拆为 `runSuite(home)`（原主体）+ finally 兜底：先回收**本次全部子进程**（新增 `smokeChildren` 集合，`spawnServer` 与两处直启 mock bridge 均注册；含崩溃/超时路径），等待句柄释放后再删目录；
- 默认 `rmSync(home, {recursive, force})` 并以新断言「PASS temp HOME cleaned up after run (DEF-2, no uemcp-smoke-* leak)」打印清理结果（失败则 FAIL 并显示路径）；
- `--keep-artifacts`（argv）或 `UEMCP_KEEP_ARTIFACTS=1`：保留现场并打印 `INFO  --keep-artifacts: temp HOME preserved for inspection: <path>`；
- 汇总改用 `process.exitCode`（原 `process.exit(1)` 在 finally 之前会跳过清理）。
- **谁受影响**：跑 smoke 的所有人（TEMP 不再累积含 mock token 与审计文件的残留目录）；排查故障者可用 `--keep-artifacts` 拿到完整现场。测试判定无任何放宽。

## 3. 验证计数（本机实跑）

- 残留基线：历史累积 **26 个** `uemcp-smoke-*`（与任务描述一致），已按精确过滤器清除 → 0。
- 第 1 次 `pnpm smoke`：**81/81 PASS**（新增清理断言），exit 0，计数 **0**；第 2 次：**81/81**，exit 0，计数 **0**（两次不增长）。
- `pnpm smoke --keep-artifacts`：80/80（无清理断言项），exit 0，计数 1 + INFO 提示（路径 `…\uemcp-smoke-kfniK9`），验证后已手动清除。
- 最终四门：`pnpm -r build` exit 0 ｜ `pnpm -r typecheck` exit 0 ｜ `pnpm test` **55/55**（54+build-chain）exit 0 ｜ `pnpm smoke` **81/81** exit 0，跑后计数 0。
- 产物一致性：tsup 切换 tsconfig.build.json 后 dist 三个文件 SHA256 与改动前完全相同。

## 4. 未做项及原因
- `uemcp/README-DEV.md` 等文档中命令顺序说明：归文档岗（边界约束），本次不代改。
- 黑盒测试自身的临时 home 清理（after 钩子）本已存在，未改动。
