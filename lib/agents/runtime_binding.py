from __future__ import annotations

from dataclasses import dataclass


def _normalize(value: str | None) -> str | None:
    text = str(value or '').strip()
    return text or None


@dataclass(frozen=True)
class RuntimeBinding:
    runtime_ref: str | None
    session_ref: str | None
    workspace_path: str | None

    @property
    def status(self) -> str:
        if self.runtime_ref and self.session_ref and self.workspace_path:
            return 'bound'
        if self.runtime_ref or self.session_ref or self.workspace_path:
            return 'partial'
        return 'unbound'

    @property
    def is_bound(self) -> bool:
        return self.status == 'bound'

    def to_fields(self) -> dict[str, str | None]:
        return {
            'runtime_ref': self.runtime_ref,
            'session_ref': self.session_ref,
            'workspace_path': self.workspace_path,
            'binding_status': self.status,
        }


def build_runtime_binding(
    *,
    runtime_ref: str | None = None,
    session_ref: str | None = None,
    workspace_path: str | None = None,
) -> RuntimeBinding:
    return RuntimeBinding(
        runtime_ref=_normalize(runtime_ref),
        session_ref=_normalize(session_ref),
        workspace_path=_normalize(workspace_path),
    )


def merge_runtime_binding(
    existing: RuntimeBinding | None,
    *,
    runtime_ref: str | None = None,
    session_ref: str | None = None,
    workspace_path: str | None = None,
) -> RuntimeBinding:
    current = existing or build_runtime_binding()
    return build_runtime_binding(
        runtime_ref=runtime_ref if runtime_ref is not None else current.runtime_ref,
        session_ref=session_ref if session_ref is not None else current.session_ref,
        workspace_path=workspace_path if workspace_path is not None else current.workspace_path,
    )


def runtime_binding_from_runtime(runtime) -> RuntimeBinding:
    if runtime is None:
        return build_runtime_binding()
    return build_runtime_binding(
        runtime_ref=getattr(runtime, 'runtime_ref', None),
        session_ref=getattr(runtime, 'session_ref', None),
        workspace_path=getattr(runtime, 'workspace_path', None),
    )
