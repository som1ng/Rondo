# 路线图状态与遗留项

核对日期：2026-11-03；当前版本：`2.0.0`。对照原始 P0–P5 计划、代码与交付记录整理。
**本版提供 GUI 下载和 npm CLI 一条命令安装；完整客户端/模型验收及 P5 仍是后续工作。**

本页汇总当前状态；各 `*_DELIVERY.md` 是对应提交时的历史记录，其中的“下一步”可能已由后续 PR 完成。
不要据旧记录重复开发，也不要把实现、客户端发现、模型行为评测和公开发布混为同一验收结果。

2.0.0 发布入口为 [GitHub Release](https://github.com/som1ng/Rondo/releases/tag/v2.0.0)
和 `npm install -g @s0m1ng/rondo`。自有代码采用 MIT；第三方声明随包提供。
npm 托管 CLI/MCP/Skill、安装器和依赖，命令为 `rondo`，支持自检、项目/用户配置、升级和升级进程中断恢复。

## 历史进度

以下段落保留各轮验收时的范围，当前剩余项以下方状态表为准。

2026-10-27 更新：[Rondo npm 归档](NPM_DELIVERY.md) 开始由 npm 托管 CLI/MCP/Skill 和依赖；
“用户须另行准备 CLI/MCP”此后只适用于源码入口。公开发布、许可和升级恢复在当时尚未完成。

2026-10-28 更新：[用户级 MCP](USER_MCP_DELIVERY.md) 已实现单客户端安装、校验、卸载以及 auto/all 安装，
测试使用隔离用户目录；实际客户端用户级自动发现与模型行为在该轮仍未验收。

2026-10-28 更新：[配置升级](CONFIG_UPGRADE_DELIVERY.md) 已提供单客户端 Skill/MCP 的显式 `upgrade`，
包含新运行文件校验、配置/收据更新和捕获失败回滚；此前更换运行文件需要卸载后重装。
批量升级、旧二进制回退和强制结束/断电恢复仍待实现。

2026-10-28 后续更新：[批量升级](BATCH_UPGRADE_DELIVERY.md) 已提供 Skill/MCP 的 `upgrade --agent all`，
包括全部目标的文件/所有权预检、共享 Skill 去重和后续目标失败时的配置恢复。
旧二进制回退和强制结束/断电恢复仍未实现；上段批量升级待办已关闭。

2026-10-28 后续更新：[Skill 升级中断恢复](SKILL_RECOVERY_DELIVERY.md) 已提供单目标 `recover`，
验证了升级/恢复进程被强制终止后的恢复与重试。MCP、安装/卸载、整批事务恢复和物理断电仍未验收；
不能把这个范围有限的恢复入口视为全部中断/断电恢复已完成。

2026-10-28 后续更新：[MCP 升级中断恢复](MCP_RECOVERY_DELIVERY.md) 已提供 `recover --integration mcp`，
覆盖三客户端和 project/user 范围，只记录受管条目、收据及配置摘要；不保存整份客户端配置。
Skill/MCP 单目标升级步骤的进程中断恢复已交付，整批事务、安装/卸载及物理断电仍未完成。

2026-10-29 更新：[整批升级中断恢复](BATCH_RECOVERY_DELIVERY.md) 已提供 Skill/MCP 的 `recover --agent all`，
支持未提交批次的整体回滚、已提交结果保留以及恢复/清理再次中断后重试。
整批升级的进程中断恢复待办已关闭；跨目标原子可见性、安装/卸载恢复、真实断电及新机器验收仍不在已验证范围内。

2026-10-29 更新：[npm 安装后自检](NPM_SELF_CHECK_DELIVERY.md) 提供 `rondo self-check [--json]`，
检查宿主前置条件、CLI 校验/启动和安装器/MCP/Skill 资源，为分发后的问题定位提供入口。
新机器、真实运行库缺失和完全断网系统仍待验收；公开 npm 发布及项目许可事项未因此关闭。

2026-10-29 后续更新：[Codex 端到端验收](CODEX_ACCEPTANCE.md) 已验证 npm 归档全局安装、自检、
项目配置的未安装/未信任/已信任/卸载后四种发现状态，以及一个真实模型自主调用 `inspect_pe` 并正确回答的场景。
本轮未用命令行注入 MCP 配置，信任仅对临时项目进程生效；此前只有固定模型响应验收。
其他客户端、用户级发现和完整 Skill 场景仍未验收，不能据一个场景关闭整个 P2/P3 阶段。

2026-11-03 更新：[OpenCode V2 接入与验收](OPENCODE_V2_ACCEPTANCE.md) 支持 `2.2.5`，
新增原生 V2 MCP 配置与 npm 客户端探测，兼容 V1 收据升级。npm 安装、自检、项目自动发现、
七工具清单、四项工具调用、重复安装及卸载已通过本机固定模型响应验证。
用户级配置生命周期有回归覆盖；V2 用户级自动发现、Skill 发现和真实模型行为仍待验收。

## 阶段状态

| 阶段 | 已交付 | 尚未关闭 |
| --- | --- | --- |
| P0 基线与工程 | 源码审计、基础缺陷修复、CMake/CTest、Windows CI、MIT 与第三方声明 | 历史实验后端的解析/执行结果与资源生命周期限制仍在 |
| P1 Core + CLI | Result/Error、只读进程和模块查询、架构判断、JSON Schema、错误码、Unicode、超时与输出参数、x86/x64 构建和跨位数测试 | 不能把只读 Core 的契约视为历史实验方法已完成同等改造；ARM64/旧系统实机未验证 |
| P2 Doctor + 报告 + Skill | PE 头部/导入/导出/延迟导入、静态诊断、依赖候选、JSON/Markdown/HTML、离线转换、权威 Skill 和 22 条评测规格；Codex 三个限定 MCP 模型场景 | Skill 自动触发、其他客户端和完整场景评测 |
| P3 MCP | 本地 stdio、7 个只读工具、路径/进程约束、超时与输出限制；客户端工具调用；Codex/OpenCode V2 项目自动发现；随 npm 分发 | Inspector 图形界面手验、全系统断网、更多用户级发现与真实模型验收 |
| P4 跨 Agent 安装 | npm 全局包与自检；项目/用户级 Skill/MCP；auto/all；校验、卸载、升级及单目标/整批升级进程中断恢复；GUI/CLI ZIP；Pi 原生本地包 | 新机器、运行库缺失、物理断电及安装/卸载中断恢复等验收 |
| P5 Testing Lab | 已有构建/测试 fixture 可作为基础 | Lab 命令、受控生命周期协议、事件时间线、结果对比和 CI 报告尚未开发；已有 smoke 测试不等于 Lab 交付 |

主要证据：[基线](BASELINE.md)、[P0](P0_DELIVERY.md)、[P1](P1_DELIVERY.md)、
[模块](MODULES_DELIVERY.md)、[PE 表](PE_TABLES_DELIVERY.md)、[Doctor](DOCTOR_DELIVERY.md)、
[依赖](DEPENDENCIES_DELIVERY.md)、[报告](REPORTS_DELIVERY.md)、[离线报告契约](SAVED_REPORTS_CONTRACT.md)、
[Skill](SKILL_DELIVERY.md)、[MCP](MCP_DELIVERY.md)、[真实 MCP 宿主](MCP_HOST_VALIDATION.md)。

## P4 分发与剩余验收

| 项目 | 当前情况 | 剩余工作 |
| --- | --- | --- |
| CLI 归档与校验 | x86/x64 ZIP、SHA-256、manifest；执行前校验；npm 管理完整运行文件 | 更多新机器和运行库组合验证 |
| 一条命令安装 | `npm install -g @s0m1ng/rondo`；包含 CLI、MCP、Skill 和依赖 | 完全离线新系统、下载中断与干净环境验收；Node 和 VC++ 仍为前置条件 |
| 用户级 MCP | 三客户端单目标及 auto/all 安装、校验、升级、卸载 | 更多真实客户端的用户级自动发现 |
| 更新与恢复 | 单目标/整批升级、捕获失败回滚、升级进程强制终止后的恢复与重试 | 旧二进制回退、安装/卸载中断及物理断电；不承诺跨目录原子可见性 |
| Pi | 原生包本地安装、资源发现、卸载及用户/项目范围验证 | 公开包、CLI 前置准备引导，以及完整 AgentSession 行为评测；可选 Extension 没有作为必需功能开发 |
| 新机器验收 | CI 和开发机测试通过 | 全新 Windows、VC++ 运行库缺失、离线首次安装等环境验收 |

2.0.0 提供 x64/x86 GUI、独立 CLI、完整 npm 归档和校验文件，见 [发布说明](RELEASE_2.0.0.md)。
旧 `injector_1.0` 资产保留。源码 npm 元数据保持 `private`，只有完整 staging 改为公开；
安装器、MCP 和 Pi 不单独发布。发行包未做代码签名。

证据：[安装器说明](../integrations/installer/README.md)、[CLI 分发](CLI_DISTRIBUTION_DELIVERY.md)、
[项目 MCP](MCP_INSTALLER_DELIVERY.md)、[客户端选择](AGENT_SELECTION_DELIVERY.md)、
[批量 Skill](BATCH_SKILL_DELIVERY.md)、[批量 MCP](BATCH_MCP_DELIVERY.md)、[Pi](PI_PACKAGE_DELIVERY.md)。

## 暂缓或未验证的项目

- **模型行为**：22 条自然语言 Skill 场景仍未完整执行。Codex 已验证 PE、架构冲突和用户报告错误 126 三个限定 MCP 场景，
  其中错误 126 未作实际加载复现。其他客户端的固定模型响应测试不替代真实模型验收。
- **资源发现**：Codex/OpenCode 项目 Skill 发现已实测；Claude Skill 发现、三者用户级 Skill 发现仍未验证。
  Pi 已验证本地包和资源加载，但未创建完整 AgentSession。Codex/OpenCode V2 的 MCP 项目自动发现另有验收，更多用户级发现仍待完成。
- **GUI 遗留**：[UI 审计](UI_BUGS.md) 的 BUG-03 仍只部分修复，宿主执行函数同步阻塞，原子标志未解决排队请求问题；多显示器 DPI 切换未实机验收。
  BUG-19 的严格消息解析已完成，不应再次列作缺失功能。
- **旧实验方法**：第三方进程注入、反射式、部署与 Direct Syscall 的有效性没有本轮验证；旧解析和执行协议限制仍在。
  Direct Syscall 未纳入当前 CMake，现有 GUI 返回请求已提交不证明目标效果。
- **质量证据**：已有固定种子变异、截断输入和 ASan 检查；持续模糊测试、计划中的解析器覆盖率 80% 目标仍无完成证据。
- **发布文档**：中英文快速开始、CHANGELOG、兼容说明已有；SECURITY.md、CONTRIBUTING.md 及系统整理的故障排查说明尚待补齐。
- **明确边界**：ARM64、旧系统实机以及完整 Windows 加载器行为未支持或未验证。
  当前依赖候选检查不递归模拟 Known DLL/SxS/API Set、动态加载与实际搜索顺序；这是公开的诊断边界，不把候选存在说成 DLL 可加载。
  SARIF/JUnit 在原计划中属于后续扩展，现有 JSON/Markdown/HTML 已可用。

补充证据：[Skill 兼容记录](AGENT_COMPATIBILITY.md)、[资源发现](AGENT_DISCOVERY_DELIVERY.md)、
[GUI 消息解析](GUI_MESSAGE_DELIVERY.md)、[PE 检查范围](PE_DELIVERY.md)、[第三方声明](THIRD_PARTY_NOTICES.md)。

## 后续优先顺序

1. **新机器分发验收**：干净 Windows、运行库缺失、完整离线安装及下载中断。
2. **客户端与模型**：Claude Skill、用户级发现、完整场景评测；真实模型 API 调用另行明确范围和费用。
3. **GUI 与恢复遗留**：同步执行、多显示器 DPI、安装/卸载中断和物理断电验收。
4. **P5 Lab**：诊断与分发主链稳定后，再做自有/授权测试程序的生命周期实验协议。

## 本次核对的验证范围

2.0.0 本机 x64/x86 Release 构建与 CTest 各 59 项通过；GUI 界面回归 17 项通过。
两种架构的真实 WebView2 窗口完成进程刷新、中文路径 DLL 诊断、双主题、错误提示及关闭验证。
完整发布验证结果见 [发布说明](RELEASE_2.0.0.md)和对应 Windows CI；历史交付记录保留其当时的版本与测试范围。
