# CCB WSL 兼容性收敛方案

## 1. 文档定位

这份文档定义 `ccb_source` 在 WSL 环境下的系统性兼容方案，目标不是为单个报错补分支，而是把平台兼容性收敛成稳定边界。

本文覆盖两类已经确认的 WSL 问题：

- 项目位于 `/mnt/<drive>/...` 时，`ccbd`/tmux Unix socket 绑定失败
- 仓库位于 Windows 挂载盘时，`install.sh` / update 路径受 CRLF 与挂载执行语义影响而失败

本文补充但不替代以下文档：

- `docs/ccbd-startup-supervision-contract.md`
- `docs/ccbd-lifecycle-stability-plan.md`
- `docs/ccbd-diagnostics-contract.md`
- `docs/ccb-config-layout-contract.md`

若后续实现出现以下倾向，则以本文为收敛目标：

- 在 `ccbd`、CLI、tmux、installer 各调用点零散添加 WSL 特判
- 仅按 socket 路径长度判断是否可用，而不判断底层文件系统是否支持 Unix socket
- 让安装脚本直接承担 CRLF 自救，而忽略脚本在解析前就可能失败
- 为兼容 WSL 而新增第二套 lifecycle authority

## 2. 当前根因

### 2.1 Socket 绑定失败不是“路径太长”，而是“目标文件系统不支持”

当前实现只按 Unix socket 路径长度回退：

- `lib/storage/path_helpers.py`
- `lib/storage/paths.py`

这意味着当项目位于 `/mnt/c/...`、`/mnt/e/...` 等 WSL 挂载 Windows 盘时，只要路径长度未超阈值，系统仍会把：

- `ccbd.sock`
- `tmux.sock`

放在项目内 `.ccb/ccbd/` 下。

但在这类 drvfs/9p 文件系统上，`AF_UNIX bind()` 可能直接失败并报：

- `Operation not supported`

因此当前根因不是“socket 名称过长”，而是：

- transport artifact 的放置策略缺少“文件系统能力”维度

### 2.2 Installer 失败不是业务逻辑错误，而是脚本执行介质失稳

当前 Unix/WSL 安装路径大量依赖：

- `bash install.sh ...`
- `source install.sh`

但仓库当前没有统一的文本行尾策略文件，导致当 checkout 位于 Windows 挂载盘时：

- shell 脚本可能被写成 CRLF
- `source`/`bash` 在脚本真正开始执行前就可能解析失败

这类错误发生在 shell 解析层，不能靠 `install.sh` 内部逻辑自修复。

因此当前根因不是 installer 某个业务函数写错，而是：

- install/update runtime 没有对“脚本执行介质”做 staging 与标准化

## 3. 设计目标

最终目标固定为：

```text
项目 authority 仍然留在 .ccb
  +
transport / execution artifact 可以脱离项目目录放置
  +
CLI / keeper / ccbd 不因为 WSL mounted fs 失去可用性
```

关键约束：

- `.ccb` 仍是唯一项目 authority 根
- `lifecycle.json`、`lease.json`、agent `runtime.json` 语义不改变
- socket 与 installer staging 只是运行时工件策略，不得演化成第二套 authority
- diagnostics 必须显式说明“期望路径”和“实际路径”，避免把兼容回退隐藏成黑盒

## 4. 收敛原则

### 4.1 一个统一的平台兼容边界

WSL 兼容性必须收敛到统一的 runtime/system 边界，而不是散落在：

- `ccbd` 启动调用点
- CLI `start/kill/ping/doctor`
- tmux namespace 代码
- `install.sh`
- `ccb update`

### 4.2 把 artifact 与 authority 分离

以下内容属于 authority，不迁移：

- `.ccb/ccbd/lifecycle.json`
- `.ccb/ccbd/lease.json`
- `.ccb/agents/<agent>/runtime.json`
- `.ccb/ccb.config`

以下内容属于 transport/execution artifact，可按平台能力放置：

- `ccbd.sock`
- `tmux.sock`
- installer 临时执行脚本副本
- 仅用于执行的临时工作目录

### 4.3 diagnostics 必须保留回退原因

一旦发生 WSL 兼容性回退，诊断面必须能回答：

- 原本期望的项目内 socket 路径是什么
- 实际启用的运行时 socket 路径是什么
- 为什么回退
- 当前使用的是哪类 socket root

## 5. Socket Placement 方案

### 5.1 新的选择逻辑

新增统一的 socket placement policy。策略输入至少包含：

- `project_root`
- `preferred_path`
- `stem`
- 当前平台是否为 WSL
- 目标目录是否支持 pathname Unix socket

策略输出至少包含：

- `preferred_path`
- `effective_path`
- `root_kind`
  - `project`
  - `runtime`
- `fallback_reason`
  - `path_too_long`
  - `unsupported_filesystem`
  - `runtime_root_unavailable`
- `filesystem_hint`
  - 例如 `wsl_drvfs`
  - 例如 `unknown`

### 5.2 目标行为

选择规则固定为：

1. 优先尝试项目内 `.ccb/ccbd/<stem>.sock`
2. 若路径长度超限，则回退到 runtime socket root
3. 若项目目录位于不支持 Unix socket bind 的文件系统，则回退到 runtime socket root
4. `ccbd.sock` 与 `tmux.sock` 必须共用同一套选择逻辑

### 5.3 WSL mounted drive 识别

第一阶段可先显式覆盖高确定性场景：

- 当前环境是 WSL
- 项目路径位于 `/mnt/<drive>/...`

这些路径应直接视为：

- `unsupported_filesystem_for_unix_socket`

后续若要扩展到更一般的 mount 能力探测，应在同一 policy 内扩展，而不是把判断重新散回调用点。

### 5.4 runtime socket root 规则

回退路径优先级：

1. `XDG_RUNTIME_DIR/ccb-runtime`
2. `/tmp/ccb-runtime`

规则：

- 路径必须可创建
- 路径必须位于支持 Unix socket 的本地 Linux 文件系统
- 文件名继续使用 project-derived key，保证项目间稳定隔离

### 5.5 authority 与读路径要求

一旦回退生效：

- `lease.json.socket_path` 必须写实际 socket 路径
- `lifecycle.json.socket_path` 必须写实际 socket 路径
- `doctor`、`ping('ccbd')`、startup report 必须暴露实际 socket 路径
- 前台 attach、kill、keeper ping 必须全部消费同一 `PathLayout` 决策结果

### 5.6 tmux namespace readiness

WSL 下除了 socket 放置，还存在 tmux server/socket 短暂就绪抖动。

规则：

- project namespace backend 必须把 tmux server/socket readiness 吸收到同一个 namespace backend 边界处理
- `prepare_server`、`create_session`、`create_window`、`rename_window`、`select-window`、`list-panes/list-windows` 这类 namespace control-plane 操作，必须使用统一的 ready-retry 语义
- tmux server warmup 与 server policy 持久化必须分阶段处理：
  - `prepare_server` 只负责 warm up server 边界
  - `destroy-unattached off` 这类 server-global policy 只能在 authoritative project session 已存在后写入
  - 不得把 pre-session `set-option` 失败误判成 namespace 不可启动；真实 tmux 可能在 `start-server` 后仍返回 `no server running`
- 背景 heartbeat 内的 namespace/supervision 失败只能记为最近一次后台维护失败，不得直接把已 mounted 的 `ccbd` authority 打成 unmounted
- 这类容错属于 tmux namespace runtime 边界，不得散落到 CLI、provider adapter、或测试调用点

## 6. Diagnostics 方案

兼容性回退不能隐藏在实现里，诊断面应新增以下字段：

- `preferred_socket_path`
- `effective_socket_path`
- `socket_root_kind`
- `socket_fallback_reason`
- `tmux_preferred_socket_path`
- `tmux_effective_socket_path`
- `tmux_socket_root_kind`
- `tmux_socket_fallback_reason`

最少需要落到：

- `.ccb/ccbd/startup-report.json`
- `ccb ping ccbd`
- `ccb doctor`

如果 startup 因 socket bind 失败而退出，失败原因必须尽量归一成稳定类别，例如：

- `listen_socket_failed: unsupported_filesystem`

而不是只暴露底层系统报错文本。

## 7. Installer / Update 方案

### 7.1 基本结论

`install.sh` 本体不应承担 CRLF 自修复责任，因为：

- 若脚本文本已被 CRLF 污染，shell 可能在脚本逻辑执行前就失败

因此 installer 的系统方案必须分两层。

### 7.2 文本规范层

仓库应新增统一文本行尾策略，至少覆盖：

- `install.sh`
- `ccb`
- `bin/*`
- `*.py`
- `*.sh`
- `*.yml`
- `*.yaml`

目标：

- 在 Windows/WSL checkout 里尽量把直接执行的 Unix 文本文件固定为 LF

### 7.3 执行 staging 层

CLI 管理路径不应直接从工作树执行 `install.sh`，而应：

1. 读取原始脚本
2. 归一化为 LF
3. 拷贝到 Unix 临时目录
4. 从 staging 副本执行

该规则应覆盖：

- `run_installer()`
- `ccb update`
- 其他由 Python 启动 Unix installer 的路径

### 7.4 source-safe helper 边界

`install.sh` 还必须满足 source-safe：

- 纯 helper/metadata 函数可通过 `source install.sh` 调用
- `root/sudo` 拒绝、install/uninstall 主流程、副作用入口，只能留在脚本主入口
- 因此测试、installer metadata、upgrade guard 等只读 helper 场景，不应因为调用方 UID 而在 source 阶段直接退出

### 7.5 staging 边界

staging 只是执行介质隔离，不改变安装语义：

- `CODEX_INSTALL_PREFIX` 等输入语义保持不变
- install metadata 行为保持不变
- 脚本内功能不因 staging 获得新的 authority

## 8. 模块落点

建议按下面边界实现：

### 8.1 storage 层

主要改动模块：

- `lib/storage/path_helpers.py`
- `lib/storage/paths.py`

职责：

- 只负责 socket placement policy
- 不引入 CLI / ccbd / tmux 业务依赖

### 8.2 ccbd / diagnostics 层

主要改动模块：

- `lib/ccbd/app_runtime/lifecycle.py`
- `lib/ccbd/handlers/ping_runtime/payloads.py`
- `lib/cli/services/doctor.py`
- 相关 render 模块

职责：

- 暴露 socket 选择结果
- 将 failure reason 稳定化

### 8.3 install / update 层

主要改动模块：

- `lib/cli/management_runtime/install.py`
- `lib/cli/management_runtime/commands_runtime/update.py`
- 仓库根 `.gitattributes`

职责：

- staging + LF normalization
- 不把兼容逻辑散进 shell 业务实现

### 8.4 tmux namespace / supervision 层

主要改动模块：

- `lib/ccbd/services/project_namespace_runtime/backend.py`
- `lib/ccbd/app_runtime/lifecycle.py`

职责：

- project namespace backend 统一处理 tmux server/socket ready-retry
- heartbeat 背景维护失败只写最近失败原因，不得直接导致已 mounted daemon authority 退出

## 9. 测试矩阵

### 9.1 storage / unit

新增回归测试：

- 项目路径在 `/mnt/c/...` 时，`ccbd_socket_path` 回退到 runtime root
- 项目路径在 `/mnt/e/...` 时，`tmux_socket_path` 回退到 runtime root
- 非 WSL 普通 Linux 项目路径仍优先使用 `.ccb/ccbd/*.sock`
- 长路径与 WSL mounted drive 两类回退原因要能区分

### 9.2 diagnostics / blackbox

新增回归测试：

- startup report 包含 preferred/effective socket path 与 fallback reason
- `ping ccbd` / `doctor` 输出 runtime socket root 信息
- bind 失败时 failure reason 分类稳定

### 9.3 installer / update

新增回归测试：

- 从 CRLF 形式的 `install.sh` staging 后仍可执行
- `run_installer()` 不再直接依赖工作树脚本文本形态
- `ccb update` 通过 staging 执行 release 包内 `install.sh`

### 9.4 真机验证

必须覆盖以下真实场景：

- WSL 项目位于 `/mnt/e/...`
- WSL 项目位于 Linux home 目录
- release 包安装
- source checkout 安装

## 10. 实施顺序

### Phase 1

- 落 socket placement policy
- 修 `ccbd.sock` / `tmux.sock` 同步回退
- 先补 unit tests

### Phase 2

- 暴露 diagnostics 字段
- 更新 startup / doctor / ping 输出

### Phase 3

- 加 `.gitattributes`
- 实现 installer staging
- 补 install/update 测试

### Phase 4

- 在真实 WSL mounted Windows drive 上跑全链路验证

## 11. 非目标

本文不做以下变更：

- 不改变 keeper 是唯一 lifecycle authority 的约束
- 不把 provider runtime 迁移成 Windows 原生控制面
- 不讨论 native Windows 支持路线
- 不顺带修复 macOS 时序类失败

macOS 问题应单独分析，不得为追求“跨平台统一”而把 WSL 根因混入同一个补丁里。
