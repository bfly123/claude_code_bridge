from __future__ import annotations

import subprocess
from types import SimpleNamespace

from provider_backends.codex.session_runtime.live_identity import live_runtime_identity


def _cp(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=['tmux'], returncode=0, stdout=stdout, stderr='')


def test_codex_live_identity_matches_bound_resume_session(monkeypatch) -> None:
    class Backend:
        def _tmux_run(self, args, *, capture=False, timeout=None):
            assert args == ['display-message', '-p', '-t', '%4', '#{pane_pid}']
            assert capture is True
            assert timeout == 1.0
            return _cp('100\n')

    session = SimpleNamespace(
        codex_session_id='sid-1',
        pane_id='%4',
        backend=lambda: Backend(),
    )
    monkeypatch.setattr(
        'provider_backends.codex.session_runtime.live_identity._process_tree_cmdlines',
        lambda pid: (
            '/bin/zsh -l',
            'node /usr/bin/codex -c disable_paste_burst=true resume sid-1',
        ),
    )

    identity = live_runtime_identity(session)

    assert identity is not None
    assert identity.state == 'match'
    assert identity.reason is None


def test_codex_live_identity_rejects_live_process_without_bound_resume(monkeypatch) -> None:
    class Backend:
        def _tmux_run(self, args, *, capture=False, timeout=None):
            return _cp('100\n')

    session = SimpleNamespace(
        codex_session_id='sid-1',
        pane_id='%4',
        backend=lambda: Backend(),
    )
    monkeypatch.setattr(
        'provider_backends.codex.session_runtime.live_identity._process_tree_cmdlines',
        lambda pid: (
            '/bin/zsh -l',
            'node /usr/bin/codex -c disable_paste_burst=true',
        ),
    )

    identity = live_runtime_identity(session)

    assert identity is not None
    assert identity.state == 'mismatch'
    assert identity.reason == 'live_codex_process_not_running_bound_resume_session'


def test_codex_live_identity_reports_unknown_when_pane_pid_unavailable() -> None:
    class Backend:
        def _tmux_run(self, args, *, capture=False, timeout=None):
            return _cp('')

    session = SimpleNamespace(
        codex_session_id='sid-1',
        pane_id='%4',
        backend=lambda: Backend(),
    )

    identity = live_runtime_identity(session)

    assert identity is not None
    assert identity.state == 'unknown'
    assert identity.reason == 'pane_pid_unavailable'


def test_codex_live_identity_is_unset_for_unbound_session() -> None:
    session = SimpleNamespace(
        codex_session_id='',
        pane_id='%4',
        backend=lambda: None,
    )

    assert live_runtime_identity(session) is None
