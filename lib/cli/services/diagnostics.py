from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tarfile
import tempfile
from typing import Any

from ccbd.system import utc_now
from cli.context import CliContext
from cli.models import ParsedDoctorCommand

from .doctor import doctor_summary

_TAIL_BYTE_LIMIT = 64 * 1024
_TAIL_LINE_LIMIT = 200
_TAIL_SUFFIXES = {'.log', '.jsonl', '.txt', '.yaml', '.yml'}
_COPY_SUFFIXES = {'.json', '.pid'}


@dataclass(frozen=True)
class DiagnosticBundleEntry:
    category: str
    source_path: str
    archive_path: str
    status: str
    truncated: bool = False
    byte_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class DiagnosticBundleSummary:
    project_root: str
    project_id: str
    bundle_id: str
    bundle_path: str
    file_count: int
    included_count: int
    missing_count: int
    truncated_count: int
    doctor_error: str | None = None


def export_diagnostic_bundle(context: CliContext, command: ParsedDoctorCommand) -> DiagnosticBundleSummary:
    generated_at = utc_now()
    bundle_id = _bundle_id(project_id=context.project.project_id, generated_at=generated_at)
    output_path = _resolve_output_path(context, command, bundle_id=bundle_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doctor_payload, doctor_error = _doctor_payload(context)
    entries: list[DiagnosticBundleEntry] = []

    support_dir = context.paths.ccbd_support_dir
    support_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bundle-', dir=str(support_dir)) as tmpdir:
        stage_root = Path(tmpdir) / bundle_id
        stage_root.mkdir(parents=True, exist_ok=True)

        _write_json(stage_root / 'generated' / 'doctor.json', doctor_payload)
        _write_json(
            stage_root / 'generated' / 'bundle-metadata.json',
            {
                'generated_at': generated_at,
                'project_root': str(context.project.project_root),
                'project_id': context.project.project_id,
                'bundle_id': bundle_id,
                'doctor_error': doctor_error,
            },
        )

        for category, path in _project_root_sources(context):
            entries.append(_stage_file(context, stage_root, category=category, source=path))

        manifest = {
            'schema_version': 1,
            'record_type': 'ccbd_diagnostic_bundle',
            'generated_at': generated_at,
            'project_root': str(context.project.project_root),
            'project_id': context.project.project_id,
            'bundle_id': bundle_id,
            'doctor_error': doctor_error,
            'entries': [
                {
                    'category': entry.category,
                    'source_path': entry.source_path,
                    'archive_path': entry.archive_path,
                    'status': entry.status,
                    'truncated': entry.truncated,
                    'byte_count': entry.byte_count,
                    'error': entry.error,
                }
                for entry in entries
            ],
        }
        _write_json(stage_root / 'manifest.json', manifest)
        _create_tarball(stage_root=stage_root, output_path=output_path, bundle_id=bundle_id)

    included_count = sum(1 for entry in entries if entry.status == 'included')
    missing_count = sum(1 for entry in entries if entry.status == 'missing')
    truncated_count = sum(1 for entry in entries if entry.truncated)
    return DiagnosticBundleSummary(
        project_root=str(context.project.project_root),
        project_id=context.project.project_id,
        bundle_id=bundle_id,
        bundle_path=str(output_path),
        file_count=len(entries),
        included_count=included_count,
        missing_count=missing_count,
        truncated_count=truncated_count,
        doctor_error=doctor_error,
    )


def _doctor_payload(context: CliContext) -> tuple[dict[str, Any], str | None]:
    try:
        return doctor_summary(context), None
    except Exception as exc:
        return {
            'project': str(context.project.project_root),
            'project_id': context.project.project_id,
            'error': str(exc),
        }, str(exc)


def _bundle_id(*, project_id: str, generated_at: str) -> str:
    safe_time = generated_at.replace(':', '').replace('-', '').replace('.', '').replace('T', 't').replace('Z', 'z')
    return f'ccb-support-{safe_time}-{project_id[:12]}'


def _resolve_output_path(context: CliContext, command: ParsedDoctorCommand, *, bundle_id: str) -> Path:
    if command.output_path:
        candidate = Path(command.output_path).expanduser()
        if not candidate.is_absolute():
            candidate = (context.cwd / candidate).resolve()
        return candidate
    return context.paths.support_bundle_path(bundle_id)


def _project_root_sources(context: CliContext) -> tuple[tuple[str, Path], ...]:
    items: list[tuple[str, Path]] = [
        ('project-config', context.paths.config_path),
        ('ccbd-authority', context.paths.ccbd_lease_path),
        ('ccbd-authority', context.paths.ccbd_keeper_path),
        ('ccbd-authority', context.paths.ccbd_shutdown_intent_path),
        ('ccbd-authority', context.paths.ccbd_state_path),
        ('ccbd-authority', context.paths.ccbd_start_policy_path),
        ('ccbd-report', context.paths.ccbd_startup_report_path),
        ('ccbd-report', context.paths.ccbd_shutdown_report_path),
        ('ccbd-report', context.paths.ccbd_restore_report_path),
        ('ccbd-events', context.paths.ccbd_submissions_path),
        ('ccbd-events', context.paths.ccbd_messages_path),
        ('ccbd-events', context.paths.ccbd_attempts_path),
        ('ccbd-events', context.paths.ccbd_replies_path),
        ('ccbd-events', context.paths.ccbd_dead_letters_path),
        ('ccbd-events', context.paths.ccbd_supervision_path),
        ('ccbd-events', context.paths.ccbd_lifecycle_log_path),
        ('ccbd-events', context.paths.ccbd_tmux_cleanup_history_path),
        ('ccbd-log', context.paths.ccbd_dir / 'ccbd.stdout.log'),
        ('ccbd-log', context.paths.ccbd_dir / 'ccbd.stderr.log'),
        ('ccbd-log', context.paths.ccbd_dir / 'keeper.stdout.log'),
        ('ccbd-log', context.paths.ccbd_dir / 'keeper.stderr.log'),
    ]

    items.extend(_iter_dir_files('ccbd-execution', context.paths.ccbd_executions_dir, suffixes={'.json'}))
    items.extend(_iter_dir_files('ccbd-snapshot', context.paths.ccbd_snapshots_dir, suffixes={'.json'}))
    items.extend(_iter_dir_files('ccbd-cursor', context.paths.ccbd_cursors_dir, suffixes={'.json'}))
    items.extend(_iter_dir_files('ccbd-heartbeat', context.paths.ccbd_heartbeats_dir, suffixes={'.json'}))
    items.extend(_iter_dir_files('ccbd-health', context.paths.ccbd_provider_health_dir, suffixes={'.jsonl'}))
    items.extend(_iter_dir_files('ccbd-mailbox', context.paths.ccbd_mailboxes_dir, suffixes={'.json', '.jsonl'}))
    items.extend(_iter_dir_files('ccbd-lease', context.paths.ccbd_leases_dir, suffixes={'.json'}))

    seen_sources: set[Path] = {path for _, path in items}
    for agent_dir in _iter_agent_dirs(context):
        agent_name = agent_dir.name
        for category, path in _agent_sources(context, agent_name, agent_dir):
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path.absolute()
            if resolved in seen_sources:
                continue
            seen_sources.add(resolved)
            items.append((category, path))
    return tuple(items)


def _agent_sources(context: CliContext, agent_name: str, agent_dir: Path) -> tuple[tuple[str, Path], ...]:
    items: list[tuple[str, Path]] = [
        ('agent-authority', context.paths.agent_spec_path(agent_name)),
        ('agent-authority', context.paths.agent_runtime_path(agent_name)),
        ('agent-authority', context.paths.agent_restore_path(agent_name)),
        ('agent-events', context.paths.agent_jobs_path(agent_name)),
        ('agent-events', context.paths.agent_events_path(agent_name)),
        ('agent-workspace', context.paths.workspace_binding_path(agent_name)),
    ]
    items.extend(_iter_dir_files('agent-log', context.paths.agent_logs_dir(agent_name), suffixes=_TAIL_SUFFIXES))
    items.extend(
        _iter_dir_files(
            'agent-runtime',
            agent_dir / 'provider-runtime',
            suffixes=_TAIL_SUFFIXES | _COPY_SUFFIXES,
        )
    )

    runtime_path = context.paths.agent_runtime_path(agent_name)
    if runtime_path.exists():
        session_path = _session_path_from_runtime(runtime_path)
        if session_path is not None:
            items.append(('agent-session', session_path))
    return tuple(items)


def _iter_dir_files(category: str, root: Path, *, suffixes: set[str]) -> list[tuple[str, Path]]:
    if not root.exists() or not root.is_dir():
        return []
    files: list[tuple[str, Path]] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        files.append((category, path))
    return files


def _iter_agent_dirs(context: CliContext) -> tuple[Path, ...]:
    root = context.paths.agents_dir
    if not root.exists() or not root.is_dir():
        return ()
    return tuple(path for path in sorted(root.iterdir()) if path.is_dir())


def _session_path_from_runtime(runtime_path: Path) -> Path | None:
    try:
        payload = json.loads(runtime_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    for key in ('session_file', 'session_ref'):
        candidate = payload.get(key)
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        path = Path(candidate).expanduser()
        if path.is_absolute() and path.exists():
            return path
    return None


def _stage_file(context: CliContext, stage_root: Path, *, category: str, source: Path) -> DiagnosticBundleEntry:
    archive_path = _archive_path_for_source(context, source)
    try:
        exists = source.exists() and source.is_file()
    except Exception as exc:
        return DiagnosticBundleEntry(
            category=category,
            source_path=str(source),
            archive_path=archive_path,
            status='error',
            error=str(exc),
        )
    if not exists:
        return DiagnosticBundleEntry(
            category=category,
            source_path=str(source),
            archive_path=archive_path,
            status='missing',
        )

    target = stage_root / archive_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in _TAIL_SUFFIXES:
        try:
            payload, truncated = _tail_text_payload(source)
            target.write_text(payload, encoding='utf-8')
            return DiagnosticBundleEntry(
                category=category,
                source_path=str(source),
                archive_path=archive_path,
                status='included',
                truncated=truncated,
                byte_count=len(payload.encode('utf-8')),
            )
        except Exception as exc:
            return DiagnosticBundleEntry(
                category=category,
                source_path=str(source),
                archive_path=archive_path,
                status='error',
                error=str(exc),
            )

    try:
        data = source.read_bytes()
        target.write_bytes(data)
        return DiagnosticBundleEntry(
            category=category,
            source_path=str(source),
            archive_path=archive_path,
            status='included',
            truncated=False,
            byte_count=len(data),
        )
    except Exception as exc:
        return DiagnosticBundleEntry(
            category=category,
            source_path=str(source),
            archive_path=archive_path,
            status='error',
            error=str(exc),
        )


def _archive_path_for_source(context: CliContext, source: Path) -> str:
    try:
        relative = source.resolve().relative_to(context.project.project_root.resolve())
        return str(Path('project') / relative)
    except Exception:
        safe_parts = [part for part in source.parts if part not in ('/', '')]
        return str(Path('external') / Path(*safe_parts[-4:]))


def _tail_text_payload(path: Path) -> tuple[str, bool]:
    with path.open('rb') as handle:
        handle.seek(0, 2)
        size = handle.tell()
        truncated = size > _TAIL_BYTE_LIMIT
        if truncated:
            handle.seek(-_TAIL_BYTE_LIMIT, 2)
        else:
            handle.seek(0)
        data = handle.read()
    text = data.decode('utf-8', errors='replace')
    lines = text.splitlines()
    if len(lines) > _TAIL_LINE_LIMIT:
        lines = lines[-_TAIL_LINE_LIMIT:]
        truncated = True
    return ('\n'.join(lines) + ('\n' if lines else '')), truncated


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _create_tarball(*, stage_root: Path, output_path: Path, bundle_id: str) -> None:
    with tarfile.open(output_path, 'w:gz') as archive:
        archive.add(stage_root, arcname=bundle_id)


__all__ = ['DiagnosticBundleSummary', 'export_diagnostic_bundle']
