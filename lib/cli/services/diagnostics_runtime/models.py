from __future__ import annotations

from dataclasses import dataclass


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


__all__ = ['DiagnosticBundleEntry', 'DiagnosticBundleSummary']
