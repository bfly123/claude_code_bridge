"""Tests for authoritative tmux pane ownership in ensure_pane().

The recorded pane_id is not sufficient. A live pane is reusable only when its
CCB ownership metadata matches the session's agent/project identity.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest

from provider_backends.claude.session import ClaudeProjectSession
from provider_backends.codebuddy.session import CodebuddyProjectSession
from provider_backends.codex.session import CodexProjectSession
from provider_backends.copilot.session import CopilotProjectSession
from provider_backends.droid.session import DroidProjectSession
from provider_backends.gemini.session import GeminiProjectSession
from provider_backends.opencode.session import OpenCodeProjectSession
from provider_backends.qwen.session import QwenProjectSession


class _FakeBackend:
    """Fake terminal backend for testing ensure_pane()."""

    def __init__(
        self,
        alive_panes: set[str],
        *,
        pane_details: Optional[dict[str, dict[str, str]]] = None,
        marker_map: Optional[dict[str, str]] = None,
    ):
        self.alive_panes = alive_panes
        self.pane_details = pane_details or {}
        self.marker_map = marker_map or {}
        self.attached: list[str] = []

    def is_alive(self, pane_id: str) -> bool:
        return pane_id in self.alive_panes

    def describe_pane(self, pane_id: str, *, user_options: tuple[str, ...] = ()) -> Optional[dict[str, str]]:
        detail = self.pane_details.get(pane_id)
        if detail is None:
            return None
        described = {
            'pane_id': pane_id,
            'pane_title': detail.get('pane_title', ''),
            'pane_dead': '0' if pane_id in self.alive_panes else '1',
        }
        for name in user_options:
            described[name] = detail.get(name, '')
        return described

    def find_pane_by_title_marker(self, marker: str) -> Optional[str]:
        return self.marker_map.get(marker)

    def ensure_pane_log(self, pane_id: str) -> None:
        self.attached.append(pane_id)


def _write_session(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_session(cls, tmp_path: Path, pane_id: str, marker: str, backend: _FakeBackend):
    """Create a session object with a fake backend."""
    session_file = tmp_path / ".session"
    data = {
        "pane_id": pane_id,
        "pane_title_marker": marker,
        "terminal": "tmux",
        "work_dir": str(tmp_path),
        "agent_name": "agent1",
        "ccb_project_id": "proj-1",
    }
    _write_session(session_file, data)
    session = cls.__new__(cls)
    session.data = data
    session.session_file = session_file
    session._backend = backend

    session.backend = lambda: backend
    session._attach_pane_log = lambda b, pid: None
    session._write_back = lambda: _write_session(session_file, session.data)
    return session


SESSION_CLASSES = [
    GeminiProjectSession,
    CodexProjectSession,
    OpenCodeProjectSession,
    DroidProjectSession,
    CodebuddyProjectSession,
    CopilotProjectSession,
    ClaudeProjectSession,
    QwenProjectSession,
]


@pytest.mark.parametrize("cls", SESSION_CLASSES, ids=lambda c: c.__name__)
def test_fast_path_returns_live_owned_pane_even_when_title_drifts(cls, tmp_path: Path) -> None:
    backend = _FakeBackend(
        alive_panes={"%10"},
        pane_details={
            "%10": {
                "pane_title": "OpenCode",
                "@ccb_agent": "agent1",
                "@ccb_project_id": "proj-1",
            }
        },
    )
    session = _make_session(cls, tmp_path, "%10", "CCB-agent1-proj", backend)

    ok, pane = session.ensure_pane()

    assert ok is True
    assert pane == "%10"
    assert session.data["pane_id"] == "%10"


@pytest.mark.parametrize("cls", SESSION_CLASSES, ids=lambda c: c.__name__)
def test_fast_path_rejects_live_foreign_pane_even_if_pane_id_is_alive(cls, tmp_path: Path) -> None:
    backend = _FakeBackend(
        alive_panes={"%10"},
        pane_details={
            "%10": {
                "pane_title": "OpenCode",
                "@ccb_agent": "demo",
                "@ccb_project_id": "foreign-project",
            }
        },
    )
    session = _make_session(cls, tmp_path, "%10", "CCB-agent1-proj", backend)

    ok, msg = session.ensure_pane()

    assert ok is False
    assert "ownership mismatch" in msg.lower()
    assert session.data["pane_id"] == "%10"


@pytest.mark.parametrize("cls", SESSION_CLASSES, ids=lambda c: c.__name__)
def test_dead_pane_does_not_resolve_by_marker(cls, tmp_path: Path) -> None:
    backend = _FakeBackend(
        alive_panes={"%20"},
        pane_details={
            "%10": {
                "pane_title": "CCB-agent1-proj",
                "@ccb_agent": "agent1",
                "@ccb_project_id": "proj-1",
            },
            "%20": {
                "pane_title": "CCB-agent1-proj",
                "@ccb_agent": "agent1",
                "@ccb_project_id": "proj-1",
            },
        },
        marker_map={"CCB-agent1-proj": "%20"},
    )
    session = _make_session(cls, tmp_path, "%10", "CCB-agent1-proj", backend)

    ok, msg = session.ensure_pane()

    assert ok is False
    assert "not alive" in msg.lower()
    assert session.data["pane_id"] == "%10"


@pytest.mark.parametrize("cls", SESSION_CLASSES, ids=lambda c: c.__name__)
def test_fast_path_keeps_pane_when_inspection_is_unavailable(cls, tmp_path: Path) -> None:
    class _LegacyBackend(_FakeBackend):
        def describe_pane(self, pane_id: str, *, user_options: tuple[str, ...] = ()) -> Optional[dict[str, str]]:
            raise RuntimeError("tmux error")

    backend = _LegacyBackend(alive_panes={"%10"})
    session = _make_session(cls, tmp_path, "%10", "CCB-agent1-proj", backend)

    ok, pane = session.ensure_pane()

    assert ok is True
    assert pane == "%10"
