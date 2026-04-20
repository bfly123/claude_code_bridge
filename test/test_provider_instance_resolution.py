from __future__ import annotations

from pathlib import Path

from provider_backends.claude.execution_runtime.start import load_session as load_claude_session
from provider_backends.codex.execution_runtime.start import load_session as load_codex_session
from provider_backends.gemini.execution_runtime.start import load_session as load_gemini_session
from provider_backends.droid.execution_runtime.helpers import load_session as load_droid_session
from provider_backends.opencode.execution_runtime.helpers import load_session as load_opencode_session


def test_named_agent_load_session_does_not_fallback_to_primary() -> None:
    calls: list[str | None] = []

    def _loader(work_dir: Path, instance: str | None = None):
        calls.append(instance)
        if instance is None:
            return {'session': 'primary'}
        return None

    work_dir = Path('/tmp/demo')

    assert load_claude_session(_loader, work_dir, agent_name='agent3') is None
    assert calls == ['agent3']

    calls.clear()
    assert load_codex_session(_loader, work_dir, agent_name='agent1') is None
    assert calls == ['agent1']

    calls.clear()
    assert load_gemini_session(_loader, work_dir, agent_name='reviewer') is None
    assert calls == ['reviewer']

    calls.clear()
    assert load_opencode_session(work_dir, agent_name='builder', primary_agent='opencode', load_project_session_fn=_loader) is None
    assert calls == ['builder']

    calls.clear()
    assert load_droid_session(work_dir, agent_name='worker', primary_agent='droid', load_project_session_fn=_loader) is None
    assert calls == ['worker']


def test_primary_agent_load_session_keeps_primary_fallback() -> None:
    calls: list[str | None] = []

    def _loader(work_dir: Path, instance: str | None = None):
        calls.append(instance)
        return {'session': 'primary'} if instance is None else None

    work_dir = Path('/tmp/demo')

    assert load_claude_session(_loader, work_dir, agent_name='claude') is None
    assert calls == ['claude']
