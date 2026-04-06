from __future__ import annotations

from pathlib import Path

from cli.management_runtime.versioning_runtime.local import format_version_info, get_version_info


def test_get_version_info_reads_embedded_ccb_metadata(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "ccb").write_text(
        'VERSION="1.2.3"\nGIT_COMMIT="abc123"\nGIT_DATE="2026-04-06"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "cli.management_runtime.versioning_runtime.local.git_version_info",
        lambda dir_path: None,
    )

    info = get_version_info(tmp_path)

    assert info == {"commit": "abc123", "date": "2026-04-06", "version": "1.2.3"}
    assert format_version_info(info) == "v1.2.3 abc123 2026-04-06"


def test_get_version_info_prefers_git_metadata_when_available(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "ccb").write_text('VERSION="1.2.3"\n', encoding="utf-8")
    monkeypatch.setattr(
        "cli.management_runtime.versioning_runtime.local.git_version_info",
        lambda dir_path: {"commit": "def456", "date": "2026-04-07"},
    )

    info = get_version_info(tmp_path)

    assert info == {"commit": "def456", "date": "2026-04-07", "version": "1.2.3"}
