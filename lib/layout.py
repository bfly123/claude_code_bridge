"""Layout strategies for provider pane/window placement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from terminal import TmuxBackend

# Callback type: start_item(item, parent, direction) -> pane_id | None
StartItemFn = Callable[[str, Optional[str], Optional[str]], Optional[str]]


class LayoutStrategy(ABC):
    """Base class for layout strategies controlling how providers are placed."""

    @abstractmethod
    def place_providers(
        self,
        spawn_items: list[str],
        left_items: list[str],
        right_items: list[str],
        anchor_pane_id: str,
        start_item: StartItemFn,
    ) -> int:
        """Place all providers. Returns 0 on success, 1 on failure."""
        ...

    @property
    def linked_sessions(self) -> list[str]:
        return []

    def cleanup(self) -> None:
        """Release resources (e.g. linked tmux sessions)."""


class PanesLayout(LayoutStrategy):
    """Place providers in a left/right split-pane grid."""

    def place_providers(
        self,
        spawn_items: list[str],
        left_items: list[str],
        right_items: list[str],
        anchor_pane_id: str,
        start_item: StartItemFn,
    ) -> int:
        # Panes mode uses left_items/right_items for grid layout; spawn_items unused.
        right_top: str | None = None
        if right_items:
            right_top = start_item(right_items[0], anchor_pane_id, "right")
            if not right_top:
                return 1

        last_left = anchor_pane_id
        for item in left_items[1:]:
            pane_id = start_item(item, last_left, "bottom")
            if not pane_id:
                return 1
            last_left = pane_id

        last_right = right_top
        for item in right_items[1:]:
            pane_id = start_item(item, last_right, "bottom")
            if not pane_id:
                return 1
            last_right = pane_id

        return 0


class WindowsLayout(LayoutStrategy):
    """Each non-anchor provider gets its own tmux window with a linked session."""

    def __init__(self, backend: TmuxBackend, anchor_pane_id: str, anchor_provider: str):
        self._backend = backend
        self._anchor_provider = anchor_provider
        # Capture main session name ONCE before any linked sessions are created.
        # Linked sessions join the session group and can pollute later
        # #{session_name} queries.
        self._main_session = backend.get_session_name(anchor_pane_id)
        self._linked: list[str] = []

    @property
    def linked_sessions(self) -> list[str]:
        return list(self._linked)

    def place_providers(
        self,
        spawn_items: list[str],
        left_items: list[str],
        right_items: list[str],
        anchor_pane_id: str,
        start_item: StartItemFn,
    ) -> int:
        # Windows mode uses spawn_items; left_items/right_items unused.
        for item in spawn_items:
            if item == "cmd":
                # cmd splits inside the anchor window (panes behaviour).
                pane_id = start_item(item, anchor_pane_id, "right")
            else:
                pane_id = start_item(item, anchor_pane_id, None)
            if not pane_id:
                return 1
            if item != "cmd":
                win_name = item.capitalize()
                self._backend.rename_window(pane_id, win_name)
                self._create_linked(win_name)

        # Label the anchor window and create its linked session.
        anchor_win = self._anchor_provider.capitalize()
        self._backend.rename_window(anchor_pane_id, anchor_win)
        self._create_linked(anchor_win)
        return 0

    def cleanup(self) -> None:
        for name in self._linked:
            self._backend.destroy_linked_session(name)
        self._linked.clear()

    def _create_linked(self, win_name: str) -> None:
        if not self._main_session:
            return
        linked_name = f"{self._main_session}-{win_name}"
        ok = self._backend.create_linked_session(
            self._main_session, linked_name,
            select_window=f"{linked_name}:{win_name}",
        )
        if ok:
            self._linked.append(linked_name)
