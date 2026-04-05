from __future__ import annotations

from dataclasses import dataclass

from agents.models import RuntimeMode
from completion.profiles import CompletionManifest


@dataclass(frozen=True)
class ProviderManifest:
    provider: str
    supports_resume: bool
    supports_permission_auto: bool
    supports_stream_watch: bool
    supports_subagents: bool
    supports_workspace_attach: bool
    runtime_profiles: dict[RuntimeMode, CompletionManifest]

    def __post_init__(self) -> None:
        provider = (self.provider or '').strip().lower()
        if not provider:
            raise ValueError('provider cannot be empty')
        object.__setattr__(self, 'provider', provider)
        if not self.runtime_profiles:
            raise ValueError('runtime_profiles cannot be empty')
        normalized: dict[RuntimeMode, CompletionManifest] = {}
        for runtime_mode, profile in dict(self.runtime_profiles).items():
            if profile.provider != provider:
                raise ValueError(
                    f'runtime profile provider {profile.provider!r} does not match manifest provider {provider!r}'
                )
            if profile.runtime_mode != runtime_mode.value:
                raise ValueError(
                    f'runtime profile mode {profile.runtime_mode!r} does not match runtime key {runtime_mode.value!r}'
                )
            normalized[runtime_mode] = profile
        object.__setattr__(self, 'runtime_profiles', normalized)

    def supports_runtime_mode(self, runtime_mode: RuntimeMode) -> bool:
        return runtime_mode in self.runtime_profiles

    def completion_manifest_for(self, runtime_mode: RuntimeMode) -> CompletionManifest:
        return self.runtime_profiles[runtime_mode]


__all__ = ['ProviderManifest']
