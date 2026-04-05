from __future__ import annotations

import os
from pathlib import Path
import shlex

from terminal_runtime import get_shell_type


def build_keep_open_cmd(provider: str, start_cmd: str) -> str:
    if get_shell_type() == "powershell":
        return (
            f"{start_cmd}; "
            f"$code = $LASTEXITCODE; "
            f'Write-Host "`n[{provider}] exited with code $code. Press Enter to close..."; '
            f"Read-Host; "
            f"exit $code"
        )
    return (
        f"{start_cmd}; "
        f"code=$?; "
        f'echo; echo "[{provider}] exited with code $code. Press Enter to close..."; '
        f"read -r _; "
        f"exit $code"
    )


def build_pane_title_cmd(marker: str) -> str:
    if get_shell_type() == "powershell":
        safe_sq = marker.replace("'", "''")
        safe_dq = marker.replace('"', '`"')
        return (
            "$esc=[char]27; "
            f'[Console]::Write("$esc]0;{safe_dq}`a"); '
            f"$Host.UI.RawUI.WindowTitle = '{safe_sq}'; "
        )
    return f"printf '\\033]0;{marker}\\007'; "


def build_export_path_cmd(bin_dir: Path) -> str:
    bin_s = str(bin_dir)
    if get_shell_type() == "powershell":
        safe = bin_s.replace("'", "''")
        current = (os.environ.get("PATH") or "").replace("'", "''")
        if current:
            return f"$env:Path = '{safe};{current}'; "
        return f"$env:Path = '{safe};' + $env:Path; "

    current = os.environ.get("PATH") or ""
    if current:
        return f"export PATH={shlex.quote(bin_s)}{os.pathsep}{shlex.quote(current)}; "
    return f"export PATH={shlex.quote(bin_s)}{os.pathsep}$PATH; "


def build_cd_cmd(work_dir: Path) -> str:
    if get_shell_type() == "powershell":
        safe = str(work_dir).replace("'", "''")
        return f"Set-Location -Path '{safe}'; "
    return f"cd {shlex.quote(str(work_dir))}; "
