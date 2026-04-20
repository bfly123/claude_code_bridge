from __future__ import annotations

from pathlib import Path

from terminal_runtime.tmux_respawn import append_stderr_redirection
from terminal_runtime.tmux_respawn import build_respawn_tmux_args
from terminal_runtime.tmux_respawn import build_shell_command
from terminal_runtime.tmux_respawn import normalize_start_dir
from terminal_runtime.tmux_respawn import resolve_shell
from terminal_runtime.tmux_respawn import resolve_shell_flags


def test_normalize_start_dir() -> None:
    assert normalize_start_dir(None) == ""
    assert normalize_start_dir(".") == ""
    assert normalize_start_dir("/tmp/demo") == "/tmp/demo"


def test_append_stderr_redirection_creates_parent(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "stderr.log"
    cmd, resolved = append_stderr_redirection("echo hi", str(log_path))
    assert resolved == str(log_path.resolve())
    assert "2>>" in cmd
    assert log_path.parent.exists()


def test_resolve_shell_prefers_explicit_then_tmux_then_process_then_fallback() -> None:
    assert resolve_shell(env_shell="/bin/zsh", tmux_default_shell="/bin/bash", process_shell="/bin/sh", fallback_shell="bash") == "/bin/zsh"
    assert resolve_shell(env_shell="", tmux_default_shell="/bin/bash", process_shell="/bin/sh", fallback_shell="bash") == "/bin/bash"
    assert resolve_shell(env_shell="", tmux_default_shell="", process_shell="/bin/sh", fallback_shell="bash") == "/bin/sh"
    assert resolve_shell(env_shell="", tmux_default_shell="", process_shell="", fallback_shell="bash") == "bash"


def test_resolve_shell_flags_defaults() -> None:
    assert resolve_shell_flags(shell="/bin/bash", flags_raw="") == ["-l", "-c"]
    assert resolve_shell_flags(shell="/bin/zsh", flags_raw="") == ["-l", "-c"]
    assert resolve_shell_flags(shell="/bin/dash", flags_raw="") == ["-c"]
    assert resolve_shell_flags(shell="/bin/custom", flags_raw="") == ["-c"]
    assert resolve_shell_flags(shell="/bin/bash", flags_raw="-c") == ["-c"]


def test_build_shell_command_quotes_arguments() -> None:
    command = build_shell_command(shell="/bin/bash", flags=["-l", "-c"], cmd_body="echo hi > /tmp/a b")
    assert command.startswith("/bin/bash")
    assert "'echo hi > /tmp/a b'" in command


def test_build_respawn_tmux_args() -> None:
    assert build_respawn_tmux_args(pane_id="%9", start_dir="/tmp/demo", full_command="bash -c 'echo hi'") == [
        "respawn-pane",
        "-k",
        "-t",
        "%9",
        "-c",
        "/tmp/demo",
        "bash -c 'echo hi'",
    ]
