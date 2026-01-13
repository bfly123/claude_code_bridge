from __future__ import annotations
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


def is_windows() -> bool:
    return platform.system() == "Windows"


def _subprocess_kwargs() -> dict:
    """
    返回适合当前平台的subprocess参数，避免Windows上创建可见窗口

    在Windows上使用CREATE_NO_WINDOW标志，确保subprocess调用不会弹出CMD窗口。
    注意：不使用DETACHED_PROCESS，以保留控制台继承能力。
    """
    if os.name == "nt":
        # CREATE_NO_WINDOW (0x08000000): 创建无窗口的进程
        # 这允许子进程继承父进程的隐藏控制台，而不是创建新的可见窗口
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": flags}
    return {}


def _run(*args, **kwargs):
    """Wrapper for subprocess.run that adds hidden window on Windows."""
    kwargs.update(_subprocess_kwargs())
    import subprocess as _sp
    return _sp.run(*args, **kwargs)


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except Exception:
        return False


def _choose_wezterm_cli_cwd() -> str | None:
    """
    Pick a safe cwd for launching Windows `wezterm.exe` from inside WSL.

    When a Windows binary is launched via WSL interop from a WSL cwd (e.g. /home/...),
    Windows may treat the process cwd as a UNC path like \\\\wsl.localhost\\...,
    which can confuse WezTerm's WSL relay and produce noisy `chdir(/wsl.localhost/...) failed 2`.
    Using a Windows-mounted path like /mnt/c avoids that.
    """
    override = (os.environ.get("CCB_WEZTERM_CLI_CWD") or "").strip()
    candidates = [override] if override else []
    candidates.extend(["/mnt/c", "/mnt/d", "/mnt"])
    for candidate in candidates:
        if not candidate:
            continue
        try:
            p = Path(candidate)
            if p.is_dir():
                return str(p)
        except Exception:
            continue
    return None


def _extract_wsl_path_from_unc_like_path(raw: str) -> str | None:
    """
    Convert UNC-like WSL paths into a WSL-internal absolute path.

    Supports forms commonly seen in Git Bash/MSYS and Windows:
      - /wsl.localhost/Ubuntu-24.04/home/user/...
      - \\\\wsl.localhost\\Ubuntu-24.04\\home\\user\\...
      - /wsl$/Ubuntu-24.04/home/user/...
    Returns a POSIX absolute path like: /home/user/...
    """
    if not raw:
        return None

    m = re.match(r'^(?:[/\\]{1,2})(?:wsl\.localhost|wsl\$)[/\\]([^/\\]+)(.*)$', raw, re.IGNORECASE)
    if not m:
        return None
    remainder = m.group(2).replace("\\", "/")
    if not remainder:
        return "/"
    if not remainder.startswith("/"):
        remainder = "/" + remainder
    return remainder


def _load_cached_wezterm_bin() -> str | None:
    """Load cached WezTerm path from installation"""
    candidates: list[Path] = []
    xdg = (os.environ.get("XDG_CONFIG_HOME") or "").strip()
    if xdg:
        candidates.append(Path(xdg) / "ccb" / "env")
    if os.name == "nt":
        localappdata = (os.environ.get("LOCALAPPDATA") or "").strip()
        if localappdata:
            candidates.append(Path(localappdata) / "ccb" / "env")
        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            candidates.append(Path(appdata) / "ccb" / "env")
    candidates.append(Path.home() / ".config" / "ccb" / "env")

    for config in candidates:
        try:
            if not config.exists():
                continue
            for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("CODEX_WEZTERM_BIN="):
                    path = line.split("=", 1)[1].strip()
                    if path and Path(path).exists():
                        return path
        except Exception:
            continue
    return None


_cached_wezterm_bin: str | None = None


def _get_wezterm_bin() -> str | None:
    """Get WezTerm path (with cache)"""
    global _cached_wezterm_bin
    if _cached_wezterm_bin:
        return _cached_wezterm_bin
    # Priority: env var > install cache > PATH > hardcoded paths
    override = os.environ.get("CODEX_WEZTERM_BIN") or os.environ.get("WEZTERM_BIN")
    if override and Path(override).exists():
        _cached_wezterm_bin = override
        return override
    cached = _load_cached_wezterm_bin()
    if cached:
        _cached_wezterm_bin = cached
        return cached
    found = shutil.which("wezterm") or shutil.which("wezterm.exe")
    if found:
        _cached_wezterm_bin = found
        return found
    if is_wsl():
        for drive in "cdefghijklmnopqrstuvwxyz":
            for path in [f"/mnt/{drive}/Program Files/WezTerm/wezterm.exe",
                         f"/mnt/{drive}/Program Files (x86)/WezTerm/wezterm.exe"]:
                if Path(path).exists():
                    _cached_wezterm_bin = path
                    return path
    return None


def _is_windows_wezterm() -> bool:
    """Detect if WezTerm is running on Windows"""
    override = os.environ.get("CODEX_WEZTERM_BIN") or os.environ.get("WEZTERM_BIN")
    if override:
        if ".exe" in override.lower() or "/mnt/" in override:
            return True
    if shutil.which("wezterm.exe"):
        return True
    if is_wsl():
        for drive in "cdefghijklmnopqrstuvwxyz":
            for path in [f"/mnt/{drive}/Program Files/WezTerm/wezterm.exe",
                         f"/mnt/{drive}/Program Files (x86)/WezTerm/wezterm.exe"]:
                if Path(path).exists():
                    return True
    return False


def _default_shell() -> tuple[str, str]:
    if is_wsl():
        return "bash", "-c"
    if is_windows():
        for shell in ["pwsh", "powershell"]:
            if shutil.which(shell):
                return shell, "-Command"
        return "powershell", "-Command"
    return "bash", "-c"


def get_shell_type() -> str:
    if is_windows() and os.environ.get("CCB_BACKEND_ENV", "").lower() == "wsl":
        return "bash"
    shell, _ = _default_shell()
    if shell in ("pwsh", "powershell"):
        return "powershell"
    return "bash"


class TerminalBackend(ABC):
    @abstractmethod
    def send_text(self, pane_id: str, text: str) -> None: ...
    @abstractmethod
    def is_alive(self, pane_id: str) -> bool: ...
    @abstractmethod
    def kill_pane(self, pane_id: str) -> None: ...
    @abstractmethod
    def activate(self, pane_id: str) -> None: ...
    @abstractmethod
    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: Optional[str] = None) -> str: ...


class TmuxBackend(TerminalBackend):
    """
    tmux backend (pane-oriented).

    Compatibility note:
    - New API prefers tmux pane IDs like `%12`.
    - Legacy CCB code may still pass a tmux *session name* as `pane_id` (pure tmux mode).
      For backward compatibility, methods accept both:
        - If target starts with `%` or contains `:`/`.` it is treated as a tmux target (pane/window/session:win.pane).
        - Otherwise it is treated as a tmux session name (single-pane session legacy behavior).
    - Uses tmux pane_id (`%xx`) + pane title marker for daemon rediscovery.
    """

    _ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

    def __init__(self, *, socket_name: str | None = None):
        # Optional tmux server socket isolation (like `tmux -L <name>`). Useful for daemon mode.
        self._socket_name = (socket_name or os.environ.get("CCB_TMUX_SOCKET") or "").strip() or None

    def _tmux_base(self) -> list[str]:
        cmd = ["tmux"]
        if self._socket_name:
            cmd.extend(["-L", self._socket_name])
        return cmd

    def _tmux_run(self, args: list[str], *, check: bool = False, capture: bool = False, input_bytes: bytes | None = None,
                  timeout: float | None = None) -> subprocess.CompletedProcess:
        kwargs: dict = {}
        if capture:
            kwargs.update({
                "capture_output": True,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
            })
        if input_bytes is not None:
            kwargs["input"] = input_bytes
        if timeout is not None:
            kwargs["timeout"] = timeout
        return _run([*self._tmux_base(), *args], check=check, **kwargs)

    @staticmethod
    def _looks_like_pane_id(value: str) -> bool:
        v = (value or "").strip()
        return v.startswith("%")

    @staticmethod
    def _looks_like_tmux_target(value: str) -> bool:
        v = (value or "").strip()
        if not v:
            return False
        return v.startswith("%") or (":" in v) or ("." in v)

    def get_current_pane_id(self) -> str:
        """
        Return current tmux pane id in `%xx` format.

        - Inside tmux, prefer `$TMUX_PANE`.
        - Fallback to `tmux display-message` (requires an attached client).
        """
        env_pane = (os.environ.get("TMUX_PANE") or "").strip()
        if self._looks_like_pane_id(env_pane):
            return env_pane

        cp = self._tmux_run(["display-message", "-p", "#{pane_id}"], capture=True)
        out = (cp.stdout or "").strip()
        if self._looks_like_pane_id(out):
            return out
        raise RuntimeError("tmux current pane id not available (not in tmux client?)")

    def split_pane(self, parent_pane_id: str, direction: str, percent: int) -> str:
        """
        Split `parent_pane_id` and return the created tmux pane id (`%xx`), using `-P -F`.
        """
        if not parent_pane_id:
            raise ValueError("parent_pane_id is required")

        # tmux cannot split a zoomed pane; unzoom automatically for a smoother UX.
        try:
            if self._looks_like_pane_id(parent_pane_id):
                zoom_cp = self._tmux_run(
                    ["display-message", "-p", "-t", parent_pane_id, "#{window_zoomed_flag}"],
                    capture=True,
                    timeout=0.5,
                )
                if zoom_cp.returncode == 0 and (zoom_cp.stdout or "").strip() in ("1", "on", "yes", "true"):
                    self._tmux_run(["resize-pane", "-Z", "-t", parent_pane_id], check=False, timeout=0.5)
        except Exception:
            pass

        if self._looks_like_pane_id(parent_pane_id) and not self.is_pane_alive(parent_pane_id):
            raise RuntimeError(f"Cannot split: pane {parent_pane_id} does not exist or is dead")

        size_cp = self._tmux_run(
            ["display-message", "-p", "-t", parent_pane_id, "#{pane_width}x#{pane_height}"],
            capture=True,
        )
        pane_size = (size_cp.stdout or "").strip() if size_cp.returncode == 0 else "unknown"

        direction_norm = (direction or "").strip().lower()
        if direction_norm in ("right", "h", "horizontal"):
            flag = "-h"
        elif direction_norm in ("bottom", "v", "vertical"):
            flag = "-v"
        else:
            raise ValueError(f"unsupported direction: {direction!r} (use 'right' or 'bottom')")

        # NOTE: Do not pass `-p <percent>` here.
        #
        # tmux 3.4 can error with `size missing` when splitting panes by percentage in detached
        # sessions (e.g. auto-created sessions before any client is attached). Using tmux's default
        # 50% split avoids that class of failures and is what CCB uses for its layouts anyway.
        try:
            cp = self._tmux_run(
                ["split-window", flag, "-t", parent_pane_id, "-P", "-F", "#{pane_id}"],
                check=True,
                capture=True,
            )
        except subprocess.CalledProcessError as e:
            out = (getattr(e, "stdout", "") or "").strip()
            err = (getattr(e, "stderr", "") or "").strip()
            msg = err or out
            raise RuntimeError(
                f"tmux split-window failed (exit {e.returncode}): {msg or 'no stdout/stderr'}\n"
                f"Pane: {parent_pane_id}, size: {pane_size}, direction: {direction_norm}\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Hint: If the pane is zoomed, press Prefix+z to unzoom; also try enlarging terminal window."
            ) from e
        pane_id = (cp.stdout or "").strip()
        if not self._looks_like_pane_id(pane_id):
            raise RuntimeError(f"tmux split-window did not return pane_id: {pane_id!r}")
        return pane_id

    def set_pane_title(self, pane_id: str, title: str) -> None:
        if not pane_id:
            return
        self._tmux_run(["select-pane", "-t", pane_id, "-T", title or ""], check=False)

    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
        """
        Set a tmux user option (e.g. `@ccb_agent`) at pane scope.

        This is used to keep UI labeling stable even if programs modify `pane_title`.
        """
        if not pane_id:
            return
        opt = (name or "").strip()
        if not opt:
            return
        if not opt.startswith("@"):
            opt = "@" + opt
        self._tmux_run(["set-option", "-p", "-t", pane_id, opt, value or ""], check=False)

    def find_pane_by_title_marker(self, marker: str) -> Optional[str]:
        marker = (marker or "").strip()
        if not marker:
            return None
        cp = self._tmux_run(["list-panes", "-a", "-F", "#{pane_id}\t#{pane_title}"], capture=True)
        if cp.returncode != 0:
            return None
        for line in (cp.stdout or "").splitlines():
            if not line.strip():
                continue
            if "\t" in line:
                pid, title = line.split("\t", 1)
            else:
                parts = line.split(" ", 1)
                pid, title = (parts[0], parts[1] if len(parts) > 1 else "")
            if (title or "").startswith(marker):
                pid = pid.strip()
                if self._looks_like_pane_id(pid):
                    return pid
        return None

    def get_pane_content(self, pane_id: str, lines: int = 20) -> Optional[str]:
        if not pane_id:
            return None
        n = max(1, int(lines))
        cp = self._tmux_run(["capture-pane", "-t", pane_id, "-p", "-S", f"-{n}"], capture=True)
        if cp.returncode != 0:
            return None
        text = cp.stdout or ""
        return self._ANSI_RE.sub("", text)

    # Keep compatibility with existing daemon code
    def get_text(self, pane_id: str, lines: int = 20) -> Optional[str]:
        return self.get_pane_content(pane_id, lines=lines)

    def is_pane_alive(self, pane_id: str) -> bool:
        if not pane_id:
            return False
        cp = self._tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_dead}"], capture=True)
        if cp.returncode != 0:
            return False
        return (cp.stdout or "").strip() == "0"

    def _ensure_not_in_copy_mode(self, pane_id: str) -> None:
        try:
            cp = self._tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_in_mode}"], capture=True, timeout=1.0)
            if cp.returncode == 0 and (cp.stdout or "").strip() in ("1", "on", "yes"):
                self._tmux_run(["send-keys", "-t", pane_id, "-X", "cancel"], check=False)
        except Exception:
            pass

    def send_text(self, pane_id: str, text: str) -> None:
        sanitized = (text or "").replace("\r", "").strip()
        if not sanitized:
            return

        # Legacy: treat `pane_id` as a tmux session name for pure-tmux mode.
        if not self._looks_like_tmux_target(pane_id):
            session = pane_id
            if "\n" not in sanitized and len(sanitized) <= 200:
                self._tmux_run(["send-keys", "-t", session, "-l", sanitized], check=True)
                self._tmux_run(["send-keys", "-t", session, "Enter"], check=True)
                return
            buffer_name = f"ccb-tb-{os.getpid()}-{int(time.time() * 1000)}"
            self._tmux_run(["load-buffer", "-b", buffer_name, "-"], check=True, input_bytes=sanitized.encode("utf-8"))
            try:
                self._tmux_run(["paste-buffer", "-t", session, "-b", buffer_name, "-p"], check=True)
                enter_delay = _env_float("CCB_TMUX_ENTER_DELAY", 0.0)
                if enter_delay:
                    time.sleep(enter_delay)
                self._tmux_run(["send-keys", "-t", session, "Enter"], check=True)
            finally:
                self._tmux_run(["delete-buffer", "-b", buffer_name], check=False)
            return

        # Pane-oriented: bracketed paste + unique tmux buffer + cleanup
        self._ensure_not_in_copy_mode(pane_id)
        buffer_name = f"ccb-tb-{os.getpid()}-{int(time.time() * 1000)}"
        self._tmux_run(["load-buffer", "-b", buffer_name, "-"], check=True, input_bytes=sanitized.encode("utf-8"))
        try:
            self._tmux_run(["paste-buffer", "-p", "-t", pane_id, "-b", buffer_name], check=True)
            enter_delay = _env_float("CCB_TMUX_ENTER_DELAY", 0.0)
            if enter_delay:
                time.sleep(enter_delay)
            self._tmux_run(["send-keys", "-t", pane_id, "Enter"], check=True)
        finally:
            self._tmux_run(["delete-buffer", "-b", buffer_name], check=False)

    def send_key(self, pane_id: str, key: str) -> bool:
        key = (key or "").strip()
        if not pane_id or not key:
            return False
        try:
            cp = self._tmux_run(["send-keys", "-t", pane_id, key], capture=True, timeout=2.0)
            return cp.returncode == 0
        except Exception:
            return False

    def is_alive(self, pane_id: str) -> bool:
        # Backward-compatible: pane_id may be a session name.
        if not pane_id:
            return False
        if self._looks_like_tmux_target(pane_id):
            return self.is_pane_alive(pane_id)
        cp = self._tmux_run(["has-session", "-t", pane_id], capture=True)
        return cp.returncode == 0

    def kill_pane(self, pane_id: str) -> None:
        if not pane_id:
            return
        if self._looks_like_tmux_target(pane_id):
            self._tmux_run(["kill-pane", "-t", pane_id], check=False)
        else:
            # Legacy: treat as session name.
            self._tmux_run(["kill-session", "-t", pane_id], check=False)

    def activate(self, pane_id: str) -> None:
        # Best-effort: focus pane if inside tmux; otherwise attach its session if resolvable.
        if not pane_id:
            return
        if self._looks_like_tmux_target(pane_id):
            self._tmux_run(["select-pane", "-t", pane_id], check=False)
            if not os.environ.get("TMUX"):
                try:
                    cp = self._tmux_run(["display-message", "-p", "-t", pane_id, "#{session_name}"], capture=True)
                    sess = (cp.stdout or "").strip()
                    if sess:
                        self._tmux_run(["attach", "-t", sess], check=False)
                except Exception:
                    pass
            return
        self._tmux_run(["attach", "-t", pane_id], check=False)

    def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None,
                     stderr_log_path: str | None = None, remain_on_exit: bool = True) -> None:
        """
        Respawn a pane process (`respawn-pane -k`) to (re)mount an AI CLI session.

        This is daemon-friendly: pane stays stable; only the process is replaced.
        """
        if not pane_id:
            raise ValueError("pane_id is required")

        cmd_body = (cmd or "").strip()
        if not cmd_body:
            raise ValueError("cmd is required")

        start_dir = (cwd or "").strip()
        if start_dir in ("", "."):
            start_dir = ""

        if stderr_log_path:
            log_path = str(Path(stderr_log_path).expanduser().resolve())
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            cmd_body = f"{cmd_body} 2>> {shlex.quote(log_path)}"

        shell = (os.environ.get("CCB_TMUX_SHELL") or "").strip()
        if not shell:
            # Prefer tmux's configured default shell when available.
            try:
                cp = self._tmux_run(["show-option", "-gqv", "default-shell"], capture=True, timeout=1.0)
                shell = (cp.stdout or "").strip()
            except Exception:
                shell = ""
        if not shell:
            shell = (os.environ.get("SHELL") or "").strip()
        if not shell:
            shell = _default_shell()[0]

        flags_raw = (os.environ.get("CCB_TMUX_SHELL_FLAGS") or "").strip()
        if flags_raw:
            flags = shlex.split(flags_raw)
        else:
            shell_name = Path(shell).name.lower()
            # Avoid assuming bash-style combined flags on shells like fish.
            if shell_name in {"bash", "zsh", "ksh"}:
                flags = ["-l", "-i", "-c"]
            elif shell_name == "fish":
                flags = ["-l", "-i", "-c"]
            elif shell_name in {"sh", "dash"}:
                flags = ["-c"]
            else:
                # Unknown shell: keep it minimal for compatibility.
                flags = ["-c"]

        full_argv = [shell, *flags, cmd_body]
        full = " ".join(shlex.quote(a) for a in full_argv)

        tmux_args = ["respawn-pane", "-k", "-t", pane_id]
        if start_dir:
            tmux_args.extend(["-c", start_dir])
        tmux_args.append(full)
        self._tmux_run(tmux_args, check=True)
        if remain_on_exit:
            self._tmux_run(["set-option", "-p", "-t", pane_id, "remain-on-exit", "on"], check=False)

    def save_crash_log(self, pane_id: str, crash_log_path: str, *, lines: int = 1000) -> None:
        text = self.get_pane_content(pane_id, lines=lines) or ""
        p = Path(crash_log_path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50,
                    parent_pane: Optional[str] = None) -> str:
        """
        Create a new pane and run `cmd` inside it.

        - If `parent_pane` is provided (or we are inside tmux), split that pane.
        - If called outside tmux without `parent_pane`, create a detached session and return its root pane id.
        """
        cmd = (cmd or "").strip()
        cwd = (cwd or ".").strip() or "."

        if parent_pane or os.environ.get("TMUX_PANE"):
            base = parent_pane or self.get_current_pane_id()
            new_pane = self.split_pane(base, direction=direction, percent=percent)
            if cmd:
                self.respawn_pane(new_pane, cmd=cmd, cwd=cwd)
            return new_pane

        # Outside tmux: create a new detached tmux session as a root container.
        session_name = f"ccb-{Path(cwd).name}-{int(time.time()) % 100000}-{os.getpid()}"
        self._tmux_run(["new-session", "-d", "-s", session_name, "-c", cwd], check=True)
        cp = self._tmux_run(["list-panes", "-t", session_name, "-F", "#{pane_id}"], capture=True, check=True)
        pane_id = (cp.stdout or "").splitlines()[0].strip() if (cp.stdout or "").strip() else ""
        if not self._looks_like_pane_id(pane_id):
            raise RuntimeError(f"tmux failed to resolve root pane_id for session {session_name!r}")
        if cmd:
            self.respawn_pane(pane_id, cmd=cmd, cwd=cwd)
        return pane_id


class WeztermBackend(TerminalBackend):
    _wezterm_bin: Optional[str] = None
    CCB_TITLE_MARKER = "CCB"

    @classmethod
    def _cli_base_args(cls) -> list[str]:
        args = [cls._bin(), "cli"]
        wezterm_class = os.environ.get("CODEX_WEZTERM_CLASS") or os.environ.get("WEZTERM_CLASS")
        if wezterm_class:
            args.extend(["--class", wezterm_class])
        if os.environ.get("CODEX_WEZTERM_PREFER_MUX", "").lower() in {"1", "true", "yes", "on"}:
            args.append("--prefer-mux")
        if os.environ.get("CODEX_WEZTERM_NO_AUTO_START", "").lower() in {"1", "true", "yes", "on"}:
            args.append("--no-auto-start")
        return args

    @classmethod
    def _bin(cls) -> str:
        if cls._wezterm_bin:
            return cls._wezterm_bin
        found = _get_wezterm_bin()
        cls._wezterm_bin = found or "wezterm"
        return cls._wezterm_bin

    def _send_key_cli(self, pane_id: str, key: str) -> bool:
        """
        Send a key to the target pane using `wezterm cli send-key`.

        WezTerm CLI syntax differs across versions; try a couple variants.
        """
        key = (key or "").strip()
        if not key:
            return False

        variants = [key]
        if key.lower() == "enter":
            variants = ["Enter", "Return", key]
        elif key.lower() in {"escape", "esc"}:
            variants = ["Escape", "Esc", key]

        for variant in variants:
            # Variant A: `send-key --pane-id <id> --key <KeyName>`
            result = _run(
                [*self._cli_base_args(), "send-key", "--pane-id", pane_id, "--key", variant],
                capture_output=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                return True

            # Variant B: `send-key --pane-id <id> <KeyName>`
            result = _run(
                [*self._cli_base_args(), "send-key", "--pane-id", pane_id, variant],
                capture_output=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                return True

        return False

    def _send_enter(self, pane_id: str) -> None:
        """
        Send Enter to submit the current input in a TUI.

        Some TUIs in raw mode may ignore a pasted newline byte and require a real key event;
        prefer `wezterm cli send-key` when available.
        """
        # Windows needs longer delay
        default_delay = 0.05 if os.name == "nt" else 0.01
        enter_delay = _env_float("CCB_WEZTERM_ENTER_DELAY", default_delay)
        if enter_delay:
            time.sleep(enter_delay)

        env_method_raw = os.environ.get("CCB_WEZTERM_ENTER_METHOD")
        # Default behavior is intentionally unchanged on non-Windows platforms:
        # previously we used `send-text` with a CR byte; keep that unless the user overrides.
        default_method = "auto" if os.name == "nt" else "text"
        method = (env_method_raw or default_method).strip().lower()
        if method not in {"auto", "key", "text"}:
            method = default_method

        # Retry mechanism for reliability (Windows native occasionally drops Enter)
        max_retries = 3
        for attempt in range(max_retries):
            # Only enable "auto key" behavior by default on native Windows.
            # Users can force key injection everywhere via CCB_WEZTERM_ENTER_METHOD=key.
            if method == "key" or (method == "auto" and os.name == "nt"):
                if self._send_key_cli(pane_id, "Enter"):
                    return

            # Fallback: send CR byte; works for shells/readline, but not for all raw-mode TUIs.
            if method in {"auto", "text", "key"}:
                result = _run(
                    [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                    input=b"\r",
                    capture_output=True,
                )
                if result.returncode == 0:
                    return

            if attempt < max_retries - 1:
                time.sleep(0.05)

    def send_text(self, pane_id: str, text: str) -> None:
        sanitized = text.replace("\r", "").strip()
        if not sanitized:
            return

        has_newlines = "\n" in sanitized

        # Single-line: always avoid paste mode (prevents Codex showing "[Pasted Content ...]").
        # Use argv for short text; stdin for long text to avoid command-line length/escaping issues.
        if not has_newlines:
            if len(sanitized) <= 200:
                _run(
                    [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste", sanitized],
                    check=True,
                )
            else:
                _run(
                    [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                    input=sanitized.encode("utf-8"),
                    check=True,
                )
            self._send_enter(pane_id)
            return

        # Slow path: multiline or long text -> use paste mode (bracketed paste)
        _run(
            [*self._cli_base_args(), "send-text", "--pane-id", pane_id],
            input=sanitized.encode("utf-8"),
            check=True,
        )

        # Wait for TUI to process bracketed paste content
        paste_delay = _env_float("CCB_WEZTERM_PASTE_DELAY", 0.1)
        if paste_delay:
            time.sleep(paste_delay)

        self._send_enter(pane_id)

    def _list_panes(self) -> list[dict]:
        try:
            result = _run(
                [*self._cli_base_args(), "list", "--format", "json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                return []
            panes = json.loads(result.stdout)
            return panes if isinstance(panes, list) else []
        except Exception:
            return []

    def _pane_id_by_title_marker(self, panes: list[dict], marker: str) -> Optional[str]:
        if not marker:
            return None
        for pane in panes:
            title = pane.get("title") or ""
            if title.startswith(marker):
                pane_id = pane.get("pane_id")
                if pane_id is not None:
                    return str(pane_id)
        return None

    def find_pane_by_title_marker(self, marker: str) -> Optional[str]:
        panes = self._list_panes()
        return self._pane_id_by_title_marker(panes, marker)

    def is_alive(self, pane_id: str) -> bool:
        panes = self._list_panes()
        if not panes:
            return False
        if any(str(p.get("pane_id")) == str(pane_id) for p in panes):
            return True
        return self._pane_id_by_title_marker(panes, pane_id) is not None

    def get_text(self, pane_id: str, lines: int = 20) -> Optional[str]:
        """Get text content from pane (last N lines)."""
        try:
            result = _run(
                [*self._cli_base_args(), "get-text", "--pane-id", pane_id],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2.0,
            )
            if result.returncode != 0:
                return None
            text = result.stdout
            if lines and text:
                text_lines = text.splitlines()
                return "\n".join(text_lines[-lines:])
            return text
        except Exception:
            return None

    def send_key(self, pane_id: str, key: str) -> bool:
        """Send a special key (e.g., 'Escape', 'Enter') to pane."""
        try:
            if self._send_key_cli(pane_id, key):
                return True
            result = _run(
                [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                input=key.encode("utf-8"),
                capture_output=True,
                timeout=2.0,
            )
            return result.returncode == 0
        except Exception:
            return False

    def kill_pane(self, pane_id: str) -> None:
        _run([*self._cli_base_args(), "kill-pane", "--pane-id", pane_id], stderr=subprocess.DEVNULL)

    def activate(self, pane_id: str) -> None:
        _run([*self._cli_base_args(), "activate-pane", "--pane-id", pane_id])

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: Optional[str] = None) -> str:
        args = [*self._cli_base_args(), "split-pane"]
        force_wsl = os.environ.get("CCB_BACKEND_ENV", "").lower() == "wsl"
        wsl_unc_cwd = _extract_wsl_path_from_unc_like_path(cwd)
        # If the caller is in a WSL UNC path (e.g. Git Bash `/wsl.localhost/...`),
        # default to launching via wsl.exe so the new pane lands in the real WSL path.
        if is_windows() and wsl_unc_cwd and not force_wsl:
            force_wsl = True
        use_wsl_launch = (is_wsl() and _is_windows_wezterm()) or (force_wsl and is_windows())
        if use_wsl_launch:
            in_wsl_pane = bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
            wsl_cwd = wsl_unc_cwd or cwd
            if wsl_unc_cwd is None and ("\\" in cwd or (len(cwd) > 2 and cwd[1] == ":")):
                try:
                    wslpath_cmd = ["wslpath", "-a", cwd] if is_wsl() else ["wsl.exe", "wslpath", "-a", cwd]
                    result = _run(wslpath_cmd, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
                    wsl_cwd = result.stdout.strip()
                except Exception:
                    pass
            if direction == "right":
                args.append("--right")
            elif direction == "bottom":
                args.append("--bottom")
            args.extend(["--percent", str(percent)])
            if parent_pane:
                args.extend(["--pane-id", parent_pane])
            # Do not `exec` here: `cmd` may be a compound shell snippet (e.g. keep-open wrappers).
            startup_script = f"cd {shlex.quote(wsl_cwd)} && {cmd}"
            if in_wsl_pane:
                args.extend(["--", "bash", "-l", "-i", "-c", startup_script])
            else:
                args.extend(["--", "wsl.exe", "bash", "-l", "-i", "-c", startup_script])
        else:
            args.extend(["--cwd", cwd])
            if direction == "right":
                args.append("--right")
            elif direction == "bottom":
                args.append("--bottom")
            args.extend(["--percent", str(percent)])
            if parent_pane:
                args.extend(["--pane-id", parent_pane])
            shell, flag = _default_shell()
            args.extend(["--", shell, flag, cmd])
        try:
            run_cwd = None
            if is_wsl() and _is_windows_wezterm():
                run_cwd = _choose_wezterm_cli_cwd()
            result = _run(
                args,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace",
                cwd=run_cwd,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"WezTerm split-pane failed:\nCommand: {' '.join(args)}\nStderr: {e.stderr}") from e


_backend_cache: Optional[TerminalBackend] = None


def detect_terminal() -> Optional[str]:
    # Priority 1: detect *current* terminal session from env vars.
    if os.environ.get("WEZTERM_PANE"):
        return "wezterm"
    if os.environ.get("TMUX") or os.environ.get("TMUX_PANE"):
        return "tmux"

    # WSL-specific: WezTerm on Windows does not always propagate WEZTERM_PANE into tmux server env
    # (or custom shells), but wezterm CLI may still be reachable via interop.
    if is_wsl() and _is_windows_wezterm() and _wezterm_cli_is_alive():
        return "wezterm"

    return None


def _wezterm_cli_is_alive(*, timeout_s: float = 0.8) -> bool:
    """
    Best-effort probe to see if `wezterm cli` can reach a running WezTerm instance.

    Uses `--no-auto-start` so it won't pop up a new terminal window.
    """
    wez = _get_wezterm_bin()
    if not wez:
        return False
    try:
        cp = _run(
            [wez, "cli", "--no-auto-start", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(0.1, float(timeout_s)),
        )
        return cp.returncode == 0
    except Exception:
        return False


def get_backend(terminal_type: Optional[str] = None) -> Optional[TerminalBackend]:
    global _backend_cache
    if _backend_cache:
        return _backend_cache
    t = terminal_type or detect_terminal()
    if t == "wezterm":
        _backend_cache = WeztermBackend()
    elif t == "tmux":
        _backend_cache = TmuxBackend()
    return _backend_cache


def get_backend_for_session(session_data: dict) -> Optional[TerminalBackend]:
    terminal = session_data.get("terminal", "tmux")
    if terminal == "wezterm":
        return WeztermBackend()
    return TmuxBackend()


def get_pane_id_from_session(session_data: dict) -> Optional[str]:
    terminal = session_data.get("terminal", "tmux")
    if terminal == "wezterm":
        return session_data.get("pane_id")
    # tmux legacy: older session files used `tmux_session` as a pseudo pane_id.
    # New tmux refactor stores real tmux pane IDs (`%12`) in `pane_id`.
    return session_data.get("pane_id") or session_data.get("tmux_session")


@dataclass(frozen=True)
class LayoutResult:
    panes: dict[str, str]      # provider -> pane_id
    root_pane_id: str
    needs_attach: bool
    created_panes: list[str]


def create_auto_layout(
    providers: list[str],
    *,
    cwd: str,
    root_pane_id: str | None = None,
    tmux_session_name: str | None = None,
    percent: int = 50,
    set_markers: bool = True,
    marker_prefix: str = "CCB",
) -> LayoutResult:
    """
    Create tmux split layout for 1–4 providers, returning a provider->pane_id mapping.

    Layout rules (matches docs/tmux-refactor-plan.md):
    - 1 AI: no split
    - 2 AI: left/right
    - 3 AI: left 1 + right top/bottom 2
    - 4 AI: 2x2 grid

    Notes:
    - This function only allocates panes (no provider commands launched).
    - If `set_markers` is True, it sets pane titles to `{marker_prefix}-{provider}`.
      Callers can pass a richer `marker_prefix` (e.g. include session_id) to avoid collisions.
    """
    if not providers:
        raise ValueError("providers must not be empty")
    if len(providers) > 4:
        raise ValueError("providers max is 4 for auto layout")

    backend = TmuxBackend()
    created: list[str] = []
    panes: dict[str, str] = {}

    needs_attach = False

    # Resolve/allocate root pane.
    if root_pane_id:
        root = root_pane_id
    else:
        # Prefer current pane when called from inside tmux.
        try:
            root = backend.get_current_pane_id()
        except Exception:
            # Daemon/outside tmux: create a detached session as a container.
            session_name = (tmux_session_name or f"ccb-{Path(cwd).name}-{int(time.time()) % 100000}-{os.getpid()}").strip()
            if session_name:
                # Reuse if already exists; else create.
                if not backend.is_alive(session_name):
                    backend._tmux_run(["new-session", "-d", "-s", session_name, "-c", cwd], check=True)
                cp = backend._tmux_run(["list-panes", "-t", session_name, "-F", "#{pane_id}"], capture=True, check=True)
                root = (cp.stdout or "").splitlines()[0].strip() if (cp.stdout or "").strip() else ""
            else:
                root = backend.create_pane("", cwd)
            if not root or not root.startswith("%"):
                raise RuntimeError("failed to allocate tmux root pane")
            created.append(root)
            needs_attach = (os.environ.get("TMUX") or "").strip() == ""

    panes[providers[0]] = root

    # Helper to set pane marker title
    def _mark(provider: str, pane_id: str) -> None:
        if not set_markers:
            return
        backend.set_pane_title(pane_id, f"{marker_prefix}-{provider}")

    _mark(providers[0], root)

    if len(providers) == 1:
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    pct = max(1, min(99, int(percent)))

    if len(providers) == 2:
        right = backend.split_pane(root, "right", pct)
        created.append(right)
        panes[providers[1]] = right
        _mark(providers[1], right)
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    if len(providers) == 3:
        right_top = backend.split_pane(root, "right", pct)
        created.append(right_top)
        right_bottom = backend.split_pane(right_top, "bottom", pct)
        created.append(right_bottom)
        panes[providers[1]] = right_top
        panes[providers[2]] = right_bottom
        _mark(providers[1], right_top)
        _mark(providers[2], right_bottom)
        return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)

    # 4 providers: 2x2 grid
    right_top = backend.split_pane(root, "right", pct)
    created.append(right_top)
    left_bottom = backend.split_pane(root, "bottom", pct)
    created.append(left_bottom)
    right_bottom = backend.split_pane(right_top, "bottom", pct)
    created.append(right_bottom)

    panes[providers[1]] = right_top
    panes[providers[2]] = left_bottom
    panes[providers[3]] = right_bottom
    _mark(providers[1], right_top)
    _mark(providers[2], left_bottom)
    _mark(providers[3], right_bottom)

    return LayoutResult(panes=panes, root_pane_id=root, needs_attach=needs_attach, created_panes=created)
