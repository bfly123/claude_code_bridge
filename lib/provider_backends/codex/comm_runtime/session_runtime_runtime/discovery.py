from __future__ import annotations

from pathlib import Path

from provider_core.session_binding_runtime import find_bound_session_file


def find_codex_session_file(*, cwd: Path | None = None) -> Path | None:
    return find_bound_session_file(
        provider="codex",
        base_filename=".codex-session",
        work_dir=cwd or Path.cwd(),
    )


__all__ = ["find_codex_session_file"]
