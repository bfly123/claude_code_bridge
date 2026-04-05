from __future__ import annotations

from pathlib import Path

from launcher.session_gateway import LauncherSessionGateway


class _FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def write_codex_session(self, *args, **kwargs):
        self.calls.append(('codex', args, kwargs))
        return True

    def write_simple_target_session(self, *args, **kwargs):
        self.calls.append(('simple', args, kwargs))
        return True

    def write_droid_session(self, *args, **kwargs):
        self.calls.append(('droid', args, kwargs))
        return True

    def write_cend_registry(self, **kwargs):
        self.calls.append(('cend', (), kwargs))
        return True


def test_session_gateway_routes_provider_session_writes(tmp_path: Path) -> None:
    store = _FakeStore()
    gateway = LauncherSessionGateway(
        target_session_store=store,
        target_names=('claude', 'codex', 'gemini', 'opencode', 'droid'),
        provider_pane_id_fn=lambda provider: {'claude': '%1', 'codex': '%2'}.get(provider, ''),
        resume=True,
    )

    assert gateway.write_codex_session(tmp_path, None, tmp_path / 'in', tmp_path / 'out', pane_id='%2') is True
    assert gateway.write_gemini_session(tmp_path, None, pane_id='%3', start_cmd='gemini') is True
    assert gateway.write_opencode_session(tmp_path, None, pane_id='%4', start_cmd='opencode') is True
    assert gateway.write_droid_session(tmp_path, None, pane_id='%5', start_cmd='droid') is True

    assert store.calls[0][0] == 'codex'
    assert store.calls[0][2]['resume'] is True
    assert store.calls[1][0] == 'simple'
    assert store.calls[1][1][0] == 'gemini'
    assert store.calls[2][1][0] == 'opencode'
    assert store.calls[3][0] == 'droid'


def test_session_gateway_syncs_cend_only_when_both_panes_exist() -> None:
    store = _FakeStore()
    gateway = LauncherSessionGateway(
        target_session_store=store,
        target_names=('claude', 'codex'),
        provider_pane_id_fn=lambda provider: {'claude': '%1', 'codex': '%2'}.get(provider, ''),
        resume=False,
    )

    gateway.sync_cend_registry()

    assert store.calls == [('cend', (), {'claude_pane_id': '%1', 'codex_pane_id': '%2'})]
