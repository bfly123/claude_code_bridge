轻量 /code 工作流，映射到 ccb 6 阶段流程，使用 cask/gask 进行并行分析、实现和评审，无外部依赖。

## 核心约束
- 中文面向用户；与工具交互使用英文
- 每次回复包含阶段标识：`[Phase X: 阶段名]`
- 仅用 `cask/gask` 与 `cask-w/gask-w`，禁用 codeagent-wrapper

## 专家角色映射

| /code 专家 | 责任 | ccb 角色 | 调用方式 |
|---|---|---|---|
| Architect | 架构与边界定义 | Claude | 直接处理 |
| Implementation Engineer | 核心实现 | Codex | `cask-w` |
| Integration Specialist | 集成与联调 | Codex | `cask-w` |
| Code Reviewer | 评审与风险识别 | Claude + Codex | `cask-w` 辅助 |

## Pre-Phase: 上下文检索
使用 `acemcp` 检索相关代码上下文后再进入 Phase 1（查询使用英文）。

## 流程模板（映射 ccb 6 阶段）

### [Phase 1: Research]
**产物：问题陈述**
- 目标与范围
- 约束与非目标
- 关键未知项
- 成功标准

**动作：** 必要时将原始需求转交 Codex/Gemini 并行分析（将 `{feature}` 替换为实际功能名）：
```
cask-w "Analyze requirements for {feature}. Identify scope, constraints, unknowns, and success criteria."
```

### [Phase 2: Ideation]
**产物：方案对比**
- 至少 2 个方案
- 主要权衡点
- 推荐方案与理由

**动作：** 请求替代方案（将 `{feature}` 替换为实际功能名）：
```
cask-w "Propose 2-3 implementation approaches for {feature}. List tradeoffs and recommend one."
```

### [Phase 3: Planning]
**产物：执行计划**
- 3-7 个步骤
- 依赖与检查点
- 回滚策略

**门禁：** 用户确认后进入执行。

### [Phase 4: Execution]
**产物：变更清单**
- 文件列表与变更意图
- 关键实现说明

**动作：** 按计划执行最小改动，Claude 为唯一实现者。

### [Phase 5: Optimization]
**产物：优化建议**
- 性能/可读性/简化建议
- 可延后项

**动作：** 请求优化建议：
```
cask-w "Review this code for optimization opportunities. Focus on performance, readability, and simplification."
```

### [Phase 6: Review]
**产物：评审结论**
- 发现的问题/风险
- 覆盖与测试建议
- 未验证项

**动作：** 请求复核：
```
cask-w "Review the implementation for correctness, edge cases, and risks. Provide concise findings."
```

## 输出格式
每次回复以阶段标识开头，严格输出该阶段对应的最小产物字段。

## 错误处理
- **不确定信息：** 必须向用户询问，禁止假设
- **任务失败：** 重试一次，仍失败则报告用户
- **依赖冲突：** 修订计划，消除循环依赖

用户需求：$ARGUMENTS
