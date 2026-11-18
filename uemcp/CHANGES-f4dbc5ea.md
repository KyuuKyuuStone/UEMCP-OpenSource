# 交付说明：0.1.5 发布第一步（任务 f4dbc5ea）

日期：2026-11-03 ｜ 负责人：Server 工程（TypeScript / MCP 协议层）
**未创建 Release**（下一步再做）。未 push 任何 tag。

## 1. 提交与推送
- **提交**：`66133c6 feat(release): 0.1.5 - D1/D4 fixes, bridge log levels and bare-class reflect, packer shebang fix`
  - 内容（23 文件，+779/−56）：
    - Server 侧 D1/D4：`uemcp/packages/shared/src/schemas/{viewport,primitives,outputs}.ts`、
      `uemcp/packages/server/src/tools/viewportCapture.ts`、`uemcp/scripts/mock-bridge.mjs`、
      `uemcp/tests/{server.blackbox,shared.schemas}.test.mjs`
    - 版本号：`uemcp/packages/server/package.json`、`buildServer.ts`（0.1.4→0.1.5）
    - 打包器：`scripts/pack-server.ps1`（shebang 修复）
    - Bridge 侧 0.1.5 工作（已在本地历史中，随本提交落地）：`handlers/{logs,objects,viewport}.py`、
      `settings.py`、`UEMCPBridge.uplugin`、`Tests/{test_log_query,test_object_call,test_viewport_capture}.py`
    - 文档：`CHANGELOG.md`、`README.md`、`UEMCPBridge/README.md`、`uemcp/CHANGES-{2e0e2aaf,80625f30}.md`
  - **未包含**（按"严禁 `git add -A`"）：`ue_p_text/` 全部改动（272 个删除，属本地停靠工程）、
    各岗位未跟踪报告（`uemcp/tests/{D5-D123-TRIAGE-2026-11-03,DEFECT-TRIAGE-2026-10-29,
    DEFECT-V014-TRIAGE,RECON-2026-10-30}.md`、`pie-acceptance.ps1`）。
- **推送**：`d03fe98..66133c6 main -> main`，exit 0；复核 `HEAD == origin/main == 66133c6e…`，ahead/behind `0/0`。

### 推送前处理的分叉（需主管知悉）
本地分支曾是**远端已发布 0.1.3/0.1.4 线的平行副本**（merge base `03398af`；本地 15 提交 / 远端 7 提交，
远端 7 个即已发布的 v0.1.3→v0.1.4）。直接 `git push` 被拒；`git merge origin/main` 产生 17 处冲突
（两份历史对同一批文件各有版本），已 `--abort` 未留残留。
采用**不改写远端历史**的方案：`git diff --name-status origin/main HEAD` 核实净差异恰为 0.1.5 的 23 个文件
（无 ue_p_text、无杂项）→ 建备份分支 `backup-pre-015-push`（指向 3ea2532）→ `git reset --soft origin/main`
→ 以单提交落地该 delta → **`HEAD^{tree}` 与 reset 前完全相等（已校验 `tree equal: True`）** → 推送成功。
远端因此保持线性：`d03fe98`(v0.1.4 线) → `66133c6`(0.1.5)。

## 2. 清旧包
- 删除 `dist-release/uemcp-server-0.1.4.tgz`（0.1.5 发布只带三个产物；历史 `RELEASE-v0.1.{1..4}.md`
  说明文件保留不动）。
- `dist-release` 现仅存：`UEMCPBridge-5.4.zip`、`UEMCPBridge-5.7.zip`、`uemcp-server-0.1.5.tgz`、
  `SHA256SUMS.txt`（+ 说明类 md）。

## 3. 校验和（重算并逐条复核）
```
27190261a59cb0f25fbf9ddf2fd1ff7f97165cf4cb5fc97dd145945cda5195ce  UEMCPBridge-5.4.zip
aa60a80292a5c07398d6af151709f10ca202074722f80ecaf09b64d36a7d3d29  UEMCPBridge-5.7.zip
b8f14de98496d0c8f7b15ff35e4e30200f1226df827c043ce9d0a95ad9da6c29  uemcp-server-0.1.5.tgz
```
三行均与文件实算值 **MATCH**（旧文件原先只有两行 zip，缺 server tgz）。

## 4. 体检（四门）
| 门 | 退出码 | 计数 |
|---|---|---|
| `pnpm -r build` | 0 | — |
| `pnpm -r typecheck` | 0 | — |
| `pnpm test` | 0 | **62/62** |
| `pnpm smoke` | 0 | **87/87** |

## 5. 未做 / 待主管决策
- **未创建 Release、未打 tag**（按任务要求留到下一步）。
- `backup-pre-015-push` 分支仅本地保留（未推送），确认无误后可删。
- 提示：上一轮报告过的 **0.1.4 server tgz 缺 shebang 缺陷**（`uemcp.cmd` 在 Windows 不可用）已随 0.1.5
  修复；0.1.4 发布物是否需要补发/加注说明，仍待主管裁决。
