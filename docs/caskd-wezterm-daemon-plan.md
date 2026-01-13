# 方案2（最终形态）：`caskd`（WezTerm）——稳定、跨系统、可并行的 Codex 同步问答守护进程（详细执行方案）

适用范围：本仓库当前架构（`bin/cask` 发送；`lib/codex_comm.py` 从 `~/.codex/sessions/**/*.jsonl` 读回；WezTerm 模式通过 `wezterm cli send-text` 注入）。

目标：把 `cask` 的“回复提取”从“读到第一条 assistant 就返回”升级为“请求↔回复强关联”，并在 **不同工作目录** 使用 **不同 Codex session/pane** 时实现真正并行（互不阻塞、互不串台）。

---

## 1. 现状与问题（为什么要上方案2）

### 1.1 现状（简述）
- **发送路径（WezTerm）**：直接把用户文本注入 Codex TUI pane（不带可关联的请求 ID）。
- **接收路径**：从 Codex 官方 JSONL 日志中“从 offset 往后读”，抽取到一条 assistant 文本就返回。
- **完成判定**：依赖一个固定字符串 marker（默认 `EXECUTION_COMPLETE`），且通常是“最后一行包含子串即完成”。

### 1.2 核心不稳定点（必须解决）
- **缺乏请求↔回复关联**：日志读取只认“下一条 assistant”，任何手动输入/其他脚本/并发请求都可能造成串台。
- **并发粒度不对**：当前锁偏向“按目录”而不是“按 session”，不同目录共享同一 session 时会绕开锁，导致乱序注入 + 互读对方回复。
- **marker 误判/短路**：固定子串既可能被用户问题触发导致不追加结束约束，也可能被模型自然输出触发误判完成。

---

## 2. 方案2总览（核心原则：三件事缺一不可）

### 2.1 三个核心策略
1) **请求级 `req_id` 协议**：每次请求生成高熵 `req_id`，把它写进发给 Codex 的 user 消息中，并要求 assistant 以严格的独占行 `CCB_DONE: <req_id>` 结束。
2) **日志锚定配对**：从 JSONL 日志里先定位该 `req_id` 的 user 锚点，再收集 assistant 输出直到 `CCB_DONE: <req_id>`。
3) **session 粒度队列**：同一 `session_key`（同一 Codex session/pane）只能串行发送；不同 `session_key` 并行。

### 2.2 为什么需要守护进程 `caskd`
即便你把“锚定配对”做对了，如果多个 `cask` 进程同时调用 `wezterm cli` 注入，仍会出现：
- 注入乱序/交错（TUI 输入通道是单路串行的）；
- 多进程反复扫描日志，性能差且容易踩到边界；
- `.codex-session` 的 session 绑定无法被统一修正与跟随更新。

`caskd` 把这些问题集中治理：
- 每个 session 一个发送队列（串行化注入）；
- 每个 session 一个日志 tailer（复用读取，按 `req_id` 分发）；
- 统一维护 `.codex-session`（根据“锚点观测”动态修正）。

---

## 3. 设计目标与非目标

### 3.1 设计目标
- **稳定**：不串台；不误判完成；对日志切换/会话恢复更鲁棒。
- **跨系统**：Linux/macOS/Windows/WSL 统一行为（WezTerm 为主）。
- **可并行**：
  - 不同 `session_key`：并行执行（互不影响）。
  - 同一 `session_key`：并行等待、串行发送（物理限制）。
- **兼容现有 CLI**：`cask` 参数、stdout/stderr、退出码、`--output` 行为不变。

### 3.2 非目标（明确边界）
- 不试图在同一 Codex TUI session 内实现真正并行“同时执行多个请求”（输入通道与上下文决定了必须串行提交）。
- 不依赖 Codex 官方提供 request_id（当前日志结构不稳定，不能假设存在）。

---

## 4. 组件与职责

### 4.1 新增/改造组件
- `bin/cask`：客户端（保持用户接口）；优先走 daemon；失败可 fallback（可配置）。
- `bin/caskd`：守护进程；提供本地 RPC；管理 per-session worker、日志 tail、`.codex-session` 更新。

### 4.2 复用既有组件
- `lib/terminal.py`：复用 `WeztermBackend.send_text()`（优先 `send-key` 发送回车、paste/no-paste 策略、WSL/Windows 兼容）。
- `lib/codex_comm.py`：复用 JSONL tail 框架，但需要扩展成 **事件级**（同时识别 user+assistant）。
- `lib/process_lock.py`：可用于 `caskd` 单实例锁（全局 lockfile），也可用于 client fallback 模式。

---

## 5. 协议（最关键的稳定性来源）

### 5.1 Codex 对话内协议（req_id + done 行）

#### req_id 生成
推荐：`uuid4().hex` 或 `secrets.token_hex(16)`（>=128bit）。

#### 发送给 Codex 的最终文本模板（必须严格）
要求：
- `CCB_REQ_ID` 行必须是独占一行；
- `CCB_DONE` 行必须是 **最后一个非空行**；
- 完成判定必须是严格匹配，不用子串包含。

模板：
```text
CCB_REQ_ID: <req_id>

<用户原始 message>

IMPORTANT:
- Reply normally.
- End your reply with this exact final line (verbatim, on its own line):
CCB_DONE: <req_id>
```

#### 完成判定与剥离
- 将已收集文本按行 `splitlines()`；
- 找到最后一个非空行；
- **仅当**其严格等于 `CCB_DONE: <req_id>` 才视为完成；
- 返回时剥离该行（以及其后的空白）。

> 这一步直接规避现有固定 marker 的短路/误判。

---

### 5.2 `cask` ↔ `caskd` IPC 协议（跨系统稳定）

#### 传输
- 本地 TCP：`127.0.0.1:<port>`（跨平台统一；避免 Unix domain socket 在 Windows 的坑）。
- 帧格式：newline-delimited JSON（每行一个 JSON，对调试友好）。
- 认证：daemon 启动生成随机 token；客户端请求必须带 token（状态文件权限 0600）。

#### 请求格式（示例）
```json
{
  "type": "cask.request",
  "v": 1,
  "id": "client_req_uuid",
  "work_dir": "/path/to/proj",
  "timeout_s": 3600,
  "quiet": false,
  "message": "..."
}
```

#### 响应格式（示例）
```json
{
  "type": "cask.response",
  "v": 1,
  "id": "client_req_uuid",
  "req_id": "generated_req_id",
  "exit_code": 0,
  "reply": "...",
  "meta": {
    "session_key": "...",
    "log_path": "...",
    "fallback_scan": false,
    "anchor_seen": true,
    "done_seen": true,
    "anchor_ms": 120,
    "done_ms": 980
  }
}
```

#### 退出码（与现有 `cli_output` 对齐）
- `0`：完成（命中 `CCB_DONE:<req_id>`）。
- `2`：超时/未完成（允许返回 partial）。
- `1`：错误（session 不健康、pane 不存在、日志不可读等）。

---

## 6. Session 路由、绑定与 `.codex-session` 动态维护

### 6.1 `.codex-session` 的定位规则（work_dir → session 文件）
对请求中的 `work_dir` 执行“向上查找”：
- `work_dir/.codex-session`
- `work_dir/../.codex-session`
- …直到根目录

> 注意：daemon **不能**使用 `Path.cwd()` 这种隐式行为，必须全程以入参 `work_dir` 为准。

### 6.2 session_key 的选择（队列/锁粒度）
优先级：
1) `.codex-session.codex_session_id`（最稳定，来自官方 log 的 UUID）。
2) `.codex-session.pane_title_marker`（WezTerm 可重定位）。
3) `.codex-session.pane_id`（最后兜底；pane 可能重建）。

### 6.3 WezTerm pane 自愈（防 pane_id 过期）
发送前检查：
- 如果 `pane_id` 不存在：用 `pane_title_marker` 调 `WeztermBackend.find_pane_by_title_marker(marker)` 重定位。
- 重定位成功则更新 `.codex-session.pane_id`（可选，但推荐）。

### 6.4 “绑定不会失败”的关键：以 req_id 锚点观测为真相
`.codex-session` 仅作为缓存提示。真正绑定由本次请求的 `req_id` 决定：
- 在某个 `log_path` 中观测到 user 锚点（包含 `CCB_REQ_ID:<req_id>`）或 done 行（包含 `CCB_DONE:<req_id>`），即可确认该请求属于此 `log_path`/session。

### 6.5 跟随对话更新（session 切换/日志轮转）
当观测到 `req_id` 实际落在某个 `log_path` 后：
1) 从 `log_path` 提取 `codex_session_id`（文件名或首行 `session_meta` 等）。
2) 写回 `.codex-session`：
   - `codex_session_path`
   - `codex_session_id`
   - `updated_at`
   - `active`（必要时修正）

推荐复用本仓库已有的更新逻辑思路（类似 `CodexCommunicator._remember_codex_session(log_path)`），但要做到 **可传入 session_file 路径**。

> 结果：用户在 pane 内 `codex resume` 切换会话后，下一次请求会命中新 log 并自动更新 `.codex-session`，而不是靠 mtime 猜。

---

## 7. 日志读取：事件级 tail（user+assistant）

### 7.1 为什么必须事件级
只抽 assistant 文本无法定位 user 锚点，无法构建“从锚点开始收集”的窗口，串台问题无法根治。

### 7.2 事件抽取要求
从每行 JSONL entry 中抽取：
- `role`：`user` 或 `assistant`（最低要求）
- `text`：对应消息的文本（可能是多段 content 拼接）
- 其他：可选 `timestamp`、`entry_type`、`session_id`

实现建议：
- 将现有逻辑整合成单一函数：`extract_event(entry) -> Optional[(role, text)]`。
- 兼容多种 entry type（`response_item`、`event_msg`、以及 fallback `payload.role`）。

### 7.3 读取算法（稳健点）
复用现有 tailing 关键点：
- 二进制 `readline()`；
- 若末行无 `\n`，回退 offset 等待 writer 续写（避免 JSON 半行）。

### 7.4 req_id 状态机（per request watcher）
每个 `req_id` 一个 watcher，状态：
- `WAIT_ANCHOR`：等待 `role=user` 且 `text` 含 `CCB_REQ_ID:<req_id>`
- `COLLECTING`：收集 `role=assistant` 的文本片段
- `DONE`：assembled 文本最后非空行严格等于 `CCB_DONE:<req_id>`
- `TIMEOUT`：超时，返回 partial（exit_code=2）

### 7.5 fallback 扫描（保证锚点总能找到）
触发条件：发送后在 `preferred_log` 中 T 秒（建议 2~3s）未命中锚点（或 log 不存在）。

扫描策略（性能护栏必须有）：
- 只扫描最近更新的 K 个日志文件（建议 K=20 或限定最近 N 分钟）。
- 每个文件只读末尾 `tail_bytes`（建议 1~8MB），直接字符串搜索 `CCB_REQ_ID:<req_id>` 或 `CCB_DONE:<req_id>`。
- 命中则切换到该 `log_path`，继续 tail，并写回 `.codex-session`。

---

## 8. 并发模型（如何实现“不同目录互不影响”）

### 8.1 结构
daemon 维护：
- `workers[session_key]`：每个 session 一个 worker（线程/协程均可）
- `queue[session_key]`：发送队列（FIFO）
- `watchers[req_id]`：每请求 watcher（由所属 session worker 驱动）

### 8.2 并发保证
- 不同 `session_key`：不同 worker 并行运行，互不影响。
- 相同 `session_key`：队列串行发送（必须）；watchers 可以并行等待完成。

### 8.3 公平性与吞吐（可选优化）
同一 session 队列可加：
- 最大排队长度；
- 请求取消；
- 超时后自动出队；
- “短请求优先”的策略（不建议默认启用，易惊喜）。

---

## 9. 安全与运维

### 9.1 daemon 单实例
在 `~/.ccb/run/` 放置：
- `caskd.lock`：进程锁（记录 pid；stale 检测）
- `caskd.json`：状态文件（host/port/token/pid/version/started_at）

权限建议：状态文件与锁文件至少 0600（仅用户可读写）。

### 9.2 客户端行为（`bin/cask`）
- 默认连接 daemon：
  - 读 `~/.ccb/run/caskd.json` 获取连接信息；
  - token 校验；
- 连接失败时：
  - 若 `CCB_CASKD_AUTOSTART=1`：尝试启动 daemon（`Popen`），等待状态文件就绪；
  - 否则 fallback 到直连模式（可配置禁用 fallback 以强制使用 daemon）。

### 9.3 观测性（强烈建议）
daemon 日志（例如 `~/.ccb/run/caskd.log`）至少记录：
- req_id、work_dir、session_key、log_path、是否 fallback、anchor/done 耗时、错误栈。

---

## 10. 详细实施步骤（一步到位也按这个任务拆解）

### Step 0：新增公共协议模块（推荐）
新增 `lib/ccbd_protocol.py`（名字可调整），包含：
- `make_req_id()`
- `wrap_codex_prompt(message, req_id)`
- `extract_done(text, req_id)` / `strip_done(text, req_id)`
- IPC JSON schema（request/response）

### Step 1：扩展 `lib/codex_comm.py` 支持事件级读取
新增：
- `CodexLogReader.wait_for_event(state, timeout)`（返回 role/text/new_state）
- `CodexLogReader.try_get_event(state)`（非阻塞）

注意：
- 现有 `wait_for_message()` 保持不破坏（兼容旧调用方）。

### Step 2：实现 `bin/caskd`
实现要点：
- TCP server（建议 `socketserver.ThreadingTCPServer` 或 asyncio）；
- 状态文件写入；
- token 校验；
- 解析请求，路由到 `session_key` worker。

### Step 3：实现 session resolver 与 `.codex-session` 更新器
新增 `lib/session_resolver.py`：
- `find_codex_session_file(work_dir)`
- `load_session_info(session_file)`
- `write_session_update(session_file, updates)`

更新策略：只根据 req_id 锚点观测到的 log_path 更新（不要靠“最新 mtime”猜）。

### Step 4：实现 per-session worker（队列 + 注入 + tail + 分发）
worker 逻辑：
1) 从队列取请求
2) `pane` 自愈定位
3) 注入 wrapped prompt（含 req_id）
4) 在日志中等 user 锚点 → 收集 assistant → done
5) 返回结果给 RPC handler
6) 写回 `.codex-session`（log_path/session_id）

### Step 5：改造 `bin/cask` 为 daemon client（保持 CLI 兼容）
- 参数解析不变；
- 结果写 `--output` 原子语义不变；
- 退出码不变；
- 增加 env 控制：
  - `CCB_CASKD=1/0`
  - `CCB_CASKD_AUTOSTART=1/0`
  - `CCB_CASKD_ADDR=127.0.0.1:port`（可选）

### Step 6：测试（建议最低保障）
不依赖真实 Codex：
- 用 fixtures 构造 JSONL 样本（含 user/assistant/done），测试 watcher 状态机与 event 抽取。
- 单测协议模块（wrap/done/strip）。
- 单测 fallback 扫描策略（K 与 tail_bytes 护栏生效）。

---

## 11. 一步到位上方案2：建议（避免大爆炸）

如果你要“一次合并全部方案2”，强烈建议同时做到：
1) **保留直连 fallback**（daemon 失效时还能用；否则会成为单点故障）。
2) **feature flag**（随时切回旧模式止血）。
3) **严格兼容 CLI 行为**（参数/退出码/输出文件语义必须不变）。
4) **性能护栏**（fallback 扫描限制 K、tail_bytes、时间窗；避免全盘扫描卡死）。
5) **观测性默认开启**（至少可通过 `CCB_DEBUG` 打开 meta/log，排障成本大幅下降）。

---

## 12. 验收标准（上线前必须满足）
- 任意用户输入包含 `EXECUTION_COMPLETE`/`CCB_DONE` 等字样，不会导致死等或误判完成。
- 两个不同目录、两个不同 Codex session 并发：互不阻塞、不串台。
- 同一 session 并发：请求排队但不串台；每个请求都能拿到自己的 `req_id` 回复。
- 在同一 pane 内 `codex resume` 切换 session：下一次请求能自动跟随新 log 并更新 `.codex-session`。

---

## 附：快捷用法（已实现）

- `ccb up ...` 会在 WezTerm/iTerm2 且包含 `codex` 后端时自动拉起 `caskd`（无感）。
- 如需禁用自动拉起：`CCB_AUTO_CASKD=0 ccb up codex`
- 手动启动/停止：`caskd` / `caskd --shutdown`
