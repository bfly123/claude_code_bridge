from __future__ import annotations

import atexit
import signal
import sys
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class LauncherRunUpLayout:
    left_items: tuple[str, ...]
    right_items: tuple[str, ...]


def plan_two_column_layout(*, anchor_name: str, spawn_items: list[str]) -> LauncherRunUpLayout:
    total_panes = 1 + len(spawn_items)
    left_count = 1 if total_panes <= 1 else max(1, total_panes // 2)
    right_count = total_panes - left_count

    extras = list(spawn_items)
    right_top_item = extras[0] if right_count > 0 and extras else None
    remaining = extras[1:] if right_top_item else extras

    left_slots = max(0, left_count - 1)
    right_slots = max(0, right_count - (1 if right_top_item else 0))

    left_items = [anchor_name]
    left_items.extend(remaining[:left_slots])

    right_items: list[str] = []
    if right_top_item:
        right_items.append(right_top_item)
    if right_slots:
        right_items.extend(remaining[left_slots:left_slots + right_slots])
    return LauncherRunUpLayout(left_items=tuple(left_items), right_items=tuple(right_items))


@dataclass
class LauncherRunUpCoordinator:
    target_names: tuple[str, ...]
    anchor_name: str
    anchor_pane_id: str
    terminal_type: str | None
    cleanup_fn: Callable[..., None]
    set_tmux_ui_active_fn: Callable[[bool], None]
    set_current_pane_label_fn: Callable[[str], None]
    write_local_claude_session_fn: Callable[..., None]
    read_local_claude_session_id_fn: Callable[[], str | None]
    start_item_fn: Callable[[str, str | None, str | None], str | None]
    sync_cend_registry_fn: Callable[[], None]
    start_anchor_fn: Callable[[str], int]
    cleanup_tmpclaude_fn: Callable[[], int]
    cleanup_stale_runtime_fn: Callable[[], int]
    shrink_logs_fn: Callable[[], int]
    debug_enabled_fn: Callable[[], bool]

    def register_cleanup_handlers(self, cleanup_kwargs: dict) -> None:
        atexit.register(lambda: self.cleanup_fn(**cleanup_kwargs))
        signal.signal(signal.SIGINT, lambda s, f: (self.cleanup_fn(**cleanup_kwargs), sys.exit(0)))
        signal.signal(signal.SIGTERM, lambda s, f: (self.cleanup_fn(**cleanup_kwargs), sys.exit(0)))

    def run_housekeeping(self) -> None:
        self._best_effort('Cleaned tmpclaude artifacts', self.cleanup_tmpclaude_fn)
        self._best_effort('Cleaned stale runtime dirs', self.cleanup_stale_runtime_fn)
        self._best_effort('Shrunk log files', self.shrink_logs_fn)

    def activate_anchor(self) -> None:
        try:
            self.set_tmux_ui_active_fn(True)
        except Exception:
            pass
        try:
            self.set_current_pane_label_fn(self.anchor_name)
        except Exception:
            pass
        if self.anchor_name == 'claude':
            try:
                self.write_local_claude_session_fn(
                    session_id=self.read_local_claude_session_id_fn(),
                    active=True,
                    pane_id=str(self.anchor_pane_id or ''),
                    pane_title_marker='CCB-Claude',
                    terminal=self.terminal_type,
                )
            except Exception:
                pass

    def launch_non_anchor(self, layout: LauncherRunUpLayout) -> bool:
        right_top: str | None = None
        if layout.right_items:
            right_top = self.start_item_fn(layout.right_items[0], self.anchor_pane_id, 'right')
            if not right_top:
                return False

        last_left = self.anchor_pane_id
        for item in layout.left_items[1:]:
            pane_id = self.start_item_fn(item, last_left, 'bottom')
            if not pane_id:
                return False
            last_left = pane_id

        last_right = right_top
        for item in layout.right_items[1:]:
            pane_id = self.start_item_fn(item, last_right, 'bottom')
            if not pane_id:
                return False
            last_right = pane_id
        return True

    def finish(self, cleanup_kwargs: dict) -> int:
        try:
            try:
                self.sync_cend_registry_fn()
            except Exception:
                pass
            return self.start_anchor_fn(self.anchor_name)
        finally:
            self.cleanup_fn(**cleanup_kwargs)

    def _best_effort(self, label: str, fn: Callable[[], int]) -> None:
        try:
            changed = fn()
            if changed and self.debug_enabled_fn():
                print(f'🧹 {label}: {changed}')
        except Exception:
            pass
