# OpenCode V2 接入与端到端验收

日期：2026-11-03。安装器 `0.1.0-dev.14`，npm 包 `0.1.0-dev.9`，OpenCode `2.2.5`。
分支 `codex/opencode-v2-mcp` 从 main `48d15c2` 创建，开始实现前已推送同名远端分支。

## 安装与升级

安装可信的本地 npm 归档后，先确认客户端候选，再在目标项目配置 MCP：

```powershell
npm install -g .\som1ng-rondo-0.1.0-dev.9.tgz
rondo self-check
rondo list-agents
rondo setup --integration mcp --agent opencode --scope project --project 'D:\work\my-app' --client 'D:\tools\opencode.exe' --allow-root 'D:\work\my-app' --verify
rondo verify --integration mcp --agent opencode --scope project --project 'D:\work\my-app'
```

`--client` 使用 `list-agents` 输出中的原生 EXE。支持 `@opencode/cli` 的嵌套和提升平台包，
x64 优先选 `cli-windows-x64-baseline/bin/opencode.exe`。包根目录的同名启动文件可能不是有效 Windows 应用。

新安装按实际客户端版本选择配置：

| 客户端 | 受管条目 | 字段 |
| --- | --- | --- |
| OpenCode `2.2.5` | `mcp.servers.dll_doctor` | `type: local`、命令数组、`disabled: false`、`codemode: false` |
| OpenCode `1.19.4` | `mcp.dll_doctor` | `type: local`、命令数组、`enabled: true` |

关闭该服务的 Code Mode 后，七个工具直接暴露给模型。已有 JSONC 中的其他服务、MCP 默认设置和注释均保留。
新安装的 `--dry-run` 不执行版本探测，返回 `managed_entries_by_client_version` 中的两种候选；
已有受管安装则按收据预览单一布局。

V1 客户端升级到 V2 后，使用相同的完整运行参数执行 `rondo upgrade`。升级更新客户端绑定，
保留 V2 可兼容读取的 V1 条目布局；这样中断恢复仍只需替换受管条目及收据。
新建的 V2 布局不接受直接降级到 V1。两种布局同时出现同名条目、手动移动受管条目、
修改 Code Mode 或损坏收据都会阻止写入。

project/user 范围均支持安装、升级、校验、卸载和已有恢复入口；用户配置位置与覆盖变量限制见
[安装器说明](../integrations/installer/README.md#用户级-mcp-配置)。

## 重复运行端到端验收

[`tests/opencode_acceptance.py`](../tests/opencode_acceptance.py) 使用已安装的原生 OpenCode `2.2.5`、
可信 npm 归档和仓库构建的 `noop_fixture.dll`。替换以下客户端路径；摘要文件必须不存在：

```powershell
python tests/opencode_acceptance.py `
  --archive .\build\npm-opencode-v2\som1ng-rondo-0.1.0-dev.9.tgz `
  --opencode 'D:\tools\opencode.exe' `
  --dll .\build\msvc-x64\Release\noop_fixture.dll `
  --output .\build\npm-opencode-v2\opencode-acceptance-new.json
```

流程：空缓存离线 npm 全局安装 → 8 项自检 → 未安装项目负例 → 生成 V2 项目配置 →
发现七个工具并验证四项调用 → 重复 setup / verify → MCP 卸载后负例 → npm 卸载。
四项调用分别为 PE 检查、读取保存的失败报告、拒绝相对路径、拒绝后再次成功检查 PE。
实时结果与直接 CLI 输出比较；保存报告必须完整保留原始错误、状态和耗时。

测试使用中文、空格、emoji 路径，配置、用户目录、数据库和运行数据位于临时目录。
项目发现保持开启；`OPENCODE_CONFIG_CONTENT` 仅提供验收 provider、权限等设置，不含 MCP 条目。
若祖先目录存在 OpenCode 配置，测试会拒绝执行，避免环境中的其他配置污染发现结果。

### V2 冷启动与结果格式

本机 `2.2.5` 冷启动时，`/api/config` 已包含项目配置，但 `/api/mcp` 会先返回空列表或 `pending`。
此时立即发起模型请求，只能看到内置 `skill`，会导致发现测试失败。
上游 [#50710](https://github.com/anomalyco/opencode/issues/50710) 的后续讨论也指出了冷启动时序问题。

验收启动私有 `serve --stdio --hostname 127.0.0.1 --port 0`，读取并检查其 loopback URL，
以 `/api/mcp?location[directory]=...` 等待 `dll_doctor` 为 `connected`，再使用 `run --server <url>`。
客户端与服务共用隔离环境和临时生成的密码；超时或连接失败不会计为通过。

`2.2.5` 即使禁用 Skill，仍会在工具清单中声明内置 `skill`。判定器只允许这一个已观察到的内置项，
其余清单必须严格等于七个 MCP 工具，参数限制也必须保留。
V2 将 MCP 错误包装为 `tool.execution`，内层 message 仍是适配器 JSON；
测试解出该 JSON 后继续验证原始 `PATH_POLICY` 错误和调用顺序。

## 本机结果

完整归档验收通过，摘要位于 `build/npm-opencode-v2/opencode-acceptance.json`。
本地归档 SHA-256：

```text
db96066170b039483315e18e9e098f0d24b3e45b960d8e96eed624ac88012092
```

| 检查 | 结果 |
| --- | --- |
| 安装器 `npm test`，设置真实 CLI/MCP 测试路径 | 245 项通过，0 跳过 |
| MCP `npm run build` | 通过 |
| npm 入口 `npm test` | 28 项通过 |
| `python tests/npm_assembly_tests.py` | 4 项通过 |
| 在 `tests` 运行 `python -m unittest mcp_hosts_tests codex_acceptance_tests opencode_acceptance_tests` | 38 项通过 |
| `tests/npm_package_tests.py`，指定三客户端及本轮归档 | 2 项通过，包含用户级三客户端升级/卸载及项目恢复检查 |
| `tests/opencode_acceptance.py`，指定本轮归档 | 全流程通过；本机模型协议请求共 7 次，外部模型调用 0 次 |

三个发现阶段的本机请求数为 **1 + 5 + 1**。安装阶段收到四个经校验的工具结果，
完成原因依次为四次 `tool-calls` 和一次 `stop`。

三客户端包检查使用 Codex `0.164.0`、Claude `2.1.310`、OpenCode `2.2.5`。
最初使用当前全局 Claude `2.1.316` 时，检查按版本门禁失败；随后从已有 npm 缓存读取并校验
`2.1.310` 平台包，在临时目录运行基线 EXE 后通过。全局 Claude 安装保留原状。

原生 x64/x86 CLI 与 DLL fixture 复用此前已验证的 `2.0.0-dev.9` / Schema `1.6` 构建。
MCP 从当前源码构建；npm 组装复用与锁文件逐项匹配的依赖目录，并通过 `npm ls --omit=dev --all` 检查。
本地组装省略 `--revision`，不把复用二进制标成新提交的构建。

CI 增加不需要安装客户端的 V2 验收判定回归；真实 V2 完整验收为本机显式运行。
这些结果证明项目发现和工具协议可用。V2 用户级自动发现、Skill 发现、真实模型自主行为和全新 Windows 环境仍待验收。

接口依据：[V2 MCP](https://opencode.ai/v2/docs/mcp-servers/)、
[V2 配置](https://opencode.ai/v2/docs/config/)、[V1 迁移](https://opencode.ai/v2/docs/migrate-v1/)、
[权限](https://opencode.ai/v2/docs/permissions/)、[CLI](https://opencode.ai/v2/docs/cli/)、
[API](https://opencode.ai/v2/docs/api/)。
