from __future__ import annotations


def normalize_user_option(name: str) -> str:
    opt = (name or "").strip()
    if not opt:
        return ""
    if not opt.startswith("@"):
        return "@" + opt
    return opt


def pane_exists_output(stdout: str) -> bool:
    return (stdout or "").strip().startswith("%")


def pane_pipe_enabled(stdout: str) -> bool:
    return (stdout or "").strip() == "1"


def pane_is_alive(stdout: str) -> bool:
    return (stdout or "").strip() == "0"


def should_attach_selected_pane(*, env_tmux: str) -> bool:
    return not bool((env_tmux or "").strip())


def parse_session_name(stdout: str) -> str:
    return (stdout or "").strip()
