# Rondo 2.0.0

第二版提供 Windows GUI 和可通过 npm 安装的 CLI，附带 DLL Doctor Skill、7 个只读 MCP 工具和 Agent 安装器。
GUI、CLI、npm 包、MCP 与安装器版本统一为 `2.0.0`，CLI/MCP JSON Schema 保持 `1.6`。

## 下载与安装

### GUI

选择 `rondo-gui-2.0.0-windows-x64.zip` 或 `rondo-gui-2.0.0-windows-x86.zip`，解压后运行 `Rondo.exe`。
需要匹配架构的 [VC++ v14 运行库](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
和 [Microsoft Edge WebView2 Evergreen](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)，无需 Node.js。

### npm CLI

需要 Windows x86/x64、Node.js 22.19+ 和 VC++ v14 运行库：

```powershell
npm install -g @s0m1ng/rondo
rondo self-check
rondo --version --json
rondo doctor 'D:\samples\example.dll' --format html --output .\doctor-report.html
```

包名中 `s0m1ng` 使用数字 `0`。包内已有两种架构的 CLI、MCP、Skill、安装器和 Node 依赖，安装时无需编译。
PowerShell 限制 `.ps1` 时可使用 `npm.cmd` 和 `rondo.cmd`。

也可下载 `s0m1ng-rondo-2.0.0.tgz` 后执行 `npm install -g .\s0m1ng-rondo-2.0.0.tgz`。
只需要原生 CLI 时，使用 `rondo-cli-2.0.0-windows-<架构>.zip`，无需 Node.js。

### Agent 接入

```powershell
rondo setup --agent auto --scope project --verify
rondo setup --integration mcp --agent auto --scope project --allow-root 'D:\samples' --verify
```

MCP 安装器当前适配 Codex `0.164.0`、Claude Code `2.1.310`、OpenCode `1.19.4` / `2.2.5`。
`rondo list-agents` 可查看本机候选。用户级配置、批量安装、升级、恢复及卸载见
[安装器说明](https://github.com/som1ng/Rondo/blob/v2.0.0/integrations/installer/README.md)。

## 本版内容

- WebView2 桌面界面、进程列表、DLL Doctor 预检、日志与双主题。
- 进程/模块只读查询，PE32/PE32+ 头部、导入、导出和延迟导入解析。
- 架构冲突、损坏 PE、DLL 标志和显式目录中的依赖候选诊断。
- JSON、Markdown、离线 HTML 报告；已有 Schema 1.0–1.6 报告的离线转换。
- Skill、只读 MCP、项目/用户级配置、批量升级、升级进程中断恢复和 `rondo self-check`。
- x86/x64 归档、版本及哈希清单、MIT 许可证和第三方声明。

## 发布验证

- 本机 MSVC x64/x86 Release 构建成功，CTest 各 59/59 通过。
- GUI 界面回归 17 项通过；两种架构均完成真实 WebView2 启动、进程刷新、中文 DLL 路径诊断、双主题和关闭验证。
- GUI 原生归档测试两种架构各 4 项通过，CLI 原生归档测试各 6 项通过。
- MCP 7 项、npm 入口 28 项、Pi 本地包 3 项通过。
- 合并最新主线后，安装器 246 项通过、0 跳过；Codex/MCP/OpenCode 宿主证据检查 45 项通过。
- 完整 npm 归档的结构与离线安装测试通过，包含自检、原生 CLI、Skill/MCP、升级中断恢复与卸载；
  额外使用 Codex `0.164.0`、Claude Code `2.1.310`、OpenCode `2.2.5` 验证配置生命周期。
- `npm publish --dry-run` 成功。发布产物由合入后的 Windows CI 构建。

## 升级与已知限制

旧 `injector_1.0` GUI 与本版下载包相互独立，直接解压本版即可。
开发版 npm 包使用过未公开的 `@som1ng/rondo` 名称；正式包改为 `@s0m1ng/rondo`。
已有 Agent 安装在更换运行文件后，需要对相应项目或用户范围执行 `rondo upgrade`，按提示重新声明 MCP 授权目录。

静态诊断不证明 DLL 可加载。旧实验方法保留，执行效果仍未做完整运行验收；GUI 执行路径仍有同步阻塞限制。
GUI 预检导出沿用独立的 `1.0.0` 格式；CLI 离线转换和 MCP `read_report` 接受 CLI Schema 1.0–1.6 报告。
ARM64、全新缺运行库系统、物理断电恢复、多显示器 DPI 和完整客户端/模型场景验收仍是后续工作。
P5 DLL 生命周期实验室尚未开发。

发布包未做代码签名。下载后可用 `Get-FileHash -Algorithm SHA256 <文件>` 对照随附校验文件。
项目自有代码采用 MIT；第三方许可随包提供。
