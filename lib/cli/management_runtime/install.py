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


def find_install_dir(script_root: Path) -> Path:
    if (script_root / "install.sh").exists() or (script_root / "install.ps1").exists():
        return script_root

    candidates = []
    env_prefix = (os.environ.get("CODEX_INSTALL_PREFIX") or "").strip()
    if env_prefix:
        candidates.append(Path(env_prefix).expanduser())

    if platform.system() == "Windows":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            candidates.append(Path(localappdata) / "codex-dual")
            candidates.append(Path(localappdata) / "claude-code-bridge")
        candidates.append(Path.home() / "AppData/Local/codex-dual")
    else:
        candidates.append(Path.home() / ".local/share/codex-dual")

    for candidate in candidates:
        if candidate and (candidate / "ccb").exists():
            return candidate
    return script_root


def run_installer(action: str, *, script_root: Path) -> int:
    install_dir = find_install_dir(script_root)
    if platform.system() == "Windows":
        script = install_dir / "install.ps1"
        if not script.exists():
            print(f"❌ install.ps1 not found in {install_dir}", file=sys.stderr)
            return 1
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
        return subprocess.run(cmd).returncode

    script = install_dir / "install.sh"
    if not script.exists():
        print(f"❌ install.sh not found in {install_dir}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["CODEX_INSTALL_PREFIX"] = str(install_dir)
    return subprocess.run(["bash", str(script), action], env=env).returncode


def pick_temp_base_dir(install_dir: Path) -> Path:
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

    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / f".ccb_tmp_probe_{os.getpid()}_{int(time.time() * 1000)}"
            probe.write_bytes(b"1")
            probe.unlink(missing_ok=True)
            return base
        except Exception:
            continue

    raise RuntimeError(
        "❌ No usable temporary directory found.\n"
        "Fix options:\n"
        "  - Create /tmp (Linux/WSL): sudo mkdir -p /tmp && sudo chmod 1777 /tmp\n"
        "  - Or set TMPDIR/CCB_TMPDIR to a writable path (e.g. export TMPDIR=$HOME/.cache/tmp)"
    )


def download_tarball(url: str, destination: Path) -> bool:
    if shutil.which("curl"):
        result = subprocess.run(["curl", "-fsSL", "-o", str(destination), url], capture_output=True)
        if result.returncode == 0:
            return True
    if shutil.which("wget"):
        result = subprocess.run(["wget", "-q", "-O", str(destination), url], capture_output=True)
        if result.returncode == 0:
            return True

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


def safe_extract_tar(tar: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in tar.getmembers():
        member_path = (destination / member.name).resolve()
        if not str(member_path).startswith(str(destination) + os.sep):
            raise RuntimeError(f"Unsafe tar member path: {member.name}")
    try:
        tar.extractall(destination, filter="data")
    except TypeError:
        tar.extractall(destination)
