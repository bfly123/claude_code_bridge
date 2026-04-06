# Agent-First Provider Backend 迁移设计方案

> 历史说明：本文成稿于双后端迁移讨论阶段。凡文中提到的 WezTerm 路线，均属于已移除的旧实现背景；当前主仓 runtime 已收口为 tmux-only，未来原生 Windows 请参考 `docs/ccbd-windows-psmux-plan.md`。

## 1. 文档目的

这份文档回答的是一个非常具体的问题：

是否应该把不同 provider 的特异性代码收拢到各自独立目录，例如 `codex/`、`claude/`、`gemini/`，而把真正的共性代码留在外层。

结论是：**应该做，而且要尽快做，但不能只是“把文件挪进文件夹”**。

当前仓库已经明显走到 agent-first 主线上，但 provider 相关行为依然横向散落在多个模块里，导致三个问题同时存在：

- provider 生命周期很难整体理解，改一个 provider 往往要碰 `catalog / launcher / execution / comm / session / completion` 多个位置。
- project 隔离、agent 隔离、provider 特判这三类职责还没有彻底分层，后续继续迭代容易互相污染。
- 新增 provider 或提升 Claude/Gemini completion 精度时，核心层仍然容易被迫追加分支。

所以这次迁移的目标不是“整理目录”，而是把 provider 从横向散落的实现细节，升级为**真正有边界、有所有权的纵向 backend slice**。

## 2. 当前架构判断

结合当前代码结构，仓库已经具备以下正确方向：

- `lib/agents/` 已经以 `agent_name` 为中心建模。
- `lib/askd/` 已经是单项目统一守护，不再按 provider 拆 daemon。
- `lib/workspace/` 已经承担 agent worktree/copy/inplace 的规划与物化。
- `lib/completion/` 已经有统一的 orchestrator / selector / profile 抽象。
- `test/system_comm_matrix.sh` 已经覆盖多 provider、多项目、多同类 agent 的系统级矩阵。

但 provider 代码仍然存在明显的横向分散：

- 执行适配在 `lib/provider_execution/*.py`
- 会话解析在 `lib/*askd_session.py`
- 回复读取在 `lib/*_comm.py`
- 启动与 pane 注入分支在 `lib/cli/services/runtime_launch.py`
- 绑定与恢复分支在 `lib/cli/services/provider_binding.py`
- 更早期的 provider-first 历史逻辑仍残留在 `lib/launcher/`

这意味着现在真正的问题不是“provider 文件太多”，而是：

**一个 provider 的完整行为没有归属于同一块代码。**

## 3. 迁移目标

本次设计方案的目标有四个，而且四个必须同时满足。

### 3.1 provider 纵向收拢

每个 provider 的特异性逻辑都收拢到自己目录下，由该目录 owning：

- 启动命令构造
- runtime 注入
- session 文件读写与恢复
- completion 输入源读取
- 回复提取
- provider 特有协议或桥接逻辑

### 3.2 共性逻辑继续外置

以下内容不能被搬进某个 provider 目录，而应保留 shared：

- agent 配置解析
- 项目级 askd 生命周期
- project id 与路径布局
- workspace 规划与 worktree/copy/inplace 物化
- completion orchestrator / detector / selector 通用抽象
- tmux / WezTerm 后端接口
- 统一日志、状态、job、snapshot、cursor 存储

### 3.3 project 隔离与 agent 隔离继续由 shared 负责

provider backend 不负责定义项目边界，也不负责决定 agent worktree 策略。

这两件事必须继续由 shared 层统一管理：

- `project` 隔离：基于项目根目录下 `.ccb/ccb.config`、`project_id`、`.ccb/askd/` 和 `.ccb/agents/`
- `agent` 隔离：基于 agent 名、workspace 规划、`git-worktree/copy/inplace` 策略、agent runtime 目录

provider backend 只消费这些结果，不自己再发明一套隔离规则。

### 3.4 completion 精度升级不再反向污染核心层

Codex、Claude、Gemini 的 completion 源头和终止判断各不相同，这是事实；但这种差异应被限制在 provider backend 内部。

shared completion 层只应该知道：

- baseline 如何捕获
- source 如何 poll
- detector 如何判断 terminal
- selector 如何提取最终 reply

它不应该知道某个 provider 的日志格式、session 文件格式或桥接协议细节。

## 4. 目标目录结构

不建议直接创建 `lib/providers/`，因为仓库已经存在 [`lib/providers.py`](/home/bfly/yunwei/ccb_source/lib/providers.py)，目录与模块同名会制造额外迁移噪音。

建议使用下面两层：

```text
lib/
  provider_core/
    __init__.py
    registry.py
    manifests.py
    catalog.py
    contracts.py
    runtime_shared.py
    session_shared.py
    completion_shared.py
    pathing.py
    compatibility.py

  provider_backends/
    __init__.py

    codex/
      __init__.py
      manifest.py
      launcher.py
      execution.py
      comm.py
      session.py
      bridge.py
      protocol.py

    claude/
      __init__.py
      manifest.py
      launcher.py
      execution.py
      comm.py
      session.py
      resolver.py

    gemini/
      __init__.py
      manifest.py
      launcher.py
      execution.py
      comm.py
      session.py

    opencode/
      __init__.py
      manifest.py
      launcher.py
      execution.py
      comm.py
      session.py
      runtime/

    droid/
      __init__.py
      manifest.py
      launcher.py
      execution.py
      comm.py
      session.py
```

## 5. 共享层与 provider 层的职责边界

### 5.1 `provider_core/` 应承担的职责

`provider_core/` 不是新的大杂烩目录，它只容纳“所有 provider 都会用到，但不属于任何单个 provider 的规则”。

建议职责如下：

- `registry.py`
  - 负责组装所有 backend manifest，并向外提供查找接口。
- `manifests.py`
  - 放通用 manifest 类型定义，避免散落在多个文件。
- `catalog.py`
  - 兼容和收敛当前 `provider_catalog.py` 的只读查询能力。
- `contracts.py`
  - 定义统一 backend 接口，例如 launcher contract、execution contract、session contract。
- `runtime_shared.py`
  - 放 provider 共用的 pane/runtime 写盘帮助函数，不放 provider 分支。
- `session_shared.py`
  - 放 session 写入、通用路径匹配、基础 session record 处理逻辑。
- `completion_shared.py`
  - 放 source factory、baseline helper、selector glue，不放 provider 读取细节。
- `pathing.py`
  - 统一 provider runtime 目录、completion artifact 目录、session artifact 目录的计算方式。
- `compatibility.py`
  - 暂存旧模块路径到新路径的兼容转换与弃用提示。

### 5.2 `provider_backends/<provider>/` 应承担的职责

每个 backend 目录要能做到：开发者只打开这个目录，就能顺着看完整个 provider 的运行链路。

建议职责如下：

- `manifest.py`
  - 声明 provider 能力、runtime mode 支持、completion family、selector family。
- `launcher.py`
  - 负责 provider 的启动命令、tmux/WezTerm 注入细节、pane 标题与 runtime artifact 写盘。
- `execution.py`
  - 负责 submit/watch/cancel/ping 期间 provider 特有的调用逻辑。
- `comm.py`
  - 负责 provider 的回复读取、增量观察、最终消息抽取。
- `session.py`
  - 负责 provider session 文件查找、解析、恢复、session_ref 派生。
- `bridge.py`
  - 仅放类似 Codex FIFO/bridge 这类真正 provider 私有的桥接逻辑。
- `protocol.py`
  - 仅放 provider 私有协议常量和协议 record 解释逻辑。
- `resolver.py`
  - 仅当 provider 需要独立 session resolver 时保留，例如 Claude。

### 5.3 shared 层继续保留在原位置的模块

下列模块不建议搬进 provider backend：

- [`lib/agents/models.py`](/home/bfly/yunwei/ccb_source/lib/agents/models.py)
- [`lib/workspace/models.py`](/home/bfly/yunwei/ccb_source/lib/workspace/models.py)
- [`lib/storage/paths.py`](/home/bfly/yunwei/ccb_source/lib/storage/paths.py)
- [`lib/completion/orchestration.py`](/home/bfly/yunwei/ccb_source/lib/completion/orchestration.py)
- [`lib/completion/profiles.py`](/home/bfly/yunwei/ccb_source/lib/completion/profiles.py)
- `lib/askd/` 整体
- `lib/cli/` 整体
- `lib/terminal.py` 与 `lib/terminal_runtime/`

这些模块的职责是 agent-first/shared-first，不应重新 provider 化。

## 6. 建议的文件迁移映射

下面不是最终唯一答案，但这是当前最稳妥的一版迁移映射。

### 6.1 Codex

- `lib/codex_comm.py` -> `lib/provider_backends/codex/comm.py`
- `lib/codex_dual_bridge.py` -> `lib/provider_backends/codex/bridge.py`
- `lib/caskd_session.py` -> `lib/provider_backends/codex/session.py`
- `lib/caskd_protocol.py` -> `lib/provider_backends/codex/protocol.py`
- `lib/provider_execution/codex.py` -> `lib/provider_backends/codex/execution.py`
- `lib/cli/services/runtime_launch.py` 中 Codex 分支 -> `lib/provider_backends/codex/launcher.py`

### 6.2 Claude

- `lib/claude_comm.py` -> `lib/provider_backends/claude/comm.py`
- `lib/claude_session_resolver.py` -> `lib/provider_backends/claude/resolver.py`
- `lib/laskd_session.py` -> `lib/provider_backends/claude/session.py`
- `lib/laskd_protocol.py` -> `lib/provider_backends/claude/protocol.py` 或并入 `session.py`
- `lib/provider_execution/claude.py` -> `lib/provider_backends/claude/execution.py`
- `lib/launcher/claude_start.py` 与 `lib/launcher/claude_launcher.py` 的 provider 特有部分 -> `lib/provider_backends/claude/launcher.py`

### 6.3 Gemini

- `lib/gemini_comm.py` -> `lib/provider_backends/gemini/comm.py`
- `lib/gaskd_session.py` -> `lib/provider_backends/gemini/session.py`
- `lib/gaskd_protocol.py` -> `lib/provider_backends/gemini/protocol.py` 或并入 `session.py`
- `lib/provider_execution/gemini.py` -> `lib/provider_backends/gemini/execution.py`
- `lib/cli/services/runtime_launch.py` 中 Gemini 分支 -> `lib/provider_backends/gemini/launcher.py`

### 6.4 OpenCode

- `lib/opencode_comm.py` -> `lib/provider_backends/opencode/comm.py`
- `lib/oaskd_session.py` -> `lib/provider_backends/opencode/session.py`
- `lib/oaskd_protocol.py` -> `lib/provider_backends/opencode/protocol.py` 或并入 `session.py`
- `lib/provider_execution/opencode.py` -> `lib/provider_backends/opencode/execution.py`
- `lib/opencode_runtime/` -> `lib/provider_backends/opencode/runtime/`
- `lib/cli/services/runtime_launch.py` 中 OpenCode 分支 -> `lib/provider_backends/opencode/launcher.py`

### 6.5 Droid

- `lib/droid_comm.py` -> `lib/provider_backends/droid/comm.py`
- `lib/daskd_session.py` -> `lib/provider_backends/droid/session.py`
- `lib/daskd_protocol.py` -> `lib/provider_backends/droid/protocol.py` 或并入 `session.py`
- `lib/provider_execution/droid.py` -> `lib/provider_backends/droid/execution.py`
- `lib/cli/services/runtime_launch.py` 中 Droid 分支 -> `lib/provider_backends/droid/launcher.py`

### 6.6 继续保留 shared 的 provider 执行共性

这些模块建议保留 shared，不要迁成单 provider 所有：

- `lib/provider_execution/base.py`
- `lib/provider_execution/common.py`
- `lib/provider_execution/service.py`
- `lib/provider_execution/state_models.py`
- `lib/provider_execution/state_store.py`

等 backend 全部落位后，再决定这些文件是否整体搬到 `provider_core/`，但不建议第一阶段就动。

## 7. completion 相关边界的最终定义

这是迁移中最容易再次做坏的一块，需要单独固定边界。

### 7.1 shared completion 层负责什么

shared completion 层继续负责：

- profile 解析
- orchestrator 驱动
- detector family
- selector family
- snapshot/cursor/decision 通用模型

### 7.2 provider backend 负责什么

backend 只负责提供 completion 输入源，不直接控制 orchestrator。

也就是：

- Codex backend 提供 protocol event stream source
- Claude backend 提供 session event log source
- Gemini backend 提供 anchored session snapshot source
- OpenCode/Droid backend 提供各自的 session/log/source

这样一来，Codex 可以继续保持精确 completion；Claude 和 Gemini 也可以逐步升级为更稳定的 completion，而不会再把差异传播到 `askd` 或 CLI 主流程。

### 7.3 `ccbdone` 的位置

设计上不应再把 `ccbdone` 视为 completion 的唯一完成信号。

正确目标是：

- 若 provider 有结构化结果或协议 turn，则优先使用结构化终止。
- 若 provider 只有 session 边界或稳定窗口，则用 session/source 层稳定判断。
- `ccbdone` 只作为 legacy fallback 或调试辅助，而不是主契约。

## 8. project 隔离与 agent worktree 隔离的边界

这部分必须说死，否则 provider 收拢后很容易有人把隔离也塞进 backend。

### 8.1 project 隔离

project 隔离继续由 shared 层负责，核心依据不变：

- 项目根目录
- `.ccb/ccb.config`
- `project_id`
- `.ccb/askd/`
- `.ccb/agents/`
- `.ccb/workspaces/`

不同项目永远不能共享同一个 askd 运行态，也不能共享同一个 agent runtime 记录。

### 8.2 agent 隔离

agent 隔离同样继续由 shared 层负责，核心依据是：

- `agent_name`
- `workspace_mode`
- `workspace_path`
- `runtime_ref`
- `session_ref`

对于 `git-worktree` 模式，隔离目标是“每个 agent 一个独立 worktree”，而不是“每个 provider 一个 worktree”。

### 8.3 provider backend 只拥有 provider-runtime 子目录

provider backend 最多只应拥有：

```text
.ccb/agents/<agent_name>/provider-runtime/<provider>/
```

这里面存放：

- provider session artifact
- provider completion artifact
- provider bridge/fifo/log
- provider 注入时产生的局部状态

但 agent 顶层目录结构、workspace 顶层路径、askd 顶层状态，都不应由 provider backend 控制。

## 9. tmux 与 WezTerm 的 title 设计

用户已经明确要求 tmux 标题从 provider 改为 name，这部分在迁移中要一起收口。

目标规则应固定为：

- pane 主标题一律以 `agent_name` 为主
- provider 只作为次级信息或诊断附加字段
- tmux / WezTerm 标题生成由 shared terminal/pane 层统一调用
- provider backend 只提供 `display_name` 或 `agent_name`，不自己拼 provider-first title

也就是说，像 `CCB-codex` 这种 provider-first 标题应彻底退出主路径，替换为基于 agent name 的标题，例如 `CCB-writer`。

## 10. 迁移顺序

这是最关键的实施部分。建议按下面顺序执行，不要大爆炸。

### Phase 0: 建立 guardrail

先把当前系统矩阵当作迁移护栏，至少保留并持续运行：

- `test/system_comm_matrix.sh`
- provider contract tests
- 多同类 agent 隔离测试
- cross-project 隔离测试

如果迁移导致这些测试一度长期失绿，说明迁移顺序错了。

### Phase 1: 建目录，不迁逻辑

先创建：

- `lib/provider_core/`
- `lib/provider_backends/`
- 每个 provider 的空目录与 `__init__.py`

然后只做以下事情：

- 建立 backend contract
- 建立 manifest registration 入口
- 为旧模块准备 shim

这一阶段不做行为变化，只做承载结构。

### Phase 2: 先迁 manifest 与 registry

把 provider 的能力声明移到各自 backend：

- `provider_backends/codex/manifest.py`
- `provider_backends/claude/manifest.py`
- `provider_backends/gemini/manifest.py`

然后让 shared `provider_core.registry` 负责统一收集。

这一步做完后，新增 provider 时至少不需要再改一堆中心化硬编码 manifest。

### Phase 3: 先选一个低耦合 provider 作为模板

不要先动 Codex。

推荐顺序：

1. Gemini
2. Claude
3. OpenCode
4. Droid
5. Codex

原因：

- Codex 目前桥接、protocol、exact completion、tmux 注入耦合最高。
- Gemini/Claude 更适合作为第一批模板，先验证目录边界是否合理。

### Phase 4: 按 provider 成组迁移 `session + comm + execution`

一个 provider 一次性迁完这三块，不要拆成多周零碎迁移。

原因是：

- 这三块天然属于同一 provider 生命周期。
- 只迁其中一块会让 import 和职责边界更乱。

每迁完一个 provider，就把内部调用尽量改到新 backend 路径，同时保留旧路径 shim。

### Phase 5: 把 `runtime_launch/provider_binding` 的分支抽出去

当前两个明显的中心化分支点是：

- [`lib/cli/services/runtime_launch.py`](/home/bfly/yunwei/ccb_source/lib/cli/services/runtime_launch.py)
- [`lib/cli/services/provider_binding.py`](/home/bfly/yunwei/ccb_source/lib/cli/services/provider_binding.py)

最终这两个文件应该变成：

- shared 编排
- backend 查表
- backend contract 调用

而不是继续维护一大组 `if provider == ...`。

### Phase 6: 清理 legacy 和 shim

当所有 backend 都已迁入新目录并且调用方已切到新路径后，再删：

- 旧 `*_comm.py`
- 旧 `*askd_session.py`
- 旧 `provider_execution/<provider>.py`
- `providers.py` 中过时的 provider-first 兼容内容
- `launcher/` 中仅服务旧 provider-first 路由的残余文件

这一步必须最后做。

## 11. 兼容策略

这次迁移推荐采用**薄 shim + 逐步改 import**，不做一次性 rename。

### 11.1 旧模块先变 re-export shim

例如：

- `lib/gemini_comm.py` 初期只 re-export `provider_backends.gemini.comm`
- `lib/gaskd_session.py` 初期只 re-export `provider_backends.gemini.session`
- `lib/provider_execution/gemini.py` 初期只 re-export `provider_backends.gemini.execution`

这样可以：

- 降低一次性改 import 的风险
- 让系统矩阵持续可跑
- 让后续逐步提交更小、更容易 review

### 11.2 兼容期不新增旧路径调用

一旦某个 provider 已经迁入新 backend，新增代码只允许 import 新路径，不再引用旧路径。

否则迁移会永远收不口。

### 11.3 兼容层需要有移除时间点

建议在文档和代码里都明确：

- 兼容 shim 是临时层
- 所有 provider backend 迁完后统一删除

## 12. 推荐的最终验收矩阵

provider 收拢后，至少要用下面这套矩阵验收，而不是只看能不能 import。

### 12.1 多同类 agent

- 同项目双 Codex
- 同项目双 Claude
- 同项目双 Gemini
- ask/pend/watch/logs/ping 全链路隔离
- session_ref/runtime_ref 不冲突

### 12.2 多不同 agent

- Codex + Claude + Gemini 混合挂载
- 广播与点对点通信正确
- completion 检测互不干扰

### 12.3 project 隔离

- 不同项目中同名 agent 不串话
- 不同项目中同 provider 不串 session
- 不同项目 kill 不误伤

### 12.4 agent worktree 隔离

- 同项目多 agent 的 git-worktree 独立
- provider-runtime 与 workspace 路径一一对应
- 恢复时不会错误恢复到其他 agent worktree

### 12.5 tmux / WezTerm

- pane 标题按 `agent_name`
- 多同类 agent 并发挂载稳定
- 发送 Enter/注入文本语义一致
- pane 恢复、重挂载、kill 行为一致

### 12.6 completion 精度

- Codex 保持 exact completion
- Claude 不依赖 `ccbdone` 也能稳定结束并提取 reply
- Gemini 不依赖 `ccbdone` 也能稳定结束并提取 reply
- provider backend 只输出 source/result，不污染 orchestrator

## 13. 风险与规避

### 13.1 最大风险：只挪文件，不改 ownership

如果只是把 `codex_comm.py` 挪到 `codex/comm.py`，但启动、session、execution 仍然散落在 shared 层，那这次迁移基本没有价值。

规避方式：

- 以 provider 生命周期为单位迁移
- 以 backend contract 为边界收口
- 以系统矩阵验收，而不是以目录整洁验收

### 13.2 第二个风险：把 shared 隔离逻辑也塞进 provider

如果 project_id、workspace 规划、agent 顶层存储被各个 provider 自己处理，后续隔离会再次失控。

规避方式：

- provider 只能拥有 `provider-runtime/<provider>` 子目录
- 顶层 `.ccb/askd`、`.ccb/agents/<agent>`、`.ccb/workspaces` 继续 shared 管理

### 13.3 第三个风险：先动 Codex

Codex 现在是最复杂 provider，先动它会让迁移模板带入太多特例。

规避方式：

- 先拿 Gemini 或 Claude 做模板
- Codex 最后迁

## 14. 最终建议

建议直接执行这次重构，而且建议把它视为当前仓库进入“真正 agent-first 后半程”的核心工程。

最合理的实施策略是：

1. 先建立 `provider_core/` 与 `provider_backends/` 骨架。
2. 先迁 manifest/registry，不改运行行为。
3. 以 Gemini 或 Claude 为模板，成组迁 `session + comm + execution + launcher`。
4. 再迁 OpenCode、Droid。
5. 最后迁 Codex，并保持现有 exact completion 与 bridge 能力不退化。
6. 所有 provider 迁完后，再删除 shim 和 provider-first 遗留入口。

如果按这个方案推进，最终能得到的是：

- 外层保持 agent-first/shared-first
- 内层 provider 真正按目录 owning 自己的全部特异性
- project 隔离、agent worktree 隔离、tmux name-first、completion 精确化能够同时成立

这比单纯“把不同 provider 代码放到不同文件夹”更重，但也是唯一不会半途反噬的做法。
