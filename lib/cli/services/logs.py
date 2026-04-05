from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from agents.config_loader import load_project_config
from agents.models import AgentValidationError, normalize_agent_name
from agents.store import AgentRuntimeStore
from cli.context import CliContext
from cli.models import ParsedLogsCommand

_TAIL_LINE_LIMIT = 40
_TAIL_BYTE_LIMIT = 32 * 1024
_LOG_SUFFIXES = {'.log', '.jsonl', '.txt'}


@dataclass(frozen=True)
class LogExcerpt:
    source: str
    path: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class LogsSummary:
    project_id: str
    agent_name: str
    provider: str
    runtime_ref: str | None
    session_ref: str | None
    entries: tuple[LogExcerpt, ...]


def agent_logs(context: CliContext, command: ParsedLogsCommand) -> LogsSummary:
    config = load_project_config(context.project.project_root).config
    try:
        agent_name = normalize_agent_name(command.agent_name)
    except AgentValidationError as exc:
        raise ValueError(str(exc)) from exc
    try:
        spec = config.agents[agent_name]
    except KeyError as exc:
        raise ValueError(f'unknown agent: {command.agent_name}') from exc

    runtime = AgentRuntimeStore(context.paths).load(agent_name)
    entries = _collect_entries(
        agent_dir=context.paths.agent_dir(agent_name),
        provider=spec.provider,
        session_ref=runtime.session_ref if runtime is not None else None,
    )
    return LogsSummary(
        project_id=context.project.project_id,
        agent_name=agent_name,
        provider=spec.provider,
        runtime_ref=runtime.runtime_ref if runtime is not None else None,
        session_ref=runtime.session_ref if runtime is not None else None,
        entries=entries,
    )


def _collect_entries(*, agent_dir: Path, provider: str, session_ref: str | None) -> tuple[LogExcerpt, ...]:
    seen: set[Path] = set()
    entries: list[LogExcerpt] = []

    session_path = _maybe_path(session_ref)
    if session_path is not None:
        _append_entry(entries, seen, source='session', path=session_path)
        session_runtime_dir = _runtime_dir_from_session_file(session_path)
        if session_runtime_dir is not None:
            for log_path in _iter_log_files(session_runtime_dir):
                _append_entry(entries, seen, source='runtime', path=log_path)

    provider_runtime_dir = agent_dir / 'provider-runtime' / provider
    for log_path in _iter_log_files(provider_runtime_dir):
        _append_entry(entries, seen, source='runtime', path=log_path)

    agent_logs_dir = agent_dir / 'logs'
    for log_path in _iter_log_files(agent_logs_dir):
        _append_entry(entries, seen, source='agent', path=log_path)

    return tuple(entries)


def _append_entry(entries: list[LogExcerpt], seen: set[Path], *, source: str, path: Path) -> None:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path.absolute()
    if resolved in seen or not path.is_file():
        return
    seen.add(resolved)
    entries.append(LogExcerpt(source=source, path=str(resolved), lines=_tail_lines(resolved)))


def _iter_log_files(root: Path) -> tuple[Path, ...]:
    if not root.exists() or not root.is_dir():
        return ()
    files: list[Path] = []
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _LOG_SUFFIXES:
            continue
        files.append(path)
    return tuple(sorted(files))


def _tail_lines(path: Path) -> tuple[str, ...]:
    try:
        with path.open('rb') as handle:
            handle.seek(0, 2)
            size = handle.tell()
            if size > _TAIL_BYTE_LIMIT:
                handle.seek(-_TAIL_BYTE_LIMIT, 2)
            else:
                handle.seek(0)
            data = handle.read()
    except Exception:
        return ('<unreadable>',)
    text = data.decode('utf-8', errors='replace')
    lines = text.splitlines()
    if len(lines) > _TAIL_LINE_LIMIT:
        lines = lines[-_TAIL_LINE_LIMIT:]
    return tuple(lines) if lines else ('<empty>',)


def _maybe_path(value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        return None
    if not candidate.exists():
        return None
    return candidate


def _runtime_dir_from_session_file(session_path: Path) -> Path | None:
    try:
        payload = json.loads(session_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    runtime_dir = payload.get('runtime_dir')
    if not isinstance(runtime_dir, str) or not runtime_dir.strip():
        return None
    candidate = Path(runtime_dir).expanduser()
    if not candidate.exists():
        return None
    return candidate
