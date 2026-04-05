from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import tempfile

from agents.models import normalize_agent_name
from ccbd.api_models import TargetKind
from mailbox_targets import normalize_mailbox_owner_name
from project.discovery import WORKSPACE_BINDING_FILENAME
from project.ids import compute_project_id, project_slug


_TARGET_SEGMENT_PATTERN = re.compile(r'[^a-z0-9._-]+')
_UNIX_SOCKET_SAFE_BYTES = 100


def _target_segment(target_kind: TargetKind | str, target_name: str) -> str:
    kind = TargetKind(target_kind)
    raw_name = str(target_name or '').strip()
    if kind is TargetKind.AGENT:
        return normalize_agent_name(raw_name)
    normalized = _TARGET_SEGMENT_PATTERN.sub('-', raw_name.lower()).strip('-.')
    if not normalized:
        raise ValueError('target_name cannot be empty')
    return normalized


def _unix_socket_path_is_safe(path: Path) -> bool:
    return len(os.fsencode(str(path))) <= _UNIX_SOCKET_SAFE_BYTES


def _runtime_socket_root() -> Path:
    base = os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir()
    return Path(base).expanduser() / 'ccb-runtime'


@dataclass(frozen=True)
class PathLayout:
    project_root: Path

    def __post_init__(self) -> None:
        root = Path(self.project_root).expanduser()
        try:
            root = root.resolve()
        except Exception:
            root = root.absolute()
        object.__setattr__(self, 'project_root', root)

    @property
    def ccb_dir(self) -> Path:
        return self.project_root / '.ccb'

    @property
    def config_path(self) -> Path:
        return self.ccb_dir / 'ccb.config'

    @property
    def ccbd_dir(self) -> Path:
        return self.ccb_dir / 'ccbd'

    @property
    def ccbd_lease_path(self) -> Path:
        return self.ccbd_dir / 'lease.json'

    @property
    def ccbd_socket_path(self) -> Path:
        return self._project_socket_path('ccbd')

    @property
    def ccbd_submissions_path(self) -> Path:
        return self.ccbd_dir / 'submissions.jsonl'

    @property
    def ccbd_mailboxes_dir(self) -> Path:
        return self.ccbd_dir / 'mailboxes'

    @property
    def ccbd_messages_dir(self) -> Path:
        return self.ccbd_dir / 'messages'

    @property
    def ccbd_messages_path(self) -> Path:
        return self.ccbd_messages_dir / 'messages.jsonl'

    @property
    def ccbd_attempts_dir(self) -> Path:
        return self.ccbd_dir / 'attempts'

    @property
    def ccbd_attempts_path(self) -> Path:
        return self.ccbd_attempts_dir / 'attempts.jsonl'

    @property
    def ccbd_replies_dir(self) -> Path:
        return self.ccbd_dir / 'replies'

    @property
    def ccbd_replies_path(self) -> Path:
        return self.ccbd_replies_dir / 'replies.jsonl'

    @property
    def ccbd_leases_dir(self) -> Path:
        return self.ccbd_dir / 'leases'

    @property
    def ccbd_dead_letters_dir(self) -> Path:
        return self.ccbd_dir / 'dead-letters'

    @property
    def ccbd_dead_letters_path(self) -> Path:
        return self.ccbd_dead_letters_dir / 'dead_letters.jsonl'

    @property
    def ccbd_provider_health_dir(self) -> Path:
        return self.ccbd_dir / 'provider-health'

    @property
    def ccbd_state_path(self) -> Path:
        return self.ccbd_dir / 'state.json'

    @property
    def ccbd_start_policy_path(self) -> Path:
        return self.ccbd_dir / 'start-policy.json'

    @property
    def ccbd_restore_report_path(self) -> Path:
        return self.ccbd_dir / 'restore-report.json'

    @property
    def ccbd_startup_report_path(self) -> Path:
        return self.ccbd_dir / 'startup-report.json'

    @property
    def ccbd_shutdown_report_path(self) -> Path:
        return self.ccbd_dir / 'shutdown-report.json'

    @property
    def ccbd_tmux_socket_path(self) -> Path:
        return self._project_socket_path('tmux')

    @property
    def ccbd_tmux_session_name(self) -> str:
        return f'ccb-{self.project_slug}'

    @property
    def ccbd_supervision_path(self) -> Path:
        return self.ccbd_dir / 'supervision.jsonl'

    @property
    def ccbd_lifecycle_log_path(self) -> Path:
        return self.ccbd_dir / 'lifecycle.jsonl'

    @property
    def ccbd_keeper_path(self) -> Path:
        return self.ccbd_dir / 'keeper.json'

    @property
    def ccbd_shutdown_intent_path(self) -> Path:
        return self.ccbd_dir / 'shutdown-intent.json'

    @property
    def ccbd_tmux_cleanup_history_path(self) -> Path:
        return self.ccbd_dir / 'tmux-cleanup-history.jsonl'

    @property
    def ccbd_fault_injection_path(self) -> Path:
        return self.ccbd_dir / 'fault-injection.json'

    @property
    def ccbd_support_dir(self) -> Path:
        return self.ccbd_dir / 'support'

    @property
    def ccbd_executions_dir(self) -> Path:
        return self.ccbd_dir / 'executions'

    @property
    def ccbd_snapshots_dir(self) -> Path:
        return self.ccbd_dir / 'snapshots'

    @property
    def ccbd_cursors_dir(self) -> Path:
        return self.ccbd_dir / 'cursors'

    @property
    def ccbd_heartbeats_dir(self) -> Path:
        return self.ccbd_dir / 'heartbeats'

    @property
    def agents_dir(self) -> Path:
        return self.ccb_dir / 'agents'

    @property
    def workspaces_dir(self) -> Path:
        return self.ccb_dir / 'workspaces'

    @property
    def project_slug(self) -> str:
        return project_slug(self.project_root)

    @property
    def project_socket_key(self) -> str:
        return compute_project_id(self.project_root)[:12]

    def agent_dir(self, agent_name: str) -> Path:
        return self.agents_dir / normalize_agent_name(agent_name)

    def agent_spec_path(self, agent_name: str) -> Path:
        return self.agent_dir(agent_name) / 'agent.json'

    def agent_mailbox_dir(self, agent_name: str) -> Path:
        return self.ccbd_mailboxes_dir / normalize_mailbox_owner_name(agent_name)

    def agent_mailbox_path(self, agent_name: str) -> Path:
        return self.agent_mailbox_dir(agent_name) / 'mailbox.json'

    def agent_inbox_path(self, agent_name: str) -> Path:
        return self.agent_mailbox_dir(agent_name) / 'inbox.jsonl'

    def agent_outbox_path(self, agent_name: str) -> Path:
        return self.agent_mailbox_dir(agent_name) / 'outbox.jsonl'

    def agent_runtime_path(self, agent_name: str) -> Path:
        return self.agent_dir(agent_name) / 'runtime.json'

    def agent_provider_path(self, agent_name: str) -> Path:
        return self.agent_dir(agent_name) / 'provider.json'

    def agent_restore_path(self, agent_name: str) -> Path:
        return self.agent_dir(agent_name) / 'restore.json'

    def agent_jobs_path(self, agent_name: str) -> Path:
        return self.agent_dir(agent_name) / 'jobs.jsonl'

    def job_store_path(self, agent_name: str) -> Path:
        return self.agent_jobs_path(agent_name)

    def agent_events_path(self, agent_name: str) -> Path:
        return self.agent_dir(agent_name) / 'events.jsonl'

    def agent_provider_runtime_dir(self, agent_name: str, provider: str) -> Path:
        normalized_provider = str(provider or '').strip().lower()
        if not normalized_provider:
            raise ValueError('provider cannot be empty')
        return self.agent_dir(agent_name) / 'provider-runtime' / normalized_provider

    def target_dir(self, target_kind: TargetKind | str, target_name: str) -> Path:
        segment = _target_segment(target_kind, target_name)
        if TargetKind(target_kind) is TargetKind.AGENT:
            return self.agent_dir(segment)
        return self.ccbd_dir / 'targets' / segment

    def target_jobs_path(self, target_kind: TargetKind | str, target_name: str) -> Path:
        return self.target_dir(target_kind, target_name) / 'jobs.jsonl'

    def target_events_path(self, target_kind: TargetKind | str, target_name: str) -> Path:
        return self.target_dir(target_kind, target_name) / 'events.jsonl'

    def agent_logs_dir(self, agent_name: str) -> Path:
        return self.agent_dir(agent_name) / 'logs'

    def workspace_path(self, agent_name: str, workspace_root: str | None = None) -> Path:
        normalized = normalize_agent_name(agent_name)
        if workspace_root:
            base = Path(workspace_root).expanduser()
            return base / self.project_slug / normalized
        return self.workspaces_dir / normalized

    def workspace_binding_path(self, agent_name: str, workspace_root: str | None = None) -> Path:
        return self.workspace_path(agent_name, workspace_root=workspace_root) / WORKSPACE_BINDING_FILENAME

    def snapshot_path(self, job_id: str) -> Path:
        return self.ccbd_snapshots_dir / f'{job_id}.json'

    def _project_socket_path(self, stem: str) -> Path:
        preferred = self.ccbd_dir / f'{stem}.sock'
        if _unix_socket_path_is_safe(preferred):
            return preferred
        return _runtime_socket_root() / f'{stem}-{self.project_socket_key}.sock'

    def cursor_path(self, job_id: str) -> Path:
        return self.ccbd_cursors_dir / f'{job_id}.json'

    def execution_state_path(self, job_id: str) -> Path:
        return self.ccbd_executions_dir / f'{job_id}.json'

    def heartbeat_subject_dir(self, subject_kind: str) -> Path:
        normalized = _TARGET_SEGMENT_PATTERN.sub('-', str(subject_kind or '').strip().lower()).strip('-.')
        if not normalized:
            raise ValueError('subject_kind cannot be empty')
        return self.ccbd_heartbeats_dir / normalized

    def heartbeat_subject_path(self, subject_kind: str, subject_id: str) -> Path:
        normalized = _TARGET_SEGMENT_PATTERN.sub('-', str(subject_id or '').strip().lower()).strip('-.')
        if not normalized:
            raise ValueError('subject_id cannot be empty')
        return self.heartbeat_subject_dir(subject_kind) / f'{normalized}.json'

    def mailbox_lease_path(self, agent_name: str) -> Path:
        return self.ccbd_leases_dir / f'{normalize_mailbox_owner_name(agent_name)}.json'

    def provider_health_path(self, job_id: str) -> Path:
        if not str(job_id or '').strip():
            raise ValueError('job_id cannot be empty')
        return self.ccbd_provider_health_dir / f'{job_id}.jsonl'

    def support_bundle_path(self, bundle_id: str) -> Path:
        normalized = _TARGET_SEGMENT_PATTERN.sub('-', str(bundle_id or '').strip().lower()).strip('-.')
        if not normalized:
            raise ValueError('bundle_id cannot be empty')
        return self.ccbd_support_dir / f'{normalized}.tar.gz'
