from __future__ import annotations

import os
from pathlib import Path
import subprocess


def set_tmux_ui_active(active: bool) -> None:
    if not ((os.environ.get('TMUX') or os.environ.get('TMUX_PANE') or '').strip()):
        return
    script = Path.home() / '.local' / 'bin' / ('ccb-tmux-on.sh' if active else 'ccb-tmux-off.sh')
    if not script.is_file():
        return
    try:
        subprocess.run(
            [str(script)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return


__all__ = ['set_tmux_ui_active']
