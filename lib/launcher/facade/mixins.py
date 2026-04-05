from __future__ import annotations

from launcher.facade.claude_mixin import LauncherClaudeFacadeMixin
from launcher.facade.current_pane_mixin import LauncherCurrentPaneFacadeMixin
from launcher.facade.support_mixin import LauncherFacadeSupportMixin
from launcher.facade.tmux_mixin import LauncherTmuxFacadeMixin


class LauncherFacadeMixin(
    LauncherFacadeSupportMixin,
    LauncherTmuxFacadeMixin,
    LauncherCurrentPaneFacadeMixin,
    LauncherClaudeFacadeMixin,
):
    pass
