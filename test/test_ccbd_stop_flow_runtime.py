from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ccbd.stop_flow_runtime.pid_cleanup import collect_pid_candidates
from ccbd.stop_flow_runtime.pid_cleanup import collect_project_process_candidates
from ccbd.stop_flow_runtime.pid_cleanup import terminate_runtime_pids
from ccbd.stop_flow_runtime.runtime_records import extra_agent_dir_names


def test_extra_agent_dir_names_skips_configured_names(tmp_path: Path) -> None:
    agents_dir = tmp_path / '.ccb' / 'agents'
    (agents_dir / 'agent1').mkdir(parents=True)
    (agents_dir / 'cmd').mkdir(parents=True)
    (agents_dir / 'agent5').mkdir(parents=True)
    (agents_dir / 'not-a-dir.txt').write_text('x', encoding='utf-8')

    paths = SimpleNamespace(agents_dir=agents_dir)

    assert extra_agent_dir_names(paths, ('agent1', 'cmd')) == ('agent5',)


def test_collect_pid_candidates_uses_runtime_root_and_force_fallback(tmp_path: Path) -> None:
    agent_dir = tmp_path / '.ccb' / 'agents' / 'agent1'
    provider_runtime_dir = agent_dir / 'provider-runtime' / 'codex'
    provider_runtime_dir.mkdir(parents=True)
    (provider_runtime_dir / 'fallback.pid').write_text('456\n', encoding='utf-8')

    dedicated_runtime_root = tmp_path / 'runtime-root'
    dedicated_runtime_root.mkdir()
    (dedicated_runtime_root / 'codex.pid').write_text('789\n', encoding='utf-8')

    runtime = SimpleNamespace(runtime_pid=123, pid=None, runtime_root=str(dedicated_runtime_root))
    candidates = collect_pid_candidates(agent_dir, runtime=runtime, fallback_to_agent_dir=True)

    assert candidates[123] == [agent_dir / 'runtime.json']
    assert candidates[456] == [provider_runtime_dir / 'fallback.pid']
    assert candidates[789] == [dedicated_runtime_root / 'codex.pid']


def test_collect_project_process_candidates_matches_ccb_runtime_cmdline(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    ccb_root = project_root / '.ccb'
    proc_root = tmp_path / 'proc'
    for pid in ('101', '202', '303'):
        (proc_root / pid).mkdir(parents=True)

    mapping = {
        101: f'python -m provider_backends.codex.bridge --runtime-dir {ccb_root / "agents/agent1/provider-runtime/codex"}',
        202: f'tmux -S {ccb_root / "ccbd/tmux.sock"} new-session -d',
        303: 'python unrelated.py',
    }

    candidates = collect_project_process_candidates(
        project_root,
        proc_root=proc_root,
        read_proc_cmdline_fn=lambda pid: mapping.get(pid, ''),
        current_pid=999999,
    )

    assert sorted(candidates) == [101, 202]
    assert candidates[101] == [ccb_root]
    assert candidates[202] == [ccb_root]


def test_terminate_runtime_pids_includes_project_process_scan(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        'ccbd.stop_flow_runtime.pid_cleanup._terminate_runtime_pids_impl',
        lambda **kwargs: seen.update(kwargs),
    )
    monkeypatch.setattr(
        'ccbd.stop_flow_runtime.pid_cleanup.collect_project_process_candidates',
        lambda project_root: {321: [project_root / '.ccb']},
    )

    terminate_runtime_pids(project_root=project_root, pid_candidates={123: [project_root / 'hint.pid']})

    collect_fn = seen['collect_project_process_candidates_fn']
    assert collect_fn(project_root) == {321: [project_root / '.ccb']}
    assert seen['pid_candidates'] == {123: [project_root / 'hint.pid']}


__all__ = []
