#!/usr/bin/env python3
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
from pathlib import Path
from typing import Optional


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except Exception:
        return False


def _load_cached_wezterm_bin() -> str | None:
    """读取安装时缓存的 WezTerm 路径"""
    config = Path.home() / ".config/ccb/env"
    if config.exists():
        try:
            for line in config.read_text().splitlines():
                if line.startswith("CODEX_WEZTERM_BIN="):
                    path = line.split("=", 1)[1].strip()
                    if path and Path(path).exists():
                        return path
        except Exception:
            pass
    return None


_cached_wezterm_bin: str | None = None


def _get_wezterm_bin() -> str | None:
    """获取 WezTerm 路径（带缓存）"""
    global _cached_wezterm_bin
    if _cached_wezterm_bin:
        return _cached_wezterm_bin
    # 优先级: 环境变量 > 安装缓存 > PATH > 硬编码路径
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
    """检测 WezTerm 是否运行在 Windows 上"""
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
    def send_text(self, session: str, text: str) -> None:
        sanitized = text.replace("\r", "").strip()
        if not sanitized:
            return
        # Fast-path for typical short, single-line commands (fewer tmux subprocess calls).
        if "\n" not in sanitized and len(sanitized) <= 200:
            subprocess.run(["tmux", "send-keys", "-t", session, "-l", sanitized], check=True)
            subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], check=True)
            return

        buffer_name = f"tb-{os.getpid()}-{int(time.time() * 1000)}"
        encoded = (sanitized + "\n").encode("utf-8")
        subprocess.run(["tmux", "load-buffer", "-b", buffer_name, "-"], input=encoded, check=True)
        subprocess.run(["tmux", "paste-buffer", "-t", session, "-b", buffer_name, "-p"], check=True)
        time.sleep(0.5)
        subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], check=True)
        subprocess.run(["tmux", "delete-buffer", "-b", buffer_name], stderr=subprocess.DEVNULL)

    def is_alive(self, session: str) -> bool:
        result = subprocess.run(["tmux", "has-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0

    def kill_pane(self, session: str) -> None:
        subprocess.run(["tmux", "kill-session", "-t", session], stderr=subprocess.DEVNULL)

    def activate(self, session: str) -> None:
        subprocess.run(["tmux", "attach", "-t", session])

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: Optional[str] = None) -> str:
        session_name = f"ai-{int(time.time()) % 100000}-{os.getpid()}"
        subprocess.run(["tmux", "new-session", "-d", "-s", session_name, "-c", cwd, cmd], check=True)
        return session_name


class Iterm2Backend(TerminalBackend):
    """iTerm2 后端，使用 it2 CLI (pip install it2)"""
    _it2_bin: Optional[str] = None

    @classmethod
    def _bin(cls) -> str:
        if cls._it2_bin:
            return cls._it2_bin
        override = os.environ.get("CODEX_IT2_BIN") or os.environ.get("IT2_BIN")
        if override:
            cls._it2_bin = override
            return override
        cls._it2_bin = shutil.which("it2") or "it2"
        return cls._it2_bin

    def send_text(self, session_id: str, text: str) -> None:
        sanitized = text.replace("\r", "").strip()
        if not sanitized:
            return
        # 类似 WezTerm 的方式：先发送文本，再发送回车
        # it2 session send 发送文本（不带换行）
        subprocess.run(
            [self._bin(), "session", "send", sanitized, "--session", session_id],
            check=True,
        )
        # 等待一点时间，让 TUI 处理输入
        time.sleep(0.01)
        # 发送回车键（使用 \r）
        subprocess.run(
            [self._bin(), "session", "send", "\r", "--session", session_id],
            check=True,
        )

    def is_alive(self, session_id: str) -> bool:
        try:
            result = subprocess.run(
                [self._bin(), "session", "list", "--json"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                return False
            sessions = json.loads(result.stdout)
            return any(s.get("id") == session_id for s in sessions)
        except Exception:
            return False

    def kill_pane(self, session_id: str) -> None:
        subprocess.run(
            [self._bin(), "session", "close", "--session", session_id, "--force"],
            stderr=subprocess.DEVNULL
        )

    def activate(self, session_id: str) -> None:
        subprocess.run([self._bin(), "session", "focus", session_id])

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: Optional[str] = None) -> str:
        # iTerm2 分屏：vertical 对应 right，horizontal 对应 bottom
        args = [self._bin(), "session", "split"]
        if direction == "right":
            args.append("--vertical")
        # 如果有 parent_pane，指定目标 session
        if parent_pane:
            args.extend(["--session", parent_pane])

        result = subprocess.run(args, capture_output=True, text=True, check=True)
        # it2 输出格式: "Created new pane: <session_id>"
        output = result.stdout.strip()
        if ":" in output:
            new_session_id = output.split(":")[-1].strip()
        else:
            # 尝试从 stderr 或其他地方获取
            new_session_id = output

        # 在新 pane 中执行启动命令
        if new_session_id and cmd:
            # 先 cd 到工作目录，再执行命令
            full_cmd = f"cd {shlex.quote(cwd)} && {cmd}"
            time.sleep(0.2)  # 等待 pane 就绪
            # 使用 send + 回车的方式，与 send_text 保持一致
            subprocess.run(
                [self._bin(), "session", "send", full_cmd, "--session", new_session_id],
                check=True
            )
            time.sleep(0.01)
            subprocess.run(
                [self._bin(), "session", "send", "\r", "--session", new_session_id],
                check=True
            )

        return new_session_id


class WeztermBackend(TerminalBackend):
    _wezterm_bin: Optional[str] = None

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

    def send_text(self, pane_id: str, text: str) -> None:
        sanitized = text.replace("\r", "").strip()
        if not sanitized:
            return
        # tmux 可单独发 Enter 键；wezterm cli 没有 send-key，只能用 send-text 发送控制字符。
        # 经验上，很多交互式 CLI 在“粘贴/多行输入”里不会自动执行；这里将文本和 Enter 分两次发送更可靠。
        subprocess.run(
            [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
            input=sanitized.encode("utf-8"),
            check=True,
        )
        # 给 TUI 一点时间退出“粘贴/突发输入”路径，再发送 Enter 更像真实按键
        time.sleep(0.01)
        try:
            subprocess.run(
                [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                input=b"\r",
                check=True,
            )
        except subprocess.CalledProcessError:
            subprocess.run(
                [*self._cli_base_args(), "send-text", "--pane-id", pane_id, "--no-paste"],
                input=b"\n",
                check=True,
            )

    def is_alive(self, pane_id: str) -> bool:
        try:
            result = subprocess.run([*self._cli_base_args(), "list", "--format", "json"], capture_output=True, text=True)
            if result.returncode != 0:
                return False
            panes = json.loads(result.stdout)
            return any(str(p.get("pane_id")) == str(pane_id) for p in panes)
        except Exception:
            return False

    def kill_pane(self, pane_id: str) -> None:
        subprocess.run([*self._cli_base_args(), "kill-pane", "--pane-id", pane_id], stderr=subprocess.DEVNULL)

    def activate(self, pane_id: str) -> None:
        subprocess.run([*self._cli_base_args(), "activate-pane", "--pane-id", pane_id])

    def create_pane(self, cmd: str, cwd: str, direction: str = "right", percent: int = 50, parent_pane: Optional[str] = None) -> str:
        args = [*self._cli_base_args(), "split-pane"]
        if is_wsl() and _is_windows_wezterm():
            in_wsl_pane = bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
            wsl_cwd = cwd
            wsl_localhost_match = re.match(r'^[/\\]{1,2}wsl\.localhost[/\\][^/\\]+(.+)$', cwd, re.IGNORECASE)
            if wsl_localhost_match:
                wsl_cwd = wsl_localhost_match.group(1).replace('\\', '/')
            elif "\\" in cwd or (len(cwd) > 2 and cwd[1] == ":"):
                try:
                    result = subprocess.run(["wslpath", "-a", cwd], capture_output=True, text=True, check=True)
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
            startup_script = f"cd {shlex.quote(wsl_cwd)} && exec {cmd}"
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
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        return result.stdout.strip()


_backend_cache: Optional[TerminalBackend] = None


def detect_terminal() -> Optional[str]:
    # 优先检测当前环境变量（已在某终端中运行）
    if os.environ.get("WEZTERM_PANE"):
        return "wezterm"
    if os.environ.get("ITERM_SESSION_ID"):
        return "iterm2"
    if os.environ.get("TMUX"):
        return "tmux"
    # 检查配置的二进制覆盖或缓存路径
    if _get_wezterm_bin():
        return "wezterm"
    override = os.environ.get("CODEX_IT2_BIN") or os.environ.get("IT2_BIN")
    if override and Path(override).expanduser().exists():
        return "iterm2"
    # 检查可用的终端工具
    if shutil.which("it2"):
        return "iterm2"
    if shutil.which("tmux") or shutil.which("tmux.exe"):
        return "tmux"
    return None


def get_backend(terminal_type: Optional[str] = None) -> Optional[TerminalBackend]:
    global _backend_cache
    if _backend_cache:
        return _backend_cache
    t = terminal_type or detect_terminal()
    if t == "wezterm":
        _backend_cache = WeztermBackend()
    elif t == "iterm2":
        _backend_cache = Iterm2Backend()
    elif t == "tmux":
        _backend_cache = TmuxBackend()
    return _backend_cache


def get_backend_for_session(session_data: dict) -> Optional[TerminalBackend]:
    terminal = session_data.get("terminal", "tmux")
    if terminal == "wezterm":
        return WeztermBackend()
    elif terminal == "iterm2":
        return Iterm2Backend()
    return TmuxBackend()


def get_pane_id_from_session(session_data: dict) -> Optional[str]:
    terminal = session_data.get("terminal", "tmux")
    if terminal == "wezterm":
        return session_data.get("pane_id")
    elif terminal == "iterm2":
        return session_data.get("pane_id")
    return session_data.get("tmux_session")
