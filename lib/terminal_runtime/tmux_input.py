from __future__ import annotations


def sanitize_text(text: str) -> str:
    return (text or "").replace("\r", "").strip()


def should_use_inline_legacy_send(*, target_is_tmux: bool, text: str, inline_limit: int = 200) -> bool:
    if target_is_tmux:
        return False
    return "\n" not in text and len(text) <= inline_limit


def build_buffer_name(*, pid: int, now_ms: int, rand_int: int) -> str:
    return f"ccb-tb-{pid}-{now_ms}-{rand_int}"


def copy_mode_is_active(value: str) -> bool:
    return (value or "").strip() in {"1", "on", "yes"}
