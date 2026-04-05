from __future__ import annotations

from pathlib import Path

from launcher.current_pane import LauncherCurrentPaneBinder


class _FakeBackend:
    pass


def test_bind_labels_tmux_pane_and_calls_session_writer(tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def _label(backend, pane_id, *, title, agent_label):
        calls['label'] = {'pane_id': pane_id, 'title': title, 'agent_label': agent_label}

    binder = LauncherCurrentPaneBinder(
        terminal_type='tmux',
        current_pane_id_fn=lambda: '%7',
        backend_factory=_FakeBackend,
        label_tmux_pane_fn=_label,
    )

    pane_id = binder.bind(
        runtime=tmp_path / 'runtime',
        pane_title_marker='CCB-Gemini',
        agent_label='Gemini',
        bind_session_fn=lambda bound_pane_id: calls.__setitem__('bound', bound_pane_id) or True,
    )

    assert pane_id == '%7'
    assert calls['bound'] == '%7'
    assert calls['label'] == {'pane_id': '%7', 'title': 'CCB-Gemini', 'agent_label': 'Gemini'}


def test_bind_returns_none_when_current_pane_is_missing(tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    binder = LauncherCurrentPaneBinder(
        terminal_type='tmux',
        current_pane_id_fn=lambda: '',
        backend_factory=_FakeBackend,
    )

    pane_id = binder.bind(
        runtime=tmp_path / 'runtime',
        pane_title_marker='CCB-Droid',
        agent_label='Droid',
        bind_session_fn=lambda bound_pane_id: calls.__setitem__('bound', bound_pane_id) or True,
    )

    assert pane_id is None
    assert 'bound' not in calls
