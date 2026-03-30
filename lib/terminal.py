from __future__ import annotations
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import tempfile
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


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _sanitize_filename(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


_LAST_PANE_LOG_CLEAN: float = 0.0


def _pane_log_root() -> Path:
    try:
        from askd_runtime import run_dir
    except Exception:
        return Path.home() / ".cache" / "ccb"
    return run_dir() / "pane-logs"


def _pane_log_dir(backend: str, socket_name: str | None) -> Path:
    root = _pane_log_root()
    if backend == "tmux":
        if socket_name:
            safe = _sanitize_filename(socket_name) or "default"
            return root / f"tmux-{safe}"
        return root / "tmux"
    safe_backend = _sanitize_filename(backend) or "pane"
    return root / safe_backend


def _pane_log_path_for(pane_id: str, backend: str, socket_name: str | None) -> Path:
    pid = (pane_id or "").strip().replace("%", "")
    safe = _sanitize_filename(pid) or "pane"
    return _pane_log_dir(backend, socket_name) / f"pane-{safe}.log"


def _maybe_trim_log(path: Path) -> None:
    max_bytes = max(0, _env_int("CCB_PANE_LOG_MAX_BYTES", 10 * 1024 * 1024))
    if max_bytes <= 0:
        return
    try:
        size = path.stat().st_size
    except Exception:
        return
    if size <= max_bytes:
        return
    try:
        with path.open("rb") as handle:
            handle.seek(-max_bytes, os.SEEK_END)
            tail = handle.read()
    except Exception:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(tail)
            os.replace(tmp_name, path)
        finally:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
    except Exception:
        return


def _cleanup_pane_logs(dir_path: Path) -> None:
    global _LAST_PANE_LOG_CLEAN
    interval_s = _env_float("CCB_PANE_LOG_CLEAN_INTERVAL_S", 600.0)
    now = time.time()
    if interval_s and (now - _LAST_PANE_LOG_CLEAN) < interval_s:
        return
    _LAST_PANE_LOG_CLEAN = now

    ttl_days = _env_int("CCB_PANE_LOG_TTL_DAYS", 7)
    max_files = _env_int("CCB_PANE_LOG_MAX_FILES", 200)
    if ttl_days <= 0 and max_files <= 0:
        return

    try:
        if not dir_path.exists():
            return
    except Exception:
        return

    files: list[Path] = []
    try:
        for entry in dir_path.iterdir():
            if entry.is_file():
                files.append(entry)
    except Exception:
        return

    if ttl_days > 0:
        cutoff = now - (ttl_days * 86400)
        for path in list(files):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    files.remove(path)
            except Exception:
                continue

    if max_files > 0 and len(files) > max_files:
        try:
            files.sort(key=lambda p: p.stat().st_mtime)
        except Exception:
            files.sort(key=lambda p: p.name)
        extra = len(files) - max_files
        for path in files[:extra]:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                continue


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

    def pane_log_path(self, pane_id: str) -> Optional[Path]:
        pid = (pane_id or "").strip()
        if not pid:
            return None
        try:
            return _pane_log_path_for(pid, "tmux", self._socket_name)
        except Exception:
            return None

    def ensure_pane_log(self, pane_id: str) -> Optional[Path]:
        """
        Ensure tmux pipe-pane logging is enabled for this pane.
        Returns the log path when available.
        """
        pid = (pane_id or "").strip()
        if not pid:
            return None
        log_path = self.pane_log_path(pid)
        if not log_path:
            return None
        try:
            _cleanup_pane_logs(log_path.parent)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.touch(exist_ok=True)
        except Exception:
            pass
        try:
            # Use tee (no shell redirection) so tmux can exec reliably.
            cmd = f"tee -a {log_path}"
            self._tmux_run(["pipe-pane", "-o", "-t", pid, cmd], check=False)
        except Exception:
            return log_path
        try:
            _maybe_trim_log(log_path)
        except Exception:
            pass
        try:
            info = getattr(self, "_pane_log_info", None)
            if info is None:
                info = {}
                self._pane_log_info = info
            info[str(pid)] = time.time()
        except Exception:
            pass
        return log_path

    def refresh_pane_logs(self) -> None:
        """
        Best-effort reattach pipe-pane for known panes. Useful when tmux loses pipe state.
        """
        info = getattr(self, "_pane_log_info", None)
        if not isinstance(info, dict):
            return
        for pid in list(info.keys()):
            try:
                if not self.is_alive(pid):
                    continue
                cp = self._tmux_run(["display-message", "-p", "-t", pid, "#{pane_pipe}"], capture=True)
                if (cp.stdout or "").strip() == "1":
                    continue
                self.ensure_pane_log(pid)
            except Exception:
                continue

    @staticmethod
    def _looks_like_pane_id(value: str) -> bool:
        v = (value or "").strip()
        return v.startswith("%")

    def pane_exists(self, pane_id: str) -> bool:
        """
        Return True if the tmux pane target exists.

        A pane can exist even if its process has exited (`#{pane_dead} == 1`).
        """
        if not self._looks_like_pane_id(pane_id):
            return False
        try:
            cp = self._tmux_run(["display-message", "-p", "-t", pane_id, "#{pane_id}"], capture=True, timeout=0.5)
            return cp.returncode == 0 and (cp.stdout or "").strip().startswith("%")
        except Exception:
            return False

    @staticmethod
    def _looks_like_tmux_target(value: str) -> bool:
        v = (value or "").strip()
        if not v:
            return False
        return v.startswith("%") or (":" in v) or ("." in v)

    def get_current_pane_id(self) -> str:
        """
        Return current tmux pane id in `%xx` format.

        Notes:
        - Prefer `$TMUX_PANE` because it refers to the pane where this process runs; it stays
          stable even if splits change the client's focused pane.
        - `$TMUX_PANE` can become stale if that pane was killed/replaced; fall back to querying tmux.
        """
        env_pane = (os.environ.get("TMUX_PANE") or "").strip()
        if self._looks_like_pane_id(env_pane) and self.pane_exists(env_pane):
            return env_pane

        try:
            cp = self._tmux_run(["display-message", "-p", "#{pane_id}"], capture=True, timeout=0.5)
            out = (cp.stdout or "").strip()
            if self._looks_like_pane_id(out) and self.pane_exists(out):
                return out
        except Exception:
            pass

        raise RuntimeError("tmux current pane id not available")

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

        # Allow splitting a "dead" pane (remain-on-exit); only fail if the pane target doesn't exist.
        if self._looks_like_pane_id(parent_pane_id) and not self.pane_exists(parent_pane_id):
            raise RuntimeError(f"Cannot split: pane {parent_pane_id} does not exist")

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

    def find_pane_by_title_marker(self, marker: str, cwd_hint: str = "") -> Optional[str]:
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
            # Use random suffix to avoid collision under high concurrency
            import random
            buffer_name = f"ccb-tb-{os.getpid()}-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
            self._tmux_run(["load-buffer", "-b", buffer_name, "-"], check=True, input_bytes=sanitized.encode("utf-8"))
            try:
                self._tmux_run(["paste-buffer", "-t", session, "-b", buffer_name, "-p"], check=True)
                enter_delay = _env_float("CCB_TMUX_ENTER_DELAY", 0.5)
                if enter_delay:
                    time.sleep(enter_delay)
                self._tmux_run(["send-keys", "-t", session, "Enter"], check=True)
            finally:
                self._tmux_run(["delete-buffer", "-b", buffer_name], check=False)
            return

        # Pane-oriented: bracketed paste + unique tmux buffer + cleanup
        self._ensure_not_in_copy_mode(pane_id)
        # Use random suffix to avoid collision under high concurrency
        import random
        buffer_name = f"ccb-tb-{os.getpid()}-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
        self._tmux_run(["load-buffer", "-b", buffer_name, "-"], check=True, input_bytes=sanitized.encode("utf-8"))
        try:
            self._tmux_run(["paste-buffer", "-p", "-t", pane_id, "-b", buffer_name], check=True)
            enter_delay = _env_float("CCB_TMUX_ENTER_DELAY", 0.5)
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

        try:
            self.ensure_pane_log(pane_id)
        except Exception:
            pass

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

        # Prevent a race where a fast-exiting command closes the pane before we can set remain-on-exit.
        if remain_on_exit:
            self._tmux_run(["set-option", "-p", "-t", pane_id, "remain-on-exit", "on"], check=False)

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

        base: str | None = (parent_pane or "").strip() or None
        if not base:
            try:
                base = self.get_current_pane_id()
            except Exception:
                base = None

        if base:
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

    def __init__(self) -> None:
        self._last_list_error: Optional[str] = None

    def last_list_error(self) -> Optional[str]:
        return self._last_list_error

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
        # Default to "auto" (prefer key injection) on all platforms for better TUI compatibility
        default_method = "auto"
        method = (env_method_raw or default_method).strip().lower()
        if method not in {"auto", "key", "text"}:
            method = default_method

        # Retry mechanism for reliability
        max_retries = 3
        for attempt in range(max_retries):
            # Try key injection first (works better with raw-mode TUIs)
            if method in {"key", "auto"}:
                if self._send_key_cli(pane_id, "Enter"):
                    return

            # Fallback: send CR byte; works for shells/readline, but not for all raw-mode TUIs.
            if method in {"auto", "text"}:
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

    def pane_log_path(self, pane_id: str) -> Optional[Path]:
        pid = (pane_id or "").strip()
        if not pid:
            return None
        try:
            return _pane_log_path_for(pid, "wezterm", None)
        except Exception:
            return None

    def ensure_pane_log(self, pane_id: str) -> Optional[Path]:
        """
        WezTerm doesn't expose a stable stream capture API; create the log file path
        for consistency so higher layers can rely on a predictable location.
        """
        log_path = self.pane_log_path(pane_id)
        if not log_path:
            return None
        try:
            _cleanup_pane_logs(log_path.parent)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.touch(exist_ok=True)
        except Exception:
            pass
        return log_path

    @staticmethod
    def _parse_list_output(text: str) -> list[dict]:
        lines = [line.rstrip() for line in (text or "").splitlines() if line.strip()]
        if not lines:
            return []

        header = lines[0]
        header_upper = header.upper()

        def parse_with_header() -> list[dict]:
            cols = [(m.start(), m.group(0).upper()) for m in re.finditer(r"\S+", header)]
            if not cols:
                return []
            col_defs: list[tuple[str, int, Optional[int]]] = []
            for idx, (start, name) in enumerate(cols):
                end = cols[idx + 1][0] if idx + 1 < len(cols) else None
                col_defs.append((name, start, end))

            def find_col(*names: str) -> Optional[tuple[int, Optional[int]]]:
                for col_name, start, end in col_defs:
                    if col_name in names:
                        return start, end
                return None

            pane_slice = find_col("PANEID", "PANE_ID", "PANE")
            title_slice = find_col("TITLE")
            entries: list[dict] = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                entry: dict = {}
                if pane_slice:
                    start, end = pane_slice
                    raw = line[start:] if end is None else line[start:end]
                    pane_id = raw.strip()
                    if pane_id:
                        entry["pane_id"] = pane_id
                if title_slice:
                    start, end = title_slice
                    raw = line[start:] if end is None else line[start:end]
                    title = raw.strip()
                    if title:
                        entry["title"] = title
                if entry.get("pane_id"):
                    entries.append(entry)
            return entries

        if "PANE" in header_upper:
            entries = parse_with_header()
            if entries:
                return entries

        # Fallback: parse rows without headers, best-effort pane id detection
        entries: list[dict] = []
        for line in lines:
            tokens = line.split()
            pane_token = next((tok for tok in tokens if tok.isdigit()), None)
            if pane_token:
                entries.append({"pane_id": pane_token})
        return entries

    def _list_panes(self) -> Optional[list[dict]]:
        self._last_list_error = None
        try:
            result = _run(
                [*self._cli_base_args(), "list", "--format", "json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1.0,
            )
            if result.returncode == 0:
                try:
                    panes = json.loads(result.stdout)
                except Exception as exc:
                    self._last_list_error = f"wezterm cli list json parse failed: {exc}"
                else:
                    if isinstance(panes, list):
                        return panes
                    self._last_list_error = "wezterm cli list json output is not a list"
            else:
                err = (result.stderr or result.stdout or "").strip()
                if err:
                    self._last_list_error = f"wezterm cli list failed ({result.returncode}): {err}"
                else:
                    self._last_list_error = f"wezterm cli list failed ({result.returncode})"
        except Exception as exc:
            self._last_list_error = f"wezterm cli list failed: {exc}"

        # Fallback: older WezTerm versions may not support --format json.
        try:
            fallback = _run(
                [*self._cli_base_args(), "list"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1.0,
            )
            if fallback.returncode == 0:
                panes = self._parse_list_output(fallback.stdout)
                if panes:
                    self._last_list_error = None
                    return panes
                if (fallback.stdout or "").strip():
                    self._last_list_error = "wezterm cli list returned unparseable output"
                    return None
                return []
            err = (fallback.stderr or fallback.stdout or "").strip()
            if err:
                self._last_list_error = f"wezterm cli list failed ({fallback.returncode}): {err}"
            else:
                self._last_list_error = f"wezterm cli list failed ({fallback.returncode})"
        except Exception as exc:
            self._last_list_error = f"wezterm cli list failed: {exc}"
        return None

    @staticmethod
    def _extract_cwd_path(file_url: str) -> str:
        """Extract filesystem path from a WezTerm file:// CWD URL."""
        if not file_url:
            return ""
        url = str(file_url).strip()
        if not url.startswith("file://"):
            return url
        # file:///path or file://hostname/path
        rest = url[7:]  # strip "file://"
        if rest.startswith("/"):
            path = rest
        else:
            # file://hostname/path -> /path
            slash = rest.find("/")
            path = rest[slash:] if slash >= 0 else ""
        # URL-decode percent-encoded characters (e.g. spaces as %20)
        try:
            from urllib.parse import unquote
            path = unquote(path)
        except Exception:
            pass
        # Windows: file:///C:/path -> /C:/path, strip leading slash before drive letter
        if len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return path.rstrip("/") or "/"

    @staticmethod
    def _cwd_matches(pane_cwd: str, work_dir: str) -> bool:
        """Check if a pane's CWD matches the expected work directory."""
        if not pane_cwd or not work_dir:
            return False
        extracted = WeztermBackend._extract_cwd_path(pane_cwd)
        if not extracted:
            return False
        try:
            return os.path.normpath(extracted) == os.path.normpath(work_dir)
        except Exception:
            return False

    def _pane_id_by_title_marker(self, panes: list[dict], marker: str, cwd_hint: str = "") -> Optional[str]:
        if not marker:
            return None
        cwd_hint = (cwd_hint or "").strip()
        # When cwd_hint is provided, prefer panes matching both marker AND CWD
        # before falling back to first-match. This prevents cross-project routing
        # when multiple WezTerm windows share the same title marker.
        if cwd_hint:
            for pane in panes:
                title = pane.get("title") or ""
                if title.startswith(marker):
                    if self._cwd_matches(pane.get("cwd", ""), cwd_hint):
                        pane_id = pane.get("pane_id")
                        if pane_id is not None:
                            return str(pane_id)
        # Fallback: first marker match (original behaviour, tmux-compatible).
        for pane in panes:
            title = pane.get("title") or ""
            if title.startswith(marker):
                pane_id = pane.get("pane_id")
                if pane_id is not None:
                    return str(pane_id)
        return None

    def find_pane_by_title_marker(self, marker: str, cwd_hint: str = "") -> Optional[str]:
        panes = self._list_panes()
        if panes is None:
            return None
        return self._pane_id_by_title_marker(panes, marker, cwd_hint)

    def pane_belongs_to_cwd(self, pane_id: str, work_dir: str) -> bool:
        """Return True if pane's CWD matches work_dir, or if CWD cannot be determined (fail-open)."""
        panes = self._list_panes()
        if not panes:
            return True  # Can't verify — assume OK
        for pane in panes:
            if str(pane.get("pane_id")) == str(pane_id):
                cwd = pane.get("cwd", "")
                if not cwd:
                    return True  # No CWD info — assume OK
                return self._cwd_matches(cwd, work_dir)
        return False  # Pane not found in list

    def is_alive(self, pane_id: str) -> bool:
        panes = self._list_panes()
        if panes is None:
            return False
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
        key = (key or "").strip()
        if not pane_id or not key:
            return False
        try:
            if self._send_key_cli(pane_id, key):
                return True
            lower = key.lower()
            if lower in {"enter", "return"}:
                payload = b"\r"
            elif lower in {"escape", "esc"}:
                payload = b"\x1b"
            elif len(key) == 1:
                payload = key.encode("utf-8")
            else:
                return False
            result = _run(
                [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                input=payload,
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


def _current_tty() -> str | None:
    for fd in (0, 1, 2):
        try:
            return os.ttyname(fd)
        except Exception:
            continue
    return None


def _inside_tmux() -> bool:
    if not (os.environ.get("TMUX") or os.environ.get("TMUX_PANE")):
        return False
    if not shutil.which("tmux"):
        return False

    tty = _current_tty()
    pane = (os.environ.get("TMUX_PANE") or "").strip()

    if pane:
        try:
            cp = _run(
                ["tmux", "display-message", "-p", "-t", pane, "#{pane_tty}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            pane_tty = (cp.stdout or "").strip()
            if cp.returncode == 0 and tty and pane_tty == tty:
                return True
        except Exception:
            pass

    if tty:
        try:
            cp = _run(
                ["tmux", "display-message", "-p", "#{client_tty}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            client_tty = (cp.stdout or "").strip()
            if cp.returncode == 0 and client_tty == tty:
                return True
        except Exception:
            pass

    if not tty and pane:
        try:
            cp = _run(
                ["tmux", "display-message", "-p", "-t", pane, "#{pane_id}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.5,
            )
            pane_id = (cp.stdout or "").strip()
            if cp.returncode == 0 and pane_id.startswith("%"):
                return True
        except Exception:
            pass

    return False


def _inside_wezterm() -> bool:
    return bool((os.environ.get("WEZTERM_PANE") or "").strip())


def detect_terminal() -> Optional[str]:
    # Priority 1: detect *current* terminal session from env vars.
    # Check tmux first - it's the "inner" environment when running WezTerm with tmux.
    if _inside_tmux():
        return "tmux"
    if _inside_wezterm():
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
