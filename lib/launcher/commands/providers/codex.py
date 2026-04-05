from __future__ import annotations

from launcher.commands.providers.codex_auto import ensure_codex_auto_approval
from launcher.commands.providers.codex_history import get_latest_codex_session_id


def build_codex_start_cmd(factory) -> str:
    if factory.auto:
        factory.ensure_codex_auto_approval()
    cmd_parts = ["codex", "-c", "disable_paste_burst=true"]
    if factory.auto:
        cmd_parts.extend(
            [
                "-c",
                'trust_level="trusted"',
                "-c",
                'approval_policy="never"',
                "-c",
                'sandbox_mode="danger-full-access"',
            ]
        )
    cmd = " ".join(cmd_parts)
    codex_resumed = False
    if factory.resume:
        session_id, _has_history = factory.get_latest_codex_session_id()
        if session_id:
            cmd = f"{cmd} resume {session_id}"
            print(f"🔁 {factory.translate_fn('resuming_session', provider='Codex', session_id=session_id[:8])}")
            codex_resumed = True
        if not codex_resumed:
            print(f"ℹ️ {factory.translate_fn('no_history_fresh', provider='Codex')}")
    return cmd


__all__ = [
    "get_latest_codex_session_id",
    "ensure_codex_auto_approval",
    "build_codex_start_cmd",
]
