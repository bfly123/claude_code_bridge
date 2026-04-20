from __future__ import annotations

from pathlib import Path

from provider_core.contracts import ProviderRuntimeIdentity

from ..start_cmd import extract_resume_session_id


def live_runtime_identity(session) -> ProviderRuntimeIdentity | None:
    expected_session_id = str(getattr(session, 'codex_session_id', '') or '').strip()
    if not expected_session_id:
        return None
    pane_id = str(getattr(session, 'pane_id', '') or '').strip()
    if not pane_id.startswith('%'):
        return ProviderRuntimeIdentity('mismatch', 'bound_codex_session_without_pane')
    backend = _session_backend(session)
    if backend is None:
        return ProviderRuntimeIdentity('unknown', 'tmux_backend_unavailable')
    pane_pid = _pane_pid(backend, pane_id)
    if pane_pid is None:
        return ProviderRuntimeIdentity('unknown', 'pane_pid_unavailable')
    cmdlines = _process_tree_cmdlines(pane_pid)
    if not cmdlines:
        return ProviderRuntimeIdentity('unknown', 'process_cmdline_unavailable')
    for cmdline in cmdlines:
        if extract_resume_session_id(cmdline) == expected_session_id:
            return ProviderRuntimeIdentity('match')
    return ProviderRuntimeIdentity('mismatch', 'live_codex_process_not_running_bound_resume_session')


def _session_backend(session):
    backend_factory = getattr(session, 'backend', None)
    if not callable(backend_factory):
        return None
    try:
        return backend_factory()
    except Exception:
        return None


def _pane_pid(backend, pane_id: str) -> int | None:
    reader = getattr(backend, 'pane_pid', None)
    if callable(reader):
        try:
            return _positive_int(reader(pane_id))
        except Exception:
            return None
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['display-message', '-p', '-t', pane_id, '#{pane_pid}'],
            capture=True,
            timeout=1.0,
        )
    except Exception:
        return None
    if getattr(result, 'returncode', 0) not in (0, None):
        return None
    return _positive_int(getattr(result, 'stdout', '') or '')


def _process_tree_cmdlines(root_pid: int) -> tuple[str, ...]:
    parents = _linux_process_parent_map()
    cmdlines: list[str] = []
    for pid in (root_pid, *sorted(_descendant_pids(root_pid, parents))):
        cmdline = _linux_process_cmdline(pid)
        if cmdline:
            cmdlines.append(cmdline)
    return tuple(cmdlines)


def _linux_process_parent_map() -> dict[int, int]:
    proc = Path('/proc')
    if not proc.is_dir():
        return {}
    parents: dict[int, int] = {}
    for entry in proc.iterdir():
        pid = _positive_int(entry.name)
        if pid is None:
            continue
        ppid = _linux_process_parent_pid(entry / 'stat')
        if ppid is not None:
            parents[pid] = ppid
    return parents


def _linux_process_parent_pid(stat_path: Path) -> int | None:
    try:
        raw = stat_path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return None
    marker = raw.rfind(') ')
    if marker < 0:
        return None
    fields = raw[marker + 2 :].split()
    if len(fields) < 2:
        return None
    return _positive_int(fields[1])


def _descendant_pids(root_pid: int, parents: dict[int, int]) -> set[int]:
    children: dict[int, list[int]] = {}
    for pid, parent in parents.items():
        children.setdefault(parent, []).append(pid)
    pending = list(children.get(root_pid, ()))
    seen: set[int] = set()
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        pending.extend(children.get(pid, ()))
    return seen


def _linux_process_cmdline(pid: int) -> str:
    try:
        raw = Path('/proc') / str(pid) / 'cmdline'
        data = raw.read_bytes()
    except Exception:
        return ''
    text = data.replace(b'\0', b' ').decode('utf-8', errors='replace').strip()
    return ' '.join(text.split())


def _positive_int(value: object) -> int | None:
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    number = int(text)
    return number if number > 0 else None


__all__ = ['live_runtime_identity']
