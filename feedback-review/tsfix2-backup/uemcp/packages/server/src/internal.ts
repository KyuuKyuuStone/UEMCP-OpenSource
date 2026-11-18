/**
 * 测试专用内部导出（任务 4248c955：为 N-2/N-3/策略口径提供单元断言入口）。
 * 不属于公开 API：仅 tests/*.test.mjs 通过 dist/internal.js 引用；
 * tsup 以独立入口打包，不影响 CLI（dist/index.js）与包导出。
 */
export { Audit, summarizeArgs } from "./audit.js";
export {
  acceptDiscovery,
  equalProjectDirOn,
  normalizeProjectDir,
  projectHash,
  resolveBridge,
} from "./bridge/discovery.js";
export { BridgeWatchdog } from "./bridge/watchdog.js";
export { isToolVisible, narrowedActions, toolDisabledGate } from "./policy.js";
export type { PolicyState } from "./policy.js";
export { loadConfig } from "./config.js";
export { auditCall } from "./tools/common.js";
export { statusTool } from "./tools/status.js";
export { viewportCaptureTool } from "./tools/viewportCapture.js";
export { pythonExecTool } from "./tools/pythonExec.js";
export { actorQueryTool } from "./tools/actorQuery.js";
export { assetSearchTool } from "./tools/assetSearch.js";
export { policyExplainTool } from "./tools/policyExplain.js";
export { reflectTool } from "./tools/reflect.js";
export { logQueryTool } from "./tools/logQuery.js";
