from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from provider_core.contracts import ProviderSessionBinding
from provider_core.instance_resolution import named_agent_instance
from provider_core.registry import build_default_session_binding_map
from provider_core.tmux_ownership import inspect_tmux_pane_ownership


@dataclass(frozen=True)
class AgentBinding:
    runtime_ref: str | None
    session_ref: str | None
    provider: str | None = None
    runtime_root: str | None = None
    runtime_pid: int | None = None
    session_file: str | None = None
    session_id: str | None = None
    tmux_socket_name: str | None = None
    tmux_socket_path: str | None = None
    terminal: str | None = None
    pane_id: str | None = None
    active_pane_id: str | None = None
    pane_title_marker: str | None = None
    pane_state: str | None = None


def binding_status(runtime_ref: str | None, session_ref: str | None, workspace_path: str | None) -> str:
    if runtime_ref and session_ref and workspace_path:
        return 'bound'
    if runtime_ref or session_ref or workspace_path:
        return 'partial'
    return 'unbound'


def default_binding_adapter(provider: str) -> ProviderSessionBinding | None:
    return build_default_session_binding_map(include_optional=True).get(str(provider or '').strip().lower())


def resolve_agent_binding(
    *,
    provider: str,
    agent_name: str,
    workspace_path: str | Path,
    project_root: str | Path | None = None,
    ensure_usable: bool = False,
    adapter_resolver=default_binding_adapter,
    sleep_fn=time.sleep,
) -> AgentBinding | None:
    normalized_provider = str(provider or '').strip().lower()
    adapter = adapter_resolver(normalized_provider)
    if adapter is None:
        return None

    search_roots = _binding_search_roots(
        workspace_path=Path(workspace_path).expanduser(),
        project_root=Path(project_root).expanduser() if project_root is not None else None,
    )
    session = _load_provider_session(
        adapter=adapter,
        provider=normalized_provider,
        agent_name=agent_name,
        roots=search_roots,
        ensure_usable=ensure_usable,
        sleep_fn=sleep_fn,
    )
    if session is None:
        return None

    pane_details = inspect_session_pane(session)
    if ensure_usable and pane_details['pane_state'] == 'unknown' and pane_details['active_pane_id']:
        pane_details['pane_state'] = 'alive'

    return AgentBinding(
        runtime_ref=session_runtime_ref(session),
        session_ref=session_ref(
            session,
            session_id_attr=adapter.session_id_attr,
            session_path_attr=adapter.session_path_attr,
        ),
        provider=normalized_provider,
        runtime_root=session_runtime_root(session),
        runtime_pid=session_runtime_pid(session, provider=normalized_provider),
        session_file=session_file(session),
        session_id=session_id(session, session_id_attr=adapter.session_id_attr),
        tmux_socket_name=session_tmux_socket_name(session),
        tmux_socket_path=session_tmux_socket_path(session),
        terminal=pane_details['terminal'],
        pane_id=pane_details['pane_id'],
        active_pane_id=pane_details['active_pane_id'],
        pane_title_marker=pane_details['pane_title_marker'],
        pane_state=pane_details['pane_state'],
    )


def session_runtime_ref(session, *, pane_id_override: str | None = None) -> str | None:
    pane_id = str(pane_id_override or getattr(session, 'pane_id', '') or '').strip()
    terminal = str(getattr(session, 'terminal', '') or '').strip() or 'tmux'
    if pane_id:
        return f'{terminal}:{pane_id}'
    return None


def session_ref(session, *, session_id_attr: str, session_path_attr: str) -> str | None:
    session_token = str(getattr(session, session_id_attr, '') or '').strip()
    if session_token:
        return session_token
    session_log = str(getattr(session, session_path_attr, '') or '').strip()
    if session_log:
        return str(Path(session_log).expanduser())
    bound_session_file = session_file(session)
    if bound_session_file:
        return bound_session_file
    return None


def session_tmux_socket_name(session) -> str | None:
    terminal = str(getattr(session, 'terminal', '') or '').strip().lower()
    if terminal != 'tmux':
        return None
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('tmux_socket_name') or '').strip()
        if text:
            return text
    backend = _session_backend(session)
    if backend is None:
        return None
    return str(getattr(backend, '_socket_name', '') or '').strip() or None


def session_tmux_socket_path(session) -> str | None:
    terminal = str(getattr(session, 'terminal', '') or '').strip().lower()
    if terminal != 'tmux':
        return None
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('tmux_socket_path') or '').strip()
        if text:
            return str(Path(text).expanduser())
    backend = _session_backend(session)
    if backend is None:
        return None
    text = str(getattr(backend, '_socket_path', '') or '').strip()
    return str(Path(text).expanduser()) if text else None


def session_id(session, *, session_id_attr: str) -> str | None:
    value = getattr(session, session_id_attr, None)
    text = str(value or '').strip()
    return text or None


def session_file(session) -> str | None:
    session_path = getattr(session, 'session_file', None)
    if session_path is None:
        return None
    return str(Path(session_path).expanduser())


def session_runtime_root(session) -> str | None:
    runtime_dir = getattr(session, 'runtime_dir', None)
    if runtime_dir is not None:
        return str(Path(runtime_dir).expanduser())
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('runtime_dir') or '').strip()
        if text:
            return str(Path(text).expanduser())
    return None


def session_runtime_pid(session, *, provider: str) -> int | None:
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        for key in ('runtime_pid', 'pid'):
            value = _coerce_pid(data.get(key))
            if value is not None:
                return value
    runtime_root = session_runtime_root(session)
    if not runtime_root:
        return None
    root = Path(runtime_root)
    preferred = root / f'{str(provider or "").strip().lower()}.pid'
    for candidate in (preferred, *sorted(root.glob('*.pid'))):
        value = _read_pid_file(candidate)
        if value is not None:
            return value
    return None


def session_terminal(session) -> str | None:
    text = str(getattr(session, 'terminal', '') or '').strip()
    return text or None


def session_pane_title_marker(session) -> str | None:
    text = str(getattr(session, 'pane_title_marker', '') or '').strip()
    if text:
        return text
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('pane_title_marker') or '').strip()
        if text:
            return text
    return None


def inspect_session_pane(session) -> dict[str, str | None]:
    terminal = str(getattr(session, 'terminal', '') or '').strip() or 'tmux'
    pane_id = str(getattr(session, 'pane_id', '') or '').strip() or None
    pane_title_marker = session_pane_title_marker(session)
    backend = _session_backend(session)
    if backend is None:
        return {
            'terminal': terminal,
            'pane_id': pane_id,
            'active_pane_id': pane_id,
            'pane_title_marker': pane_title_marker,
            'pane_state': 'unknown' if pane_id else ('missing' if pane_title_marker else None),
        }

    pane_state = _resolve_pane_state(
        session,
        backend,
        terminal=terminal,
        pane_id=pane_id,
        pane_title_marker=pane_title_marker,
    )
    active_pane_id = pane_id if pane_state == 'alive' else None
    return {
        'terminal': terminal,
        'pane_id': pane_id,
        'active_pane_id': active_pane_id,
        'pane_title_marker': pane_title_marker,
        'pane_state': pane_state,
    }


def _binding_search_roots(*, workspace_path: Path, project_root: Path | None) -> tuple[Path, ...]:
    roots: list[Path] = []
    for candidate in (project_root, workspace_path):
        if candidate is None:
            continue
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate.absolute()
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _load_provider_session(
    *,
    adapter: ProviderSessionBinding,
    provider: str,
    agent_name: str,
    roots: tuple[Path, ...],
    ensure_usable: bool,
    sleep_fn,
):
    instance = named_agent_instance(agent_name, primary_agent=provider)
    instances: tuple[str | None, ...] = (instance,) if instance is not None else (None,)

    for root in roots:
        seen_instances: set[str | None] = set()
        for instance_name in instances:
            if instance_name in seen_instances:
                continue
            seen_instances.add(instance_name)
            session = adapter.load_session(root, instance_name)
            if session is None:
                continue
            if not ensure_usable or _session_binding_is_usable(session, sleep_fn=sleep_fn):
                return session
    return None


def _session_binding_is_usable(session, *, sleep_fn) -> bool:
    if not _should_validate_session(session):
        return True
    ensure = getattr(session, 'ensure_pane', None)
    if not callable(ensure):
        return True
    try:
        ok, pane_or_err = ensure()
    except Exception:
        return False
    if not ok:
        return False
    if not _binding_is_stable(session, pane_or_err, sleep_fn=sleep_fn):
        return False
    return _binding_has_owned_tmux_pane(session, str(pane_or_err or '').strip() or None)


def _should_validate_session(session) -> bool:
    if str(getattr(session, 'pane_id', '') or '').strip():
        return True
    if str(getattr(session, 'pane_title_marker', '') or '').strip():
        return True
    data = getattr(session, 'data', None)
    if not isinstance(data, dict):
        return True
    if data.get('active') is True:
        return True
    for key in ('pane_id', 'tmux_session', 'pane_title_marker', 'runtime_dir', 'start_cmd', 'codex_start_cmd'):
        if str(data.get(key) or '').strip():
            return True
    return False


def _binding_is_stable(session, pane_or_err: object, *, delay_s: float = 0.1, sleep_fn) -> bool:
    backend = _session_backend(session)
    if backend is None:
        return True
    pane_id = str(pane_or_err or getattr(session, 'pane_id', '') or '').strip()
    if not pane_id:
        return False
    checker = getattr(backend, 'is_alive', None)
    if not callable(checker):
        checker = getattr(backend, 'is_tmux_pane_alive', None)
    if not callable(checker):
        return True
    try:
        if not checker(pane_id):
            return False
        sleep_fn(delay_s)
        return bool(checker(pane_id))
    except Exception:
        return False


def _binding_has_owned_tmux_pane(session, pane_id: str | None) -> bool:
    terminal = str(getattr(session, 'terminal', '') or '').strip().lower()
    if terminal != 'tmux':
        return True
    backend = _session_backend(session)
    if backend is None:
        return True
    ownership = inspect_tmux_pane_ownership(session, backend, str(pane_id or '').strip())
    return ownership.is_owned


def _session_backend(session):
    backend_factory = getattr(session, 'backend', None)
    if not callable(backend_factory):
        return None
    try:
        return backend_factory()
    except Exception:
        return None


def _resolve_pane_state(
    session,
    backend,
    *,
    terminal: str,
    pane_id: str | None,
    pane_title_marker: str | None,
) -> str | None:
    if not pane_id:
        return 'missing' if pane_title_marker else None
    if terminal == 'tmux' and pane_id:
        pane_exists = getattr(backend, 'pane_exists', None)
        if callable(pane_exists):
            try:
                if not pane_exists(pane_id):
                    return 'missing'
            except Exception:
                return 'unknown'
        ownership = inspect_tmux_pane_ownership(session, backend, pane_id)
        if not ownership.is_owned:
            return 'foreign'
        if _backend_pane_alive(backend, pane_id):
            return 'alive'
        return 'dead'
    if _backend_pane_alive(backend, pane_id):
        return 'alive'
    if pane_id:
        return 'dead'
    return 'missing'


def _backend_pane_alive(backend, pane_id: str | None) -> bool:
    pane_text = str(pane_id or '').strip()
    if not pane_text:
        return False
    checker = getattr(backend, 'is_tmux_pane_alive', None)
    if not callable(checker):
        checker = getattr(backend, 'is_alive', None)
    if not callable(checker):
        return False
    try:
        return bool(checker(pane_text))
    except Exception:
        return False


def _coerce_pid(value: object) -> int | None:
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


def _read_pid_file(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        return _coerce_pid(path.read_text(encoding='utf-8'))
    except Exception:
        return None


__all__ = [
    'AgentBinding',
    'binding_status',
    'default_binding_adapter',
    'inspect_session_pane',
    'resolve_agent_binding',
    'session_file',
    'session_id',
    'session_pane_title_marker',
    'session_ref',
    'session_runtime_pid',
    'session_runtime_ref',
    'session_runtime_root',
    'session_terminal',
    'session_tmux_socket_name',
    'session_tmux_socket_path',
]
