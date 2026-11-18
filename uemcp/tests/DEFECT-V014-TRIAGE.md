# B-HTTP 疑似会话回归定性（0.1.4 tgz，2026-11-03 限时取证）

- 执行人：测试与验证岗（限时 20 分钟取证，任务 9569616f 遗留项 + 主管裁定）
- 服务器：`uemcp-server-0.1.4.tgz` 解包 `package/dist/index.js --transport http --port 1919x --policy standard`（tgz 内 dist SHA256 `6AF8F6C7…DFC23D1`，**与本地仓库 dist `2F335C98…` 不同**——打包管线产物差异，行为以 tgz 为准）
- 结论先行：**不确认为包内会话回归。** 0.1.4 tgz 的会话层在 Node fetch 客户端下全部正常（矩阵 T1–T5：notify 202、list 200、session 累积无丢失、无一例 SESSION_NOT_FOUND）。10-30 与 11-03 两次 PS 客户端观察到的"notify/list 立即 SESSION_NOT_FOUND"**定性为 PS 客户端与会话查找的交互问题**，服务器侧 session 实际存在（`/health sessions=1`）——**带同一 sid 的 Node 请求在同一服务器上返回 202**。旧 dist（10-30）同一 PS 序列同样失败——**非 0.1.4 引入的回归**。

## 证据矩阵

| 实验 | 客户端 | 序列 | 结果 |
|------|--------|------|------|
| T1（json-only Accept） | Node | init→notify→list | init 200+sid；**notify 406**；list 406（Accept 缺 text/event-stream，SDK 拒绝——注：notify 406 而非 202，说明 0.1.4 对 notify 也校验 Accept 双类型） |
| T2（SSE Accept 全程） | Node | init→notify→list(json-only) | init 200+sid；**notify 202**；list 406（list 用了 json-only 的锅） |
| T3（双 notify + list） | Node | notify×2→list | 202/202/list 406 |
| T4（不 notify） | Node | init→list | 200/406（仍是 Accept 问题） |
| T5（T2 序列×5） | Node | — | notify 失败 0/5；会话累积正常 |
| **PS 重放（10-30 序列）** | **pwsh Invoke-WebRequest** | init→notify→list（Accept 均 json+sse） | **init 200+sid（sessions=1 存在）→ notify 404 -32001 SESSION_NOT_FOUND → list 404 同错** |
| **sid 交叉验证（决定性）** | PS init 取 sid → **Node 用同一 sid notify** | — | **Node 返回 202（成功）**——同一 sid 在同一服务器上：PS 发=404，Node 发=202 |

## 定性

1. **服务器会话层无回归**：session 存在（health sessions=1）、Node 客户端可用（202）、Node 全矩阵无失败。
2. **失败模式为客户端绑定**：PS `Invoke-WebRequest` 发出的 notify/list 请求被服务器判定为未知会话，而**字面上相同的 sid 由 Node 发送则成功**。结合 404 响应带 `hint:"reinitialize"`/`ttlMs:1800000`（0.1.4 新增的提示字段，采纳自 10-30 建议），失败点在**请求到达服务器时的会话查找**。PS 与 Node 请求的已知差异（Accept 集合、header 编码、HTTP/1.1 细节、keep-alive 行为）中，**具体哪个字段触发待 Server 岗在服务端加请求日志定位**（我方无服务端逐请求日志权限，20 分钟窗口内不猜测具体 header）。
3. **与外部团队报告的关系**：外部团队报告的"initialize 后立刻 SESSION_NOT_FOUND（偶发）"与我在 PS 客户端下 100% 复现的形态一致——**他们的客户端（可能也是 .NET 系/PowerShell/MCP SDK 客户端）落在同一失败模式**。此前（10-30）我用 Node 客户端把根因指向 TTL/会话池是**不完整的**：客户端依赖失败模式当时未被测试覆盖。**修正定性：P1-5 的直接机理是"特定客户端的后续请求不被会话查找接受"（服务器 sessions=1 仍查无），触发条件客户端绑定；TTL/会话池是真实存在的次生风险但非该现象主因。**
4. **给 Server 岗的定位建议**：在 POST /mcp 的 sid 查找分支（SESSION_NOT_FOUND 返回处）加请求侧日志：记录收到的 `mcp-session-id` 原值（含转义/不可见字符十六进制）与 map 内键列表；重点核对 PS/.NET 客户端对响应头 `mcp-session-id` 的读取是否存在重复头/编码差异（PS 读到值打印长度=36 正常，但**真正发出的 header 值需在服务器侧证实**）。
5. **给客户端侧的规避**（可立即给业务团队）：收到 SESSION_NOT_FOUND 时按 `hint:"reinitialize"` 重新 initialize 即可自愈（0.1.4 已内置该提示字段）；或改用 MCP 官方 SDK 客户端（Node/Python）验证——我方 Node 客户端全程无此问题。

## 试了什么/为何不再深挖

- 已试：Node 矩阵 5 组、PS 重放 3 组、sid 交叉验证 1 组、header 原值打印；两台服务器（tgz dist 6AF8F6C7）、四个端口（19192–19195）、各自独立审计目录。
- 未再深挖的原因：服务器侧无逐请求日志，进一步定位需 Server 岗加日志或抓包（超出测试岗"不改产品代码"边界与本次 20 分钟时限）；**当前证据已足以排除"0.1.4 包内会话回归"**（Node 全绿）并定性失败为客户端绑定。
