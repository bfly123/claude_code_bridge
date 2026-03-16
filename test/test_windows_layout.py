from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

import terminal
from ccb_start_config import _parse_config_obj
from pane_registry import get_layout_mode, upsert_registry, registry_path_for_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cp(*, stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["tmux"], returncode=returncode, stdout=stdout, stderr="")


# ---------------------------------------------------------------------------
# Config parsing tests
# ---------------------------------------------------------------------------

class TestConfigLayoutParsing:
    def test_config_layout_windows(self) -> None:
        data = _parse_config_obj({"providers": ["codex"], "layout": "windows"})
        assert data["layout"] == "windows"

    def test_config_layout_panes_default(self) -> None:
        data = _parse_config_obj({"providers": ["codex"]})
        assert "layout" not in data

    def test_config_layout_invalid(self) -> None:
        data = _parse_config_obj({"providers": ["codex"], "layout": "stacked"})
        assert "layout" not in data

    def test_config_layout_panes_explicit(self) -> None:
        data = _parse_config_obj({"providers": ["codex"], "layout": "panes"})
        assert data["layout"] == "panes"

    def test_config_layout_case_insensitive(self) -> None:
        data = _parse_config_obj({"providers": ["codex"], "layout": "WINDOWS"})
        assert data["layout"] == "windows"

    def test_config_layout_non_string_stripped(self) -> None:
        data = _parse_config_obj({"providers": ["codex"], "layout": 123})
        assert "layout" not in data


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestRegistryLayoutMode:
    def test_get_layout_mode_default(self) -> None:
        record: dict[str, Any] = {"ccb_session_id": "s1"}
        assert get_layout_mode(record) == "panes"

    def test_get_layout_mode_windows(self) -> None:
        record: dict[str, Any] = {"ccb_session_id": "s1", "layout_mode": "windows"}
        assert get_layout_mode(record) == "windows"

    def test_get_layout_mode_panes_explicit(self) -> None:
        record: dict[str, Any] = {"ccb_session_id": "s1", "layout_mode": "panes"}
        assert get_layout_mode(record) == "panes"

    def test_registry_stores_layout_mode(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        # Point the registry dir to tmp_path so we don't pollute the real home.
        monkeypatch.setattr("pane_registry._registry_dir", lambda: tmp_path)

        record: dict[str, Any] = {
            "ccb_session_id": "test-layout-001",
            "layout_mode": "windows",
            "terminal": "tmux",
            "work_dir": str(tmp_path),
        }
        assert upsert_registry(record) is True

        written = registry_path_for_session("test-layout-001")
        assert written.exists()
        data = json.loads(written.read_text(encoding="utf-8"))
        assert data["layout_mode"] == "windows"


# ---------------------------------------------------------------------------
# TmuxBackend mock tests
# ---------------------------------------------------------------------------

class TestCreatePaneLayoutMode:
    def test_create_pane_windows_mode_calls_new_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When layout_mode='windows', create_pane should call new_window instead of split_pane."""
        calls: list[dict[str, Any]] = []

        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append({"args": args, "check": check, "capture": capture})
            # get_current_pane_id queries
            if args == ["display-message", "-p", "#{pane_id}"]:
                return _cp(stdout="%0\n")
            # pane_exists check
            if args == ["display-message", "-p", "-t", "%0", "#{pane_dead}"]:
                return _cp(stdout="0\n")
            # session_name lookup for new_window
            if len(args) >= 4 and "#{session_name}" in args:
                return _cp(stdout="mysession\n")
            # new-window call
            if args and args[0] == "new-window":
                return _cp(stdout="%99\n")
            # respawn-pane (noop)
            if args and args[0] == "respawn-pane":
                return _cp()
            # set-option for remain-on-exit
            if args and args[0] == "set-option":
                return _cp()
            return _cp(stdout="")

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        pane_id = backend.create_pane(cmd="echo hello", cwd="/tmp", parent_pane="%0", layout_mode="windows")
        assert pane_id == "%99"

        # Verify that new-window was called (not split-window).
        new_window_calls = [c for c in calls if c["args"] and c["args"][0] == "new-window"]
        split_calls = [c for c in calls if c["args"] and c["args"][0] == "split-window"]
        assert len(new_window_calls) == 1
        assert len(split_calls) == 0

        # Verify the session target was passed to new-window.
        nw_args = new_window_calls[0]["args"]
        assert "-t" in nw_args and "mysession" in nw_args

    def test_create_pane_panes_mode_calls_split(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When layout_mode='panes' (default), create_pane should call split_pane."""
        calls: list[dict[str, Any]] = []

        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append({"args": args, "check": check, "capture": capture})
            # pane_exists uses display-message #{pane_id}
            if args == ["display-message", "-p", "-t", "%0", "#{pane_id}"]:
                return _cp(stdout="%0\n")
            # pane size for split_pane
            if len(args) >= 4 and "#{pane_width}x#{pane_height}" in args:
                return _cp(stdout="160x40\n")
            # zoom check
            if len(args) >= 4 and "#{window_zoomed_flag}" in args:
                return _cp(stdout="0\n")
            # split-window
            if args and args[0] == "split-window":
                return _cp(stdout="%55\n")
            # respawn-pane
            if args and args[0] == "respawn-pane":
                return _cp()
            # set-option for remain-on-exit
            if args and args[0] == "set-option":
                return _cp()
            return _cp(stdout="")

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        pane_id = backend.create_pane(cmd="echo hello", cwd="/tmp", parent_pane="%0", layout_mode="panes")
        assert pane_id == "%55"

        # Verify that split-window was called (not new-window).
        split_calls = [c for c in calls if c["args"] and c["args"][0] == "split-window"]
        new_window_calls = [c for c in calls if c["args"] and c["args"][0] == "new-window"]
        assert len(split_calls) == 1
        assert len(new_window_calls) == 0

    def test_create_pane_default_layout_is_panes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling create_pane without layout_mode should behave as 'panes'."""
        calls: list[dict[str, Any]] = []

        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append({"args": args})
            # pane_exists uses display-message #{pane_id}
            if args == ["display-message", "-p", "-t", "%0", "#{pane_id}"]:
                return _cp(stdout="%0\n")
            if len(args) >= 4 and "#{pane_width}x#{pane_height}" in args:
                return _cp(stdout="160x40\n")
            if len(args) >= 4 and "#{window_zoomed_flag}" in args:
                return _cp(stdout="0\n")
            if args and args[0] == "split-window":
                return _cp(stdout="%10\n")
            if args and args[0] == "respawn-pane":
                return _cp()
            if args and args[0] == "set-option":
                return _cp()
            return _cp(stdout="")

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        pane_id = backend.create_pane(cmd="echo hi", cwd="/tmp", parent_pane="%0")
        assert pane_id == "%10"

        split_calls = [c for c in calls if c["args"] and c["args"][0] == "split-window"]
        new_window_calls = [c for c in calls if c["args"] and c["args"][0] == "new-window"]
        assert len(split_calls) == 1
        assert len(new_window_calls) == 0


# ---------------------------------------------------------------------------
# new_window unit tests
# ---------------------------------------------------------------------------

class TestNewWindow:
    def test_new_window_returns_pane_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            # new-window
            if args and args[0] == "new-window":
                return _cp(stdout="%77\n")
            # session_name lookup for linked session creation
            if len(args) >= 4 and "#{session_name}" in args:
                return _cp(stdout="mysess\n")
            # new-session (linked)
            if args and args[0] == "new-session":
                return _cp()
            # select-window
            if args and args[0] == "select-window":
                return _cp()
            return _cp(stdout="")

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        pane_id = backend.new_window(session="sess1", window_name="my-win")
        assert pane_id == "%77"
        # First call should be new-window.
        argv = calls[0]
        assert argv[0] == "new-window"
        assert "-P" in argv
        assert "-F" in argv and "#{pane_id}" in argv
        assert "-t" in argv and "sess1" in argv
        assert "-n" in argv and "my-win" in argv

    def test_new_window_no_session_no_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return _cp(stdout="%80\n")

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        pane_id = backend.new_window()
        assert pane_id == "%80"
        # Without window_name, only new-window is called (no linked session).
        assert len(calls) == 1
        argv = calls[0]
        assert "-t" not in argv
        assert "-n" not in argv

    def test_new_window_returns_empty_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            raise subprocess.CalledProcessError(1, ["tmux", *args])

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        pane_id = backend.new_window(session="s")
        assert pane_id == ""

    def test_new_window_does_not_create_linked_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify new_window() only creates the window; linked sessions are handled by run_up()."""
        calls: list[dict[str, Any]] = []

        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append({"args": args, "check": check})
            if args and args[0] == "new-window":
                return _cp(stdout="%42\n")
            return _cp(stdout="")

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        pane_id = backend.new_window(session="main-sess", window_name="Codex")
        assert pane_id == "%42"

        # Should only have the new-window call -- no new-session or display-message
        new_session_calls = [c for c in calls if c["args"] and c["args"][0] == "new-session"]
        assert len(new_session_calls) == 0
        display_calls = [c for c in calls if c["args"] and "#{session_name}" in str(c["args"])]
        assert len(display_calls) == 0


# ---------------------------------------------------------------------------
# destroy_linked_session unit tests
# ---------------------------------------------------------------------------

class TestDestroyLinkedSession:
    def test_destroy_linked_session_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return _cp(returncode=0)

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        result = backend.destroy_linked_session("main-sess-Codex")
        assert result is True
        assert len(calls) == 1
        assert calls[0][0] == "kill-session"
        assert "-t" in calls[0] and "main-sess-Codex" in calls[0]

    def test_destroy_linked_session_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            return _cp(returncode=1)

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        result = backend.destroy_linked_session("nonexistent")
        assert result is False

    def test_destroy_linked_session_empty_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        backend = terminal.TmuxBackend()
        assert backend.destroy_linked_session("") is False

    def test_destroy_linked_session_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            raise OSError("tmux not found")

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        result = backend.destroy_linked_session("sess-Codex")
        assert result is False


# ---------------------------------------------------------------------------
# focus_pane unit tests
# ---------------------------------------------------------------------------

class TestFocusPane:
    def test_focus_pane_selects_window_then_pane(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if "#{window_id}" in args:
                return _cp(stdout="@3\n")
            return _cp()

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        result = backend.focus_pane("%5")
        assert result is True
        # Should have: display-message (get window), select-window, select-pane
        assert len(calls) == 3
        assert calls[1][0] == "select-window"
        assert "@3" in calls[1]
        assert calls[2][0] == "select-pane"
        assert "%5" in calls[2]

    def test_focus_pane_empty_id_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        backend = terminal.TmuxBackend()
        assert backend.focus_pane("") is False

    def test_focus_pane_returns_false_on_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_tmux_run(
            self: terminal.TmuxBackend, args: list[str], *, check: bool = False,
            capture: bool = False, input_bytes: bytes | None = None,
            timeout: float | None = None,
        ) -> subprocess.CompletedProcess[str]:
            return _cp(returncode=1)

        backend = terminal.TmuxBackend()
        monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

        assert backend.focus_pane("%1") is False
