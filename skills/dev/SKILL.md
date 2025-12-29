---
name: dev
description: /dev 7 步完整开发工作流，使用 cask/gask 并行调用替代 codeagent-wrapper，可配置覆盖率目标。
---

# /dev 7 步开发工作流

## 核心约束
- 中文面向用户；与工具交互使用英文
- 每次回复包含阶段标识：`[Phase X: 阶段名]`
- 仅用 `cask/gask` 与 `cask-w/gask-w`，禁用 codeagent-wrapper

## 后端选择（简化）

| 任务类型 | 默认后端 | 调用方式 |
|---------|---------|---------|
| 后端/逻辑 | Codex | `cask-w` |
| UI/前端 | Gemini | `gask-w` |

## 覆盖率目标（软目标）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 目标覆盖率 | 80% | 可配置为 70/80/90 |
| 性质 | 软目标 | 作为风险提示，不阻断交付 |

## Pre-Phase: 上下文检索
使用 `acemcp` 检索相关代码上下文后再进入 Phase 1（查询使用英文）。

## 7 步流程

### [Phase 1: Research] Step 0 - 后端选择
**产物：后端选择确认**
- Codex（默认）或 Gemini（UI 任务）
- 选择原因

### [Phase 1: Research] Step 1 - 需求澄清
**产物：问题陈述**
- 目标/范围/约束/未知项
- 功能边界、输入输出、测试要求

**动作：** 并行识别遗漏（将 `{feature}` 替换为实际功能名）：
```
cask-w "Analyze requirements for {feature}. Identify scope, constraints, edge cases, and testing needs."
gask-w "Review requirements from UI/UX perspective. Identify missing interactions or flows."
```

### [Phase 2: Ideation] Step 2 - 深度分析
**产物：分析报告**
- 上下文与约束
- 实现选项与权衡
- 技术决策
- 任务分解（2-5 个任务）

**动作：** 请求深度分析（将 `{feature}` 替换为实际功能名）：
```
cask-w "Perform deep analysis for {feature}. Explore codebase, evaluate options, make architectural decisions, break down into 2-5 tasks."
```

### [Phase 3: Planning] Step 3 - 计划与确认
**产物：开发计划**
- 任务列表（ID、描述、文件范围、依赖）
- 测试命令
- 回滚策略

**🛑 门禁：** 用户批准后进入执行。
```
开发计划已生成。是否确认执行？(yes/no)
```

### [Phase 4: Execution] Step 4 - 并行执行
**产物：变更清单**
- 各任务实现状态
- 文件变更列表

**动作：** 并行请求实现建议（将 `{id}`, `{description}`, `{files}` 替换为实际值）：
```
cask-w "Implement task {id}: {description}. Scope: {files}. Provide implementation approach and key code."
gask-w "Implement UI task {id}: {description}. Provide component structure and styling approach."
```

**注意：** Claude 为唯一实现者，Codex/Gemini 仅提供建议。

### [Phase 5: Optimization] Step 5 - 覆盖率检查
**产物：覆盖与测试建议**
- 当前覆盖率估算
- 关键路径测试点
- 未覆盖风险区域

**动作：** 请求测试建议（将 `{target}` 替换为目标覆盖率）：
```
cask-w "Review implementation for test coverage. Identify critical paths and suggest test cases for >= {target}% coverage."
```

### [Phase 6: Review] Step 6 - 完成总结
**产物：交付总结**
- 完成任务列表
- 各任务覆盖率
- 关键文件变更
- 风险与后续建议

**动作：** 最终评审：
```
cask-w "Final review of implementation. Check correctness, edge cases, and provide completion summary."
```

## 错误处理
- **任务失败：** 重试一次，仍失败则报告用户
- **覆盖率不足：** 提示风险，建议补充测试（最多 2 轮）
- **依赖冲突：** 修订任务分解，消除循环依赖

## 输出格式
每次回复以阶段标识开头，Step 3 门禁处必须等待用户确认。
