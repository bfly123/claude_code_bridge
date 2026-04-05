from __future__ import annotations

import os
from pathlib import Path
import sys


def set_tmux_ui_active(
    launcher,
    active: bool,
    *,
    subprocess_module,
) -> None:
    if launcher.terminal_type != "tmux":
        return
    if not os.environ.get("TMUX"):
        return
    script = Path.home() / ".local" / "bin" / ("ccb-tmux-on.sh" if active else "ccb-tmux-off.sh")
    if not script.exists():
        return
    try:
        debug = os.environ.get("CCB_DEBUG") in ("1", "true", "yes")
        cp = subprocess_module.run(
            [str(script)],
            check=False,
            capture_output=debug,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if cp.returncode != 0 and debug:
            out = (cp.stdout or "").strip()
            err = (cp.stderr or "").strip()
            detail = "\n".join([s for s in [out, err] if s])
            if detail:
                print(f"⚠️ ccb tmux ui script failed (rc={cp.returncode}):\n{detail}", file=sys.stderr)
    except Exception:
        return
