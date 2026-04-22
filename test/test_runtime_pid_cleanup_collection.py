from __future__ import annotations

from pathlib import Path

from runtime_pid_cleanup.collection import runtime_job_owner_pid


def test_runtime_job_owner_pid_prefers_canonical_owner_file(tmp_path: Path) -> None:
    agent_dir = tmp_path / 'agent1'
    runtime_dir = agent_dir / 'provider-runtime' / 'codex'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / 'bridge.pid').write_text('321\n', encoding='utf-8')
    (runtime_dir / 'job-owner.pid').write_text('654\n', encoding='utf-8')

    assert runtime_job_owner_pid(agent_dir, runtime=None, fallback_to_agent_dir=True) == 654
