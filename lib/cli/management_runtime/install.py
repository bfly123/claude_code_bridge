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


def _is_within_directory(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


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


def _normalize_lf_bytes(content: bytes) -> bytes:
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _should_normalize_unix_text(rel_path: Path) -> bool:
    rel = Path(rel_path)
    if rel.name in {"install.sh", "ccb"}:
        return True
    if rel.suffix.lower() in {".py", ".sh", ".yml", ".yaml"}:
        return True
    return len(rel.parts) >= 2 and rel.parts[0] == "bin"


def _stage_tree_ignores(_root: str, names: list[str]) -> set[str]:
    ignored = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv"}
    return {name for name in names if name in ignored}


def _detect_git_head(source_dir: Path) -> tuple[str | None, str | None]:
    git_bin = shutil.which("git")
    if not git_bin:
        return None, None
    probe = subprocess.run(
        [git_bin, "-C", str(source_dir), "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if probe.returncode != 0:
        return None, None
    commit = subprocess.run(
        [git_bin, "-C", str(source_dir), "log", "-1", "--format=%h"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout.strip() or None
    commit_date = subprocess.run(
        [git_bin, "-C", str(source_dir), "log", "-1", "--format=%cs"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout.strip() or None
    return commit, commit_date


def _build_unix_installer_env(
    install_dir: Path,
    *,
    source_dir: Path,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env["CODEX_INSTALL_PREFIX"] = str(install_dir)
    if extra_env:
        env.update(extra_env)
    if not env.get("CCB_SOURCE_KIND") and (source_dir / ".git").exists():
        env["CCB_SOURCE_KIND"] = "source"
    if not env.get("CCB_GIT_COMMIT"):
        git_commit, git_date = _detect_git_head(source_dir)
        if git_commit:
            env["CCB_GIT_COMMIT"] = git_commit
        if git_date and not env.get("CCB_GIT_DATE"):
            env["CCB_GIT_DATE"] = git_date
    return env


def _stage_unix_installer_tree(source_dir: Path, *, temp_base: Path) -> tuple[Path, Path]:
    staging_root = Path(tempfile.mkdtemp(prefix="ccb-installer-", dir=str(temp_base))).expanduser()
    staged_source = staging_root / (source_dir.name or "source")
    shutil.copytree(
        source_dir,
        staged_source,
        ignore=_stage_tree_ignores,
        copy_function=shutil.copy2,
    )
    for path in staged_source.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel_path = path.relative_to(staged_source)
        if not _should_normalize_unix_text(rel_path):
            continue
        original = path.read_bytes()
        normalized = _normalize_lf_bytes(original)
        if normalized != original:
            path.write_bytes(normalized)
    return staging_root, staged_source


def run_staged_unix_installer(
    action: str,
    *,
    source_dir: Path,
    install_dir: Path,
    extra_env: dict[str, str] | None = None,
) -> int:
    source_dir = Path(source_dir).expanduser()
    script = source_dir / "install.sh"
    if not script.exists():
        return _missing_installer_message("install.sh", source_dir)
    temp_base = pick_temp_base_dir(install_dir)
    staging_root, staged_source = _stage_unix_installer_tree(source_dir, temp_base=temp_base)
    try:
        bash_bin = shutil.which("bash")
        if not bash_bin:
            raise RuntimeError("❌ Unix installer requires 'bash' to be available")
        env = _build_unix_installer_env(
            install_dir,
            source_dir=source_dir,
            extra_env=extra_env,
        )
        staged_script = staged_source / "install.sh"
        return subprocess.run(
            [bash_bin, str(staged_script), action],
            env=env,
            cwd=staged_source,
        ).returncode
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def run_installer(action: str, *, script_root: Path) -> int:
    install_dir = find_install_dir(script_root)
    if platform.system() == "Windows":
        cmd, script = _windows_installer_command(install_dir, action)
        if not script.exists():
            return _missing_installer_message("install.ps1", install_dir)
        return subprocess.run(cmd).returncode

    return run_staged_unix_installer(action, source_dir=install_dir, install_dir=install_dir)


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
        if not _is_within_directory(destination, member_path):
            raise RuntimeError(f"Unsafe tar member path: {member.name}")
        if not (member.issym() or member.islnk()):
            continue
        link_target = Path(member.linkname)
        if link_target.is_absolute():
            raise RuntimeError(f"Unsafe tar link target: {member.name} -> {member.linkname}")
        resolved_link_target = ((destination / member.name).parent / member.linkname).resolve()
        if not _is_within_directory(destination, resolved_link_target):
            raise RuntimeError(f"Unsafe tar link target: {member.name} -> {member.linkname}")


def _format_tar_extract_error(exc: tarfile.TarError) -> str:
    detail = str(exc).strip() or exc.__class__.__name__
    return (
        "Unsafe tar archive content detected: "
        f"{detail}. "
        "This usually means the downloaded archive contains unsafe paths or links. "
        "Use an official release asset or a clean source archive."
    )


def safe_extract_tar(tar: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    _ensure_safe_tar_members(tar, destination)
    try:
        tar.extractall(destination, filter="data")
    except TypeError:
        tar.extractall(destination)
    except tarfile.TarError as exc:
        raise RuntimeError(_format_tar_extract_error(exc)) from exc
