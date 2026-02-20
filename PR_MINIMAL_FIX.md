# Pull Request: 修复异步通信卡住问题

## 问题描述

在使用 CCB Multi 时，发现以下问题：
1. OpenCode 第二次调用一定失败，一直显示 "processing"
2. Gemini 有时会出现类似问题
3. 当 LLM 返回的 `CCB_DONE:` 标记中的 req_id 不匹配时，永远不会触发完成通知

## 根本原因

经过多模型协作分析（Claude + Gemini + OpenCode + Codex），发现三个关键问题：

1. **OpenCode 会话 ID 固定**: `_get_latest_session_from_db()` 在设置了 `session_id_filter` 后，会跳过所有新会话，导致第二次调用轮询错误的会话
2. **状态更新不完整**: `_read_since()` 只更新 `session_updated` 时间戳，但不更新 `assistant_count` 等状态字段，导致使用过时状态进行比较
3. **完成检测过于严格**: 当 req_id 不完全匹配时，`done_seen` 永远为 False，不会触发完成通知

## 修复内容

### 1. 修复 OpenCode 会话 ID 固定问题

**文件**: `lib/opencode_comm.py`
**位置**: `_get_latest_session_from_db()` 方法

**修改**:
- 跟踪最新的未过滤会话
- 如果发现比过滤会话更新的会话，使用新会话
- 这允许检测到第二次调用时创建的新会话

### 2. 修复状态更新不完整问题

**文件**: `lib/opencode_comm.py`
**位置**: `_read_since()` 方法，line ~1132-1134

**修改**:
- 在更新 `session_updated` 时，同时更新所有状态字段
- 包括 `assistant_count`, `last_assistant_id`, `last_assistant_completed`, `last_assistant_has_done`
- 防止第二次调用使用过时的状态进行比较

### 3. 添加降级完成检测

**文件**:
- `lib/askd/adapters/opencode.py`
- `lib/askd/adapters/gemini.py`

**修改**:
- 在超时后，如果回复中包含任何 `CCB_DONE:` 标记，接受为完成
- 记录 WARN 日志，显示期望的和实际的 req_id
- 这提供了一个降级路径，即使 req_id 不匹配也能完成

## 测试

运行测试脚本：
```bash
./test_minimal_fix.sh
```

预期结果：
1. OpenCode 第二次调用成功
2. Gemini 稳定返回
3. 即使 req_id 不匹配，也能完成（会有 WARN 日志）

## 影响范围

- **最小化修改**: 只修改了关键的三个位置
- **向后兼容**: 不影响现有功能
- **降级安全**: 降级检测只在严格匹配失败后才触发

## 相关 Issue

解决了以下问题：
- OpenCode 第二次调用失败
- Gemini 间歇性失败
- req_id 不匹配导致的永久 "processing" 状态

## 后续工作

这是最小修复集。完整的修复计划包括：
- 修复 daemon 启动崩溃问题
- 改进 Gemini 会话绑定
- 修复 notify_completion 阻塞
- 改进错误处理和日志
- 添加监控指标

详细分析报告见：`ISSUE_ANALYSIS.md`
