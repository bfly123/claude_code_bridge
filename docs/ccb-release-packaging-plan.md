# CCB Release 封装与发布方案

## 1. 文档定位

本文定义 `ccb_source` 面向真实用户交付时的 release 封装方案，重点回答以下问题：

- `ccb` 应该以源码仓安装为主，还是以 release 分发为主
- release 应该封装到什么程度
- 不同平台和不同用户环境下，哪些依赖由 release 内置，哪些必须外置
- 安装、更新、回滚、诊断分别由哪个层负责

本文是发布与分发方向的设计文档，不替代运行时契约文档：

- `docs/ccbd-startup-supervision-contract.md`
- `docs/ccbd-diagnostics-contract.md`
- `docs/ccb-config-layout-contract.md`
- `docs/ccbd-windows-psmux-plan.md`

当 release 方案真正落地并改变 CLI 行为、诊断面或平台支持面时，必须同步更新对应 contract 文档，而不是只改本文。

## 2. 当前现状

### 2.1 直接来自当前代码的事实

以下结论直接来自当前仓库代码和文档：

- 当前主安装入口是源码仓内的 `./install.sh install`
- Windows 安装入口是 `install.ps1`
- `ccb update` 目前优先尝试对安装目录做 `git pull` 或 `git checkout tag`
- 如果安装目录不是 git 仓，`ccb update` 会退回到下载 tarball 再安装
- 当前默认安装目录是用户目录下的 `~/.local/share/codex-dual`
- 当前默认可执行链接目录是 `~/.local/bin`
- 当前 README 仍以“clone 仓库后运行 `install.sh`”作为主要安装说明
- 当前分发已经有 release/tarball 更新能力雏形，但它还不是唯一主路径

对应代码锚点：

- [install.sh](/home/bfly/yunwei/ccb_source/install.sh)
- [lib/cli/management_runtime/install.py](/home/bfly/yunwei/ccb_source/lib/cli/management_runtime/install.py)
- [lib/cli/management_runtime/commands_runtime/update.py](/home/bfly/yunwei/ccb_source/lib/cli/management_runtime/commands_runtime/update.py)
- [README.md](/home/bfly/yunwei/ccb_source/README.md)

### 2.2 基于这些事实的归纳

以下判断是基于上述事实做的设计归纳，不是代码里已经完全成立的现状：

- 当前项目处于“开发安装”和“产品分发”混用阶段
- 安装成功与否仍有较多现场环境依赖，封装边界不够清晰
- 如果继续把源码安装当作主要分发方式，兼容性复杂度会持续堆积在用户机器上
- 现有 `ccb update` 的 tarball 路径说明项目已经适合收口到 release-first 分发

## 3. 设计结论

### 3.1 总体决策

`ccb` 应采用：

- `release` 作为正式交付物
- `install.sh` / `install.ps1` 作为 release 安装器
- 源码仓安装仅保留给开发者和调试场景

不再把“用户 git clone 仓库，然后直接安装当前工作树”作为主要产品路径。

### 3.2 原因

这样做的核心收益：

- 版本边界清晰，用户问题可以精确对齐到 release 版本
- 安装输入更稳定，不依赖用户当前 clone 的工作树状态
- 更新和回滚可以围绕正式版本收口
- 平台兼容可以在发布阶段预处理，而不是在用户机器现场分支判断
- 可以逐步提升封装性，例如未来内置 Python runtime，而不破坏外部 CLI 语义

## 4. 目标与非目标

### 4.1 目标

release 方案必须满足：

- 对普通用户，主入口是安装 release，而不是 clone 源码仓
- 对 Linux/macOS/WSL，提供稳定的 `tmux` 方案
- 对 Windows Native，保留向 `psmux` 方案收敛的独立路径
- 安装、更新、诊断职责清晰，不再彼此混用
- 版本、日志、诊断包能精确指向某个 release 构建
- 支持稳定更新与显式回滚
- 尽量减少用户机器上的动态依赖安装

### 4.2 非目标

本文不追求：

- 第一阶段就把所有外部依赖全部打进 release
- 第一阶段支持所有 Linux 发行版的零前置依赖安装
- 第一阶段彻底解决 Windows Native mux 路线
- 用平台特判散落在 CLI、`ccbd`、provider 逻辑中

## 5. 核心职责拆分

### 5.1 release 的职责

release 负责提供一个明确版本、明确构建来源、明确支持平台的交付物。

release 必须承担：

- 项目代码本体
- 内部 Python 模块
- skills、模板、默认配置、tmux 样式资源
- build metadata
- version manifest
- checksum
- 对应平台的安装器脚本

release 不应继续承担：

- 依赖用户当前源码工作树
- 依赖用户当前 git 状态来定义版本身份

### 5.2 安装器的职责

安装器负责把某个 release 正确落到本机。

安装器应承担：

- 选择安装目录
- 放置版本目录
- 建立可执行入口
- 做前置环境检查
- 输出精确缺失项
- 写入最小必要的用户级配置

安装器不应承担：

- 从源码目录“推导当前产品长什么样”
- 在安装过程中临时拼装一套未版本化的运行时

### 5.3 `ccb doctor` 的职责

`doctor` 负责说明“为什么当前环境不能运行”，而不是替代安装器完成封装。

它应承担：

- 检查系统依赖是否齐备
- 检查 provider CLI 是否存在
- 检查当前平台是否被正式支持
- 检查安装目录、版本信息、日志目录、`ccbd` 诊断信息

## 6. 依赖分层策略

### 6.1 A 层：必须内置到 release

这部分由项目完全控制，应该尽量随 release 一起交付：

- `ccb` 代码和 Python 包
- `ccbd` 控制面代码
- skills、命令模板、默认 rules
- 默认 tmux 配置和样式文件
- 内部脚本、数据模型、静态资源
- build 信息与版本元数据

这部分不应要求用户在安装时现场下载。

### 6.2 B 层：可以逐步内置，但允许分阶段推进

这部分建议作为 release 封装增强方向：

- Python runtime
- Python 第三方依赖
- 文件监听等辅助运行时依赖

推荐路线：

- 第一阶段：保留本机 Python 3.10+ 前置要求，但依赖尽量少
- 第二阶段：按平台打包自带 Python runtime 的 self-contained release

原因：

- 第一阶段成本低，先把分发路径收口
- 第二阶段可以显著减少“用户环境 Python 不一致”问题

### 6.3 C 层：明确外置，不做强内置

以下依赖不适合作为当前 release 的内置对象，应该作为外部前置条件明确声明：

- `tmux`
- Windows Native 路线下未来的 `psmux`
- Claude/Codex/Gemini/OpenCode 等 provider CLI
- 用户自己的 provider 登录态、token、配置文件
- 用户终端、shell、PATH、终端宿主环境

原因：

- 这些依赖受平台、用户账号、许可、认证和运行方式强约束
- 即使技术上强行打包，也会放大维护成本和行为不确定性

结论：

release 的目标不是“把一切都带上”，而是“把项目内部依赖尽量带上，并把少数外部依赖清晰外置”。

## 7. 平台支持策略

### 7.1 稳定支持面

第一优先级稳定支持：

- Linux + `tmux`
- macOS + `tmux`
- WSL + `tmux`

这些平台共享同一条主产品路线：

- `ccb`
- `ccbd`
- `tmux`
- Unix socket

### 7.2 独立支持面

Windows Native 不应与当前 `tmux` 路线硬混在一起。

建议：

- Windows Native 继续作为独立发布轨
- 与 `docs/ccbd-windows-psmux-plan.md` 对齐
- 在 `psmux` 后端成熟前，不宣称与 Linux/macOS/WSL 同等稳定

### 7.3 发布矩阵

建议最终形成以下构建矩阵：

- `ccb-linux-x86_64.tar.gz`
- `ccb-linux-aarch64.tar.gz`
- `ccb-macos-universal.tar.gz` 或按架构拆分
- `ccb-wsl.tar.gz`
- `ccb-windows-x86_64.zip`

每个 artifact 至少附带：

- `install.sh` 或 `install.ps1`
- `VERSION`
- `BUILD_INFO.json`
- `SHA256SUMS`

### 7.4 平台推进顺序

第一阶段不应同时追求 Linux、macOS、Windows 三线并进。

建议顺序：

1. 先把 Linux release 路线做成正式主路径
2. 再做 macOS release
3. 最后做 Windows Native `psmux` 路线

原因：

- 当前主运行时语义最接近 Linux + `tmux`
- 现有安装、socket、tmux、PATH、日志与诊断路径本质上都更偏 Unix/Linux 语义
- Windows Native 后端尚未进入 `psmux` 实装阶段，不适合现在纳入 release 主线
- macOS 虽然也走 `tmux`，但它的安装与分发问题和 Linux 不是完全同一类

关于 macOS 的结论：

- 不需要单独再写一套 release 理念或运行时契约
- 但需要单独的构建目标、安装验证和兼容性测试

也就是说，macOS 不需要与 Linux 完全分裂成两套设计，但应被视为单独发布目标，而不是“Linux 顺手兼容一下”。

## 8. 安装拓扑设计

### 8.1 用户级安装

继续保持用户级安装，而不是系统级安装：

- 安装目录默认：`~/.local/share/codex-dual`
- 命令链接目录默认：`~/.local/bin`

这样做的原因：

- 避免 root/sudo
- 降低权限复杂度
- 与 provider CLI 的用户级配置模型一致

### 8.2 版本目录结构

建议从“单安装目录覆盖”逐步演进为“版本目录 + current 链接”：

```text
~/.local/share/codex-dual/
  releases/
    vX.Y.Z/
    vX.Y.Z+1/
  current -> releases/vX.Y.Z+1
```

优点：

- 升级和回滚更清晰
- `ccb version` 可以准确读取当前激活版本
- 诊断包更容易给出版本路径

### 8.3 命令入口

`~/.local/bin/ccb` 应始终指向 `current` 下的统一入口，而不是散落链接到临时工作树。

## 9. 更新与回滚策略

### 9.1 更新策略

`ccb update` 应逐步收口为：

- 默认只更新到正式 release
- 默认只跟踪稳定通道
- 可选显式指定版本，例如 `ccb update 6.2.1`

不建议长期保留“在已安装 git 仓上直接 `git pull`”作为普通用户主路径。

开发者仍可在源码仓里手动更新并运行 `./install.sh install`，但这不是产品更新模型。

### 9.2 回滚策略

必须支持显式回滚：

- `ccb update 6.2.0`
- 或未来显式增加 `ccb rollback 6.2.0`

回滚只切换当前激活版本，不修改用户项目内的 `.ccb` authority。

### 9.3 失败恢复

安装/更新失败时必须满足：

- 不污染当前已安装稳定版本
- 不让 `~/.local/bin/ccb` 指向半安装状态
- 失败后仍能继续运行旧版本

## 10. 诊断与问题定位方案

release 化之后，诊断面必须同步加强。

每个正式 release 应至少携带：

- 版本号
- commit hash
- build 时间
- 构建平台
- 渠道信息，例如 `stable` / `preview`

`ccb doctor` 与日志 bundle 应输出：

- 当前激活 release 版本
- 安装目录
- 平台与架构
- `tmux` / `psmux` 检查结果
- provider CLI 探测结果
- `ccbd` 状态、socket、tmux namespace、最近错误摘要

这样用户提交日志时，定位不再依赖猜测“你是不是装了一个本地改过的源码树”。

## 11. CI 与发布流水线

建议发布流水线最少分为四步：

### 11.1 构建

- 生成 release artifact
- 生成 build metadata
- 生成 checksum

### 11.2 测试

- 单元测试
- CLI smoke test
- `ccb` 启动/attach/kill smoke test
- `ask` 异步投递与回收 smoke test
- Linux release 基本安装测试
- macOS/WSL 测试在后续平台阶段补齐

### 11.3 发布

- 打 tag
- 上传 GitHub Release assets
- 记录 release notes

### 11.4 安装验证

- 用纯 release 包做一次新机安装测试
- 验证 `ccb version`
- 验证 `ccb update`
- 验证 `ccb doctor`

## 12. Linux First 实施路线

本文后续 phase 默认以 Linux 为主线定义。macOS 和 Windows 只在边界上说明，不在第一轮实现里摊开。

### 12.1 为什么第一步只做 Linux

Linux 是当前最适合作为 release 主收口面的平台，原因如下：

- 当前 `tmux` 主路径最稳定
- 当前开发和手工回归环境主要集中在 Linux / WSL
- `install.sh`、路径布局、shell 行为、Unix socket、日志诊断模型都更贴近 Linux
- 先把一个平台做成闭环，比一开始追求多平台“都能装一点”更有价值

因此第一轮正式目标应明确为：

- 只做 Linux 正式 release
- 不把 macOS 阻塞在本阶段
- Windows Native 暂不纳入 release 落地范围

### 12.2 Linux Phase 1 目标

Phase 1 的目标不是做“最终完美封装”，而是做出第一条真实可发布、可升级、可回滚、可诊断的 Linux 主路径。

Phase 1 必须实现：

- 形成 Linux release artifact
- 用户不再需要 `git clone` 后再安装
- `install.sh` 能从 release 包完成安装
- `ccb version` 能明确显示 release 版本与 build 信息
- `ccb update` 至少能沿 release 路径更新
- `ccb doctor` 能输出 release 安装信息和关键前置依赖状态
- README 主流程切到 Linux release 安装

Phase 1 明确不做：

- Windows Native release
- `psmux`
- 自带 Python runtime
- 完整的多平台统一流水线
- 所有历史安装模式的一次性兼容保留

### 12.3 Linux Phase 1 交付物

第一轮建议只产出一个正式 artifact：

- `ccb-linux-x86_64.tar.gz`

当前建议的构建入口：

- `python3 scripts/build_linux_release.py --output-dir dist`

构建约束：

- 正式 release 构建默认要求 git worktree 干净
- 正式 release 默认从受控 git ref 导出源码，而不是直接打包当前工作树
- 脏工作树只允许显式使用 `--allow-dirty` 做本地预览构建，不可作为正式发布路径
- `--allow-dirty` 产物默认应标记为 `preview`，不得伪装成正式 `stable release`

artifact 内至少包含：

- 项目运行时代码
- `install.sh`
- `VERSION`
- `BUILD_INFO.json`
- `SHA256SUMS`
- README 或 install note

`BUILD_INFO.json` 至少包含：

- version
- commit
- build_time
- platform
- arch
- channel

### 12.4 Linux Phase 1 安装模型

Linux 第一轮建议采用“release 包 + 用户级安装器”的最小稳定模型：

1. 用户下载 `ccb-linux-x86_64.tar.gz`
2. 解压到临时目录
3. 运行 `./install.sh install`
4. 安装器将 release 内容安装到用户目录
5. `~/.local/bin/ccb` 指向已安装版本

第一轮可以继续沿用现有默认安装位置：

- 安装目录：`~/.local/share/codex-dual`
- 可执行目录：`~/.local/bin`

但安装器语义要收紧为：

- 安装输入是 release 内容
- 不是当前用户随手 clone 的开发工作树

### 12.5 Linux Phase 1 依赖边界

Linux 第一轮建议明确前置条件，只保留少数外部依赖：

- Python 3.10+
- `tmux`
- 至少一个 provider CLI

其中：

- Python 3.10+ 先保留为前置要求
- `tmux` 明确由用户系统提供
- provider CLI 与认证态继续由用户系统提供

release 内部必须自带：

- `ccb` / `ccbd` 代码
- skills 和模板
- 默认 tmux 样式和配置
- 版本与构建信息

### 12.6 Linux Phase 1 代码改造项

第一轮应优先做以下几类改造。

#### A. 安装来源收口

- 让安装器能明确识别“当前内容是 release 目录”
- 明确区分开发安装与 release 安装
- 安装完成后落盘版本元数据
- release 构建默认拒绝 dirty worktree
- release 构建默认从干净 git ref 导出，而不是直接复制当前开发工作树

#### B. 版本身份收口

- `ccb version` 优先读取 release 安装元数据
- 版本信息不再依赖当前目录是不是 git 仓
- 诊断包输出安装路径与激活版本

#### C. 更新路径收口

- `ccb update` 默认走 release 通道
- 已安装 release 不再优先尝试 `git pull`
- 保留开发工作树手动 `./install.sh install`，但不作为用户更新模型

#### D. README 与安装文案收口

- README 主入口改为下载 release 安装
- 源码安装降级为“开发者安装”
- 错误提示统一面向 release 用户而不是源码仓用户

#### E. 诊断收口

- `ccb doctor` 输出 release 版本、build 信息、安装目录
- 明确报告 Python、`tmux`、provider CLI 状态
- 诊断输出里区分“缺失前置依赖”和“release 内部损坏”

### 12.7 Linux Phase 1 测试范围

第一轮至少应覆盖以下测试：

- 新机器 Linux release 安装 smoke
- 安装后 `ccb version`
- 安装后 `ccb doctor`
- 新建项目 `ccb` 启动 smoke
- `ccb kill` smoke
- `ccb ask` 异步投递与回收 smoke
- `ccb update` 升级 smoke
- 升级失败不破坏旧安装

### 12.8 Linux Phase 1 验收标准

Linux Phase 1 完成的判定标准：

- 普通用户无需 clone 仓库即可安装
- 安装后所有命令都来自已安装 release，而不是源码路径
- `ccb version` 能稳定报告 release 信息
- `ccb doctor` 能判断关键缺失项
- `ccb update` 能从一个 release 更新到另一个 release
- 文档主入口不再要求用户先 clone 源码仓

### 12.9 macOS Phase 2 设计边界

macOS 建议放在 Linux release 路线稳定后单独推进。

macOS 和 Linux 可以共享：

- release-first 模型
- 安装目录/链接目录思路
- `tmux` 主运行时契约
- `ccb update` / `doctor` / 版本元数据模型

但 macOS 需要单独验证和可能单独处理：

- `tmux` 安装来源，通常是 Homebrew
- BSD 用户态工具与 GNU 行为差异
- shell 初始化文件差异
- 下载文件的 quarantine / 权限问题
- Apple Silicon 与 Intel 架构差异

结论：

- macOS 不需要现在就单独写一整套架构设计
- 但发布、测试和兼容性验证必须按单独目标处理

### 12.10 Windows 后续边界

Windows Native 暂不进入当前 release 实施。

后续进入 Windows 阶段时：

- 以 `docs/ccbd-windows-psmux-plan.md` 为准
- 视为新的后端落地工程，而不是 Linux/macOS release 的附带任务

## 13. 后续阶段

### 13.1 Linux Phase 2

目标：

- 引入 `releases/` + `current` 安装结构
- 明确激活版本与已安装版本
- 保证失败安装不污染现有版本

### 13.2 Linux Phase 3

目标：

- 评估并引入 per-platform Python runtime
- 减少现场依赖安装
- 降低环境差异导致的问题

### 13.3 macOS Phase

目标：

- 在 Linux release 模型基础上补足 macOS 构建与验证
- 形成独立 macOS artifact

### 13.4 Windows Native Phase

目标：

- 按 `psmux` 方案单独构建 Windows release
- 不再把 Windows Native 当作 tmux 主线的附属分支

## 14. 设计取舍

### 14.1 为什么不是只保留 install.sh

只保留 `install.sh` 的问题在于：

- 安装输入不稳定
- 用户环境差异直接暴露给源码工作树
- 版本和诊断边界不清晰
- 更新和回滚难以产品化

### 14.2 为什么不是把所有依赖都打进去

因为 `ccb` 不是纯单机工具，它依赖：

- mux 后端
- provider CLI
- 用户账号与认证状态

这类依赖不适合作为 release 的“强内置对象”。

正确路线是：

- 把项目自己能控制的运行时尽量封进去
- 把少数外部依赖清楚、稳定地外置
- 用安装器与 `doctor` 把缺失项精确讲清楚

## 15. 最终建议

面向当前项目，推荐采用以下产品策略：

- 正式用户安装：只推荐 release
- 开发者安装：允许源码仓 `./install.sh install`
- 稳定平台：Linux/macOS/WSL + `tmux`
- Windows Native：按 `psmux` 单独推进
- release 首先收口分发路径，再逐步提升自包含程度

一句话概括：

`ccb` 不应继续把“源码仓安装”当成产品本体，而应把“明确版本的 release + 很薄的安装器 + 清晰外置依赖”作为正式封装模型。
