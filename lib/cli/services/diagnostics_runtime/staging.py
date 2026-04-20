from __future__ import annotations

import json
from pathlib import Path
import tarfile

from .models import DiagnosticBundleEntry
from .sources import archive_path_for_source

_TAIL_BYTE_LIMIT = 64 * 1024
_TAIL_LINE_LIMIT = 200
_TAIL_SUFFIXES = {'.log', '.jsonl', '.txt', '.yaml', '.yml'}


def stage_file(context, stage_root: Path, *, category: str, source: Path) -> DiagnosticBundleEntry:
    archive_path = archive_path_for_source(context, source)
    exists, error = _source_exists(source)
    if error is not None:
        return DiagnosticBundleEntry(category=category, source_path=str(source), archive_path=archive_path, status='error', error=error)
    if not exists:
        return DiagnosticBundleEntry(category=category, source_path=str(source), archive_path=archive_path, status='missing')

    target = stage_root / archive_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in _TAIL_SUFFIXES:
        return _stage_tailed_text(category=category, source=source, archive_path=archive_path, target=target)
    return _stage_bytes(category=category, source=source, archive_path=archive_path, target=target)


def tail_text_payload(path: Path) -> tuple[str, bool]:
    with path.open('rb') as handle:
        handle.seek(0, 2)
        size = handle.tell()
        truncated = size > _TAIL_BYTE_LIMIT
        handle.seek(-_TAIL_BYTE_LIMIT, 2) if truncated else handle.seek(0)
        data = handle.read()
    text = data.decode('utf-8', errors='replace')
    lines = text.splitlines()
    if len(lines) > _TAIL_LINE_LIMIT:
        lines = lines[-_TAIL_LINE_LIMIT:]
        truncated = True
    return ('\n'.join(lines) + ('\n' if lines else '')), truncated


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def create_tarball(*, stage_root: Path, output_path: Path, bundle_id: str) -> None:
    with tarfile.open(output_path, 'w:gz') as archive:
        archive.add(stage_root, arcname=bundle_id)


def _source_exists(source: Path) -> tuple[bool, str | None]:
    try:
        return source.exists() and source.is_file(), None
    except Exception as exc:
        return False, str(exc)


def _stage_tailed_text(*, category: str, source: Path, archive_path: str, target: Path) -> DiagnosticBundleEntry:
    try:
        payload, truncated = tail_text_payload(source)
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
        return DiagnosticBundleEntry(category=category, source_path=str(source), archive_path=archive_path, status='error', error=str(exc))


def _stage_bytes(*, category: str, source: Path, archive_path: str, target: Path) -> DiagnosticBundleEntry:
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
        return DiagnosticBundleEntry(category=category, source_path=str(source), archive_path=archive_path, status='error', error=str(exc))


__all__ = ['create_tarball', 'stage_file', 'tail_text_payload', 'write_json']
