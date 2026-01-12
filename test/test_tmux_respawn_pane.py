from __future__ import annotations

import subprocess

import pytest

import terminal


def test_respawn_pane_builds_command_and_sets_remain(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = terminal.TmuxBackend()
    calls: list[list[str]] = []

    def fake_tmux_run(self, args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(["tmux", *args], 0, stdout="", stderr="")

    monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

    backend.respawn_pane(
        "%9",
        cmd="echo hi",
        cwd="/tmp",
        stderr_log_path="/tmp/ccb/stderr.log",
        remain_on_exit=True,
    )

    assert calls
    # Check respawn-pane command
    respawn_cmd = [c for c in calls if c[0] == "respawn-pane"]
    assert len(respawn_cmd) >= 1
    assert "-k" in respawn_cmd[0]
    assert "-t" in respawn_cmd[0]
    assert "%9" in respawn_cmd[0]


def test_respawn_pane_without_remain_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = terminal.TmuxBackend()
    calls: list[list[str]] = []

    def fake_tmux_run(self, args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(["tmux", *args], 0, stdout="", stderr="")

    monkeypatch.setattr(backend, "_tmux_run", fake_tmux_run.__get__(backend, terminal.TmuxBackend))

    backend.respawn_pane("%9", cmd="echo hi", remain_on_exit=False)

    assert calls
    respawn_cmd = [c for c in calls if c[0] == "respawn-pane"]
    assert len(respawn_cmd) >= 1
