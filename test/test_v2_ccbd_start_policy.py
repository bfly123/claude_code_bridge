from __future__ import annotations

from pathlib import Path

from ccbd.services.start_policy import CcbdStartPolicy, CcbdStartPolicyStore, recovery_start_options
from storage.paths import PathLayout


def test_start_policy_store_roundtrip(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    policy = CcbdStartPolicy(
        project_id='project-1',
        auto_permission=True,
        recovery_restore=True,
        last_started_at='2026-04-03T00:00:00Z',
        source='start_command',
    )

    CcbdStartPolicyStore(layout).save(policy)
    loaded = CcbdStartPolicyStore(layout).load()

    assert loaded == policy


def test_recovery_start_options_default_to_cold_start_without_policy() -> None:
    assert recovery_start_options(None) == (False, False)


def test_recovery_start_options_force_restore_and_inherit_auto_permission() -> None:
    policy = CcbdStartPolicy(
        project_id='project-1',
        auto_permission=True,
        recovery_restore=True,
        last_started_at='2026-04-03T00:00:00Z',
        source='start_command',
    )

    assert recovery_start_options(policy) == (True, True)
