# Windows 原生支持说明

## 1. 概述

CCB Windows 原生支持的目标是：在不依赖 WSL runtime 的情况下，让 `ccb`、`ccbd`、agent 通信、任务派发和回收能在 Windows PowerShell/cmd 环境下闭环运行。

当前状态：P0-P6 代码和文档阶段已完成，P5 Windows 真机黑盒验证 V1-V4 已通过。Windows 原生路径仍建议以实验开关启用：`CCB_EXPERIMENTAL_WINDOWS_NATIVE=1`。

## 2. 架构变更

### IPC：Unix Socket → Named Pipe

- Linux/macOS 继续使用 Unix Socket。
- Windows 原生环境使用 Named Pipe。
- `lease.json` / `ipc.json` 记录 `ipc_kind`、`ipc_ref`，客户端不再只依赖 socket path。
- Named Pipe listener 支持多实例，避免 keeper probe 和 client 请求互相抢占。
- readiness probe、accept、recv/send 生命周期补了 Windows 时序处理。

### 终端复用：tmux → psmux

- Linux/macOS 默认仍走 tmux backend。
- Windows 原生环境走 psmux backend。
- mux backend contract 收口后，上层尽量不直接拼 tmux 命令。
- `CCB_PSMUX_BIN` 可指定 psmux 路径；否则从 PATH 查找。

### 进程管理

- Windows daemon / keeper / 子进程启动加 `CREATE_NO_WINDOW`，避免弹控制台窗口。
- Windows runtime kill 优先走 Job Object metadata，失败再 fallback PID tree。
- PID 存活检查改用 Windows `tasklist.exe`，并使用 System32 绝对路径避免 PATH 劫持。

## 3. psmux 兼容性处理

- `kill-session` 在 psmux named server 下不可靠：项目 teardown 改用 per-project `kill-server`。
- `pipe-pane` 可能输出空文件：logging 改用 `capture-pane` 轮询降级。
- `switch-client` 在 Windows 下存在 capability gap：不作为关键路径依赖。
- `pwsh` placeholder pane 会退出：Windows/psmux placeholder 改用 `cmd.exe /d /s /c "ping -t 127.0.0.1 >nul"`。
- psmux 执行 WSL shell hook/status 脚本会导致 session 不稳定：Windows/psmux 下跳过 `ccb-border.sh`、`ccb-status.sh`、`ccb-git.sh` 等外部 UI 脚本。
- psmux 启动和 start_flow 时间较长：keeper probe timeout、ready timeout、heartbeat grace 已放宽，并在 start request 前刷新 heartbeat。
- 所有 Windows 系统工具调用使用 `%SystemRoot%\System32` 或 `%COMSPEC%`，避免当前目录/PATH 劫持。

## 4. 改动文件清单

### IPC / daemon / keeper

- `lib/ccbd/ipc.py`
- `lib/ccbd/socket_server_runtime/loop.py`
- `lib/ccbd/socket_server_runtime/protocol.py`
- `lib/ccbd/daemon_process.py`
- `lib/ccbd/keeper.py`
- `lib/ccbd/keeper_runtime/loop.py`
- `lib/ccbd/keeper_runtime/records.py`
- `lib/ccbd/keeper_runtime/state.py`
- `lib/ccbd/app_runtime/lifecycle.py`
- `lib/ccbd/handlers/start.py`
- `lib/ccbd/services/ownership.py`
- `lib/ccbd/services/health_monitor_runtime/status.py`
- `lib/ccbd/system.py`

### mux / namespace / UI

- `lib/ccbd/services/project_namespace_runtime/backend.py`
- `lib/ccbd/services/project_namespace_runtime/destroy.py`
- `lib/cli/services/tmux_ui_runtime/service.py`
- `lib/terminal_runtime/env.py`
- `ccb`
- `lib/ccbd/main.py`
- `lib/ccbd/keeper_main.py`

### kill / process cleanup

- `lib/cli/kill_runtime/processes.py`
- `lib/cli/services/kill.py`
- `lib/cli/services/kill_runtime/agent_cleanup.py`
- `lib/cli/services/kill_runtime/finalize.py`
- `lib/ccbd/stop_flow_runtime/pid_cleanup.py`

### CLI / startup

- `lib/cli/services/daemon.py`
- `lib/cli/services/daemon_runtime/compat.py`
- `lib/cli/services/daemon_runtime/facade.py`
- `lib/cli/services/open.py`

### 验证脚本和报告

- `scripts/psmux-capability-gate.ps1`
- `docs/psmux-capability-report.md`

## 5. 测试验证结果

P5 Windows 真机黑盒验证已通过：

- V1：Windows 原生环境初始化通过。
- V2：`ccb` 启动、ccbd mount、psmux namespace 创建通过。
- V3：`ccb ping ccbd` 和 `ccb ask demo "hello"` 通信通过。
- V4：任务派发、`ccb pend demo` 回收链路通过。

验证要求：使用 Windows 原生 PowerShell/cmd，设置：

```powershell
$env:CCB_EXPERIMENTAL_WINDOWS_NATIVE = '1'
$env:CCB_PSMUX_BIN = 'D:\psmux\psmux.exe'
$env:CCB_NO_AUTO_OPEN = '1'
```

## 6. 已知限制和后续计划

- Windows 原生支持当前仍建议走实验开关。
- psmux `switch-client`、`pipe-pane`、`kill-session` 与 tmux 语义不完全一致，已在关键路径做 workaround。
- start_flow 仍在主线程执行，长时间 namespace 构建主要靠 heartbeat/probe 宽限避免 keeper 误重启；后续可改为后台任务或显式 busy 状态。
- Named Pipe 还有少量异常路径可继续补单元测试，例如多实例 race、WinError 232、server recv 错误分类。
- Windows 真机测试要一次只拉一个测试进程，失败后先分析，不连续自动重试。

## 7. 对 Linux/macOS 的影响说明

- Linux/macOS IPC 默认仍是 Unix Socket。
- tmux backend 和现有 tmux UI 逻辑保持默认路径。
- Windows 专用逻辑基本受 `os.name == 'nt'`、`ipc_kind == 'named_pipe'`、`backend_impl == 'psmux'` 限制。
- `subprocess` no-window patch 在非 Windows 直接 no-op。
- PID 检查、Job Object、Named Pipe、psmux placeholder 等改动不应影响 Linux/macOS。
