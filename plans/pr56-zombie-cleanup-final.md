# PR #56 最终方案：`ccb kill` 僵尸清理功能

## 命令设计

| 命令 | 作用域 | 行为 |
|------|--------|------|
| `ccb kill [providers...]` | 当前项目 | 清理当前目录的 sessions + 静默清理相关僵尸 |
| `ccb kill -f` | 全局 | 清理所有僵尸 sessions（需确认） |
| `ccb kill -f -y` | 全局 | 清理所有僵尸 sessions（跳过确认） |

## 实现逻辑

### `ccb kill [providers...]`（项目级）

```python
def cmd_kill(args):
    providers = _parse_providers(args.providers or ALL_PROVIDERS)
    force = getattr(args, "force", False)

    if force:
        # 全局模式：清理所有僵尸
        return _kill_global_zombies(yes=getattr(args, "yes", False))

    # 项目模式
    for provider in providers:
        # 1. 原有逻辑：清理当前目录的 session
        _kill_provider_session(provider)

        # 2. 新增：静默清理该 provider 相关的僵尸
        _kill_provider_zombies(provider, silent=True)
```

### `ccb kill -f`（全局）

```python
def _kill_global_zombies(yes: bool = False) -> int:
    """清理所有僵尸 tmux sessions"""
    zombies = _find_all_zombie_sessions()

    if not zombies:
        print("✅ 没有僵尸 sessions")
        return 0

    # 显示列表
    print(f"发现 {len(zombies)} 个僵尸 sessions:")
    for z in zombies:
        print(f"  - {z['session']} (parent PID {z['parent_pid']} 已退出)")

    # 确认
    if not yes:
        reply = input("是否清理这些 sessions? [y/N] ")
        if reply.lower() != 'y':
            print("❌ 已取消")
            return 1

    # 清理
    for z in zombies:
        subprocess.run(["tmux", "kill-session", "-t", z["session"]],
                       stderr=subprocess.DEVNULL)

    print(f"✅ 已清理 {len(zombies)} 个僵尸 sessions")
    return 0
```

## 僵尸检测

```python
def _find_all_zombie_sessions() -> list[dict]:
    """查找所有僵尸 tmux sessions"""
    pattern = re.compile(r"^(codex|gemini|opencode|claude|droid)-(\d+)-")
    zombies = []

    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    for session in result.stdout.strip().split("\n"):
        if not session:
            continue
        match = pattern.match(session)
        if not match:
            continue

        provider, parent_pid = match.groups()
        parent_pid = int(parent_pid)

        # 检查 parent PID 是否存活
        if _is_pid_alive(parent_pid):
            continue

        zombies.append({
            "session": session,
            "provider": provider,
            "parent_pid": parent_pid
        })

    return zombies


def _is_pid_alive(pid: int) -> bool:
    """检查进程是否存活"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
```

## 参数解析修改

```python
kill_parser = subparsers.add_parser("kill", help="Terminate sessions")
kill_parser.add_argument("providers", nargs="*", default=[],
    help="Backends to terminate (codex/gemini/opencode/claude/droid)")
kill_parser.add_argument("-f", "--force", action="store_true",
    help="Clean up all zombie sessions globally")
kill_parser.add_argument("-y", "--yes", action="store_true",
    help="Skip confirmation prompt (with -f)")
```

## 输出示例

### 项目级清理

```
$ ccb kill codex
✅ Codex session terminated
✅ caskd daemon shutdown requested
```

### 全局清理

```
$ ccb kill -f
发现 3 个僵尸 sessions:
  - codex-12345-abc123 (parent PID 12345 已退出)
  - gemini-67890-def456 (parent PID 67890 已退出)
  - droid-11111-xyz789 (parent PID 11111 已退出)

是否清理这些 sessions? [y/N] y
✅ 已清理 3 个僵尸 sessions
```

### 无僵尸

```
$ ccb kill -f
✅ 没有僵尸 sessions
```

## 不采纳的内容

- `ccb-start` 脚本
- `ccb-cleanup` 脚本
- `CLEANUP_GUIDE.md`
- `--dry-run` 选项（用确认机制替代）
- `--zombies` 独立选项（合并到 `-f`）

## 测试计划

1. 创建测试僵尸 sessions
2. 验证 `ccb kill` 项目级清理
3. 验证 `ccb kill -f` 全局清理（带确认）
4. 验证 `ccb kill -f -y` 跳过确认
5. 验证无僵尸时的输出
6. 验证 tmux 未运行时的行为
