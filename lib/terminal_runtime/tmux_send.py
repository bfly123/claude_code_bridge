from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class TmuxTextSender:
    tmux_run_fn: Callable[..., object]
    looks_like_tmux_target_fn: Callable[[str], bool]
    ensure_not_in_copy_mode_fn: Callable[[str], None]
    build_buffer_name_fn: Callable[..., str]
    sanitize_text_fn: Callable[[str], str]
    should_use_inline_legacy_send_fn: Callable[..., bool]
    env_float_fn: Callable[[str, float], float]
    os_getpid_fn: Callable[[], int] = os.getpid
    time_fn: Callable[[], float] = time.time
    randint_fn: Callable[[int, int], int] = random.randint
    sleep_fn: Callable[[float], None] = time.sleep

    def send_text(self, pane_id: str, text: str) -> None:
        sanitized = self.sanitize_text_fn(text)
        if not sanitized:
            return

        target_is_tmux = self.looks_like_tmux_target_fn(pane_id)
        if not target_is_tmux:
            session = pane_id
            if self.should_use_inline_legacy_send_fn(target_is_tmux=target_is_tmux, text=sanitized):
                self.tmux_run_fn(['send-keys', '-t', session, '-l', sanitized], check=True)
                self.tmux_run_fn(['send-keys', '-t', session, 'Enter'], check=True)
                return
            self._paste_via_buffer(target=session, text=sanitized, pane_target=False)
            return

        self.ensure_not_in_copy_mode_fn(pane_id)
        self._paste_via_buffer(target=pane_id, text=sanitized, pane_target=True)

    def _paste_via_buffer(self, *, target: str, text: str, pane_target: bool) -> None:
        buffer_name = self.build_buffer_name_fn(
            pid=self.os_getpid_fn(),
            now_ms=int(self.time_fn() * 1000),
            rand_int=self.randint_fn(1000, 9999),
        )
        self.tmux_run_fn(['load-buffer', '-b', buffer_name, '-'], check=True, input_bytes=text.encode('utf-8'))
        try:
            if pane_target:
                self.tmux_run_fn(['paste-buffer', '-p', '-t', target, '-b', buffer_name], check=True)
            else:
                self.tmux_run_fn(['paste-buffer', '-t', target, '-b', buffer_name, '-p'], check=True)
            enter_delay = self.env_float_fn('CCB_TMUX_ENTER_DELAY', 0.5)
            if enter_delay:
                self.sleep_fn(enter_delay)
            self.tmux_run_fn(['send-keys', '-t', target, 'Enter'], check=True)
        finally:
            self.tmux_run_fn(['delete-buffer', '-b', buffer_name], check=False)
