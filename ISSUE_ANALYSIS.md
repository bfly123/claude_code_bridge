# CCB Multi 异步通信问题分析报告

## 问题概述

给其他 LLM (gemini/opencode) 发出需求后，对方完成了但没有返回完成信息，导致一直显示 'processing'。

- **OpenCode**: 第二次调用一定没有返回
- **Gemini**: 有时候会出现这个问题
- **Codex**: 当前测试中也没有返回（验证了问题存在）

## 根本原因分析（综合三个模型的发现）

### 关键 Bug 列表（按严重程度）

#### Critical: Daemon 启动崩溃
**位置**: `lib/askd_server.py:221`, `lib/askd_server.py:235`
**问题**: `_parent_monitor` 条件定义但无条件启动，当没有 parent PID 时会崩溃
**影响**: 直接导致 "daemon 无法启动" 的历史问题

#### High: OpenCode 会话 ID 固定问题（第二次调用失败的主因）
**位置**:
- `lib/askd/adapters/opencode.py:133` - 从会话文件传递 `session_id_filter`
- `lib/opencode_comm.py:673` - DB 会话查找强制使用该过滤器
- `lib/opencode_comm.py:651` - DB 路径优先于文件路径
- `lib/opencode_comm.py:788` - 只有文件查找有 "新会话覆盖" 逻辑

**问题**: OpenCode 会话 ID 被固定，第二次请求轮询错误的会话并超时
**影响**: 第二次调用一定失败

#### High: 完成回调严格依赖 done_seen
**位置**:
- `lib/completion_hook.py:132` - 硬性检查 `if not done_seen: return`
- `lib/askd/adapters/opencode.py:196` - 只在严格标记匹配时设置 done
- `lib/askd/adapters/gemini.py:230` - 同上
- `bin/ask:255` - 默认超时 3600 秒
- `lib/askd/daemon.py:186` - daemon 等待窗口

**问题**: 如果回复完成但标记缺失/错位，不会发送完成通知
**影响**: UI 显示 "processing forever"

#### Medium: Gemini 会话绑定风险
**位置**:
- `lib/gemini_comm.py:235`, `lib/gemini_comm.py:293` - 扫描 basename/sha hash 文件夹
- `lib/gemini_comm.py:337` - 跨 hash 保护仅在首选会话存在时应用
- `lib/gemini_comm.py:355` - 首次绑定直接接受扫描结果

**问题**: 实例模式下可能附加到错误的会话
**影响**: Gemini 有时会出现问题

#### Medium: notify_completion 阻塞 worker
**位置**: `lib/completion_hook.py:100`, `lib/completion_hook.py:102`
**问题**: 名为 async 但实际阻塞最多 65 秒（`join(timeout=65)`）
**影响**: 降低每会话吞吐量，负载下后续任务看起来卡住

#### Medium/Low: 取消/错误处理不完整
**位置**:
- `lib/askd/adapters/opencode.py:34` - 取消检测辅助函数存在但未连接
- `lib/opencode_comm.py:33` - 取消 req-id 正则仍假设旧的 32-hex ID
- `lib/ccb_protocol.py:56` - 当前 req ID 是 datetime/pid/counter 格式

**问题**: 中止的任务倾向于退化为长超时
**影响**: 错误处理不友好

### 1. req_id 不匹配问题

**症状**:
- OpenCode 返回: `CCB_DONE: 20260219-210049-399-57397-2`
- 期望的 req_id: `20260219-224825-969-86134`

**原因**:
- LLM 没有正确解析提示中的 `CCB_REQ_ID: {req_id}`
- LLM 可能使用了之前请求的 req_id（状态污染）
- LLM 可能自己生成了一个 req_id

**影响**:
```python
# lib/ccb_protocol.py:76-82
def is_done_text(text: str, req_id: str) -> bool:
    # 使用严格的正则匹配
    return bool(done_line_re(req_id).match(lines[i]))
    # 如果 req_id 不匹配，返回 False
```

当 `is_done_text()` 返回 False 时：
- `done_seen` 保持为 False
- `notify_completion()` 不会被调用（因为检查 `if not done_seen: return`）
- 用户永远不会收到完成通知

### 2. 状态管理问题（第二次调用失败）

**OpenCode 的状态跟踪**:
```python
state = {
    "session_id": "...",
    "session_updated": timestamp,
    "assistant_count": N,
    "last_assistant_id": "...",
    "last_assistant_completed": timestamp,
    "last_assistant_has_done": bool
}
```

**问题**:
- 第二次调用时，状态可能没有正确重置
- `_read_since()` 可能错误地认为新消息是重复的
- 重复检测逻辑可能过滤掉合法的新回复

### 3. LLM 提示解析问题

**当前提示格式** (lib/oaskd_protocol.py):
```
CCB_REQ_ID: {req_id}

{user_message}

IMPORTANT:
- Reply normally, in English.
- End your reply with this exact final line (verbatim, on its own line):
CCB_DONE: {req_id}
```

**可能的问题**:
- LLM 可能忽略了 `CCB_REQ_ID:` 行
- LLM 可能没有理解需要原样输出 req_id
- LLM 可能在多轮对话中混淆了不同请求的 req_id

## 解决方案

### 方案 1: 修复 OpenCode 状态更新不完整问题（最关键）

**问题定位** (来自 OpenCode 的深度分析):

在 `lib/opencode_comm.py` 的 `_read_since()` 方法中，Line 1132-1134：
```python
# Update state baseline even if reply isn't ready yet.
state = dict(state)
state["session_updated"] = updated_i
```

**缺陷**: 当 `session_updated` 变化但没有检测到新回复时，只更新了 `session_updated`，但**没有更新** `assistant_count`、`last_assistant_id`、`last_assistant_completed`、`last_assistant_has_done`。

**第二次调用失败的场景**:
1. 第一次调用成功，状态为 `assistant_count=2`
2. 第二次调用时，`capture_state()` 返回 `assistant_count=2`
3. 发送新消息，OpenCode 开始创建新的 assistant message
4. 如果在 polling 周期内 `session_updated` 变化但 `_find_new_assistant_reply_with_state` 返回 `None`（消息未完成）
5. 此时 `session_updated` 被更新，但 `assistant_count` 仍是旧值 2
6. 下一轮循环时，由于 `session_updated` 已是最新值，`should_scan` 为 False
7. 即使 force read 触发，使用旧的 `assistant_count=2` 进行比较会导致检测失败

**修复方案**:

```python
# lib/opencode_comm.py, around line 1132-1134
# Replace:
#     state = dict(state)
#     state["session_updated"] = updated_i

# With:
state = dict(state)
state["session_updated"] = updated_i
# Also update assistant state baseline to avoid stale comparisons
current_assistants = [m for m in self._read_messages(current_session_id)
                      if m.get("role") == "assistant" and isinstance(m.get("id"), str)]
state["assistant_count"] = len(current_assistants)
if current_assistants:
    latest = current_assistants[-1]
    state["last_assistant_id"] = latest.get("id")
    completed = (latest.get("time") or {}).get("completed")
    try:
        state["last_assistant_completed"] = int(completed) if completed is not None else None
    except Exception:
        state["last_assistant_completed"] = None
    # Update has_done flag
    parts = self._read_parts(str(latest.get("id")))
    text = self._extract_text(parts, allow_reasoning_fallback=True)
    state["last_assistant_has_done"] = bool(text) and ("CCB_DONE:" in text)
```

### 方案 2: 增强 req_id 检测容错性

**目标**: 即使 req_id 不完全匹配，也能检测到完成信号

**实现**:

```python
# lib/ccb_protocol.py - 添加宽松匹配模式
def is_done_text_relaxed(text: str, req_id: str) -> bool:
    """
    检测 CCB_DONE 标记，允许部分 req_id 匹配
    用于处理 LLM 可能修改或截断 req_id 的情况
    """
    lines = [ln.rstrip() for ln in (text or "").splitlines()]

    # 首先尝试严格匹配
    for i in range(len(lines) - 1, -1, -1):
        if _is_trailing_noise_line(lines[i]):
            continue
        if done_line_re(req_id).match(lines[i]):
            return True
        break

    # 如果严格匹配失败，尝试宽松匹配
    # 检查是否有任何 CCB_DONE: 行
    for i in range(len(lines) - 1, -1, -1):
        if _is_trailing_noise_line(lines[i]):
            continue
        line = lines[i]
        if line.strip().startswith("CCB_DONE:"):
            # 提取 req_id 并检查日期部分是否匹配
            # req_id 格式: YYYYMMDD-HHMMSS-mmm-PID-counter
            parts = line.split(":", 1)
            if len(parts) == 2:
                found_req_id = parts[1].strip()
                # 至少检查日期部分 (YYYYMMDD) 是否匹配
                if req_id[:8] == found_req_id[:8]:
                    return True
        break

    return False

# 在 lib/askd/adapters/opencode.py 和 gemini.py 中使用
# Line 189 (opencode.py):
if is_done_text_relaxed(combined, task.req_id):
    done_seen = True
    done_ms = _now_ms() - started_ms
    break
```

### 方案 3: 改进 LLM 提示格式

**目标**: 让 LLM 更容易理解和遵循 req_id 要求

**实现**:

```python
# lib/oaskd_protocol.py - 改进提示格式
def wrap_opencode_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"[SYSTEM] Request ID: {req_id}\n\n"
        f"{message}\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Process the request normally and reply in English\n"
        "2. At the very end of your response, add this EXACT line (copy it verbatim):\n"
        f"   CCB_DONE: {req_id}\n"
        "3. Do NOT modify the Request ID in any way\n"
        "4. The CCB_DONE line must be the last line of your response\n"
    )
```

### 方案 4: 添加超时和重试机制

**目标**: 当检测失败时，提供降级方案

**实现**:

```python
# lib/askd/adapters/opencode.py - 添加降级检测
def _handle_task_locked(self, task: QueuedTask, session: Any, session_key: str, started_ms: int) -> ProviderResult:
    # ... existing code ...

    # 添加降级检测：如果超时但有回复内容，检查是否包含任何 CCB_DONE
    if not done_seen and chunks:
        combined = "\n".join(chunks)
        # 检查是否有任何 CCB_DONE 标记（即使 req_id 不匹配）
        if "CCB_DONE:" in combined:
            _write_log(f"[WARN] Found CCB_DONE but req_id mismatch for req_id={task.req_id}")
            # 可以选择：
            # 1. 设置 done_seen=True（宽松模式）
            # 2. 返回特殊错误码让用户知道
            done_seen = True  # 宽松模式
            done_ms = _now_ms() - started_ms

    # ... rest of the code ...
```

### 方案 5: 增强日志和调试

**目标**: 便于诊断问题

**实现**:

```python
# 添加环境变量控制的调试日志
# lib/opencode_comm.py
def _read_since(self, state: Dict[str, Any], timeout: float, block: bool):
    debug = os.environ.get("CCB_DEBUG_OPENCODE_STATE", "").lower() in ("1", "true", "yes")

    # ... existing code ...

    if debug:
        print(f"[DEBUG] OpenCode state: session_id={session_id}, "
              f"updated={updated_i}, count={state.get('assistant_count')}, "
              f"last_id={state.get('last_assistant_id')}", file=sys.stderr)

    # ... rest of the code ...
```

## 推荐实施顺序（基于风险和影响）

### 阶段 1: 关键修复（立即实施）

**1.1 修复 Daemon 启动崩溃**
```python
# lib/askd_server.py
# 确保 _parent_monitor 只在有 parent PID 时启动
if self._parent_pid:
    self._parent_monitor = threading.Thread(target=self._monitor_parent, daemon=True)
    self._parent_monitor.start()
```

**1.2 修复 OpenCode 会话 ID 固定问题**
```python
# lib/opencode_comm.py
# 在 _get_latest_session_from_db 中添加新会话检测
def _get_latest_session_from_db(self) -> Optional[Dict[str, Any]]:
    # ... existing code ...

    # 如果有 session_id_filter，检查是否有更新的会话
    if self._session_id_filter:
        # 也查询没有过滤器的最新会话
        all_sessions = self._fetch_opencode_db_rows(
            "SELECT * FROM session ORDER BY time_updated DESC LIMIT 1",
            []
        )
        if all_sessions and all_sessions[0].get("id") != self._session_id_filter:
            # 发现更新的会话，更新过滤器
            self._session_id_filter = all_sessions[0].get("id")
            return all_sessions[0]

    # ... rest of existing code ...
```

**1.3 修复 OpenCode 状态更新不完整**
```python
# lib/opencode_comm.py, line ~1132
state = dict(state)
state["session_updated"] = updated_i
# 同步更新所有状态字段
current_assistants = [m for m in self._read_messages(current_session_id)
                      if m.get("role") == "assistant" and isinstance(m.get("id"), str)]
state["assistant_count"] = len(current_assistants)
if current_assistants:
    latest = current_assistants[-1]
    state["last_assistant_id"] = latest.get("id")
    completed = (latest.get("time") or {}).get("completed")
    try:
        state["last_assistant_completed"] = int(completed) if completed is not None else None
    except Exception:
        state["last_assistant_completed"] = None
```

### 阶段 2: 高优先级修复（短期内实施）

**2.1 添加降级完成检测**
```python
# lib/askd/adapters/opencode.py, after line ~196
# 如果超时但有回复，检查是否有任何 CCB_DONE 标记
if not done_seen and chunks:
    combined = "\n".join(chunks)
    if "CCB_DONE:" in combined:
        _write_log(f"[WARN] Found CCB_DONE but req_id mismatch for req_id={task.req_id}")
        # 降级模式：接受任何 CCB_DONE
        done_seen = True
        done_ms = _now_ms() - started_ms
```

**2.2 改进 Gemini 会话绑定**
```python
# lib/gemini_comm.py, line ~355
# 首次绑定时也检查 hash 匹配
def _scan_latest_session(self) -> Optional[Path]:
    # ... existing code ...

    # 如果在实例模式下，验证 hash 匹配
    if self._instance_mode and latest_path:
        expected_hash = self._get_project_hash()
        if expected_hash and expected_hash not in str(latest_path):
            _debug(f"[WARN] Session hash mismatch, skipping {latest_path}")
            return None

    return latest_path
```

**2.3 修复 notify_completion 阻塞**
```python
# lib/completion_hook.py
# 移除 join，让线程真正异步运行
def _run_hook_async(...):
    # ... existing code ...

    thread = threading.Thread(target=_run, daemon=False)
    thread.start()
    # 移除: thread.join(timeout=65)
    # 让线程真正在后台运行
```

### 阶段 3: 中期改进

**3.1 添加宽松 req_id 匹配**
```python
# lib/ccb_protocol.py
def is_done_text_relaxed(text: str, req_id: str) -> bool:
    # 首先尝试严格匹配
    if is_done_text(text, req_id):
        return True

    # 宽松匹配：检查日期部分
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    for i in range(len(lines) - 1, -1, -1):
        if _is_trailing_noise_line(lines[i]):
            continue
        line = lines[i]
        if line.strip().startswith("CCB_DONE:"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                found_req_id = parts[1].strip()
                # 检查日期部分 (YYYYMMDD)
                if len(req_id) >= 8 and len(found_req_id) >= 8:
                    if req_id[:8] == found_req_id[:8]:
                        return True
        break
    return False
```

**3.2 改进 LLM 提示格式**
```python
# lib/oaskd_protocol.py
def wrap_opencode_prompt(message: str, req_id: str) -> str:
    message = (message or "").rstrip()
    return (
        f"[SYSTEM] Request ID: {req_id}\n\n"
        f"{message}\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Process the request and reply in English\n"
        "2. At the END of your response, add this EXACT line:\n"
        f"   CCB_DONE: {req_id}\n"
        "3. Do NOT modify the Request ID\n"
        "4. The CCB_DONE line must be the LAST line\n"
    )
```

**3.3 修复取消检测**
```python
# lib/opencode_comm.py, line ~33
# 更新正则以匹配新的 req_id 格式
_REQ_ID_RE = re.compile(r"\d{8}-\d{6}-\d{3}-\d+-\d+")
```

### 阶段 4: 长期优化

**4.1 增强错误处理**
- 将 `except Exception: pass` 替换为具体的异常处理和日志
- 添加错误状态返回，而不是静默失败

**4.2 添加调试日志**
```python
# 添加环境变量控制的调试模式
CCB_DEBUG_OPENCODE_STATE=1  # OpenCode 状态跟踪
CCB_DEBUG_GEMINI_SESSION=1  # Gemini 会话绑定
CCB_DEBUG_COMPLETION=1      # 完成检测
```

**4.3 添加监控指标**
- 完成率
- 超时率
- req_id 不匹配率
- 平均响应时间

## 推荐实施顺序（基于风险和影响）

1. **立即修复**: 方案 1 (OpenCode 状态更新) - 解决第二次调用失败的根本原因
2. **短期修复**: 方案 2 (宽松 req_id 匹配) - 提高容错性
3. **中期改进**: 方案 3 (改进提示) - 减少 LLM 错误
4. **长期优化**: 方案 4 (降级机制) + 方案 5 (调试日志)

## 测试验证计划

### 回归测试列表

**测试 1: Daemon 启动稳定性**
```bash
# 测试在没有 parent PID 的情况下启动 daemon
unset PPID
ccb -r  # 应该成功启动而不崩溃
```

**测试 2: OpenCode 第二次调用**
```bash
# 第一次调用
CCB_CALLER=claude ask opencode "Test 1"
pend opencode  # 应该成功返回

# 第二次调用（关键测试）
CCB_CALLER=claude ask opencode "Test 2"
pend opencode  # 应该成功返回，不应该超时
```

**测试 3: Gemini 稳定性**
```bash
# 多次调用测试
for i in {1..5}; do
    CCB_CALLER=claude ask gemini "Test $i"
    sleep 2
    pend gemini
done
# 所有调用都应该成功返回
```

**测试 4: req_id 不匹配降级**
```bash
# 手动测试：让 LLM 返回错误的 req_id
# 应该在日志中看到 WARN 但仍然完成
CCB_DEBUG_COMPLETION=1 CCB_CALLER=claude ask opencode "Reply with CCB_DONE: 12345678-000000-000-00000-0"
```

**测试 5: 并发请求**
```bash
# 测试多个并发请求
CCB_CALLER=claude ask gemini "Task 1" &
CCB_CALLER=claude ask opencode "Task 2" &
CCB_CALLER=claude ask codex "Task 3" &
wait
# 所有任务都应该完成
```

### 性能基准

修复前后对比：
- **完成率**: 目标 > 95%（当前 < 50% for OpenCode 第二次调用）
- **平均响应时间**: 目标 < 30 秒（当前可能超时 3600 秒）
- **第二次调用成功率**: 目标 100%（当前 0%）
- **Daemon 启动成功率**: 目标 100%（当前有崩溃）

## 四个报告症状的映射

基于综合分析，四个症状的根本原因：

1. **"完成了但没有返回完成信息"**
   - 根本原因: 严格的 `done_seen` 检查 + 没有降级路径
   - 修复: 阶段 2.1 (降级完成检测)

2. **"OpenCode 第二次调用一定没有返回"**
   - 根本原因: 会话 ID 固定 + DB 优先查找
   - 修复: 阶段 1.2 (会话 ID 更新) + 阶段 1.3 (状态同步)

3. **"Gemini 有时候会出现这个问题"**
   - 根本原因: 会话绑定风险 + 严格标记要求
   - 修复: 阶段 2.2 (会话绑定) + 阶段 2.1 (降级检测)

4. **"之前还有 daemon 无法启动的问题"**
   - 根本原因: `_parent_monitor` 无条件启动
   - 修复: 阶段 1.1 (条件启动)

## 协作分析总结

### Gemini 的贡献
- 识别了 `done_seen` 检测机制
- 分析了 `is_done_text` 的严格匹配要求
- 提出了 req_id 不匹配的可能原因

### OpenCode 的贡献
- 发现了 `_read_since` 状态更新不完整的关键缺陷
- 详细分析了第二次调用失败的场景
- 提供了状态同步的具体修复方案

### Codex 的贡献
- 进行了端到端的代码审查
- 识别了 6 个具体的 bug 及其位置
- 评估了状态管理、并发安全、错误处理和超时机制
- 提供了按严重程度排序的问题列表

### Claude 的贡献
- 协调多模型协作分析
- 整合所有发现到统一报告
- 提供分阶段的修复计划
- 设计测试验证方案

## 下一步行动建议

1. **立即**: 实施阶段 1 的三个关键修复
2. **本周**: 实施阶段 2 的高优先级修复
3. **本月**: 完成阶段 3 的中期改进
4. **持续**: 添加阶段 4 的监控和日志

## 相关文件（按修改优先级）

- `lib/opencode_comm.py` - OpenCode 日志读取器
- `lib/gemini_comm.py` - Gemini 日志读取器
- `lib/ccb_protocol.py` - 协议定义和检测函数
- `lib/oaskd_protocol.py` - OpenCode 提示包装
- `lib/askd/adapters/opencode.py` - OpenCode 适配器
- `lib/askd/adapters/gemini.py` - Gemini 适配器
- `lib/completion_hook.py` - 完成通知钩子

