# UEMCP 路线图（Roadmap）

> 状态：2026-10-30。依据：业务团队两天真实试用反馈（20 条需求，其中 3 条为文档坑，已单独写入 [README](../README.md)「常见使用坑」与 [UEMCPBridge/README.md](../UEMCPBridge/README.md) §13）。
> 本页只陈述方向与边界，**不承诺任何交付时间**；条目顺序可能随反馈调整。事实性描述以代码与 [CHANGELOG](../CHANGELOG.md) 为准。
>
> EN: This roadmap states what is done, in progress, planned, and explicitly out of scope — each with a reason and an alternative. **No delivery dates are promised.**

## 已做（Done）

**EN: v0.1.2 shipped fail-fast viewport capture with diagnostics, real Blueprint parent-class/graph reads, explicit UTF-8 charset and an offline server package.**

| 能力 | 说明 | 为什么做 | 此前的替代 |
|---|---|---|---|
| 截图硬截止 + 诊断 | `viewport.capture` 在桥接端自带截止，不再挂到 Server 侧 45s 超时；`CAPTURE_TIMEOUT` 附渲染环境诊断 | 编辑器失焦时 UE 限帧（实测约 3 fps），调用方此前只能干等到超时 | 保持编辑器前台、增大 `timeoutMs`、重试（文档已有） |
| 蓝图父类 / 生成类 / 类型 / 命名图可读 | `parentClass` / `generatedClass` / `blueprintType` 经 Asset Registry 读取；`EventGraph` 等命名图经 `find_graph` 发现；结构完全不可读时返回显式 `UNSUPPORTED` 而非"空成功" | "空成功"曾让业务得出"蓝图是空的"错误结论 | `variables` 列表仍不可用（见「明确不做」）；用编译 + 查询确认可用性 |
| JSON / SSE 显式 `charset=utf-8` | `/mcp`、`/health`、错误包全部带 charset | PowerShell 5.1 等客户端默认按 Latin-1 解码，中文与特殊字符乱码 | 无需替代（已修复） |
| 离线 Server 包 | `uemcp-server-0.1.0.tgz`（esbuild 全量 bundle），内网可离线安装 | `@uemcp/shared` 未发布到 npm，官方 `pnpm pack` 产物装不上 | 源码仓库内 `pnpm install && pnpm build` |

## 在做（In progress）

**EN: PIE start/stop, a policy explainer and traceable `/health` metadata are being built on the current contract.**

| 能力 | 说明 | 为什么 | 现在的替代 |
|---|---|---|---|
| PIE 启停 `ue_pie_control` | 进入 / 退出 Play-In-Editor | 业务要验证"运行时状态"必须先进 PIE，现在只能手动点编辑器 | 手动 PIE + 只读查询（写操作仍受 `EDITOR_UNSAFE_STATE` 约束） |
| `ue_policy_explain` | 解释当前生效策略与"这个调用为什么被拒" | 写操作被拒时，调用方看不出是 Server 策略还是桥接配置哪一层拦的 | README 安全默认表 + 错误 `details.gate` 字段 |
| `/health` 可追溯元数据 | `buildHash` / `buildTime` / `sourcePath` / `instanceId` | 两个构建共用同一 `pluginVersion` 的事故（见 README 常见使用坑 2）；排查"到底加载了哪份代码" | 比对源码目录；源码已落地、尚未进入发行包，字段以 `/health` 实际输出为准 |

## 计划（Planned，顺序可能调整）

**EN: Batch/async execution, log query, scene exploration, richer capture artifacts and multi-instance routing are the next candidates — in no committed order.**

| 能力 | 说明 | 为什么 | 现在的替代 |
|---|---|---|---|
| 批量 / 异步执行 `ue_batch`（含 resumeToken） | 一次下发多个操作，可断点续跑 | 批量遍历受 30 req/s 限流与逐调用往返开销限制 | 脚本侧循环 + 容错重试 |
| 日志查询 `ue_log_query` | 按关键字 / 时间过滤编辑器日志 | 排错目前要人肉翻 `Saved/Logs` | 手动查 `Saved/Logs/<Project>.log` 里的 `[UEMCP]` 行 |
| 场景探查 `ue_scene_query` | 一次返回关卡结构概览 | 逐个 `actor.query` 分页遍历太慢 | `actor.query` 分页 + 按 class / folder 过滤 |
| 截图增强：绝对路径 + sha256 + stats | 产出物可校验、可直接进流水线 | 业务要做截图验收链路，需要完整性凭证 | 本地读 PNG 自行计算哈希 |
| 多实例支持 | 基于 `instanceId` 的定向路由 / 选择策略（字段先行，语义后定） | 同时开 5.4 / 5.7 两个编辑器时，无法指定调用哪一个 | 一次只开一个编辑器实例（发现文件已按工程哈希区分，但路由语义未定义） |

## 明确不做（Won't do）

**EN: Five requests are explicitly out of scope — because of engine-correct behavior, engine-protected data, engine API boundaries, security boundaries, or front-end responsibilities.**

| 项 | 为什么不做 | 替代方案 |
|---|---|---|
| UE 视口截图包含前端叠加的 UMG 覆盖层 | UE 本就不把前端（Slate）层渲染进视口截图目标——这是引擎行为，不是插件缺陷；强行合成需要引擎侧改造，超出纯 Python 插件边界。EN: UE does not render the front-end (Slate) layer into the viewport capture target; compositing it would require engine-side changes. | 需要覆盖层画面时由前端自行截图；或用控制台命令调整视口内实际呈现的内容 |
| 蓝图变量列表 / 节点数 | `UBlueprint.NewVariables` 等是引擎 protected 属性，纯 Python 读不到；需要 P2 C++ 辅助模块才能突破 | 已做的编译触发 + `UNSUPPORTED` 显式诊断（含 `variablesUnavailable` 原因码）；或自研 C++ 辅助模块 |
| 基材质默认参数值 | 引擎 API 边界：基材质的默认参数不在引擎 Python 暴露面内 | `material.params` 读取材质实例自身的覆盖参数（已支持） |
| 远程读取工程任意文本文件 | 安全边界：把"读任意文件"做成 MCP 工具等于开了远程文件读取口，违背本地最小攻击面设计 | 显式开启 `allowExec` 后用 `python.exec` 自行读取（责任自担）；或走版本控制工具链 |
| 图像对比基线 | 属前端 / CI 职责，成熟工具（OpenCV、Percy 等）比在 MCP 层内嵌更合适 | `viewport.capture` 拿到 PNG 后接你自己的对比工具 |

---

反馈渠道：请开 Issue（附 UE 版本、MCP 客户端、`/health` 输出与错误码）。路线图由文档岗依据业务反馈与当前代码状态维护。
