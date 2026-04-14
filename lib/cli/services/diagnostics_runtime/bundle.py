from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from ccbd.system import utc_now

from ..doctor import doctor_summary
from .models import DiagnosticBundleEntry, DiagnosticBundleSummary
from .sources import project_root_sources
from .staging import create_tarball, stage_file, write_json


def export_diagnostic_bundle(context, command) -> DiagnosticBundleSummary:
    generated_at = utc_now()
    bundle_id = bundle_identifier(project_id=context.project.project_id, generated_at=generated_at)
    output_path = resolve_output_path(context, command, bundle_id=bundle_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doctor_data, doctor_error = _doctor_payload(context)
    entries: list[DiagnosticBundleEntry] = []

    support_dir = context.paths.ccbd_support_dir
    support_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bundle-', dir=str(support_dir)) as tmpdir:
        stage_root = Path(tmpdir) / bundle_id
        stage_root.mkdir(parents=True, exist_ok=True)
        _write_generated_payloads(
            stage_root,
            context=context,
            bundle_id=bundle_id,
            generated_at=generated_at,
            doctor_payload=doctor_data,
            doctor_error=doctor_error,
        )
        for category, path in project_root_sources(context):
            entries.append(stage_file(context, stage_root, category=category, source=path))
        manifest = _bundle_manifest(
            context=context,
            generated_at=generated_at,
            bundle_id=bundle_id,
            doctor_error=doctor_error,
            entries=entries,
        )
        write_json(stage_root / 'manifest.json', manifest)
        create_tarball(stage_root=stage_root, output_path=output_path, bundle_id=bundle_id)

    return _bundle_summary(context, output_path=output_path, bundle_id=bundle_id, doctor_error=doctor_error, entries=entries)


def _doctor_payload(context) -> tuple[dict[str, Any], str | None]:
    try:
        return doctor_summary(context), None
    except Exception as exc:
        return {
            'project': str(context.project.project_root),
            'project_id': context.project.project_id,
            'error': str(exc),
        }, str(exc)


def bundle_identifier(*, project_id: str, generated_at: str) -> str:
    safe_time = generated_at.replace(':', '').replace('-', '').replace('.', '').replace('T', 't').replace('Z', 'z')
    return f'ccb-support-{safe_time}-{project_id[:12]}'


def resolve_output_path(context, command, *, bundle_id: str) -> Path:
    if command.output_path:
        candidate = Path(command.output_path).expanduser()
        if not candidate.is_absolute():
            candidate = (context.cwd / candidate).resolve()
        return candidate
    return context.paths.support_bundle_path(bundle_id)


def _write_generated_payloads(stage_root: Path, *, context, bundle_id: str, generated_at: str, doctor_payload: dict[str, Any], doctor_error: str | None) -> None:
    write_json(stage_root / 'generated' / 'doctor.json', doctor_payload)
    write_json(
        stage_root / 'generated' / 'bundle-metadata.json',
        {
            'generated_at': generated_at,
            'project_root': str(context.project.project_root),
            'project_id': context.project.project_id,
            'bundle_id': bundle_id,
            'doctor_error': doctor_error,
        },
    )


def _bundle_manifest(*, context, generated_at: str, bundle_id: str, doctor_error: str | None, entries: list[DiagnosticBundleEntry]) -> dict[str, Any]:
    return {
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


def _bundle_summary(context, *, output_path: Path, bundle_id: str, doctor_error: str | None, entries: list[DiagnosticBundleEntry]) -> DiagnosticBundleSummary:
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


__all__ = ['export_diagnostic_bundle']
