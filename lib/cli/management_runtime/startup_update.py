from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO

from cli.models_start import ParsedStartCommand
from cli.parser import CliParser, CliUsageError

from .commands_runtime import cmd_update, is_newer_version, latest_version
from .install import find_install_dir
from .versioning import get_available_versions, get_version_info


BACKGROUND_REFRESH_COMMAND = "__refresh-update-cache"
_CACHE_SCHEMA_VERSION = 1
_CACHE_FILE_NAME = ".update-check.json"
_LOCK_FILE_NAME = ".update-check.lock"
_CACHE_TTL_S = 12 * 60 * 60
_PROMPT_DEFER_S = 12 * 60 * 60
_REFRESH_LOCK_TTL_S = 5 * 60
_REFRESH_URLLIB_TIMEOUT_S = 1.5
_REFRESH_CURL_TIMEOUT_S = 1.5
_REFRESH_GIT_TIMEOUT_S = 1.0


def maybe_handle_background_update_refresh_command(tokens: list[str], *, script_root: Path) -> int | None:
    if list(tokens[:1]) != [BACKGROUND_REFRESH_COMMAND]:
        return None
    install_dir = find_install_dir(script_root)
    lock_path = Path(os.environ.get("CCB_UPDATE_REFRESH_LOCK") or update_check_lock_path(install_dir))
    try:
        refresh_update_check_cache(install_dir)
    except Exception:
        return 0
    finally:
        _release_refresh_lock(lock_path)
    return 0


def maybe_handle_startup_release_update(
    tokens: list[str],
    *,
    script_root: Path,
    cwd: Path,
    stdout: TextIO,
    stderr: TextIO,
    stdin,
    env: dict[str, str] | None = None,
    schedule_refresh_fn=None,
    update_fn=None,
    relaunch_fn=None,
) -> int | None:
    del stderr
    if os.environ.get("CCB_SKIP_STARTUP_UPDATE_CHECK"):
        return None
    if not _stream_is_tty(stdin) or not _stream_is_tty(stdout):
        return None
    if not _is_start_command(tokens):
        return None

    install_dir = find_install_dir(script_root)
    local_info = get_version_info(install_dir)
    if not _supports_startup_release_update(local_info):
        return None

    state = load_update_check_state(install_dir)
    now = time.time()
    schedule_refresh = schedule_refresh_fn or schedule_background_update_refresh
    if state is None or update_check_state_is_stale(state, now=now):
        try:
            schedule_refresh(script_root=script_root, install_dir=install_dir)
        except Exception:
            pass
        return None
    if not should_prompt_for_update(state, local_info=local_info, now=now):
        return None

    choice = prompt_for_startup_update(state, local_info=local_info, stdout=stdout, stdin=stdin)
    if choice == "s":
        silence_update_version(install_dir, state)
        return None
    if choice != "y":
        defer_update_prompt(install_dir, state, now=now)
        return None

    run_update = update_fn or cmd_update
    relaunch = relaunch_fn or relaunch_after_update
    print(f"🔄 Updating to v{state.get('latest_version')} before startup...", file=stdout)
    code = int(run_update(SimpleNamespace(target=None), script_root=script_root) or 0)
    if code != 0:
        print("⚠️  Update failed; continuing with current version.", file=stdout)
        return None
    return relaunch(tokens, script_root=script_root, cwd=cwd, env=dict(env or os.environ))


def refresh_update_check_cache(install_dir: Path) -> bool:
    local_info = get_version_info(install_dir)
    if not _supports_startup_release_update(local_info):
        return False
    versions = get_available_versions(
        urllib_timeout=_REFRESH_URLLIB_TIMEOUT_S,
        curl_timeout=_REFRESH_CURL_TIMEOUT_S,
        git_timeout=_REFRESH_GIT_TIMEOUT_S,
    )
    latest = latest_version(versions)
    if not latest:
        return False
    now = time.time()
    existing = load_update_check_state(install_dir) or {}
    current = str(local_info.get("version") or "").strip() or None
    muted_version = str(existing.get("muted_version") or "").strip() or None
    if muted_version != latest:
        muted_version = None
    deferred_version = str(existing.get("deferred_version") or "").strip() or None
    deferred_until_epoch = _safe_float(existing.get("deferred_until_epoch"))
    if deferred_version != latest or deferred_until_epoch <= now:
        deferred_version = None
        deferred_until_epoch = None
    payload = {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "checked_at": _utc_now_text(now),
        "checked_at_epoch": now,
        "current_version": current,
        "latest_version": latest,
        "update_available": bool(current and is_newer_version(latest, current)),
        "muted_version": muted_version,
        "deferred_version": deferred_version,
        "deferred_until_epoch": deferred_until_epoch,
    }
    write_update_check_state(install_dir, payload)
    return True


def load_update_check_state(install_dir: Path) -> dict[str, object] | None:
    path = update_check_cache_path(install_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("schema_version") or 0) != _CACHE_SCHEMA_VERSION:
        return None
    latest_version_text = str(payload.get("latest_version") or "").strip()
    if not latest_version_text:
        return None
    return {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "checked_at": str(payload.get("checked_at") or "").strip() or None,
        "checked_at_epoch": _safe_float(payload.get("checked_at_epoch")),
        "current_version": str(payload.get("current_version") or "").strip() or None,
        "latest_version": latest_version_text,
        "update_available": bool(payload.get("update_available")),
        "muted_version": str(payload.get("muted_version") or "").strip() or None,
        "deferred_version": str(payload.get("deferred_version") or "").strip() or None,
        "deferred_until_epoch": _optional_float(payload.get("deferred_until_epoch")),
    }


def write_update_check_state(install_dir: Path, payload: dict[str, object]) -> None:
    path = update_check_cache_path(install_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def update_check_cache_path(install_dir: Path) -> Path:
    return Path(install_dir) / _CACHE_FILE_NAME


def update_check_lock_path(install_dir: Path) -> Path:
    return Path(install_dir) / _LOCK_FILE_NAME


def update_check_state_is_stale(state: dict[str, object], *, now: float | None = None) -> bool:
    checked_at_epoch = _safe_float(state.get("checked_at_epoch"))
    return checked_at_epoch <= 0 or checked_at_epoch + _CACHE_TTL_S <= float(now or time.time())


def should_prompt_for_update(
    state: dict[str, object],
    *,
    local_info: dict[str, object],
    now: float | None = None,
) -> bool:
    if update_check_state_is_stale(state, now=now):
        return False
    latest = str(state.get("latest_version") or "").strip()
    current = str(local_info.get("version") or "").strip()
    if not latest or not current or not bool(state.get("update_available")):
        return False
    if not is_newer_version(latest, current):
        return False
    if str(state.get("muted_version") or "").strip() == latest:
        return False
    deferred_version = str(state.get("deferred_version") or "").strip()
    deferred_until_epoch = _safe_float(state.get("deferred_until_epoch"))
    if deferred_version == latest and deferred_until_epoch > float(now or time.time()):
        return False
    return True


def prompt_for_startup_update(
    state: dict[str, object],
    *,
    local_info: dict[str, object],
    stdout: TextIO,
    stdin,
) -> str:
    latest = str(state.get("latest_version") or "").strip()
    current = str(local_info.get("version") or "").strip()
    print(f"📦 Release update available: v{latest} (current v{current})", file=stdout)
    print("   [y] upgrade now  [Enter/n] continue  [s] silence this version", file=stdout)
    stdout.write("Upgrade now? [y/N/s]: ")
    stdout.flush()
    try:
        reply = str(stdin.readline() or "")
    except Exception:
        reply = ""
    answer = reply.strip().lower()
    if answer in {"y", "n", "s"}:
        return answer
    return ""


def defer_update_prompt(install_dir: Path, state: dict[str, object], *, now: float | None = None) -> None:
    payload = dict(state)
    payload["deferred_version"] = str(state.get("latest_version") or "").strip() or None
    payload["deferred_until_epoch"] = float(now or time.time()) + _PROMPT_DEFER_S
    write_update_check_state(install_dir, payload)


def silence_update_version(install_dir: Path, state: dict[str, object]) -> None:
    payload = dict(state)
    payload["muted_version"] = str(state.get("latest_version") or "").strip() or None
    payload["deferred_version"] = None
    payload["deferred_until_epoch"] = None
    write_update_check_state(install_dir, payload)


def schedule_background_update_refresh(*, script_root: Path, install_dir: Path) -> bool:
    lock_path = _acquire_refresh_lock(install_dir)
    if lock_path is None:
        return False
    env = dict(os.environ)
    env["CCB_UPDATE_REFRESH_LOCK"] = str(lock_path)
    env["CCB_SKIP_STARTUP_UPDATE_CHECK"] = "1"
    command = [sys.executable, str(Path(script_root) / "ccb"), BACKGROUND_REFRESH_COMMAND]
    try:
        subprocess.Popen(
            command,
            cwd=str(install_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        _release_refresh_lock(lock_path)
        return False
    return True


def relaunch_after_update(tokens: list[str], *, script_root: Path, cwd: Path, env: dict[str, str]) -> int:
    child_env = dict(env)
    child_env["CCB_SKIP_STARTUP_UPDATE_CHECK"] = "1"
    command = [sys.executable, str(Path(script_root) / "ccb"), *list(tokens)]
    return subprocess.run(command, cwd=str(cwd), env=child_env).returncode


def _acquire_refresh_lock(install_dir: Path) -> Path | None:
    lock_path = update_check_lock_path(install_dir)
    now = time.time()
    if lock_path.exists():
        lock_age = max(0.0, now - lock_path.stat().st_mtime)
        if lock_age > _REFRESH_LOCK_TTL_S:
            try:
                lock_path.unlink()
            except OSError:
                pass
        else:
            return None
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"pid": os.getpid(), "created_at": _utc_now_text(now)}))
        handle.write("\n")
    return lock_path


def _release_refresh_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def _supports_startup_release_update(local_info: dict[str, object]) -> bool:
    if platform.system() not in {"Linux", "Darwin"}:
        return False
    return (
        str(local_info.get("install_mode") or "").strip() == "release"
        and str(local_info.get("source_kind") or "").strip() == "release"
        and str(local_info.get("channel") or "").strip() == "stable"
    )


def _is_start_command(tokens: list[str]) -> bool:
    try:
        command = CliParser().parse(list(tokens))
    except CliUsageError:
        return False
    return isinstance(command, ParsedStartCommand)


def _stream_is_tty(stream: object) -> bool:
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False


def _safe_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _optional_float(value: object) -> float | None:
    try:
        resolved = float(value)
    except Exception:
        return None
    return resolved if resolved > 0 else None


def _utc_now_text(now: float) -> str:
    return datetime.fromtimestamp(now, tz=timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "BACKGROUND_REFRESH_COMMAND",
    "defer_update_prompt",
    "load_update_check_state",
    "maybe_handle_background_update_refresh_command",
    "maybe_handle_startup_release_update",
    "prompt_for_startup_update",
    "refresh_update_check_cache",
    "relaunch_after_update",
    "schedule_background_update_refresh",
    "should_prompt_for_update",
    "silence_update_version",
    "update_check_cache_path",
    "update_check_lock_path",
    "update_check_state_is_stale",
    "write_update_check_state",
]
