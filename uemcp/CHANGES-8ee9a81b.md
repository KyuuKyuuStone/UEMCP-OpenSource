# 交付说明：发布 v0.1.5 到 GitHub（任务 8ee9a81b）

日期：2026-11-03 ｜ 负责人：Server 工程（TypeScript / MCP 协议层）
**已发布**：https://github.com/KyuuKyuuStone/UEMCP-OpenSource/releases/tag/v0.1.5
（draft=False、prerelease=False、published_at 2026-11-03 08:58:30 UTC）

## 1. 产物（字节零改动，发布前后复核一致）
| 文件 | 大小 | SHA256 |
|---|---|---|
| `UEMCPBridge-5.4.zip` | 162,584 B | `27190261a59cb0f25fbf9ddf2fd1ff7f97165cf4cb5fc97dd145945cda5195ce` |
| `UEMCPBridge-5.7.zip` | 162,584 B | `aa60a80292a5c07398d6af151709f10ca202074722f80ecaf09b64d36a7d3d29` |
| `uemcp-server-0.1.5.tgz` | 709,310 B | `b8f14de98496d0c8f7b15ff35e4e30200f1226df827c043ce9d0a95ad9da6c29` |
| `SHA256SUMS.txt` | 264 B | `781a3e4da65284dd681b1ee7e3d610c4f420aa6ba4cf40ede9f193b6cb8a8d56` |

## 2. 执行步骤
1. **建 draft**：`POST /repos/.../releases`，`tag_name=v0.1.5`、`target_commitish=6fa4f353daf71682a1deaf00dccd2412ffce7d39`
   （远端 main 头）、`name=UEMCP v0.1.5`、`draft=true`；body 取自 `dist-release/RELEASE-v0.1.5.md`
   中 `---` 之后的正文（6,797 字符，中英双语）。→ draft id `432462494`。
2. **上传 4 附件**：`POST /releases/<id>/assets?name=…`（curl `--data-binary`，避免内存拼接）。
   全部 `state=uploaded`，尺寸与本地一致。
3. **哈希校验（关键）**：从 API 逐个下载已上传附件回本地，与 `dist-release/` 原件比对——
   **4/4 SHA256 MATCH、尺寸 MATCH**（证明上传链路未改字节）。
4. **发布**：`PATCH /releases/<id>`（`draft=false`）→ 已公开发布。
5. **发布后核验**：
   - API：`releases/tags/v0.1.5` 存在，`draft=false`，4 附件齐全；
   - `git ls-remote origin refs/tags/v0.1.5` → `6fa4f353daf71682a1deaf00dccd2412ffce7d39`（与 main 头一致）；
   - **匿名下载**（不带 token）四个 `releases/download/v0.1.5/<name>` 均 **HTTP 200**；
   - README 中四个下载链接名与 Release 实际附件名逐一一致（`SHA256SUMS.txt` /
     `uemcp-server-0.1.5.tgz` / `UEMCPBridge-5.4.zip` / `UEMCPBridge-5.7.zip`）。

## 3. 认证方式说明
环境无 `gh` CLI、无 `GITHUB_TOKEN`；使用仓库既有的 git 凭据文件
（`.git/push-credentials`，`gho_` OAuth token，账号 `KyuuKyuuStone`，scopes 含 `repo`，
repo `push=true admin=true`）走 GitHub REST API。凭据未回显、未外传。

## 4. 未改动 / 遗留
- `dist-release/` 产物字节未变（发布前后 SHA256 前缀一致）；未重打包。
- 未新增任何 git 提交（发布是纯 GitHub 侧动作）；工作树仅余各岗位未跟踪报告与
  `uemcp/CHANGES-f4dbc5ea.md`（未提交，按边界不擅自 add）。
- `backup-pre-015-push` 分支按主管指示保留（发布完成，可清理）。
- 已知历史问题（上轮报告）：0.1.4 server tgz 缺 shebang（`uemcp.cmd` 在 Windows 不可用），
  已随 0.1.5 修复；0.1.4 发布物是否补发/加注说明仍待主管裁决。
