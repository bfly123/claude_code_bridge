from __future__ import annotations

from agents.models import AgentSpec, PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from completion.detectors.protocol_turn import ProtocolTurnDetector
from completion.detectors.session_boundary import SessionBoundaryDetector
from completion.models import CompletionFamily, CompletionSourceKind, SelectorFamily
from completion.profiles import CompletionManifest
from completion.registry import CompletionRegistry
from completion.selectors.final_message import FinalMessageSelector


def _spec(*, provider: str = 'codex', runtime_mode: RuntimeMode = RuntimeMode.PANE_BACKED) -> AgentSpec:
    return AgentSpec(
        name='agent1',
        provider=provider,
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=runtime_mode,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
    )


def test_registry_builds_protocol_turn_detector_and_selector() -> None:
    registry = CompletionRegistry()
    manifest = CompletionManifest(
        provider='codex',
        runtime_mode='pane-backed',
        completion_family=CompletionFamily.PROTOCOL_TURN,
        completion_source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
        supports_exact_completion=True,
        supports_observed_completion=False,
        supports_anchor_binding=True,
        supports_reply_stability=False,
        supports_terminal_reason=True,
        selector_family=SelectorFamily.FINAL_MESSAGE,
    )
    profile = registry.build_profile(_spec(), None, manifest)

    assert isinstance(registry.build_detector(profile), ProtocolTurnDetector)
    assert isinstance(registry.build_selector(profile), FinalMessageSelector)


def test_registry_builds_session_boundary_detector_for_opencode() -> None:
    registry = CompletionRegistry()
    manifest = CompletionManifest(
        provider='opencode',
        runtime_mode='pane-backed',
        completion_family=CompletionFamily.SESSION_BOUNDARY,
        completion_source_kind=CompletionSourceKind.SESSION_SNAPSHOT,
        supports_exact_completion=False,
        supports_observed_completion=True,
        supports_anchor_binding=True,
        supports_reply_stability=False,
        supports_terminal_reason=True,
        selector_family=SelectorFamily.FINAL_MESSAGE,
    )
    profile = registry.build_profile(_spec(provider='opencode'), None, manifest)

    assert isinstance(registry.build_detector(profile), SessionBoundaryDetector)
