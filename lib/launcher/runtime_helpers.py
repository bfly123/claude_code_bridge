from __future__ import annotations

import os


def default_cmd_start_cmd(*, get_shell_type_fn, shutil_module) -> str:
    if get_shell_type_fn() == "powershell":
        return "pwsh" if shutil_module.which("pwsh") else "powershell"
    shell = (os.environ.get("SHELL") or "bash").strip() or "bash"
    if not shutil_module.which(shell):
        shell = "bash"
    return shell


def with_bin_path_env(launcher, env: dict | None = None) -> dict:
    base = dict(env or os.environ)
    bin_path = str(launcher.script_dir / "bin")
    current = base.get("PATH") or ""
    parts = current.split(os.pathsep) if current else []
    if bin_path not in parts:
        base["PATH"] = bin_path + (os.pathsep + current if current else "")
    return base


def current_pane_id(launcher, *, tmux_backend_factory) -> str:
    try:
        backend = tmux_backend_factory()
        return backend.get_current_pane_id()
    except Exception:
        return (os.environ.get("TMUX_PANE") or "").strip()


def build_env_prefix(env: dict, *, get_shell_type_fn, shlex_module) -> str:
    if not env:
        return ""
    if get_shell_type_fn() == "powershell":
        parts: list[str] = []
        for key, val in env.items():
            if val is None:
                continue
            safe = str(val).replace("'", "''")
            parts.append(f"$env:{key} = '{safe}'; ")
        return "".join(parts)
    parts: list[str] = []
    for key, val in env.items():
        if val is None:
            continue
        parts.append(f"export {key}={shlex_module.quote(str(val))}; ")
    return "".join(parts)


def provider_pane_id(launcher, provider: str) -> str:
    prov = (provider or "").strip().lower()
    anchor = (launcher.anchor_name or "").strip().lower()
    if prov and prov == anchor and launcher.anchor_pane_id:
        return str(launcher.anchor_pane_id)
    return str(launcher.tmux_panes.get(prov, "") or "")


def set_current_pane_label(
    launcher,
    label: str,
    *,
    tmux_backend_factory,
    label_tmux_pane_fn,
) -> None:
    if launcher.terminal_type != "tmux":
        return
    if not os.environ.get("TMUX"):
        return
    try:
        backend = tmux_backend_factory()
        pane_id = backend.get_current_pane_id()
        title = f"CCB-{label}"
        label_tmux_pane_fn(backend, pane_id, title=title, agent_label=label)
    except Exception:
        pass


def run_shell_command(
    launcher,
    cmd: str,
    *,
    env: dict | None,
    cwd: str | None,
    get_shell_type_fn,
    shutil_module,
    subprocess_module,
) -> int:
    cmd = cmd or ""
    run_env = launcher._with_bin_path_env(env)
    if get_shell_type_fn() == "powershell":
        shell = "pwsh" if shutil_module.which("pwsh") else "powershell"
        return subprocess_module.run([shell, "-Command", cmd], env=run_env, cwd=cwd).returncode
    shell = (os.environ.get("SHELL") or "bash").strip() or "bash"
    if not shutil_module.which(shell):
        shell = "bash"
    return subprocess_module.run([shell, "-lc", cmd], env=run_env, cwd=cwd).returncode
