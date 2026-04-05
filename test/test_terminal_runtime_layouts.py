from __future__ import annotations

import subprocess

from terminal_runtime.layouts import create_tmux_auto_layout


def _cp(*, stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["tmux"], returncode=returncode, stdout=stdout, stderr="")


class FakeLayoutBackend:
    def __init__(self, *, current_pane: str | None = "%root", alive_sessions: set[str] | None = None) -> None:
        self.current_pane = current_pane
        self.alive_sessions = alive_sessions or set()
        self.split_calls: list[tuple[str, str, int]] = []
        self.title_calls: list[tuple[str, str]] = []
        self.tmux_calls: list[tuple[list[str], bool, bool]] = []
        self._seq = iter(["%1", "%2", "%3", "%4", "%5"])

    def get_current_pane_id(self) -> str:
        if self.current_pane is None:
            raise RuntimeError("no current pane")
        return self.current_pane

    def is_alive(self, pane_id: str) -> bool:
        return pane_id in self.alive_sessions

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: str | None = None) -> str:
        del cmd, cwd, direction, percent, parent_pane
        return "%created"

    def split_pane(self, parent_pane_id: str, direction: str, percent: int) -> str:
        self.split_calls.append((parent_pane_id, direction, percent))
        return next(self._seq)

    def set_pane_title(self, pane_id: str, title: str) -> None:
        self.title_calls.append((pane_id, title))

    def _tmux_run(self, args: list[str], *, check: bool = False, capture: bool = False, input_bytes: bytes | None = None, timeout: float | None = None):
        del input_bytes, timeout
        self.tmux_calls.append((args, check, capture))
        if args[:2] == ["list-panes", "-t"]:
            return _cp(stdout="%root-detached\n")
        return _cp(stdout="")


def test_create_tmux_auto_layout_uses_current_pane_when_available() -> None:
    backend = FakeLayoutBackend(current_pane="%root")
    result = create_tmux_auto_layout(["agent1", "agent2"], cwd="/tmp", backend=backend, marker_prefix="M")
    assert result.panes == {"agent1": "%root", "agent2": "%1"}
    assert result.created_panes == ["%1"]
    assert result.needs_attach is False
    assert backend.split_calls == [("%root", "right", 50)]
    assert backend.title_calls == [("%root", "M-agent1"), ("%1", "M-agent2")]


def test_create_tmux_auto_layout_allocates_detached_session_when_outside_tmux() -> None:
    backend = FakeLayoutBackend(current_pane=None)
    result = create_tmux_auto_layout(
        ["agent1"],
        cwd="/tmp/demo",
        backend=backend,
        detached_session_name="ccb-demo-1",
        inside_tmux=False,
    )
    assert result.panes == {"agent1": "%root-detached"}
    assert result.root_pane_id == "%root-detached"
    assert result.created_panes == ["%root-detached"]
    assert result.needs_attach is True
    assert backend.tmux_calls == [
        (["new-session", "-d", "-s", "ccb-demo-1", "-c", "/tmp/demo"], True, False),
        (["list-panes", "-t", "ccb-demo-1", "-F", "#{pane_id}"], True, True),
    ]


def test_create_tmux_auto_layout_reuses_existing_session() -> None:
    backend = FakeLayoutBackend(current_pane=None, alive_sessions={"ccb-demo-2"})
    result = create_tmux_auto_layout(
        ["agent1", "agent2", "agent3"],
        cwd="/tmp/demo",
        backend=backend,
        tmux_session_name="ccb-demo-2",
        inside_tmux=True,
    )
    assert result.root_pane_id == "%root-detached"
    assert result.needs_attach is False
    assert backend.tmux_calls == [
        (["list-panes", "-t", "ccb-demo-2", "-F", "#{pane_id}"], True, True),
    ]
    assert backend.split_calls == [
        ("%root-detached", "right", 50),
        ("%1", "bottom", 50),
    ]
