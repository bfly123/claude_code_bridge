from __future__ import annotations

from agents.models import RuntimeMode
from completion.models import CompletionFamily, CompletionSourceKind, SelectorFamily
from completion.profiles import CompletionManifest
from provider_core.manifests import ProviderManifest


def build_manifest() -> ProviderManifest:
    return ProviderManifest(
        provider='claude',
        supports_resume=True,
        supports_permission_auto=True,
        supports_stream_watch=True,
        supports_subagents=True,
        supports_workspace_attach=True,
        runtime_profiles={
            RuntimeMode.PANE_BACKED: CompletionManifest(
                provider='claude',
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
            RuntimeMode.HEADLESS: CompletionManifest(
                provider='claude',
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
    )


__all__ = ['build_manifest']
