from __future__ import annotations

import io
import tarfile
from pathlib import Path

from cli.management_runtime import install as install_runtime


def _build_tar_with_link(*, name: str, linkname: str) -> io.BytesIO:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo(name=name)
        info.type = tarfile.SYMTYPE
        info.linkname = linkname
        archive.addfile(info)
    buffer.seek(0)
    return buffer


def test_safe_extract_tar_rejects_absolute_symlink_targets(tmp_path: Path) -> None:
    payload = _build_tar_with_link(name="badlink", linkname="/abs/path")

    with tarfile.open(fileobj=payload, mode="r:gz") as archive:
        try:
            install_runtime.safe_extract_tar(archive, tmp_path)
        except RuntimeError as exc:
            text = str(exc)
        else:
            raise AssertionError("expected RuntimeError")

    assert "Unsafe tar link target" in text
    assert "badlink" in text


def test_safe_extract_tar_rejects_escaping_relative_symlink_targets(tmp_path: Path) -> None:
    payload = _build_tar_with_link(name="nested/badlink", linkname="../../escape")

    with tarfile.open(fileobj=payload, mode="r:gz") as archive:
        try:
            install_runtime.safe_extract_tar(archive, tmp_path)
        except RuntimeError as exc:
            text = str(exc)
        else:
            raise AssertionError("expected RuntimeError")

    assert "Unsafe tar link target" in text
    assert "nested/badlink" in text
