#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist"
EXCLUDES = {
    ".git",
    ".ccb",
    ".architec",
    ".claude",
    ".gemini",
    ".hippocampus",
    ".loop",
    ".tmp_pytest",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "dist",
}


def main() -> int:
    args = parse_args()
    if platform.system() != "Linux":
        raise SystemExit("build_linux_release.py must run on Linux")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    channel = args.channel or ("preview" if args.allow_dirty else "stable")

    use_git_ref_source = is_git_checkout(REPO_ROOT) and not args.allow_dirty
    version = resolve_version(REPO_ROOT, git_ref=args.git_ref if use_git_ref_source else None)
    commit, commit_date = resolve_git_metadata(REPO_ROOT, git_ref=args.git_ref if is_git_checkout(REPO_ROOT) else None)
    arch = normalize_arch(platform.machine())
    artifact_basename = f"ccb-linux-{arch}"
    stage_root = output_dir / f".stage-{artifact_basename}"
    artifact_root = stage_root / artifact_basename
    artifact_path = output_dir / f"{artifact_basename}.tar.gz"
    sha_path = output_dir / "SHA256SUMS"

    if stage_root.exists():
        shutil.rmtree(stage_root)
    if artifact_path.exists():
        artifact_path.unlink()

    export_release_tree(
        REPO_ROOT,
        artifact_root,
        git_ref=args.git_ref,
        allow_dirty=args.allow_dirty,
    )
    patch_ccb_metadata(artifact_root / "ccb", version=version, commit=commit, date=commit_date)

    build_info = {
        "version": version,
        "commit": commit,
        "date": commit_date,
        "build_time": utc_now(),
        "platform": "linux",
        "arch": arch,
        "channel": channel,
        "source_kind": "preview" if args.allow_dirty else "release",
        "install_mode": "release",
    }
    write_release_metadata(artifact_root, build_info)
    create_tarball(stage_root=stage_root, artifact_root=artifact_root, artifact_path=artifact_path)
    write_sha256(artifact_path=artifact_path, output_path=sha_path)

    print(f"artifact: {artifact_path}")
    print(f"sha256: {sha_path}")
    print(f"version: {version}")
    print(f"commit: {commit}")
    print(f"channel: {channel}")
    if args.allow_dirty:
        print("warning: built from current dirty worktree for local preview only")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Linux release artifact for ccb")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--channel")
    parser.add_argument(
        "--git-ref",
        default="HEAD",
        help="git ref to archive when building from a git checkout (default: HEAD)",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow building from the current dirty worktree for local preview only",
    )
    return parser.parse_args()


def resolve_version(repo_root: Path, *, git_ref: str | None = None) -> str:
    if git_ref and is_git_checkout(repo_root):
        version_text = read_git_file(repo_root, git_ref=git_ref, relative_path="VERSION")
        if version_text.strip():
            return version_text.strip()
        ccb_text = read_git_file(repo_root, git_ref=git_ref, relative_path="ccb")
        match = re.search(r'^VERSION\s*=\s*"([^"]+)"', ccb_text, re.MULTILINE)
        if match:
            return match.group(1)
    version_file = repo_root / "VERSION"
    if version_file.exists():
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    ccb_path = repo_root / "ccb"
    text = ccb_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'^VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match:
        return match.group(1)
    raise RuntimeError("unable to resolve version from VERSION or ccb")


def resolve_git_metadata(repo_root: Path, *, git_ref: str | None = None) -> tuple[str | None, str | None]:
    if not (repo_root / ".git").exists():
        return None, None
    resolved_ref = git_ref or "HEAD"
    commit = run_git(repo_root, ["log", "-1", "--format=%h", resolved_ref])
    commit_date = run_git(repo_root, ["log", "-1", "--format=%cs", resolved_ref])
    return commit or None, commit_date or None


def run_git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def read_git_file(repo_root: Path, *, git_ref: str, relative_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{git_ref}:{relative_path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def normalize_arch(raw_arch: str) -> str:
    text = str(raw_arch or "").strip().lower()
    mapping = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }
    return mapping.get(text, text or "unknown")


def copy_repo_tree(repo_root: Path, destination: Path) -> None:
    def _ignore(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in EXCLUDES}

    shutil.copytree(repo_root, destination, ignore=_ignore)
    prune_excluded_paths(destination)


def export_release_tree(
    repo_root: Path,
    destination: Path,
    *,
    git_ref: str,
    allow_dirty: bool,
) -> None:
    if is_git_checkout(repo_root):
        if allow_dirty:
            copy_repo_tree(repo_root, destination)
            return
        ensure_clean_worktree(repo_root)
        export_git_archive(repo_root, destination, git_ref=git_ref)
        return
    copy_repo_tree(repo_root, destination)


def is_git_checkout(repo_root: Path) -> bool:
    return (repo_root / ".git").exists()


def ensure_clean_worktree(repo_root: Path) -> None:
    entries = dirty_worktree_entries(repo_root)
    if not entries:
        return
    preview = "\n".join(f"  {entry}" for entry in entries[:20])
    remaining = len(entries) - min(len(entries), 20)
    if remaining > 0:
        preview += f"\n  ... and {remaining} more"
    raise RuntimeError(
        "refusing to build release from a dirty worktree.\n"
        "Commit or stash changes first, or pass --allow-dirty for a local preview build.\n"
        f"Dirty entries:\n{preview}"
    )


def dirty_worktree_entries(repo_root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip() or result.stdout.strip() or result.returncode}")
    return tuple(
        line.rstrip()
        for line in result.stdout.splitlines()
        if line.strip() and not is_excluded_status_entry(line)
    )


def is_excluded_status_entry(line: str) -> bool:
    text = str(line or "").rstrip()
    if len(text) < 4:
        return False
    payload = text[3:].strip()
    if not payload:
        return False
    candidates = [part.strip() for part in payload.split("->")]
    return all(is_excluded_relpath(candidate) for candidate in candidates if candidate)


def is_excluded_relpath(value: str) -> bool:
    path = Path(str(value or "").strip())
    return any(is_excluded_part(part) for part in path.parts)


def is_excluded_part(part: str) -> bool:
    text = str(part or "").strip()
    if not text:
        return False
    if text in EXCLUDES:
        return True
    return text.startswith(".tmp_test_env_")


def export_git_archive(repo_root: Path, destination: Path, *, git_ref: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "archive", "--format=tar", git_ref],
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git archive failed for {git_ref}: {stderr or result.returncode}")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as tar:
        tar.extractall(destination)
    prune_excluded_paths(destination)


def prune_excluded_paths(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if not is_excluded_part(path.name):
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def patch_ccb_metadata(ccb_path: Path, *, version: str, commit: str | None, date: str | None) -> None:
    text = ccb_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r'^VERSION\s*=\s*"[^"]*"', f'VERSION = "{version}"', text, flags=re.MULTILINE)
    if commit:
        text = re.sub(r'^GIT_COMMIT\s*=\s*"[^"]*"', f'GIT_COMMIT = "{commit}"', text, flags=re.MULTILINE)
    if date:
        text = re.sub(r'^GIT_DATE\s*=\s*"[^"]*"', f'GIT_DATE = "{date}"', text, flags=re.MULTILINE)
    ccb_path.write_text(text, encoding="utf-8")


def write_release_metadata(artifact_root: Path, build_info: dict[str, str | None]) -> None:
    version_text = str(build_info.get("version") or "").strip()
    if version_text:
        (artifact_root / "VERSION").write_text(version_text + "\n", encoding="utf-8")
    (artifact_root / "BUILD_INFO.json").write_text(
        json.dumps(build_info, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def create_tarball(*, stage_root: Path, artifact_root: Path, artifact_path: Path) -> None:
    with tarfile.open(artifact_path, "w:gz") as tar:
        tar.add(artifact_root, arcname=artifact_root.name)
    shutil.rmtree(stage_root, ignore_errors=True)


def write_sha256(*, artifact_path: Path, output_path: Path) -> None:
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    output_path.write_text(f"{digest}  {artifact_path.name}\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
