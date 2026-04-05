from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from cli.phase2 import maybe_handle_phase2
from cli.services.ask import AskSummary


def test_phase2_ask_wait_submit_writes_output(monkeypatch, tmp_path: Path) -> None:
    import cli.phase2 as phase2_module

    fake_context = SimpleNamespace(project=SimpleNamespace(project_root=tmp_path, project_id='proj-1'))

    monkeypatch.setattr(phase2_module, '_build_context', lambda command, cwd, out: fake_context)
    monkeypatch.setattr(phase2_module, 'ensure_bootstrap_project_config', lambda project_root: None)
    monkeypatch.setattr(
        phase2_module,
        'submit_ask',
        lambda context, command: AskSummary(
            project_id='proj-1',
            submission_id=None,
            jobs=({'job_id': 'job_1', 'target_name': 'agent1', 'status': 'accepted'},),
        ),
    )
    monkeypatch.setattr(
        phase2_module,
        'watch_ask_job',
        lambda context, job_id, out, timeout, emit_output: SimpleNamespace(status='completed', reply='done'),
    )

    output_path = tmp_path / 'reply.txt'
    stdout = StringIO()
    stderr = StringIO()
    code = maybe_handle_phase2(
        ['ask', '--wait', '--output', str(output_path), 'agent1', 'hello'],
        cwd=tmp_path,
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 0
    assert stdout.getvalue() == ''
    assert stderr.getvalue() == ''
    assert output_path.read_text(encoding='utf-8') == 'done\n'
