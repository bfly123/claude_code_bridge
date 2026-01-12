from __future__ import annotations

from pathlib import Path

import terminal


def _clear_terminal_env(monkeypatch) -> None:
    monkeypatch.delenv("WEZTERM_PANE", raising=False)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.delenv("CODEX_IT2_BIN", raising=False)
    monkeypatch.delenv("IT2_BIN", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")


def test_detect_terminal_prefers_current_tmux_session(monkeypatch) -> None:
    _clear_terminal_env(monkeypatch)
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,123,0")
    monkeypatch.setattr(terminal, "_get_wezterm_bin", lambda: "/usr/bin/wezterm")
    assert terminal.detect_terminal() == "tmux"


def test_detect_terminal_does_not_select_tmux_when_not_inside_tmux(monkeypatch) -> None:
    _clear_terminal_env(monkeypatch)
    monkeypatch.setattr(terminal, "_get_wezterm_bin", lambda: None)
    assert terminal.detect_terminal() is None


def test_detect_terminal_selects_wezterm_when_available(monkeypatch) -> None:
    _clear_terminal_env(monkeypatch)
    monkeypatch.setattr(terminal, "_get_wezterm_bin", lambda: "/usr/bin/wezterm")
    assert terminal.detect_terminal() == "wezterm"


def test_detect_terminal_respects_iterm2_override_bin(monkeypatch, tmp_path: Path) -> None:
    _clear_terminal_env(monkeypatch)
    it2 = tmp_path / "it2"
    it2.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_IT2_BIN", str(it2))
    monkeypatch.setattr(terminal, "_get_wezterm_bin", lambda: None)
    assert terminal.detect_terminal() == "iterm2"

