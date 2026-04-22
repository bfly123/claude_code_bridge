from __future__ import annotations

from pathlib import Path

from runtime_pid_cleanup.process_tree_owner import LocalProcessTreeOwner, ProcessTreeTarget
from runtime_pid_cleanup.termination import terminate_runtime_pids
from runtime_pid_cleanup.windows_process_tree_owner import (
    WindowsJobMetadataProcessTreeOwnerFactory,
    WindowsJobObjectProcessTreeOwner,
)


def test_terminate_runtime_pids_uses_process_tree_owner(tmp_path: Path) -> None:
    removed: list[tuple[Path, ...]] = []
    terminated: list[int] = []

    class FakeOwner:
        def terminate(self, pid: int, *, timeout_s: float, is_pid_alive_fn) -> bool:
            terminated.append(pid)
            return True

    pid_file = tmp_path / 'repo' / '.ccb' / 'agent.pid'
    terminate_runtime_pids(
        project_root=tmp_path / 'repo',
        pid_candidates={123: [pid_file]},
        is_pid_alive_fn=lambda pid: True,
        pid_matches_project_fn=lambda pid, project_root, hint_paths: True,
        process_tree_owner=FakeOwner(),
        remove_pid_files_fn=lambda paths: removed.append(tuple(paths)),
    )

    assert terminated == [123]
    assert removed == [(pid_file,)]


def test_local_process_tree_owner_delegates_terminate_call() -> None:
    calls: list[tuple[int, float]] = []
    owner = LocalProcessTreeOwner(
        lambda pid, *, timeout_s, is_pid_alive_fn: calls.append((pid, timeout_s)) or True
    )

    assert owner.terminate(456, timeout_s=1.5, is_pid_alive_fn=lambda pid: True) is True
    assert calls == [(456, 1.5)]


def test_terminate_runtime_pids_prioritizes_priority_pids(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    owner_pid_file = project_root / '.ccb' / 'owner.pid'
    child_pid_file = project_root / '.ccb' / 'child.pid'
    live_pids = {111, 999}
    terminated: list[int] = []
    removed: list[tuple[Path, ...]] = []

    def _terminate(pid: int, *, timeout_s: float, is_pid_alive_fn) -> bool:
        terminated.append(pid)
        if pid == 999:
            live_pids.clear()
        else:
            live_pids.discard(pid)
        return True

    terminate_runtime_pids(
        project_root=project_root,
        pid_candidates={111: [child_pid_file], 999: [owner_pid_file]},
        priority_pids=(999,),
        is_pid_alive_fn=lambda pid: pid in live_pids,
        pid_matches_project_fn=lambda pid, project_root, hint_paths: True,
        terminate_pid_tree_fn=_terminate,
        remove_pid_files_fn=lambda paths: removed.append(tuple(paths)),
    )

    assert terminated == [999]
    assert removed == [(owner_pid_file,), (child_pid_file,)]


def test_terminate_runtime_pids_uses_pid_specific_process_tree_owner_factory(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    pid_file = project_root / '.ccb' / 'owner.pid'
    removed: list[tuple[Path, ...]] = []
    built_targets: list[ProcessTreeTarget] = []
    terminated: list[int] = []

    class FakeOwner:
        def terminate(self, pid: int, *, timeout_s: float, is_pid_alive_fn) -> bool:
            terminated.append(pid)
            return True

    class FakeFactory:
        def build(self, target: ProcessTreeTarget):
            built_targets.append(target)
            if target.metadata and target.metadata.get('job_id') == 'job-object-9':
                return FakeOwner()
            return None

    terminate_runtime_pids(
        project_root=project_root,
        pid_candidates={777: [pid_file]},
        pid_metadata={777: {'job_id': 'job-object-9', 'job_owner_pid': 777}},
        is_pid_alive_fn=lambda pid: True,
        pid_matches_project_fn=lambda pid, project_root, hint_paths: True,
        terminate_pid_tree_fn=lambda pid, *, timeout_s, is_pid_alive_fn: False,
        process_tree_owner_factory=FakeFactory(),
        remove_pid_files_fn=lambda paths: removed.append(tuple(paths)),
    )

    assert terminated == [777]
    assert built_targets == [ProcessTreeTarget(pid=777, hint_paths=(pid_file,), metadata={'job_id': 'job-object-9', 'job_owner_pid': 777})]
    assert removed == [(pid_file,)]


def test_windows_job_object_process_tree_owner_terminates_named_job_before_fallback() -> None:
    terminated_jobs: list[str] = []
    fallback_calls: list[int] = []
    owner = WindowsJobObjectProcessTreeOwner(
        'job-object-5',
        LocalProcessTreeOwner(
            lambda pid, *, timeout_s, is_pid_alive_fn: fallback_calls.append(pid) or True
        ),
        terminate_named_job_fn=lambda job_id: terminated_jobs.append(job_id) or True,
    )

    assert owner.terminate(555, timeout_s=1.0, is_pid_alive_fn=lambda pid: True) is True
    assert terminated_jobs == ['job-object-5']
    assert fallback_calls == []


def test_windows_job_object_process_tree_owner_falls_back_when_named_job_terminate_fails() -> None:
    fallback_calls: list[int] = []
    owner = WindowsJobObjectProcessTreeOwner(
        'job-object-5',
        LocalProcessTreeOwner(
            lambda pid, *, timeout_s, is_pid_alive_fn: fallback_calls.append(pid) or True
        ),
        terminate_named_job_fn=lambda job_id: False,
    )

    assert owner.terminate(555, timeout_s=1.0, is_pid_alive_fn=lambda pid: True) is True
    assert fallback_calls == [555]


def test_windows_job_metadata_process_tree_owner_factory_selects_owner_pid_on_windows() -> None:
    terminated_jobs: list[str] = []
    owner = LocalProcessTreeOwner(lambda pid, *, timeout_s, is_pid_alive_fn: True)
    factory = WindowsJobMetadataProcessTreeOwnerFactory(
        owner,
        is_windows_fn=lambda: True,
        terminate_named_job_fn=lambda job_id: terminated_jobs.append(job_id) or True,
    )

    selected = factory.build(
        ProcessTreeTarget(
            pid=555,
            metadata={'job_id': 'job-object-5', 'job_owner_pid': 555},
        )
    )

    assert selected is not None
    assert selected.terminate(555, timeout_s=1.0, is_pid_alive_fn=lambda pid: True) is True
    assert terminated_jobs == ['job-object-5']


def test_windows_job_metadata_process_tree_owner_factory_ignores_non_owner_targets() -> None:
    owner = LocalProcessTreeOwner(lambda pid, *, timeout_s, is_pid_alive_fn: True)
    factory = WindowsJobMetadataProcessTreeOwnerFactory(owner, is_windows_fn=lambda: True)

    selected = factory.build(
        ProcessTreeTarget(
            pid=444,
            metadata={'job_id': 'job-object-5', 'job_owner_pid': 555},
        )
    )

    assert selected is None


def test_windows_job_metadata_process_tree_owner_factory_ignores_invalid_owner_pid() -> None:
    owner = LocalProcessTreeOwner(lambda pid, *, timeout_s, is_pid_alive_fn: True)
    factory = WindowsJobMetadataProcessTreeOwnerFactory(owner, is_windows_fn=lambda: True)

    selected = factory.build(
        ProcessTreeTarget(
            pid=444,
            metadata={'job_id': 'job-object-5', 'job_owner_pid': 'not-a-pid'},
        )
    )

    assert selected is None


def test_terminate_runtime_pids_skips_job_children_after_owner_termination(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    owner_pid_file = project_root / '.ccb' / 'owner.pid'
    child_pid_file = project_root / '.ccb' / 'child.pid'
    child_two_pid_file = project_root / '.ccb' / 'child-two.pid'
    terminated: list[int] = []
    removed: list[tuple[Path, ...]] = []

    terminate_runtime_pids(
        project_root=project_root,
        pid_candidates={
            111: [owner_pid_file],
            222: [child_pid_file],
            333: [child_two_pid_file],
        },
        priority_pids=(111,),
        pid_metadata={
            111: {'job_id': 'job-object-1', 'job_owner_pid': 111},
            222: {'job_id': 'job-object-1', 'job_owner_pid': 111},
            333: {'job_id': 'job-object-1', 'job_owner_pid': 111},
        },
        is_pid_alive_fn=lambda pid: True,
        pid_matches_project_fn=lambda pid, project_root, hint_paths: True,
        terminate_pid_tree_fn=lambda pid, *, timeout_s, is_pid_alive_fn: terminated.append(pid) or True,
        remove_pid_files_fn=lambda paths: removed.append(tuple(paths)),
    )

    assert terminated == [111]
    assert removed == [
        (owner_pid_file,),
        (child_pid_file,),
        (child_two_pid_file,),
    ]
