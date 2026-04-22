from __future__ import annotations

from pathlib import Path

from runtime_pid_cleanup.matching import pid_matches_project


def test_pid_matches_project_windows_requires_project_evidence(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    hint = project_root / '.ccb' / 'agent.pid'

    assert pid_matches_project(
        123,
        project_root=project_root,
        hint_paths=(hint,),
        read_proc_path_fn=lambda pid, entry: None,
        read_proc_cmdline_fn=lambda pid: '',
        path_within_fn=lambda path, root: False,
        os_name='nt',
    ) is False


def test_pid_matches_project_windows_accepts_cmdline_with_project_hint(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    hint = project_root / '.ccb' / 'agent.pid'
    cmdline = f'python worker.py --runtime {project_root / ".ccb" / "agents"}'

    assert pid_matches_project(
        123,
        project_root=project_root,
        hint_paths=(hint,),
        read_proc_path_fn=lambda pid, entry: None,
        read_proc_cmdline_fn=lambda pid: cmdline,
        path_within_fn=lambda path, root: False,
        os_name='nt',
    ) is True


def test_pid_matches_project_windows_accepts_executable_under_project(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    hint = project_root / '.ccb' / 'agent.pid'
    exe_path = project_root / '.ccb' / 'bin' / 'worker.exe'

    assert pid_matches_project(
        123,
        project_root=project_root,
        hint_paths=(hint,),
        read_proc_path_fn=lambda pid, entry: exe_path if entry == 'exe' else None,
        read_proc_cmdline_fn=lambda pid: '',
        path_within_fn=lambda path, root: str(path).startswith(str(root)),
        os_name='nt',
    ) is True
