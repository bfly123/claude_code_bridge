from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccbd.models_runtime.common import API_VERSION, SCHEMA_VERSION, CcbdModelError

from .cleanup import CcbdTmuxCleanupSummary
from .common import clean_text, clean_tuple, coerce_int


@dataclass(frozen=True)
class CcbdStartupAgentResult:
    agent_name: str
    provider: str | None
    action: str
    health: str
    workspace_path: str | None
    runtime_ref: str | None = None
    session_ref: str | None = None
    lifecycle_state: str | None = None
    desired_state: str | None = None
    reconcile_state: str | None = None
    binding_source: str | None = None
    terminal_backend: str | None = None
    tmux_socket_name: str | None = None
    tmux_socket_path: str | None = None
    pane_id: str | None = None
    active_pane_id: str | None = None
    pane_state: str | None = None
    runtime_pid: int | None = None
    runtime_root: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.agent_name == '':
            raise CcbdModelError('agent_name cannot be empty')
        if self.action == '':
            raise CcbdModelError('action cannot be empty')
        if self.health == '':
            raise CcbdModelError('health cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'agent_name': self.agent_name,
            'provider': self.provider,
            'action': self.action,
            'health': self.health,
            'workspace_path': self.workspace_path,
            'runtime_ref': self.runtime_ref,
            'session_ref': self.session_ref,
            'lifecycle_state': self.lifecycle_state,
            'desired_state': self.desired_state,
            'reconcile_state': self.reconcile_state,
            'binding_source': self.binding_source,
            'terminal_backend': self.terminal_backend,
            'tmux_socket_name': self.tmux_socket_name,
            'tmux_socket_path': self.tmux_socket_path,
            'pane_id': self.pane_id,
            'active_pane_id': self.active_pane_id,
            'pane_state': self.pane_state,
            'runtime_pid': self.runtime_pid,
            'runtime_root': self.runtime_root,
            'failure_reason': self.failure_reason,
        }

    def summary_token(self) -> str:
        return f'{self.agent_name}:{self.action}/{self.health}'

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'CcbdStartupAgentResult':
        return cls(
            agent_name=clean_text(record.get('agent_name')) or '',
            provider=clean_text(record.get('provider')),
            action=clean_text(record.get('action')) or 'unknown',
            health=clean_text(record.get('health')) or 'unknown',
            workspace_path=clean_text(record.get('workspace_path')),
            runtime_ref=clean_text(record.get('runtime_ref')),
            session_ref=clean_text(record.get('session_ref')),
            lifecycle_state=clean_text(record.get('lifecycle_state')),
            desired_state=clean_text(record.get('desired_state')),
            reconcile_state=clean_text(record.get('reconcile_state')),
            binding_source=clean_text(record.get('binding_source')),
            terminal_backend=clean_text(record.get('terminal_backend')),
            tmux_socket_name=clean_text(record.get('tmux_socket_name')),
            tmux_socket_path=clean_text(record.get('tmux_socket_path')),
            pane_id=clean_text(record.get('pane_id')),
            active_pane_id=clean_text(record.get('active_pane_id')),
            pane_state=clean_text(record.get('pane_state')),
            runtime_pid=coerce_int(record.get('runtime_pid')),
            runtime_root=clean_text(record.get('runtime_root')),
            failure_reason=clean_text(record.get('failure_reason')),
        )


@dataclass(frozen=True)
class CcbdStartupReport:
    project_id: str
    generated_at: str
    trigger: str
    status: str
    requested_agents: tuple[str, ...]
    desired_agents: tuple[str, ...]
    restore_requested: bool
    auto_permission: bool
    daemon_generation: int | None = None
    daemon_started: bool | None = None
    config_signature: str | None = None
    inspection: dict[str, Any] | None = None
    restore_summary: dict[str, Any] | None = None
    actions_taken: tuple[str, ...] = ()
    cleanup_summaries: tuple[CcbdTmuxCleanupSummary, ...] = ()
    agent_results: tuple[CcbdStartupAgentResult, ...] = ()
    failure_reason: str | None = None
    api_version: int = API_VERSION

    def __post_init__(self) -> None:
        if self.api_version != API_VERSION:
            raise CcbdModelError(f'api_version must be {API_VERSION}')
        for field_name in ('project_id', 'generated_at', 'trigger', 'status'):
            if not str(getattr(self, field_name) or '').strip():
                raise CcbdModelError(f'{field_name} cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'ccbd_startup_report',
            'api_version': self.api_version,
            'project_id': self.project_id,
            'generated_at': self.generated_at,
            'trigger': self.trigger,
            'status': self.status,
            'requested_agents': list(self.requested_agents),
            'desired_agents': list(self.desired_agents),
            'restore_requested': self.restore_requested,
            'auto_permission': self.auto_permission,
            'daemon_generation': self.daemon_generation,
            'daemon_started': self.daemon_started,
            'config_signature': self.config_signature,
            'inspection': dict(self.inspection or {}),
            'restore_summary': dict(self.restore_summary or {}),
            'actions_taken': list(self.actions_taken),
            'cleanup_summaries': [item.to_record() for item in self.cleanup_summaries],
            'agent_results': [item.to_record() for item in self.agent_results],
            'failure_reason': self.failure_reason,
        }

    def summary_fields(self) -> dict[str, Any]:
        total_killed = sum(len(item.killed_panes) for item in self.cleanup_summaries)
        return {
            'startup_last_at': self.generated_at,
            'startup_last_trigger': self.trigger,
            'startup_last_status': self.status,
            'startup_last_generation': self.daemon_generation,
            'startup_last_daemon_started': self.daemon_started,
            'startup_last_requested_agents': list(self.requested_agents),
            'startup_last_desired_agents': list(self.desired_agents),
            'startup_last_actions': list(self.actions_taken),
            'startup_last_cleanup_killed': total_killed,
            'startup_last_failure_reason': self.failure_reason,
            'startup_last_agent_results_text': 'none' if not self.agent_results else '; '.join(item.summary_token() for item in self.agent_results),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'CcbdStartupReport':
        _validate_record(record, expected_type='ccbd_startup_report')
        return cls(
            project_id=str(record['project_id']),
            generated_at=str(record['generated_at']),
            trigger=str(record['trigger']),
            status=str(record['status']),
            requested_agents=clean_tuple(record.get('requested_agents')),
            desired_agents=clean_tuple(record.get('desired_agents')),
            restore_requested=bool(record.get('restore_requested')),
            auto_permission=bool(record.get('auto_permission')),
            daemon_generation=coerce_int(record.get('daemon_generation')),
            daemon_started=(bool(record['daemon_started']) if record.get('daemon_started') is not None else None),
            config_signature=clean_text(record.get('config_signature')),
            inspection=dict(record.get('inspection') or {}),
            restore_summary=dict(record.get('restore_summary') or {}),
            actions_taken=clean_tuple(record.get('actions_taken')),
            cleanup_summaries=tuple(
                CcbdTmuxCleanupSummary.from_record(item)
                for item in (record.get('cleanup_summaries') or [])
                if isinstance(item, dict)
            ),
            agent_results=tuple(
                CcbdStartupAgentResult.from_record(item)
                for item in (record.get('agent_results') or [])
                if isinstance(item, dict)
            ),
            failure_reason=clean_text(record.get('failure_reason')),
            api_version=int(record.get('api_version', API_VERSION)),
        )


def _validate_record(record: dict[str, Any], *, expected_type: str) -> None:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != expected_type:
        raise ValueError(f"record_type must be '{expected_type}'")


__all__ = ['CcbdStartupAgentResult', 'CcbdStartupReport']
