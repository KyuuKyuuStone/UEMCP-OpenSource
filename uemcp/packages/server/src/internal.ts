/**
 * 测试专用内部导出（任务 4248c955：为 N-2/N-3/策略口径提供单元断言入口）。
 * 不属于公开 API：仅 tests/*.test.mjs 通过 dist/internal.js 引用；
 * tsup 以独立入口打包，不影响 CLI（dist/index.js）与包导出。
 */
export { Audit, summarizeArgs } from "./audit.js";
export { equalProjectDirOn, normalizeProjectDir, projectHash } from "./bridge/discovery.js";
export { isToolVisible, narrowedActions, toolDisabledGate } from "./policy.js";
export type { PolicyState } from "./policy.js";
