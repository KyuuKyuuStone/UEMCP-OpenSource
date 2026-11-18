# v0.1.6 落地方案（squash / tag / 上传命令，供发布执行人执行）

- 生成时间：2026-11-18 16:4x +08:00（任务 a45487d5，运维脚本）；17:1x 按打回原因 R2 返工（title/正文剥离/执行前提/-uall 计数）。
- 本文档只给命令方案，**本任务未执行任何 git 写操作**；当前证据见 `feedback-review/logs/rel016-rel-git.log`（HEAD 前后一致 `bacbe1c`、staged 为空、远端无 v0.1.6 tag）。
- 执行前提：人工逐条复核 `git status --porcelain`（默认折叠 66 项 / `-uall` 展开 512 项：`uemcp/` 41、`UEMCPBridge/` 21、`docs/` 1、`CHANGELOG.md` 1、`feedback-review/` 1、`README.md` 1 为折叠口径），确认均为 0.1.6 范围内变更后，再执行第 2 节。

## 0. 执行前提（2026-11-18 17:0x 实测，见 `feedback-review/logs/rel016-rel-plan-env.log`）

1. **git 推送凭据未就位**：`.git/config` 的 `credential.helper = store --file=C:\UE5_P\5.4\UEMCP-OpenSource\.git\push-credentials`，**该文件与父目录均不存在（已证实）**。`git push` 前必须二选一：确认凭据文件已就位，或用一次性注入（token 经环境变量提供，**禁止把 token 打进命令行回显或日志**）。凭据不可用就不要 push，先解决凭据。
2. **gh CLI 本机不可用**：`gh --version` 实测输出「'gh' is not recognized…」（EXIT=1），且无 `hosts.yml` 认证配置。发布上传必须走本节第 3.2 步的 REST API 方式；不要按 gh 路径执行。
3. **本机无 v0.1.5 标签**（仅远端有，已证实）：如需 v0.1.5 作基线对比，先 `git fetch --tags`（只拉标签，属唯一允许的写引用操作，由发布执行人自行决定并留档）。
4. **RELEASE 的 GitHub 正文须剥离包装行**：`dist-release/RELEASE-v0.1.6.md` 前 5 行是本地包装（`# 标题`、`Release body…`、`---` 分隔行），不能作为发布页首屏；按第 **3.1** 节的内联命令剥出纯 body（从锚点行 `## 中文` 起），并核对该文件首行以 `## 中文` 起头、末行为 PROB-006 验收段。
5. **工作区计数基准用 `-uall`**：默认 porcelain 折叠未跟踪目录得 66 条，`git status --porcelain -uall` 实测 **512 条**——`git add -A` 后的核对期望值是 ≈512，不是 66，照 66 核对会误判。

## 1. 发布集清单（上传到 GitHub Release 的 4 个工件）

| 文件 | 大小 | SHA256（小写） |
|---|---|---|
| `dist-release/UEMCPBridge-5.4.zip` | 186,613 B | `71f46343c82ca5102efa0c0c7b80d416e1f99c3efb0f93b4a533fbb44e96e5a4` |
| `dist-release/UEMCPBridge-5.7.zip` | 186,614 B | `9d08bc6118f249b1ce403474d658d7fa5851e899726658810a60b28030aef1e0` |
| `dist-release/uemcp-server-0.1.6.tgz` | 712,856 B | `f652f2c3ff8b4659c030d865369363f708a9104b8ebfad1bebf979eaddc47bf5` |
| `dist-release/SHA256SUMS.txt` | 264 B | `808089de751f7afe49d13a1a56ef58091a5ef465b293bab05f047ed94f9853e7` |

- `SHA256SUMS.txt` 覆盖前三项（3 行，不含自身、不含任何 0.1.5 行），逐行校验 PASS 见 `feedback-review/logs/rel016-rel-sha256sums.log`。
- 两个 zip 由 `scripts/pack-bridge.ps1 -EngineVersion 5.4,5.7` 同一暂存快照生成，跨版本清单一致性检查通过；`.uplugin` 读回 EngineVersion `5.4.0`/`5.7.0`、VersionName `0.1.6`，见 `feedback-review/logs/rel016-rel-zip-contents.log`。
- 发布说明正文：`dist-release/RELEASE-v0.1.6.md`（已更正与服务端 TS 修复批次的冲突表述，并按 R1 返工更正 5.4 真机口径——5.7.4 有本版插件 8/8 冒烟运行记录、5.4 未复测如实声明；grep 证据见 `feedback-review/logs/rel016-rel-release-grep.log`）。
- 注意：`dist-release/` 被 `.gitignore` 忽略，工件**不入库**，只作为 Release 附件上传。

## 2. squash 提交、tag、推送（在仓库根 `C:\UE5_P\5.4\UEMCP` 执行）

当前分支 `main`；本地 HEAD `bacbe1c`（bridge PROB-006/007 修复提交）领先远端 `refs/heads/main = 6fa4f35`；工作区 66 项未提交变更尚未纳入任何提交。

```powershell
# 2.1 复核后一次性提交全部 0.1.6 工作区变更（dist-release 被 gitignore 自动排除）
git add -A
git status --porcelain -uall | Measure-Object -Line   # 期望≈512（-uall 展开未跟踪文件的实测值，见第 0 节；不是 66——默认折叠计数只用于改动前的粗核）
git status --short          # 人工扫一眼：不应出现 dist-release/ 条目（gitignored）

git commit -m "feat(release): 0.1.6 - bridge fixes + server second-batch fixes + docs" -m "Bridge (plugin-side):
- PROB-006: ue_call_function distinguishes in-body TypeError (EXECUTION_ERROR, phase=in-body) from bind failure (INVALID_ARGUMENT); unverifiedSignature degraded path flagged.
- PROB-007: object.call blacklist moves to exact-name + prefix matching; matchedRule in denial details; false-positive names (e.g. execute_console_command) released.
- UEMCPBridge: version 0.1.6 (uplugin/settings.py); COMPAT-UE57.md IMP-003 dependency-option engine matrix.

Server (MCP, 0.1.5 second batch):
- bridge watchdog retains last-known identity on transport drop; markDown clears all.
- audit: origin/stage, policySnapshot, schemaVersion, bridge build identity, read-only calls audited, clientInfo backfill, stdio without sessionId; RETENTION_DAYS=30 fixed; 3-fail stderr warn + auditDegraded.
- discovery: stale/staleReason/staleAt; schemaVersion mismatch warning; /health passthrough.
- viewport.capture: 20 s bound + capability precheck (CAPABILITY_UNAVAILABLE).
- outputSchema dual-shape registration for all visible tools.
- SERVER_VERSION -> 0.1.6 (serverInfo.version and /health version).

Docs: root README (CN/EN) download links -> v0.1.6; CHANGELOG [0.1.6]; README-DEV smoke 87/87, test 82; feedback-review evidence."

# 2.2 附注 tag
git tag -a v0.1.6 -m "UEMCP v0.1.6: plugin PROB-006/007 + server second-batch fixes + IMP-003 compat doc"

# 2.3 推送（普通推送，禁止 force）
git push origin main
git push origin v0.1.6
```

- 如发布执行人想把「文档/证据」与「代码」分成两个提交，可自行拆分；本方案按任务要求给单 squash 版本。
- 回滚预案：推送前如需放弃，`git reset --soft HEAD~1`（撤销本提交保留变更）与 `git tag -d v0.1.6`；推送后回滚需与团队协商，勿 force-push。

## 3. 上传工件到 GitHub Release v0.1.6

### 3.1 剥出发布页正文（RELEASE 前 5 行为本地包装，不能上发布页）

```powershell
# 在仓库根执行；结果写入 TEMP，不新增 dist-release 文件
$src='dist-release/RELEASE-v0.1.6.md'; $ln=Get-Content $src -Encoding UTF8
$i=[Array]::IndexOf($ln,'## 中文'); if($i -lt 0){ throw '正文锚点「## 中文」未找到，停止并人工核对' }
$out="$env:TEMP\release-notes-v0.1.6.md"
$ln[$i..($ln.Count-1)] | Set-Content $out -Encoding UTF8
(Get-Content $out -TotalCount 1)        # 核对首行 = "## 中文"
(Get-Content $out | Select-Object -Last 1)  # 核对末行 = PROB-006 验收段（"How to acceptance-test PROB-006..."）
```

### 3.2 REST API 上传（**本机 gh 不可用，按第 0 节实测走此路**；若在执行机上 gh 可用，等价命令见下）

```powershell
# token 从环境变量或凭据文件读取：绝不允许把 token 写进命令行明文回显或日志
if(-not $env:GH_TOKEN){ $env:GH_TOKEN=(Get-Content '<token文件路径>' -Raw).Trim() }
$h = @{ Authorization="token $env:GH_TOKEN"; Accept='application/vnd.github+json' }
$bodyJson = (@{ tag_name='v0.1.6'; name='UEMCP v0.1.6'; body=(Get-Content "$env:TEMP\release-notes-v0.1.6.md" -Raw -Encoding UTF8) } | ConvertTo-Json)
$rel = Invoke-RestMethod -Method Post -Uri 'https://api.github.com/repos/KyuuKyuuStone/UEMCP-OpenSource/releases' -Headers $h -ContentType 'application/json; charset=utf-8' -Body $bodyJson
$up = $rel.upload_url -replace '\{.*$',''   # upload_url 为模板字面量（尾部 "{?name,label}"），先剥占位；必须写 ${up}——执行机 PS 7.4+ 会把 "$up?name=…" 解析为 null-conditional 而吞掉 "?name"（实证见 rel016-rel-plan-uploadurl.log）
foreach($f in 'UEMCPBridge-5.4.zip','UEMCPBridge-5.7.zip','uemcp-server-0.1.6.tgz','SHA256SUMS.txt'){
  Invoke-RestMethod -Method Post -Uri "${up}?name=$f" -Headers $h -ContentType 'application/octet-stream' -InFile "dist-release/$f" | Out-Null
}
```

```powershell
# gh 路径仅在执行机装有并认证了 gh 时使用（v0.1.5 的 release name 为 "UEMCP v0.1.5"，故 title 用 "UEMCP v0.1.6"）
gh release create v0.1.6 dist-release/UEMCPBridge-5.4.zip dist-release/UEMCPBridge-5.7.zip dist-release/uemcp-server-0.1.6.tgz dist-release/SHA256SUMS.txt --title "UEMCP v0.1.6" --notes-file "$env:TEMP\release-notes-v0.1.6.md"
```

- 上传清单即第 1 节 4 个工件，一个不缺不多（`RELEASE-v0.1.6.md` 作为 notes 正文上传，不作为附件；0.1.5 旧工件不动）。
- 上传后人工核验：在发布页对每个附件重新下载取 SHA256，与 `SHA256SUMS.txt` 逐行比对（应 MATCH）。
- 根 README（:91-95/:145/:396-400/:450 等）的 v0.1.6 下载链接在 Release 创建前为 404，属预期；发布后链接自动生效。
- 不用 GitHub API 直接改 Release 之外的任何仓库内容；本任务的产物只到本地 `dist-release/` 为止。
