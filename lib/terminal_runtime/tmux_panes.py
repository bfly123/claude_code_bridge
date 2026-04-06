from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .tmux_panes_runtime.actions import set_pane_style, set_pane_title, set_pane_user_option, split_pane
from .tmux_panes_runtime.queries import (
    describe_pane,
    find_pane_by_title_marker,
    get_current_pane_id,
    get_pane_content,
    is_pane_alive,
    list_panes_by_user_options,
    pane_exists,
)


@dataclass
class TmuxPaneService:
    tmux_run_fn: Callable[..., object]
    looks_like_pane_id_fn: Callable[[str], bool]
    normalize_split_direction_fn: Callable[[str], tuple[str, str]]
    pane_exists_output_fn: Callable[[str], bool]
    pane_id_by_title_marker_output_fn: Callable[[str, str], str | None]
    pane_is_alive_fn: Callable[[str], bool]
    normalize_user_option_fn: Callable[[str], str]
    strip_ansi_fn: Callable[[str], str]

    def pane_exists(self, pane_id: str) -> bool:
        return pane_exists(self, pane_id)

    def get_current_pane_id(self, *, env_pane: str) -> str:
        return get_current_pane_id(self, env_pane=env_pane)

    def split_pane(self, parent_pane_id: str, *, direction: str, percent: int) -> str:
        return split_pane(self, parent_pane_id, direction=direction, percent=percent)

    def set_pane_title(self, pane_id: str, title: str) -> None:
        set_pane_title(self, pane_id, title)

    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
        set_pane_user_option(self, pane_id, name, value)

    def set_pane_style(
        self,
        pane_id: str,
        *,
        border_style: str | None = None,
        active_border_style: str | None = None,
    ) -> None:
        set_pane_style(self, pane_id, border_style=border_style, active_border_style=active_border_style)

    def find_pane_by_title_marker(self, marker: str) -> str | None:
        return find_pane_by_title_marker(self, marker)

    def find_pane_by_user_options(self, expected: dict[str, str]) -> str | None:
        matches = self.list_panes_by_user_options(expected)
        if len(matches) == 1:
            return matches[0]
        return None

    def list_panes_by_user_options(self, expected: dict[str, str]) -> list[str]:
        return list_panes_by_user_options(self, expected)

    def describe_pane(self, pane_id: str, *, user_options: tuple[str, ...] = ()) -> dict[str, str] | None:
        return describe_pane(self, pane_id, user_options=user_options)

    def get_pane_content(self, pane_id: str, *, lines: int = 20) -> str | None:
        return get_pane_content(self, pane_id, lines=lines)

    def is_pane_alive(self, pane_id: str) -> bool:
        return is_pane_alive(self, pane_id)
