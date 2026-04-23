from __future__ import annotations

from dataclasses import replace

from agents.models import RuntimeBindingSource

from ..common import ACTIVE_RUNTIME_STATES, fallback_workspace_path


def restore_attachment_kwargs(*, layout, spec, runtime) -> dict[str, object]:
    return {
        "agent_name": spec.name,
        "workspace_path": fallback_workspace_path(layout=layout, spec=spec, runtime=runtime),
        "backend_type": runtime.backend_type if runtime is not None else spec.runtime_mode.value,
        "pid": runtime.pid if runtime is not None else None,
        "runtime_ref": runtime.runtime_ref if runtime is not None else None,
        "session_ref": runtime.session_ref if runtime is not None else None,
        "provider": runtime.provider if runtime is not None else None,
        "runtime_root": runtime.runtime_root if runtime is not None else None,
        "runtime_pid": runtime.runtime_pid if runtime is not None else None,
        "job_id": getattr(runtime, 'job_id', None) if runtime is not None else None,
        "job_owner_pid": getattr(runtime, 'job_owner_pid', None) if runtime is not None else None,
        "terminal_backend": runtime.terminal_backend if runtime is not None else None,
        "pane_id": runtime.pane_id if runtime is not None else None,
        "active_pane_id": runtime.active_pane_id if runtime is not None else None,
        "pane_title_marker": runtime.pane_title_marker if runtime is not None else None,
        "pane_state": runtime.pane_state if runtime is not None else None,
        "tmux_socket_name": runtime.tmux_socket_name if runtime is not None else None,
        "tmux_socket_path": runtime.tmux_socket_path if runtime is not None else None,
        "session_file": runtime.session_file if runtime is not None else None,
        "session_id": runtime.session_id if runtime is not None else None,
        "slot_key": runtime.slot_key if runtime is not None else spec.name,
        "window_id": runtime.window_id if runtime is not None else None,
        "workspace_epoch": runtime.workspace_epoch if runtime is not None else None,
        "lifecycle_state": runtime.lifecycle_state if runtime is not None else None,
        "managed_by": runtime.managed_by if runtime is not None else None,
        "binding_source": (
            runtime.binding_source if runtime is not None else RuntimeBindingSource.PROVIDER_SESSION
        ),
    }


def touch_active_runtime(*, registry, runtime, timestamp: str, health: str | None = None):
    updated_runtime = replace(
        runtime,
        last_seen_at=timestamp,
        health=health if health is not None else runtime.health,
    )
    return registry.upsert(updated_runtime)


def runtime_is_active(runtime) -> bool:
    return runtime is not None and runtime.state in ACTIVE_RUNTIME_STATES


__all__ = ["restore_attachment_kwargs", "runtime_is_active", "touch_active_runtime"]
