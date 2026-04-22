from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cli import kill


def test_cmd_kill_force_mode_uses_global_zombie_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[bool, object]] = []

    def fake_kill_global_zombies(*, yes: bool, is_pid_alive):
        calls.append((yes, is_pid_alive))
        return 7

    monkeypatch.setattr(kill, "kill_global_zombies", fake_kill_global_zombies)

    result = kill.cmd_kill(
        SimpleNamespace(force=True, yes=True, providers=[]),
        parse_providers=lambda values: values,
        cwd=Path("/tmp"),
        session_finder=lambda cwd, name: None,
        tmux_backend_factory=lambda: None,
        safe_write_session=lambda path, text: (True, None),
        state_file_path_fn=lambda name: Path(f"/tmp/{name}"),
        shutdown_daemon_fn=lambda prefix, timeout, path: True,
        read_state_fn=lambda path: None,
        specs_by_provider={},
        is_pid_alive=lambda pid: False,
    )

    assert result == 7
    assert calls and calls[0][0] is True


def test_cmd_kill_terminates_session_and_force_kills_daemon(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session_path = tmp_path / ".codex-session"
    session_path.write_text(
        json.dumps(
            {
                "terminal": "tmux",
                "pane_id": "%42",
                "active": True,
            }
        ),
        encoding="utf-8",
    )

    killed_panes: list[str] = []
    killed_pids: list[tuple[int, bool]] = []

    class FakeTmuxBackend:
        def kill_pane(self, pane_id: str) -> None:
            killed_panes.append(pane_id)

    monkeypatch.setattr("cli.kill_runtime.sessions.shutil.which", lambda name: "/usr/bin/tmux" if name == "tmux" else None)
    monkeypatch.setattr(kill, "kill_pid", lambda pid, force=False: killed_pids.append((pid, force)) or True)

    result = kill.cmd_kill(
        SimpleNamespace(force=False, yes=False, providers=["codex"]),
        parse_providers=lambda values: ["codex"],
        cwd=tmp_path,
        session_finder=lambda cwd, name: session_path,
        tmux_backend_factory=FakeTmuxBackend,
        safe_write_session=lambda path, text: (path.write_text(text, encoding="utf-8") or True, None),
        state_file_path_fn=lambda name: tmp_path / name,
        shutdown_daemon_fn=lambda prefix, timeout, path: False,
        read_state_fn=lambda path: {"pid": 9911},
        specs_by_provider={"codex": SimpleNamespace()},
        is_pid_alive=lambda pid: False,
    )

    assert result == 0
    assert killed_panes == ["%42"]
    assert killed_pids == [(9911, True)]

    updated = json.loads(session_path.read_text(encoding="utf-8"))
    assert updated["active"] is False
    assert updated["ended_at"]

    out = capsys.readouterr().out
    assert "Codex session terminated" in out
    assert "ccbd runtime force killed" in out


def test_kill_global_zombies_reports_empty(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(kill, "find_all_zombie_sessions", lambda *, is_pid_alive: [])
    assert kill.kill_global_zombies(yes=False, is_pid_alive=lambda pid: False) == 0
    assert "No zombie sessions found" in capsys.readouterr().out
