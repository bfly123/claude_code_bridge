from __future__ import annotations

import subprocess
from typing import Any

import pytest

import terminal


def _cp(*, stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["tmux"], returncode=returncode, stdout=stdout, stderr="")


def test_tmux_split_pane_builds_command_and_parses_pane_id(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_tmux_run(self: terminal.TmuxBackend, args: list[str], *, check: bool = False, capture: bool = False,
                      input_bytes: bytes | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(
            {"args": args, "check": check, "capture": capture, "input_bytes": input_bytes, "timeout": timeout}
        )
        if args == ["display-message", "-p", "-t", "%1", "#{pane_dead}"]:
            return _cp(stdout="0\n")
        if args == ["display-message", "-p", "-t", "%1", "#{pane_width}x#{pane_height}"]:
            return _cp(stdout="80x24\n")
        return _cp(stdout="%42\n")

    backend = terminal.TmuxBackend()
    monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

    pane_id = backend.split_pane("%1", "right", 50)
    assert pane_id == "%42"
    assert calls
    call = calls[-1]
    assert call["check"] is True
    assert call["capture"] is True
    argv = call["args"]
    assert argv[:2] == ["split-window", "-h"]
    assert not any(a.startswith("-p") for a in argv)
    assert "-t" in argv and "%1" in argv
    assert "-P" in argv
    assert "-F" in argv and "#{pane_id}" in argv


def test_tmux_find_pane_by_title_marker_parses_list_panes(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_tmux_run(self: terminal.TmuxBackend, args: list[str], *, check: bool = False, capture: bool = False,
                      input_bytes: bytes | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        assert args == ["list-panes", "-a", "-F", "#{pane_id}\t#{pane_title}"]
        assert capture is True
        return _cp(stdout="%1\tCCB-opencode-abc\n%2\tOTHER\n")

    backend = terminal.TmuxBackend()
    monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

    assert backend.find_pane_by_title_marker("CCB-opencode") == "%1"
    assert backend.find_pane_by_title_marker("NOPE") is None


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("0\n", True),
        ("1\n", False),
        ("", False),
    ],
)
def test_tmux_is_pane_alive_uses_pane_dead(monkeypatch: pytest.MonkeyPatch, stdout: str, expected: bool) -> None:
    def fake_tmux_run(self: terminal.TmuxBackend, args: list[str], *, check: bool = False, capture: bool = False,
                      input_bytes: bytes | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        assert args == ["display-message", "-p", "-t", "%9", "#{pane_dead}"]
        assert capture is True
        return _cp(stdout=stdout)

    backend = terminal.TmuxBackend()
    monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))
    assert backend.is_pane_alive("%9") is expected


def test_tmux_send_text_always_deletes_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_tmux_run(self: terminal.TmuxBackend, args: list[str], *, check: bool = False, capture: bool = False,
                      input_bytes: bytes | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args and args[0] == "paste-buffer":
            raise subprocess.CalledProcessError(1, ["tmux", *args])
        return _cp(stdout="")

    backend = terminal.TmuxBackend()
    monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

    with pytest.raises(subprocess.CalledProcessError):
        backend.send_text("%1", "hello")

    assert any(cmd[:2] == ["load-buffer", "-b"] for cmd in calls)
    assert any(cmd and cmd[0] == "paste-buffer" and "-p" in cmd for cmd in calls)
    assert any(cmd[:2] == ["delete-buffer", "-b"] for cmd in calls)


def test_create_auto_layout_topologies(monkeypatch: pytest.MonkeyPatch) -> None:
    split_calls: list[tuple[str, str]] = []
    title_calls: list[tuple[str, str]] = []
    seq = iter(["%r1", "%r2", "%r3", "%r4", "%r5", "%r6"])

    def fake_get_current(self: terminal.TmuxBackend) -> str:
        return "%root"

    def fake_split(self: terminal.TmuxBackend, parent: str, direction: str, percent: int) -> str:
        split_calls.append((parent, direction))
        return next(seq)

    def fake_title(self: terminal.TmuxBackend, pane_id: str, title: str) -> None:
        title_calls.append((pane_id, title))

    monkeypatch.setattr(terminal.TmuxBackend, "get_current_pane_id", fake_get_current)
    monkeypatch.setattr(terminal.TmuxBackend, "split_pane", fake_split)
    monkeypatch.setattr(terminal.TmuxBackend, "set_pane_title", fake_title)

    split_calls.clear()
    title_calls.clear()
    r2 = terminal.create_auto_layout(["codex", "gemini"], cwd="/tmp", marker_prefix="M")
    assert r2.panes == {"codex": "%root", "gemini": "%r1"}
    assert split_calls == [("%root", "right")]
    assert ("M-codex" in [t for _, t in title_calls]) and ("M-gemini" in [t for _, t in title_calls])

    split_calls.clear()
    title_calls.clear()
    r3 = terminal.create_auto_layout(["codex", "gemini", "opencode"], cwd="/tmp", marker_prefix="M")
    assert r3.panes == {"codex": "%root", "gemini": "%r2", "opencode": "%r3"}
    assert split_calls == [("%root", "right"), ("%r2", "bottom")]

    split_calls.clear()
    title_calls.clear()
    r4 = terminal.create_auto_layout(["codex", "gemini", "opencode", "x"], cwd="/tmp", marker_prefix="M")
    assert r4.panes == {"codex": "%root", "gemini": "%r4", "opencode": "%r5", "x": "%r6"}
    assert split_calls == [("%root", "right"), ("%root", "bottom"), ("%r4", "bottom")]


def test_tmux_kill_pane_prefers_pane_id_over_session(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_tmux_run(self: terminal.TmuxBackend, args: list[str], *, check: bool = False, capture: bool = False,
                      input_bytes: bytes | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return _cp(stdout="")

    backend = terminal.TmuxBackend()
    monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

    calls.clear()
    backend.kill_pane("%1")
    assert calls == [["kill-pane", "-t", "%1"]]

    calls.clear()
    backend.kill_pane("mysession")
    assert calls == [["kill-session", "-t", "mysession"]]
