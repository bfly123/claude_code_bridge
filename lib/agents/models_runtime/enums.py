from __future__ import annotations

from enum import Enum

from .names import AgentValidationError


class WorkspaceMode(str, Enum):
    GIT_WORKTREE = 'git-worktree'
    COPY = 'copy'
    INPLACE = 'inplace'


class RuntimeMode(str, Enum):
    PANE_BACKED = 'pane-backed'
    PTY_BACKED = 'pty-backed'
    HEADLESS = 'headless'


class RuntimeBindingSource(str, Enum):
    PROVIDER_SESSION = 'provider-session'
    EXTERNAL_ATTACH = 'external-attach'


class RestoreMode(str, Enum):
    FRESH = 'fresh'
    PROVIDER = 'provider'
    AUTO = 'auto'


class PermissionMode(str, Enum):
    MANUAL = 'manual'
    AUTO = 'auto'
    READONLY = 'readonly'


class QueuePolicy(str, Enum):
    SERIAL_PER_AGENT = 'serial-per-agent'
    REJECT_WHEN_BUSY = 'reject-when-busy'


class AgentState(str, Enum):
    STARTING = 'starting'
    IDLE = 'idle'
    BUSY = 'busy'
    STOPPING = 'stopping'
    STOPPED = 'stopped'
    DEGRADED = 'degraded'
    FAILED = 'failed'


class RestoreStatus(str, Enum):
    FRESH = 'fresh'
    PROVIDER = 'provider'
    CHECKPOINT = 'checkpoint'
    FAILED = 'failed'


def normalize_runtime_mode(value: str | RuntimeMode) -> RuntimeMode:
    if isinstance(value, RuntimeMode):
        return value
    if not isinstance(value, str):
        raise AgentValidationError('runtime_mode must be a string')
    raw = value.strip().lower()
    aliases = {
        'pane': RuntimeMode.PANE_BACKED,
        'pane-backed': RuntimeMode.PANE_BACKED,
        'pty': RuntimeMode.PTY_BACKED,
        'pty-backed': RuntimeMode.PTY_BACKED,
        'headless': RuntimeMode.HEADLESS,
    }
    try:
        return aliases[raw]
    except KeyError as exc:
        raise AgentValidationError(
            'runtime_mode must be one of: pane-backed, pty-backed, headless'
        ) from exc


def normalize_runtime_binding_source(value: str | RuntimeBindingSource) -> RuntimeBindingSource:
    if isinstance(value, RuntimeBindingSource):
        return value
    if not isinstance(value, str):
        raise AgentValidationError('runtime binding source must be a string')
    raw = value.strip().lower()
    aliases = {
        'provider': RuntimeBindingSource.PROVIDER_SESSION,
        'provider-session': RuntimeBindingSource.PROVIDER_SESSION,
        'external': RuntimeBindingSource.EXTERNAL_ATTACH,
        'external-attach': RuntimeBindingSource.EXTERNAL_ATTACH,
    }
    try:
        return aliases[raw]
    except KeyError as exc:
        raise AgentValidationError(
            'runtime binding source must be one of: provider-session, external-attach'
        ) from exc


__all__ = [
    'AgentState',
    'PermissionMode',
    'QueuePolicy',
    'RestoreMode',
    'RestoreStatus',
    'RuntimeBindingSource',
    'RuntimeMode',
    'WorkspaceMode',
    'normalize_runtime_binding_source',
    'normalize_runtime_mode',
]
