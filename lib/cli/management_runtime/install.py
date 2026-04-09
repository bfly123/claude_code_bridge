from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request


def _env_install_prefix() -> Path | None:
    env_prefix = (os.environ.get("CODEX_INSTALL_PREFIX") or "").strip()
    return Path(env_prefix).expanduser() if env_prefix else None


def _install_dir_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_prefix = _env_install_prefix()
    if env_prefix is not None:
        candidates.append(env_prefix)
    if platform.system() == "Windows":
        candidates.extend(_windows_install_dir_candidates())
    else:
        candidates.append(Path.home() / ".local/share/codex-dual")
    return candidates


def _windows_install_dir_candidates() -> list[Path]:
    candidates: list[Path] = []
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        candidates.append(Path(localappdata) / "codex-dual")
        candidates.append(Path(localappdata) / "claude-code-bridge")
    candidates.append(Path.home() / "AppData/Local/codex-dual")
    return candidates


def _installed_candidate(candidate: Path) -> bool:
    return bool(candidate and (candidate / "ccb").exists())


def find_install_dir(script_root: Path) -> Path:
    if (script_root / "install.sh").exists() or (script_root / "install.ps1").exists():
        return script_root

    for candidate in _install_dir_candidates():
        if _installed_candidate(candidate):
            return candidate
    return script_root


def _missing_installer_message(script_name: str, install_dir: Path) -> int:
    print(f"❌ {script_name} not found in {install_dir}", file=sys.stderr)
    return 1


def _windows_installer_command(install_dir: Path, action: str) -> tuple[list[str], Path]:
    script = install_dir / "install.ps1"
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        action,
        "-InstallPrefix",
        str(install_dir),
    ]
    return cmd, script


def _unix_installer_command(install_dir: Path, action: str) -> tuple[list[str], Path, dict[str, str]]:
    script = install_dir / "install.sh"
    env = os.environ.copy()
    env["CODEX_INSTALL_PREFIX"] = str(install_dir)
    return ["bash", str(script), action], script, env


def run_installer(action: str, *, script_root: Path) -> int:
    install_dir = find_install_dir(script_root)
    if platform.system() == "Windows":
        cmd, script = _windows_installer_command(install_dir, action)
        if not script.exists():
            return _missing_installer_message("install.ps1", install_dir)
        return subprocess.run(cmd).returncode

    cmd, script, env = _unix_installer_command(install_dir, action)
    if not script.exists():
        return _missing_installer_message("install.sh", install_dir)
    return subprocess.run(cmd, env=env).returncode


def _temp_base_candidates(install_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for key in ("CCB_TMPDIR", "TMPDIR", "TEMP", "TMP"):
        value = (os.environ.get(key) or "").strip()
        if value:
            candidates.append(Path(value).expanduser())
    try:
        candidates.append(Path(tempfile.gettempdir()))
    except Exception:
        pass
    candidates.extend(
        [
            Path("/tmp"),
            Path("/var/tmp"),
            Path("/usr/tmp"),
            Path.home() / ".cache" / "ccb" / "tmp",
            install_dir / ".tmp",
            Path.cwd() / ".tmp",
        ]
    )
    return candidates


def _probe_temp_base(base: Path) -> bool:
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / f".ccb_tmp_probe_{os.getpid()}_{int(time.time() * 1000)}"
        probe.write_bytes(b"1")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def pick_temp_base_dir(install_dir: Path) -> Path:
    for base in _temp_base_candidates(install_dir):
        if _probe_temp_base(base):
            return base

    raise RuntimeError(
        "❌ No usable temporary directory found.\n"
        "Fix options:\n"
        "  - Create /tmp (Linux/WSL): sudo mkdir -p /tmp && sudo chmod 1777 /tmp\n"
        "  - Or set TMPDIR/CCB_TMPDIR to a writable path (e.g. export TMPDIR=$HOME/.cache/tmp)"
    )


def _download_with_command(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def _download_with_urllib(url: str, destination: Path) -> bool:
    import ssl

    try:
        urllib.request.urlretrieve(url, destination)
        return True
    except ssl.SSLError:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx) as resp:
            destination.write_bytes(resp.read())
        return True
    except Exception:
        return False


def download_tarball(url: str, destination: Path) -> bool:
    if shutil.which("curl"):
        if _download_with_command(["curl", "-fsSL", "-o", str(destination), url]):
            return True
    if shutil.which("wget"):
        if _download_with_command(["wget", "-q", "-O", str(destination), url]):
            return True
    return _download_with_urllib(url, destination)


def _ensure_safe_tar_members(tar: tarfile.TarFile, destination: Path) -> None:
    for member in tar.getmembers():
        member_path = (destination / member.name).resolve()
        if not str(member_path).startswith(str(destination) + os.sep):
            raise RuntimeError(f"Unsafe tar member path: {member.name}")


def safe_extract_tar(tar: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    _ensure_safe_tar_members(tar, destination)
    try:
        tar.extractall(destination, filter="data")
    except TypeError:
        tar.extractall(destination)
