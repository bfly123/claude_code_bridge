from __future__ import annotations

import os
import sys


def sync_terminal_type_state(launcher) -> None:
    launcher.current_pane_binder.terminal_type = launcher.terminal_type
    launcher.claude_pane_launcher.terminal_type = launcher.terminal_type
    launcher.cmd_pane_launcher.terminal_type = launcher.terminal_type
    launcher.target_router.terminal_type = launcher.terminal_type
    launcher.target_session_store.terminal_type = launcher.terminal_type
    launcher.session_gateway.target_names = tuple(launcher.target_names)
    launcher.runup_preflight.terminal_type = launcher.terminal_type
    launcher.runup_preflight.target_names = tuple(launcher.target_names)


def managed_env_overrides(launcher, *, environ: dict[str, str]) -> dict[str, str]:
    env = {
        "CCB_MANAGED": "1",
        "CCB_PARENT_PID": str(launcher.ccb_pid),
    }
    if environ.get("CCB_RUN_DIR"):
        env["CCB_RUN_DIR"] = environ["CCB_RUN_DIR"]
    return env


def display_label(provider: str, display_label: str | None = None) -> str:
    if display_label and str(display_label).strip():
        return str(display_label).strip()
    prov = (provider or "").strip().lower()
    labels = {
        "codex": "Codex",
        "claude": "Claude",
        "gemini": "Gemini",
        "opencode": "OpenCode",
        "droid": "Droid",
        "cmd": "Cmd",
    }
    return labels.get(prov, prov.capitalize() if prov else "Unknown")


def provider_env_overrides(launcher, provider: str, *, environ: dict[str, str]) -> dict[str, str]:
    env = managed_env_overrides(launcher, environ=environ)
    prov = (provider or "").strip().lower()
    if prov in {"claude", "codex", "gemini", "opencode", "droid", "manual"}:
        env["CCB_CALLER"] = prov
    return env


def require_project_config_dir(launcher, *, stderr) -> bool:
    cfg = launcher._project_config_dir()
    if cfg.is_dir():
        return True
    print("❌ Missing required project config directory: .ccb", file=stderr)
    print(f"   project_root: {launcher.project_root}", file=stderr)
    print(f"   cwd:          {launcher.invocation_dir}", file=stderr)
    print(f"💡 Fix: mkdir -p {cfg}", file=stderr)
    return False


def clear_codex_log_binding(data: dict, *, stderr):
    try:
        if not isinstance(data, dict):
            return {}
        cleared = dict(data)
        for key in ("codex_session_path", "codex_session_id", "codex_start_cmd"):
            if key in cleared:
                cleared.pop(key, None)
        if cleared.get("active") is False:
            cleared["active"] = True
        return cleared
    except Exception as exc:
        print(f"⚠️ codex_session_clear_failed: {exc}", file=stderr)
        return data if isinstance(data, dict) else {}


def claude_env_overrides(launcher, *, env_builder_cls):
    return env_builder_cls(
        target_names=tuple(launcher.target_names),
        runtime_dir=launcher.runtime_dir,
        ccb_session_id=launcher.ccb_session_id,
        terminal_type=launcher.terminal_type,
        provider_env_overrides_fn=launcher._provider_env_overrides,
        provider_pane_id_fn=launcher._provider_pane_id,
    ).build_env_overrides()


def build_claude_env(launcher, *, env_builder_cls):
    env = launcher._with_bin_path_env()
    env.update(claude_env_overrides(launcher, env_builder_cls=env_builder_cls))
    return env
