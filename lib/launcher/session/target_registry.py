from __future__ import annotations

from pathlib import Path
import sys

from launcher.session.payloads import build_cend_registry_payload, build_provider_registry_payload


def write_cend_registry(
    store,
    *,
    claude_pane_id: str,
    codex_pane_id: str | None,
) -> bool:
    if not claude_pane_id:
        return False
    record = build_cend_registry_payload(
        ccb_session_id=store.ccb_session_id,
        project_root=store.project_root,
        terminal_type=store.terminal_type,
        compute_project_id_fn=store.compute_project_id_fn,
        claude_pane_id=claude_pane_id,
        codex_pane_id=codex_pane_id,
    )
    ok = store.upsert_registry_fn(record)
    if not ok:
        print("⚠️ Failed to update Codex registry", file=sys.stderr)
    return bool(ok)


def upsert_provider_registry(
    store,
    provider: str,
    *,
    pane_id: str | None,
    pane_title_marker: str | None,
    session_file: Path,
    extra_registry: dict | None = None,
) -> None:
    try:
        payload = build_provider_registry_payload(
            provider=provider,
            ccb_session_id=store.ccb_session_id,
            project_root=store.project_root,
            terminal_type=store.terminal_type,
            session_file=session_file,
            compute_project_id_fn=store.compute_project_id_fn,
            pane_id=pane_id,
            pane_title_marker=pane_title_marker,
            extra_registry=extra_registry,
        )
        store.upsert_registry_fn(payload)
    except Exception:
        pass
