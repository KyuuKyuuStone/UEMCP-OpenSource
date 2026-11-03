# 变更说明：0.1.5 Server 侧打包（任务 80625f30）

日期：2026-11-03 ｜ 负责人：Server 工程（TypeScript / MCP 协议层）
范围：`uemcp/packages/server/package.json`、`uemcp/packages/server/src/mcp/buildServer.ts`、
`scripts/pack-server.ps1`、产物 `dist-release/uemcp-server-0.1.5.tgz`。
未 push、未发 Release、未改 UE 侧 Python、未动 0.1.4 既有产物与 `SHA256SUMS.txt`。

## 1. 版本号
- `uemcp/packages/server/package.json`：`version` 0.1.4 → **0.1.5**
- `uemcp/packages/server/src/mcp/buildServer.ts`：`SERVER_VERSION` 0.1.4 → **0.1.5**
  （`serverInfo.version` 的唯一来源；`shared`/根 package.json 版本未动，与 0.1.4 bump 的
  Server 侧范围一致——0.1.4 的 bump 提交里 Server 侧也只有这两处。）

## 2. 四门（版本号改动后实跑）
| 门 | 退出码 | 计数 |
|---|---|---|
| `pnpm -r build` | 0 | — |
| `pnpm -r typecheck` | 0 | — |
| `pnpm test` | 0 | **62/62** |
| `pnpm smoke` | 0 | **87/87**（跑后 `uemcp-smoke-*` 计数 0） |

## 3. 打包缺陷（本轮发现并修复，影响 0.1.3/0.1.4 已发布产物）
- **现象**：用官方 `scripts/pack-server.ps1` 打出的 tgz 全局安装后，Windows 上
  `uemcp.cmd` 直接执行 `.js`（shim 内容为 `"%dp0%\...\dist\index.js" %*`），
  退出码 1、无任何输出；而 `node .../dist/index.js` 直跑完全正常。
- **根因**：npm 的 cmd-shim 只有在 bin 目标以 `#!/usr/bin/env node` 开头时才生成
  node 包装 shim，否则按"原生可执行文件"处理。`pack-server.ps1` 的 esbuild
  `--banner:js` 只注入了 createRequire（CJS→ESM 所需），**漏了 shebang**。
- **影响面**：0.1.3 引入该脚本起即存在；实测 0.1.4 的
  `uemcp-server-0.1.4.tgz` 内 `dist/index.js` 首行同样是 createRequire、无 shebang
  ——**已发布的 0.1.4 server 包在 Windows 上 `uemcp.cmd` 不可用**（需 `node <prefix>
ode_modules/@uemcp/server/dist/index.js` 直跑）。0.1.5 已修复。
- **修复**：`scripts/pack-server.ps1` 的 banner 前置 `#!/usr/bin/env node`（附注释说明
  原因）；重新打包后 shim 变为 `"%_prog%" "%dp0%\...\index.js" %*`（node 包装）✓。
- **建议（交主管裁决）**：0.1.4 发布物是否重打/补发说明，不在本轮边界内。

## 4. 产物与验证
- 产物：`dist-release/uemcp-server-0.1.5.tgz`，**709,310 B**，
  SHA256 `b8f14de98496d0c8f7b15ff35e4e30200f1226df827c043ce9d0a95ad9da6c29`
  （内容仅 `package/{LICENSE,dist/index.js,package.json,README.md}`；
  manifest：`@uemcp/server` 0.1.5、`dependencies:{}`、`engines.node>=20`、`bin.uemcp`）。
- 验证（临时 prefix 全局安装，实测 10 项全 PASS）：
  1. `npm install -g --prefix <tmp> <tgz>` exit 0；
  2. stdio `initialize` → `serverInfo.version = 0.1.5`；
  3. read-only 默认 `tools/list` = **11**（含 `ue_reflect`/`ue_log_query`，不含 `ue_call_function`）；
  4. stdin 结束后进程 exit 0；
  5. `--policy standard` HTTP `tools/list` = **13**（含 `ue_call_function`）；
  6. 验证后删除临时 prefix 与日志目录。

## 5. 备注
- 工作树中除本轮 3 个文件外，还包含上一任务 2e0e2aaf（D1 activateWindow / D4 captureLog）
  尚未提交的改动（shared schema ×3、viewportCapture、mock-bridge、tests ×2、
  CHANGES-2e0e2aaf.md）——均由主管统一提交，本轮未触碰。
