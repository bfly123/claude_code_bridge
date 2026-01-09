"""
i18n - Internationalization support for CCB

Language detection priority:
1. CCB_LANG environment variable (zh/en/auto)
2. System locale (LANG/LC_ALL/LC_MESSAGES)
3. Default to English
"""

import os
import locale

_current_lang = None

MESSAGES = {
    "en": {
        # Terminal detection
        "no_terminal_backend": "No terminal backend detected (WezTerm or tmux)",
        "solutions": "Solutions:",
        "install_wezterm": "Install WezTerm (recommended): https://wezfurlong.org/wezterm/",
        "or_install_tmux": "Or install tmux",
        "or_set_ccb_terminal": "Or set CCB_TERMINAL=wezterm and configure CODEX_WEZTERM_BIN",
        "tmux_not_installed": "tmux not installed and WezTerm unavailable",
        "install_wezterm_or_tmux": "Solution: Install WezTerm (recommended) or tmux",

        # Startup messages
        "starting_backend": "Starting {provider} backend ({terminal})...",
        "started_backend": "{provider} started ({terminal}: {pane_id})",
        "unknown_provider": "Unknown provider: {provider}",
        "resuming_session": "Resuming {provider} session: {session_id}...",
        "no_history_fresh": "No {provider} history found, starting fresh",
        "warmup": "Warmup: {script}",
        "warmup_failed": "Warmup failed: {provider}",

        # Claude
        "starting_claude": "Starting Claude...",
        "resuming_claude": "Resuming Claude session: {session_id}...",
        "no_claude_session": "No local Claude session found, starting fresh",
        "session_id": "Session ID: {session_id}",
        "runtime_dir": "Runtime dir: {runtime_dir}",
        "active_backends": "Active backends: {backends}",
        "available_commands": "Available commands:",
        "codex_commands": "cask/cask-w/caskd/cping/cpend - Codex communication",
        "gemini_commands": "gask/gask-w/gping/gpend - Gemini communication",
        "executing": "Executing: {cmd}",
        "user_interrupted": "User interrupted",
        "cleaning_up": "Cleaning up session resources...",
        "cleanup_complete": "Cleanup complete",

        # Banner
        "banner_title": "Claude Code Bridge {version}",
        "banner_date": "{date}",
        "banner_backends": "Backends: {backends}",

        # No-claude mode
        "backends_started_no_claude": "Backends started (--no-claude mode)",
        "switch_to_pane": "Switch to pane:",
        "kill_hint": "Kill: ccb kill {providers}",

        # Status
        "backend_status": "AI backend status:",

        # Errors
        "cannot_write_session": "Cannot write {filename}: {reason}",
        "fix_hint": "Fix: {fix}",
        "error": "Error",
        "execution_failed": "Execution failed: {error}",
        "import_failed": "Import failed: {error}",
        "module_import_failed": "Module import failed: {error}",

        # Connectivity
        "connectivity_test_failed": "{provider} connectivity test failed: {error}",
        "no_reply_available": "No {provider} reply available",

        # Commands
        "usage": "Usage: {cmd}",
        "sending_to": "Sending question to {provider}...",
        "waiting_for_reply": "Waiting for {provider} reply (no timeout, Ctrl-C to interrupt)...",
        "reply_from": "{provider} reply:",
        "timeout_no_reply": "Timeout: no reply from {provider}",
        "session_not_found": "No active {provider} session found",

        # Install messages
        "install_complete": "Installation complete",
        "uninstall_complete": "Uninstall complete",
        "python_version_old": "Python version too old: {version}",
        "requires_python": "Requires Python 3.10+",
        "missing_dependency": "Missing dependency: {dep}",
        "detected_env": "Detected {env} environment",
        "confirm_continue": "Confirm continue? (y/N)",
        "cancelled": "Cancelled",
    },
    "zh": {
        # Terminal detection
        "no_terminal_backend": "未检测到终端后端 (WezTerm 或 tmux)",
        "solutions": "解决方案：",
        "install_wezterm": "安装 WezTerm (推荐): https://wezfurlong.org/wezterm/",
        "or_install_tmux": "或安装 tmux",
        "or_set_ccb_terminal": "或设置 CCB_TERMINAL=wezterm 并配置 CODEX_WEZTERM_BIN",
        "tmux_not_installed": "tmux 未安装且 WezTerm 不可用",
        "install_wezterm_or_tmux": "解决方案：安装 WezTerm (推荐) 或 tmux",

        # Startup messages
        "starting_backend": "正在启动 {provider} 后端 ({terminal})...",
        "started_backend": "{provider} 已启动 ({terminal}: {pane_id})",
        "unknown_provider": "未知提供者: {provider}",
        "resuming_session": "正在恢复 {provider} 会话: {session_id}...",
        "no_history_fresh": "未找到 {provider} 历史记录，全新启动",
        "warmup": "预热: {script}",
        "warmup_failed": "预热失败: {provider}",

        # Claude
        "starting_claude": "正在启动 Claude...",
        "resuming_claude": "正在恢复 Claude 会话: {session_id}...",
        "no_claude_session": "未找到本地 Claude 会话，全新启动",
        "session_id": "会话 ID: {session_id}",
        "runtime_dir": "运行目录: {runtime_dir}",
        "active_backends": "活动后端: {backends}",
        "available_commands": "可用命令：",
        "codex_commands": "cask/cask-w/caskd/cping/cpend - Codex 通信",
        "gemini_commands": "gask/gask-w/gping/gpend - Gemini 通信",
        "executing": "执行: {cmd}",
        "user_interrupted": "用户中断",
        "cleaning_up": "正在清理会话资源...",
        "cleanup_complete": "清理完成",

        # Banner
        "banner_title": "Claude Code Bridge {version}",
        "banner_date": "{date}",
        "banner_backends": "后端: {backends}",

        # No-claude mode
        "backends_started_no_claude": "后端已启动 (--no-claude 模式)",
        "switch_to_pane": "切换到面板:",
        "kill_hint": "终止: ccb kill {providers}",

        # Status
        "backend_status": "AI 后端状态:",

        # Errors
        "cannot_write_session": "无法写入 {filename}: {reason}",
        "fix_hint": "修复: {fix}",
        "error": "错误",
        "execution_failed": "执行失败: {error}",
        "import_failed": "导入失败: {error}",
        "module_import_failed": "模块导入失败: {error}",

        # Connectivity
        "connectivity_test_failed": "{provider} 连通性测试失败: {error}",
        "no_reply_available": "暂无 {provider} 回复",

        # Commands
        "usage": "用法: {cmd}",
        "sending_to": "正在发送问题到 {provider}...",
        "waiting_for_reply": "等待 {provider} 回复 (无超时，Ctrl-C 中断)...",
        "reply_from": "{provider} 回复:",
        "timeout_no_reply": "超时: 未收到 {provider} 回复",
        "session_not_found": "未找到活动的 {provider} 会话",

        # Install messages
        "install_complete": "安装完成",
        "uninstall_complete": "卸载完成",
        "python_version_old": "Python 版本过旧: {version}",
        "requires_python": "需要 Python 3.10+",
        "missing_dependency": "缺少依赖: {dep}",
        "detected_env": "检测到 {env} 环境",
        "confirm_continue": "确认继续？(y/N)",
        "cancelled": "已取消",
    },
}


def detect_language() -> str:
    """Detect language from environment.

    Priority:
    1. CCB_LANG environment variable (zh/en/auto)
    2. System locale
    3. Default to English
    """
    ccb_lang = os.environ.get("CCB_LANG", "auto").lower()

    if ccb_lang in ("zh", "cn", "chinese"):
        return "zh"
    if ccb_lang in ("en", "english"):
        return "en"

    # Auto-detect from system locale
    try:
        lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "") or os.environ.get("LC_MESSAGES", "")
        if not lang:
            lang, _ = locale.getdefaultlocale()
            lang = lang or ""

        lang = lang.lower()
        if lang.startswith("zh") or "chinese" in lang:
            return "zh"
    except Exception:
        pass

    return "en"


def get_lang() -> str:
    """Get current language setting."""
    global _current_lang
    if _current_lang is None:
        _current_lang = detect_language()
    return _current_lang


def set_lang(lang: str) -> None:
    """Set language explicitly."""
    global _current_lang
    if lang in ("zh", "en"):
        _current_lang = lang


def t(key: str, **kwargs) -> str:
    """Get translated message by key.

    Args:
        key: Message key
        **kwargs: Format arguments

    Returns:
        Translated and formatted message
    """
    lang = get_lang()
    messages = MESSAGES.get(lang, MESSAGES["en"])

    msg = messages.get(key)
    if msg is None:
        # Fallback to English
        msg = MESSAGES["en"].get(key, key)

    if kwargs:
        try:
            msg = msg.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return msg
