需求驱动工作流，带可配置质量门禁，适配 ccb 6 阶段流程，使用 cask/gask 进行分析和评审。

## 核心约束
- 中文面向用户；与工具交互使用英文
- 每次回复包含阶段标识：`[Phase X: 阶段名]`
- 仅用 `cask/gask` 与 `cask-w/gask-w`，禁用 codeagent-wrapper

## 角色映射
- **Claude**：需求确认与总协调（PO/Orchestrator）
- **Codex**：实现与后端验证
- **Gemini**：替代方案与验证补充

## 质量门禁（可配置）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 质量阈值 | 90 | 可调整为 80/85/90 |
| 评估维度 | 完整性、清晰度、可执行性、可测性 | 各占 25 分 |

## Pre-Phase: 上下文检索
使用 `acemcp` 检索相关代码上下文后再进入 Phase 1（查询使用英文）。

## 流程模板

### [Phase 1: Research] 需求确认
**产物：需求确认单**
- 目标/范围/约束/非目标
- 关键未知项与依赖
- 现有结构/约束（快速扫描）
- 质量评分

**门禁：** 质量分达到阈值后进入 Phase 2。

**动作：** 并行请求识别风险与遗漏（将 `{feature}` 替换为实际功能名）：
```
cask-w "Validate requirements for {feature}. Check completeness, ambiguity, and testability. Provide a score (0-100) and key gaps."
gask-w "Suggest alternative approaches or missing requirements for {feature}. Provide a quality score."
```

### [Phase 2: Ideation] 方案验证
**产物：方案与验证点**
- 2 个方案 + 主要权衡
- 推荐方案与验证要点

**动作：** 交叉验证方案：
```
cask-w "Cross-validate the proposed approach. Identify risks and edge cases."
```

### [Phase 3: Planning] 实施计划
**产物：执行计划**
- 3-7 步
- 关键边界与回滚

**门禁：** 用户确认后进入执行。

### [Phase 4: Execution] 实施
**产物：变更清单**
- 文件/模块/意图

**动作：** 按计划执行最小改动。

### [Phase 5: Optimization] 优化
**产物：优化建议**
- 必要优化与可延后项

### [Phase 6: Review] 评审
**产物：评审结论**
- 风险/缺陷
- 测试建议

**动作：** 测试决策（智能推荐）：
- 简单任务（配置/文档）：建议跳过测试
- 复杂任务（业务逻辑/API）：建议编写测试

## 输出格式
每次回复以阶段标识开头，包含质量评分（如适用）。

## 错误处理
- **不确定信息：** 必须向用户询问，禁止假设
- **质量分不足：** 继续迭代澄清，直到达到阈值
- **任务失败：** 重试一次，仍失败则报告用户

用户需求：$ARGUMENTS
