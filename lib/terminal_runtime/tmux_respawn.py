from __future__ import annotations

import shlex
from pathlib import Path


def normalize_start_dir(cwd: str | None) -> str:
    start_dir = (cwd or "").strip()
    if start_dir in ("", "."):
        return ""
    return start_dir


def append_stderr_redirection(cmd_body: str, stderr_log_path: str | None) -> tuple[str, str | None]:
    if not stderr_log_path:
        return cmd_body, None
    log_path = str(Path(stderr_log_path).expanduser().resolve())
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    return f"{cmd_body} 2>> {shlex.quote(log_path)}", log_path


def resolve_shell(*, env_shell: str, tmux_default_shell: str, process_shell: str, fallback_shell: str) -> str:
    shell = (env_shell or "").strip()
    if shell:
        return shell
    shell = (tmux_default_shell or "").strip()
    if shell:
        return shell
    shell = (process_shell or "").strip()
    if shell:
        return shell
    return fallback_shell


def resolve_shell_flags(*, shell: str, flags_raw: str) -> list[str]:
    raw = (flags_raw or "").strip()
    if raw:
        return shlex.split(raw)
    shell_name = Path(shell).name.lower()
    if shell_name in {"bash", "zsh", "ksh", "fish"}:
        return ["-l", "-c"]
    if shell_name in {"sh", "dash"}:
        return ["-c"]
    return ["-c"]


def build_shell_command(*, shell: str, flags: list[str], cmd_body: str) -> str:
    argv = [shell, *flags, cmd_body]
    return " ".join(shlex.quote(arg) for arg in argv)


def build_respawn_tmux_args(*, pane_id: str, start_dir: str, full_command: str) -> list[str]:
    args = ["respawn-pane", "-k", "-t", pane_id]
    if start_dir:
        args.extend(["-c", start_dir])
    args.append(full_command)
    return args
