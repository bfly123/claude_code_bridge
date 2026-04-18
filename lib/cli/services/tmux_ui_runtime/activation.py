from __future__ import annotations

import os
import subprocess

from .helpers import script_path


def set_tmux_ui_active(active: bool) -> None:
    if not ((os.environ.get('TMUX') or os.environ.get('TMUX_PANE') or '').strip()):
        return
    script = script_path('ccb-tmux-on.sh' if active else 'ccb-tmux-off.sh')
    if not script:
        return
    try:
        subprocess.run(
            [script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return


__all__ = ['set_tmux_ui_active']
