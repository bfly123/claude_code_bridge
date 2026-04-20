from __future__ import annotations

import os
import shlex
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"


def _render_install_identity(*, source_kind: str, channel: str, version: str = "9.9.9") -> str:
    env = os.environ.copy()
    env.update(
        {
            "CCB_LANG": "en",
            "CCB_SOURCE_KIND": source_kind,
            "CCB_BUILD_CHANNEL": channel,
            "CCB_BUILD_VERSION": version,
        }
    )
    command = textwrap.dedent(
        f"""
        set -euo pipefail
        source {shlex.quote(str(INSTALL_SH))}
        print_install_identity_summary
        print_install_identity_notice
        """
    )
    completed = subprocess.run(
        ["bash", "-lc", command],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.stdout


def test_source_install_identity_output_is_explicit() -> None:
    output = _render_install_identity(source_kind="source", channel="dev", version="1.2.3")

    assert "install_mode=source" in output
    assert "source_kind=source" in output
    assert "channel=dev" in output
    assert "version=1.2.3" in output
    assert "Development/source install detected" in output
    assert "This is a development install, not an official release package." in output


def test_release_install_identity_output_is_explicit() -> None:
    output = _render_install_identity(source_kind="release", channel="stable", version="2.0.0")

    assert "install_mode=release" in output
    assert "source_kind=release" in output
    assert "channel=stable" in output
    assert "version=2.0.0" in output
    assert "Official release package install detected" in output


def test_preview_release_install_identity_is_not_misreported_as_source() -> None:
    output = _render_install_identity(source_kind="preview", channel="preview", version="2.0.0-preview")

    assert "install_mode=release" in output
    assert "source_kind=preview" in output
    assert "channel=preview" in output
    assert "version=2.0.0-preview" in output
    assert "Preview release package install detected" in output
    assert "not an official stable release" in output
