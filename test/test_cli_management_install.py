from __future__ import annotations

from pathlib import Path

from cli.management_runtime import install as install_runtime


def test_run_installer_stages_and_normalizes_crlf_checkout(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-install"
    source_dir.mkdir()
    install_sh = source_dir / "install.sh"
    marker_path = source_dir / "ran.txt"
    install_sh.write_bytes(
        b"#!/usr/bin/env bash\r\n"
        b"set -euo pipefail\r\n"
        b"printf '%s\\n' \"$0\" > \"$CODEX_INSTALL_PREFIX/ran.txt\"\r\n"
    )

    code = install_runtime.run_installer("install", script_root=source_dir)

    assert code == 0
    ran_from = marker_path.read_text(encoding="utf-8").strip()
    assert ran_from != str(install_sh)
    assert "ccb-installer-" in ran_from
