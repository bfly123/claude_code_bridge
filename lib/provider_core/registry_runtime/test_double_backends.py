from __future__ import annotations

from agents.models import RuntimeMode
from completion.models import CompletionFamily, CompletionSourceKind, SelectorFamily
from completion.profiles import CompletionManifest
from provider_execution.fake import FakeProviderAdapter

from provider_core.contracts import ProviderBackend
from provider_core.manifests import ProviderManifest

TEST_DOUBLE_PROVIDER_NAMES = ("fake", "fake-codex", "fake-claude", "fake-gemini", "fake-legacy")


def build_test_double_backends() -> list[ProviderBackend]:
    return [
        ProviderBackend(
            manifest=ProviderManifest(
                provider="fake",
                supports_resume=True,
                supports_permission_auto=True,
                supports_stream_watch=True,
                supports_subagents=False,
                supports_workspace_attach=True,
                runtime_profiles={
                    RuntimeMode.PANE_BACKED: CompletionManifest(
                        provider="fake",
                        runtime_mode=RuntimeMode.PANE_BACKED.value,
                        completion_family=CompletionFamily.STRUCTURED_RESULT,
                        completion_source_kind=CompletionSourceKind.STRUCTURED_RESULT_STREAM,
                        supports_exact_completion=True,
                        supports_observed_completion=False,
                        supports_anchor_binding=True,
                        supports_reply_stability=False,
                        supports_terminal_reason=True,
                        selector_family=SelectorFamily.STRUCTURED_RESULT,
                    ),
                    RuntimeMode.HEADLESS: CompletionManifest(
                        provider="fake",
                        runtime_mode=RuntimeMode.HEADLESS.value,
                        completion_family=CompletionFamily.STRUCTURED_RESULT,
                        completion_source_kind=CompletionSourceKind.STRUCTURED_RESULT_STREAM,
                        supports_exact_completion=True,
                        supports_observed_completion=False,
                        supports_anchor_binding=True,
                        supports_reply_stability=False,
                        supports_terminal_reason=True,
                        selector_family=SelectorFamily.STRUCTURED_RESULT,
                    ),
                },
            ),
            execution_adapter=FakeProviderAdapter(),
        ),
        ProviderBackend(
            manifest=ProviderManifest(
                provider="fake-codex",
                supports_resume=True,
                supports_permission_auto=True,
                supports_stream_watch=True,
                supports_subagents=False,
                supports_workspace_attach=True,
                runtime_profiles={
                    RuntimeMode.PANE_BACKED: CompletionManifest(
                        provider="fake-codex",
                        runtime_mode=RuntimeMode.PANE_BACKED.value,
                        completion_family=CompletionFamily.PROTOCOL_TURN,
                        completion_source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
                        supports_exact_completion=True,
                        supports_observed_completion=False,
                        supports_anchor_binding=True,
                        supports_reply_stability=False,
                        supports_terminal_reason=True,
                        selector_family=SelectorFamily.FINAL_MESSAGE,
                    ),
                },
            ),
            execution_adapter=FakeProviderAdapter(
                provider="fake-codex",
                source_kind=CompletionSourceKind.PROTOCOL_EVENT_STREAM,
                script_mode="protocol_turn",
            ),
        ),
        ProviderBackend(
            manifest=ProviderManifest(
                provider="fake-claude",
                supports_resume=True,
                supports_permission_auto=True,
                supports_stream_watch=True,
                supports_subagents=False,
                supports_workspace_attach=True,
                runtime_profiles={
                    RuntimeMode.PANE_BACKED: CompletionManifest(
                        provider="fake-claude",
                        runtime_mode=RuntimeMode.PANE_BACKED.value,
                        completion_family=CompletionFamily.SESSION_BOUNDARY,
                        completion_source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
                        supports_exact_completion=False,
                        supports_observed_completion=True,
                        supports_anchor_binding=True,
                        supports_reply_stability=False,
                        supports_terminal_reason=True,
                        selector_family=SelectorFamily.FINAL_MESSAGE,
                    ),
                },
            ),
            execution_adapter=FakeProviderAdapter(
                provider="fake-claude",
                source_kind=CompletionSourceKind.SESSION_EVENT_LOG,
                script_mode="session_boundary",
            ),
        ),
        ProviderBackend(
            manifest=ProviderManifest(
                provider="fake-gemini",
                supports_resume=True,
                supports_permission_auto=True,
                supports_stream_watch=True,
                supports_subagents=False,
                supports_workspace_attach=True,
                runtime_profiles={
                    RuntimeMode.PANE_BACKED: CompletionManifest(
                        provider="fake-gemini",
                        runtime_mode=RuntimeMode.PANE_BACKED.value,
                        completion_family=CompletionFamily.ANCHORED_SESSION_STABILITY,
                        completion_source_kind=CompletionSourceKind.SESSION_SNAPSHOT,
                        supports_exact_completion=False,
                        supports_observed_completion=True,
                        supports_anchor_binding=True,
                        supports_reply_stability=True,
                        supports_terminal_reason=True,
                        selector_family=SelectorFamily.SESSION_REPLY,
                    ),
                },
            ),
            execution_adapter=FakeProviderAdapter(
                provider="fake-gemini",
                source_kind=CompletionSourceKind.SESSION_SNAPSHOT,
                script_mode="anchored_session_stability",
            ),
        ),
        ProviderBackend(
            manifest=ProviderManifest(
                provider="fake-legacy",
                supports_resume=True,
                supports_permission_auto=True,
                supports_stream_watch=True,
                supports_subagents=False,
                supports_workspace_attach=True,
                runtime_profiles={
                    RuntimeMode.PANE_BACKED: CompletionManifest(
                        provider="fake-legacy",
                        runtime_mode=RuntimeMode.PANE_BACKED.value,
                        completion_family=CompletionFamily.LEGACY_TEXT_QUIET,
                        completion_source_kind=CompletionSourceKind.TERMINAL_TEXT,
                        supports_exact_completion=False,
                        supports_observed_completion=False,
                        supports_anchor_binding=False,
                        supports_reply_stability=False,
                        supports_terminal_reason=False,
                        selector_family=SelectorFamily.FINAL_MESSAGE,
                    ),
                },
            ),
            execution_adapter=FakeProviderAdapter(
                provider="fake-legacy",
                source_kind=CompletionSourceKind.TERMINAL_TEXT,
                script_mode="legacy_text",
            ),
        ),
    ]


__all__ = ["TEST_DOUBLE_PROVIDER_NAMES", "build_test_double_backends"]
