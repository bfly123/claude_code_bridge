from __future__ import annotations

from terminal_runtime.tmux_input import build_buffer_name
from terminal_runtime.tmux_input import copy_mode_is_active
from terminal_runtime.tmux_input import sanitize_text
from terminal_runtime.tmux_input import should_use_inline_legacy_send


def test_sanitize_text_and_inline_legacy_send() -> None:
    assert sanitize_text(" hello\r\n") == "hello"
    assert should_use_inline_legacy_send(target_is_tmux=False, text="hello") is True
    assert should_use_inline_legacy_send(target_is_tmux=False, text="a\nb") is False
    assert should_use_inline_legacy_send(target_is_tmux=True, text="hello") is False


def test_build_buffer_name_and_copy_mode() -> None:
    assert build_buffer_name(pid=1, now_ms=2, rand_int=3) == "ccb-tb-1-2-3"
    assert copy_mode_is_active("1") is True
    assert copy_mode_is_active("yes") is True
    assert copy_mode_is_active("0") is False
