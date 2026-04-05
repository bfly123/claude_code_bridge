from __future__ import annotations

from launcher.commands.providers.opencode_config import ensure_opencode_auto_config
from launcher.commands.providers.opencode_resume import opencode_resume_allowed



def build_opencode_start_cmd(factory) -> str:
    import os

    cmd = (os.environ.get("OPENCODE_START_CMD") or "opencode").strip() or "opencode"
    if factory.auto:
        factory.ensure_opencode_auto_config()
    if factory.resume:
        if factory.opencode_resume_allowed():
            cmd = f"{cmd} --continue"
            print(f"🔁 {factory.translate_fn('resuming_session', provider='OpenCode', session_id='')}")
        else:
            print(f"ℹ️ {factory.translate_fn('no_history_fresh', provider='OpenCode')}")
    return cmd


__all__ = [
    "opencode_resume_allowed",
    "ensure_opencode_auto_config",
    "build_opencode_start_cmd",
]
