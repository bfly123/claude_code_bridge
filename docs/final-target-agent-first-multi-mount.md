# CCB 最终目标文档

> 历史说明：本文成稿于早期双后端设计阶段。凡文中提到的 WezTerm 路径，均属于已移除的旧方案；当前主仓运行时已收口为 tmux-only，未来原生 Windows 请以 `docs/ccbd-windows-psmux-plan.md` 为准。

## 1. 最终目标

本项目的最终目标是：

在保留 `ccb` 核心能力的前提下，放弃邮件功能，重构为一个以 `name` 为第一身份、支持任意多 agent 并发挂载的多 CLI 协作框架。

这里的“保留核心能力”指的是：

- 项目级启动与附着
- agent 间异步通信
- 对话完成检测
- 会话恢复
- 工作区隔离
- 项目级统一守护
- tmux / WezTerm 多窗格运行
- 状态查看、日志查看、诊断、自恢复

这里的“放弃邮件功能”指的是：

- 不再把 `mail` / `maild` 作为新架构目标的一部分
- 邮件入口、邮件路由、邮件 UI、邮件配置，不再继续演进
- 新架构的设计、实现、测试、文档、安装路径都不再围绕邮件能力展开

## 2. 目标形态

### 2.1 name-first，而不是 provider-first

用户面向的是 `name`，不是 provider 类型。

例如：

- `agent1 -> codex`
- `agent2 -> claude`
- `agent3 -> codex`
- `reviewer -> gemini`

用户看到、输入、管理、通信的主体都应是这些名字，而不是 `codex` / `claude` / `gemini`。

这意味着：

- 启动时按 `name` 指定目标
- tmux / WezTerm 窗格标题按 `name` 显示
- ask / ping / pend / watch / logs / ps 都按 `name` 工作
- 内部路由先解析 `name -> agent spec -> provider adapter`

### 2.2 基于 `.ccb/ccb.config` 动态挂载任意多 CLI

项目目录下由 `.ccb/ccb.config` 定义 agent 集合。

目标不是写死：

- `codex`
- `claude`
- `gemini`

而是动态读取用户配置。

例如：
agent1:codex, agent2:claude, reviewer:gemini, agent4:codex, cmd

这要求：

- 同一种 CLI 类型可以重复出现多次
- 每个实例必须通过不同 `name` 独立建模
- `name` 与 `provider` 解耦
- provider 只是一个可扩展属性，不是主键

### 2.3 同类 CLI 可并发，且必须隔离

系统必须允许：

- 同一项目同时启动 3 个 `codex`
- 同一项目同时启动 3 个 `claude`
- 同一项目同时启动多个不同 provider 的 agent

但并发不能只停留在“能同时拉起”。

必须同时满足：

- 工作目录隔离
- 会话文件隔离
- 运行态元数据隔离
- ask 队列隔离
- 完成检测隔离
- pane 标识隔离
- 日志隔离
- 锁文件 / pid / socket / state 隔离

最终应确保：

- `agent1` 发给 `agent2` 的消息不会串到 `agent3`
- 两个 `codex` 同时工作时不会共用一份 session 状态
- 恢复时是恢复某个 agent，而不是恢复某个 provider 类型

### 2.4 统一命令入口

命令入口统一为 `ccb`。

示例：

```bash
ccb
ccb -s
ccb -n
ccb ask agent1 from agent2 "请继续实现剩余部分"
ccb ask all from user "准备进入统一测试"
ccb ping agent1
ccb pend agent1
ccb watch agent1
ccb logs agent1
ccb ps
ccb doctor
ccb kill
```

约束如下：

- `ccb` 默认动作是启动/附着 agent
- `ccb ask <target> [from <sender>] <message>` 是唯一标准通信语法
- 广播目标保留字为 `all`
- 广播默认排除发送者自身
- `kill` 只做项目级清理，不做单 agent kill

### 2.5 tmux 与 Windows WezTerm 都是一级目标

新架构不能只对 Linux tmux 成立。

必须同时支持：

- Linux / macOS 下的 tmux
- Windows / WSL 场景下的 WezTerm

要求：

- pane 创建策略一致
- pane 命名策略一致
- 文本投递语义一致
- 完成检测抽象一致
- runtime binding 模型一致

也就是说，tmux 和 WezTerm 只是终端后端不同，不能让它们分裂成两套架构。

### 2.6 高扩展性：新增 CLI 类型应低成本接入

这是最终目标中的硬要求。

随着 CLI 类型增多，系统必须仍然容易扩展，而不是每增加一个 provider 就复制一套：

- 启动逻辑
- ask 逻辑
- pend 逻辑
- 完成检测逻辑
- session 解析逻辑
- pane 绑定逻辑
- 配置校验逻辑

理想状态是新增一个 provider 时，开发者只需要补齐少量清晰的扩展点，而不是修改大量核心代码。

最少应具备以下扩展面：

- `provider manifest`：声明 provider 能力
- `launcher adapter`：声明如何启动 / 恢复 / 附着
- `execution adapter`：声明如何发送消息、如何检测完成、如何提取结果
- `completion detector family`：声明结束识别方式
- `session resolver`：声明如何解析和持久化 provider 会话引用
- `terminal binding strategy`：声明 pane / terminal 注入细节

核心框架只负责：

- agent 解析
- 项目级守护
- 队列调度
- 生命周期编排
- 存储与状态管理
- 跨终端统一接口

不应在核心控制流里堆积大量 `if provider == ...`。

## 3. 架构要求

### 3.1 单项目单 askd

每个项目只保留一个 `askd`。

它负责：

- agent 注册与挂载状态
- 消息投递
- job 状态
- 完成检测调度
- 运行态快照
- health / doctor / watch
- 项目级 kill / shutdown

不再围绕 provider 维度拆成多守护。

### 3.2 agent 是一级运行时实体

所有运行时记录都应以 `agent_name` 为主键或一级索引，包括：

- runtime binding
- session binding
- workspace binding
- pend/watch 查询
- restore state
- logs
- diagnostics

`provider` 只应作为 agent 的属性存在。

### 3.3 工作区隔离策略

对每个 agent，必须能独立决定工作区模式，例如：

- `inplace`
- `git-worktree`
- `copy`

对于“同项目多同类 CLI 并发”，推荐默认策略是：

- 在 `.ccb/` 下维护 agent 专属运行态目录
- 工作目录与运行态目录分离
- 工作目录绑定回原项目目标路径

也就是说：

- 运行控制目录是 agent 私有的
- 实际代码工作区也应能做到 agent 级隔离
- prompt / env 中明确告知“原始目标目录”和“当前 agent 工作目录”

### 3.4 文件结构必须清晰，不允许巨石文件

不允许再出现一个脚本承担：

- CLI 解析
- 配置加载
- 终端控制
- provider 启动
- 守护管理
- session 持久化
- 完成检测
- 文本渲染

推荐边界：

- `lib/cli/`：只处理命令解析、上下文装配、输出渲染
- `lib/agents/`：只处理 agent 模型、配置、存储、策略
- `lib/askd/`：只处理守护、调度、挂载、watch、health
- `lib/provider_execution/`：只处理 provider 执行与结果抽取
- `lib/completion/`：只处理完成检测模型与 detector family
- `lib/workspace/`：只处理工作区规划、物化、校验
- `lib/terminal_runtime/`：只处理 tmux / WezTerm 后端
- `lib/launcher/`：只处理 pane 启动编排，不承载业务状态机

任何单文件如果继续膨胀，应优先拆分，而不是继续追加兼容逻辑。

## 4. 最终验收标准

当下列条件全部成立，才算达到最终目标：

### 4.1 配置层

- 项目通过 `.ccb/ccb.config` 定义 agent
- agent 名由用户自定义，不与 provider 名绑定
- 同一个 provider 可以在配置中重复出现多次
- 默认配置只是一组模板，不影响用户自定义 name

### 4.2 启动层

- `ccb` 能按 `.ccb/ccb.config` 启动或附着目标 agent
- 同时启动多个同类 provider 不冲突
- tmux / WezTerm pane 标题按 `name` 展示
- `ccb` 默认包含 restore + auto-permission，`ccb -s` 关闭 CLI auto-permission override

### 4.3 通信层

- `ccb ask agent1 "..."` 在 agent workspace 内可自动推断发送者
- `ccb ask agent1 from agent2 "..."` 可显式覆写发送者
- `ccb ask all from user "..."` 可广播到所有存活 agent
- 广播默认排除发送者自身
- `pend/watch/logs/ping/ps` 全部按 `name` 运作

### 4.4 隔离层

- 两个同类 CLI 的 session 不冲突
- 两个同类 CLI 的 ask 不串话
- 两个同类 CLI 的完成检测互不干扰
- 两个同类 CLI 的工作区与运行态可独立追踪

### 4.5 稳定性层

- 长时间任务不会误判完成
- 弱模型漏打文本标记时，结构化 provider 仍可稳定结束
- `askd` 在异常退出、kill、重启后能回到一致状态
- `ccb kill` 可清理当前项目 askd 与关联运行态

### 4.6 扩展性层

- 新增一个 provider 时，不需要改动核心路由大面积代码
- 新 provider 至少可以通过 manifest + adapter + detector 接入
- 新 provider 的测试可以复用统一测试夹具和契约测试

## 5. 当前已经具备的基础

结合当前 `ccb_source` 的状态，已经具备以下基础：

- 已经有明显的 agent-first v2 方向
- CLI 已支持 `ccb ask <agent> [from <sender>] <message>` 语法
- `lib/agents/` 已有独立配置加载、模型、store
- `lib/askd/` 已经是项目级统一守护
- `lib/provider_execution/` 已具备 provider 执行抽象
- `lib/completion/` 已经把 `codex` / `claude` / `gemini` 区分为不同完成检测族
- `lib/terminal_runtime/` 已经开始把 tmux / WezTerm 运行时拆出
- 当前测试里已经覆盖了部分“两个不同 name 的 codex 并发隔离”场景
- 启动编排主链路已开始从 `providers` / `anchor_provider` 收口到 `target_names` / `anchor_name`
- `runtime_ref` / `session_ref` 已替代旧的 provider runtime/session 主字段
- pane 展示与主入口 banner 已统一为 `Targets`

这说明方向是对的，基础骨架已经出现，不是从零开始。

## 6. 距离最终目标还差什么

下面是当前最关键的缺口。

### 6.1 配置文件命名已经明确，但文档和实现必须继续保持一致

当前规范已经确定为：

- `.ccb/ccb.config`

这项不再继续摇摆。

后续要求是：

- 文档统一使用 `.ccb/ccb.config`
- 默认配置生成逻辑统一使用 `.ccb/ccb.config`
- 测试夹具统一使用 `.ccb/ccb.config`
- 不再在新架构文档中引入 `.ccb/ccb_config`

### 6.2 默认配置仍然带有“provider 名就是 agent 名”的影子

当前默认配置生成仍直接生成：

- `codex`
- `claude`
- `gemini`

虽然这在功能上可用，但仍然会强化“provider-first”的心智。

最终目标下，默认模板可以保留这些名字作为示例，但系统设计不能依赖这种绑定关系。

### 6.3 provider 注册仍偏静态，扩展面还不够统一

当前已经有 `provider_catalog`，这是正确方向。

但仍存在问题：

- provider 列表仍在若干位置写死
- 某些模块仍通过 `if provider == ...` 方式分发
- launcher / session / terminal 注入层还有 provider 特判
- 可选 provider、历史 provider、测试 provider 混在同一注册面中

要达到高扩展性，仍需要进一步收敛为统一 provider 插件契约。

### 6.4 启动编排主链路已基本转向 agent-first，但边缘层仍有 provider 残留

当前已经完成的部分：

- `anchor_provider` 已收口为 `anchor_name`
- `provider_label` 已收口为 `display_label`
- `providers` 主链路已开始收口为 `target_names`
- `runtime_ref` / `session_ref` 已替代旧 runtime/session 绑定字段

当前剩余问题主要在边缘层：

- 若干 launcher 文件名和类名仍带 `provider`
- 某些 provider 特定启动器仍直接暴露 provider 术语
- daemon/session 边界仍存在 provider 维度特判

这说明主控制流已经进入 agent-first，但外围适配层还需要继续清理。

### 6.5 pane 标题与 UI 展示已有明显改善，但还没完全 name-first

当前已经完成的部分：

- 主入口 banner 已展示 `Targets`
- Claude 活动列表已展示 `Active targets`
- pane launcher 已支持显式 `display_label`

当前仍需继续推进的部分：

- 真实 agent name 还没有彻底取代 provider label 成为 pane 主标题来源
- 诊断输出里仍有若干 provider-first 文案
- tmux / WezTerm 下的多实例 name 展示还需要继续做黑盒验证

### 6.6 仍保留大量旧架构残留

仓库内仍然存在大量与最终目标不一致的旧内容，例如：

- mail / maild 相关模块
- provider-first README 叙述
- 旧安装脚本对 mail 的处理
- 旧 `ask <provider>` / `pend <provider>` 语义残留
- 旧辅助脚本和 legacy 路由

这些残留会带来三个问题：

- 让用户文档与实际目标冲突
- 让代码入口继续背负兼容复杂度
- 让测试范围被旧系统拖住

最终若不再追求旧兼容，应逐步从“共存”转向“剥离”。

### 6.7 会话与运行态存储还没有完全 agent-only 化

最终目标下，session / runtime / restore / logs 应全部以 `agent_name` 组织。

当前虽然已有 agent store，但仓库里仍保留大量 provider 维度的 session 文件、session helper、legacy session 脚本与根命名。

这说明：

- 新架构路径已经存在
- 但仓库整体还没有完成收口

### 6.8 Windows WezTerm 的“多同类 agent”专项验证仍不够

当前 WezTerm 支持基础已经存在。

但距离最终目标，还需要专项证明：

- 多个同类 agent 同时挂载时，WezTerm pane 创建与注入稳定
- 名称显示正确
- ask 路由正确
- 完成检测稳定
- kill / 重挂载稳定

也就是说，Windows/WezTerm 不能只停留在“能运行”，而要验证“在 agent-first 多实例模型下仍然成立”。

### 6.9 测试体系还需要从“功能覆盖”升级为“架构契约覆盖”

目前 v2 测试已经比旧结构干净很多，但最终还差几类关键测试：

- 配置契约测试：动态 agent 名、保留字、重复 provider、多实例合法性
- provider 契约测试：新增 provider 的最小接入测试集
- 多实例隔离测试：同 provider 多 name 的并发 ask / pend / watch / restore
- Windows/WezTerm 契约测试
- 项目级 kill / askd 生命周期一致性测试
- 文档与安装器一致性测试

如果没有这些测试，后续每加一个 provider 都可能把架构重新拉回“特判堆积”。

## 7. 建议的后续实施顺序

### 第 1 步：先统一最终规范

统一以下规范，只保留一个答案：

- 配置文件名到底是 `.ccb/ccb_config` 还是 `.ccb/ccb.config`
- 默认模板怎么定义
- 保留关键字集合
- pane 命名规则
- runtime 目录结构
- 是否彻底删除 mail 相关入口

### 第 2 步：把 agent 作为唯一主语继续收口

重点收口这些路径：

- CLI 入口
- askd 挂载记录
- workspace binding
- session binding
- runtime binding
- pend/watch/logs 查询目标

保证这些主流程都先看 `agent_name`，再解析 provider。

### 第 3 步：把 provider 接入面彻底插件化

目标是新增 provider 时只需补：

- manifest
- launcher adapter
- execution adapter
- completion detector
- session resolver
- 对应测试

核心控制流不再修改大量分支。

### 第 4 步：移除旧架构噪音

逐步移除或冻结：

- mail / maild
- 旧 provider-first 文档
- 旧技能命名与旧脚本入口
- phase1/legacy 非必要兼容路径

### 第 5 步：补足专项测试与验收文档

把最终目标转化为自动化测试矩阵，特别是：

- 多同类 agent 并发隔离
- name-first 通信
- WezTerm on Windows
- `ccb kill` 生命周期
- 新 provider 接入契约

## 8. 推荐验收测试矩阵

### 8.1 基础配置测试

- 单 agent
- 多 agent
- 同 provider 多 name
- 非法保留字
- 非法重名
- 非法 provider

### 8.2 启动与附着测试

- `ccb`
- `ccb -s`
- `ccb -n`

### 8.3 通信测试

- `ccb ask agent1 from user "..."`
- `ccb ask agent1 from agent2 "..."`
- `ccb ask all from user "..."`
- 广播排除发送者自身

### 8.4 隔离测试

- 两个 `codex` 同时 ask
- 两个 `claude` 同时 ask
- `codex + claude + gemini` 混合 ask
- pend / watch / logs 返回各自正确结果

### 8.5 恢复与生命周期测试

- `-r` 恢复指定 agent
- askd 重启后状态恢复
- `ccb kill` 清理当前项目全部运行态
- kill 后重新启动不串旧状态

### 8.6 Windows / WezTerm 测试

- pane 创建
- pane 标题按 name
- 大文本注入
- ask 完成识别
- kill / restart / remount

## 9. 结论

当前 `ccb_source` 已经具备通往最终目标的核心基础，但还没有真正“完成最终目标”。

最主要的差距不是某个单点 bug，而是以下四件事还没有完全收口：

- 规范尚未完全统一
- agent-first 语义尚未彻底压过 provider-first 残留
- provider 扩展面尚未完全插件化
- 旧 mail / legacy / README / 安装路径仍在干扰新架构边界

因此，下一阶段工作的重点不应只是继续堆功能，而应是：

- 统一规范
- 收口主语
- 收敛扩展面
- 剥离旧路径
- 用测试把最终目标固定下来

只有这样，后续继续增加新的 CLI 类型时，项目才不会再次退化成一个巨石兼容系统。
