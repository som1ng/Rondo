<p align="center">
  <img src="assets/logo.png" alt="Rondo" width="160" />
</p>

<h1 align="center">Rondo</h1>

<p align="center">
  Windows DLL 注入与 PE 诊断工具集
</p>

<p align="center">
  <a href="https://github.com/som1ng/Rondo/releases/tag/v2.0.0"><img src="https://img.shields.io/github/v/release/som1ng/Rondo?label=Release&color=blue" alt="Release" /></a>
  <a href="https://www.npmjs.com/package/@s0m1ng/rondo"><img src="https://img.shields.io/npm/v/@s0m1ng/rondo?label=npm&color=cb3837" alt="npm" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/som1ng/Rondo" alt="License" /></a>
  <img src="https://img.shields.io/badge/platform-Windows_x64%20|%20x86-0078D4" alt="Platform" />
</p>

<br />

<p align="center">
  <img src="assets/screenshot.jpg" alt="Rondo Workbench" width="820" />
</p>

<br />

## 功能特性

- **6 种 DLL 注入机制 (GUI & CLI)** — 支持 CreateRemoteThread、QueueUserAPC、SetWindowsHookEx、Reflective Injection、DLL Hijacking 以及 Direct Syscall。
- **Core 注入预检与安全防护** — 注入前自动校验 DLL 有效性、PE 架构与目标进程匹配度，防止因架构不匹配（如 x86 注入 x64）导致崩溃，提供 `--force` 选项支持强制执行。
- **WebView2 现代 GUI** — 原生 Win32 宿主 + WebView2 渲染，轻量流畅；支持浅色/深色主题、进程即时搜索与架构筛选、DLL 拖放以及活动日志。
- **进程与模块深度诊断** — 免提权只读枚举系统进程与模块快照，精准识别 x86/x64/ARM64 架构。
- **PE 静态分析** — 纯静态解析 PE32/PE32+ 头部、节区表、导入表、导出表（含转发与别名）以及延迟导入表，无需加载文件。
- **DLL Doctor 智能诊断** — 自动排查 PE 损坏、架构冲突与依赖缺失，提供置信度评估与排查建议。
- **多格式报告导出** — 原生支持 JSON / Markdown / HTML 单文件离线报告，支持对已有诊断报告进行离线转换。
- **Agent Skill & MCP 集成** — 内置 Windows DLL Doctor Skill 与本地 stdio MCP 服务，支持 Codex、Claude Code、OpenCode、Pi 等 AI 编程助手。

## 快速开始

### GUI 下载

从 [Releases](https://github.com/som1ng/Rondo/releases/tag/v2.0.0) 下载对应架构压缩包，解压后直接运行 `Rondo.exe`：

| 架构 | 下载 |
| --- | --- |
| Windows x64 | [rondo-gui-2.0.0-windows-x64.zip](https://github.com/som1ng/Rondo/releases/download/v2.0.0/rondo-gui-2.0.0-windows-x64.zip) |
| Windows x86 | [rondo-gui-2.0.0-windows-x86.zip](https://github.com/som1ng/Rondo/releases/download/v2.0.0/rondo-gui-2.0.0-windows-x86.zip) |

> 运行环境要求：[WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) 与 [VC++ v14 运行库](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)，无需 Node.js。

### npm 全局安装

```powershell
npm install -g @s0m1ng/rondo
rondo self-check
rondo --version --json
```

> 需要 Windows x86/x64、Node.js 22.19+ 和 VC++ v14 运行库。详见 [npm 包说明](integrations/npm/README.md)。

### 源码构建

```powershell
git clone https://github.com/som1ng/Rondo.git
cd Rondo
python -m pip install -r tests/requirements.txt   # 测试依赖
cmake --preset msvc-x64
cmake --build --preset msvc-x64-debug --parallel
ctest --preset msvc-x64-debug
```

构建产物：
- GUI: `build/msvc-x64/Debug/Rondo.exe`
- CLI: `build/msvc-x64/Debug/cli/rondo.exe`

## CLI 使用指南

Rondo CLI 兼具强大的 **DLL 注入能力** 与完整的 **进程/PE 诊断工作流**，支持终端管道与自动化脚本。

### 1. DLL 注入 (`inject`)

Rondo CLI 内置 Core 预检引擎，执行注入前自动校验目标进程与 DLL 的架构一致性：

```powershell
# 远程线程注入 (CreateRemoteThread，经典通用)
rondo inject --dll C:\path\to\payload.dll --method crt --pid 1234

# 异步过程调用注入 (QueueUserAPC)
rondo inject --dll C:\path\to\payload.dll --method apc --pid 1234

# 窗口消息钩子注入 (SetWindowsHookEx)
rondo inject --dll C:\path\to\payload.dll --method hook --pid 1234

# 内存反射注入 (Reflective DLL Injection，不依赖磁盘落地模块)
rondo inject --dll C:\path\to\payload.dll --method reflective --pid 1234

# DLL 劫持部署 (部署同名代理 DLL 至目标程序目录)
rondo inject --dll C:\path\to\version.dll --method hijack --target-dir "C:\Program Files\TargetApp"

# 强制注入 (忽略预检架构不匹配等警告)
rondo inject --dll C:\path\to\payload.dll --method crt --pid 1234 --force

# 输出结构化 JSON 结果 (适合脚本与自动化工具捕获预检和执行状态)
rondo inject --dll C:\path\to\payload.dll --method crt --pid 1234 --json
```

#### 注入机制对照表

| 机制 (`--method`) | 目标指定 | 说明 |
| --- | --- | --- |
| `crt` | `--pid <PID>` | **CreateRemoteThread**：经典注入方式，在目标进程创建远程线程加载 DLL |
| `apc` | `--pid <PID>` | **QueueUserAPC**：向目标可警惕线程的 APC 队列投递执行例程 |
| `hook` | `--pid <PID>` | **SetWindowsHookEx**：通过设置 WH_GETMESSAGE 等全局/局部窗口钩子注入 |
| `reflective` | `--pid <PID>` | **Reflective Injection**：自解析 PE 并在目标内存直接映射展开，隐蔽性高 |
| `hijack` | `--target-dir <DIR>` | **DLL Hijacking**：向目标 EXE 所在目录放置同名 DLL 劫持加载流程 |
| `syscall` | `--pid <PID>` | **Direct Syscall**：实验性直接 NT 系统调用 (GNU x64 构建可用) |

### 2. 进程与模块查询

```powershell
rondo process list --json                                           # 列出所有活跃进程
rondo process inspect --pid <PID> --json                            # 查询指定进程详细信息与架构
rondo process modules --pid <PID> --json                            # 枚举目标进程已加载模块与基址
rondo process modules --pid <PID> --format markdown --output mod.md  # 导出 Markdown 模块清单
```

### 3. PE 静态解析与 DLL Doctor

```powershell
rondo pe inspect <file.dll> --json                                  # 纯静态分析 PE 头部、节区与导入导出表
rondo doctor <file.dll> --target-arch x64 --json                    # 预检 DLL 在目标架构下的可加载性
rondo doctor <file.dll> --search-dir ./libs --json                  # 检查 DLL 的直接/延迟依赖候选文件
rondo doctor <file.dll> --format html --output report.html          # 生成单文件自包含 HTML 诊断报告
rondo report export saved.json --format html --output out.html      # 将已保存的 JSON 报告转换为 HTML
```

#### 退出码规范

| 退出码 | 含义 |
| --- | --- |
| `0` | 命令成功完成，无阻断性发现 |
| `1` | PE 损坏、Doctor 阻断项或注入失败 |
| `2` | 命令行参数无效 (Usage / InvalidArgument) |
| `3` | 目标不可访问或权限不足 (AccessDenied / NotFound) |
| `4` | 内部错误、不支持的格式或输出写入失败 |
| `5` | 执行或查询超时 (`--timeout-ms`) |

## Agent 集成 (Skill & MCP)

Rondo 原生支持主流 AI 编程助手，提供只读诊断能力与 MCP 服务：

```powershell
# 自动检测并配置本机 Agent 客户端 (Codex / Claude Code / OpenCode)
rondo setup --agent auto --scope project --verify
```

- **Windows DLL Doctor Skill**：[Skill 规范](integrations/skills/windows-dll-doctor/SKILL.md)
- **本地 stdio MCP 服务**：[MCP 接入文档](integrations/mcp/README.md)
- **客户端兼容性说明**：[Agent Compatibility](docs/AGENT_COMPATIBILITY.md)
- **本地安装器详情**：[Installer Guide](integrations/installer/README.md)

## 项目结构

```text
src/                    Win32 GUI 实现与注入核心方法
core/                   进程枚举、PE 解析、注入预检与 RAII 工具
include/dllinjector/    公共头文件、数据类型与接口定义
apps/cli/               CLI 命令行工具入口与格式化渲染
apps/gui/               基于 WebView2 的现代桌面 GUI
schemas/                版本化 JSON Schema (v1.0 - v1.6)
tests/                  CTest 回归测试、Playwright GUI 测试与 Fixtures
integrations/           Agent Skill、MCP 服务、npm 包与安装器
docs/                   技术契约、交付记录与设计文档
```

## 技术文档

| 文档 | 说明 |
| --- | --- |
| [CLI 契约](docs/P1_CONTRACT.md) | 命令行接口规范与参数说明 |
| [PE 解析契约](docs/PE_TABLES_CONTRACT.md) | PE 静态检查实现细节 |
| [Doctor 契约](docs/DOCTOR_CONTRACT.md) | 诊断规则与置信度体系 |
| [依赖候选契约](docs/DEPENDENCIES_CONTRACT.md) | 目录依赖候选扫描规则 |
| [报告契约](docs/REPORTS_CONTRACT.md) | Markdown / HTML 报告模板规范 |
| [离线转换契约](docs/SAVED_REPORTS_CONTRACT.md) | 已保存报告导出转换说明 |
| [模块契约](docs/MODULES_CONTRACT.md) | 模块枚举与内存基址解析 |
| [Agent 接入指南](docs/AGENT_COMPATIBILITY.md) | Skill 与 MCP 安装配置手册 |
| [npm 包交付](integrations/npm/README.md) | 全局命令打包与环境自检 |
| [项目路线图](docs/ROADMAP_STATUS.md) | 开发阶段与功能规划 |

## English Overview

Rondo 2.0 is a modern Windows DLL injection engine and PE diagnostic toolkit. It provides a lightweight WebView2 GUI, a standalone CLI with full injection and diagnostic workflows, an npm package (`@s0m1ng/rondo`), and native Agent Skill / MCP integrations.

### Key Capabilities
- **6 Injection Methods in GUI & CLI**: CreateRemoteThread (`crt`), QueueUserAPC (`apc`), SetWindowsHookEx (`hook`), Reflective Injection (`reflective`), DLL Hijacking (`hijack`), and Direct Syscall (`syscall`).
- **Preflight Safety Checks**: Built-in architecture compatibility and PE format validation before injection (with `--force` override).
- **Diagnostics**: Read-only process/module enumeration, static PE parsing (PE32/PE32+), dependency candidate checks, and self-contained HTML/Markdown report generation.

Quick install via npm:
```powershell
npm install -g @s0m1ng/rondo
rondo self-check
```

Or inject via CLI:
```powershell
rondo inject --dll payload.dll --method crt --pid 1234
```

See the sections above for GUI downloads and complete CLI documentation.

## 许可证

本项目自有代码遵循 [MIT](LICENSE) 许可证。第三方代码保留其原有许可证，详情请参阅 [第三方声明](docs/THIRD_PARTY_NOTICES.md)。

---

<p align="center">
  <a href="https://github.com/som1ng/Rondo/issues">Issues</a> · <a href="https://github.com/som1ng/Rondo/releases">Releases</a>
</p>
