from __future__ import annotations

import subprocess

import terminal_runtime.api as terminal


def _clear_terminal_env(monkeypatch) -> None:
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")


def test_detect_terminal_prefers_current_tmux_session(monkeypatch) -> None:
    _clear_terminal_env(monkeypatch)
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,123,0")
    monkeypatch.setenv("TMUX_PANE", "%1")
    monkeypatch.setattr(terminal, "_current_tty", lambda: "/dev/pts/7")
    monkeypatch.setattr(terminal.shutil, "which", lambda name: "/usr/bin/tmux" if name == "tmux" else None)

    def fake_run(*args, **kwargs):
        cmd = args[0]
        if "#{pane_tty}" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="/dev/pts/7\n", stderr="")
        if "#{client_tty}" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="/dev/pts/7\n", stderr="")
        if "#{pane_id}" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="%1\n", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="fail")

    monkeypatch.setattr(terminal, "_run", fake_run)
    assert terminal.detect_terminal() == "tmux"


def test_detect_terminal_does_not_select_tmux_when_not_inside_tmux(monkeypatch) -> None:
    _clear_terminal_env(monkeypatch)
    assert terminal.detect_terminal() is None


def test_detect_terminal_rejects_stale_tmux_env(monkeypatch) -> None:
    _clear_terminal_env(monkeypatch)
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,123,0")
    monkeypatch.setenv("TMUX_PANE", "%1")
    monkeypatch.setattr(terminal, "_current_tty", lambda: "/dev/pts/9")
    monkeypatch.setattr(terminal.shutil, "which", lambda name: "/usr/bin/tmux" if name == "tmux" else None)

    def fake_run(*args, **kwargs):
        cmd = args[0]
        if "#{pane_tty}" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="/dev/pts/7\n", stderr="")
        if "#{client_tty}" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="/dev/pts/7\n", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="fail")

    monkeypatch.setattr(terminal, "_run", fake_run)
    assert terminal.detect_terminal() is None
