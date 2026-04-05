#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]  # Windows


@dataclass(frozen=True)
class Cursor:
    type: str
    step_index: int | None
    sub_index: int | None

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "Cursor":
        current = state.get("current") or {}
        return cls(
            type=str(current.get("type") or "none"),
            step_index=current.get("stepIndex"),
            sub_index=current.get("subIndex"),
        )

    def to_json(self) -> dict[str, Any]:
        return {"type": self.type, "stepIndex": self.step_index, "subIndex": self.sub_index}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _get_pane_id(repo: Path) -> str | None:
    if pane := os.environ.get("CLAUDE_PANE_ID"):
        return pane
    for candidate in [
        repo / ".ccb" / ".claude-session",
        repo / ".ccb_config" / ".claude-session",
        repo / ".claude-session",
    ]:
        session = _load_json(candidate)
        if session and session.get("pane_id"):
            return str(session["pane_id"])
    return None


def _run(cmd: list[str], *, cwd: Path, timeout_s: int = 60) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, cwd=str(cwd), check=False, capture_output=True, timeout=timeout_s)


def _lask(repo: Path, text: str) -> None:
    import shutil
    ask_path = shutil.which("ask")
    if not ask_path:
        ask_path = str(Path.home() / ".local" / "bin" / "ask")
    env = dict(os.environ)
    env["CCB_CALLER"] = "autoloop"
    proc = subprocess.run(
        [str(ask_path), "claude", "--no-wrap", "--foreground", text],
        cwd=str(repo), check=False, capture_output=True, timeout=30, env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace").strip() or "ask claude failed")


def _claude_projects_root() -> Path:
    return Path.home() / ".claude" / "projects"


def _candidate_project_dirnames(repo: Path) -> list[str]:
    parts = list(repo.resolve().parts)
    parts = [p for p in parts if p not in (os.sep, "")]
    joined = "-".join(parts)
    joined_dash = joined.replace("_", "-")
    return [f"-{joined}", f"-{joined_dash}"]


def _find_project_dir(repo: Path) -> Path | None:
    root = _claude_projects_root()
    if not root.exists():
        return None

    for name in _candidate_project_dirnames(repo):
        candidate = root / name
        if candidate.is_dir():
            return candidate

    repo_name = repo.name
    hints = {repo_name, repo_name.replace("_", "-")}
    best: Path | None = None
    best_mtime = -1.0
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        if not any(h in entry.name for h in hints):
            continue
        mtime = entry.stat().st_mtime
        if mtime > best_mtime:
            best = entry
            best_mtime = mtime
    return best


def _find_latest_session_jsonl(project_dir: Path) -> Path | None:
    best: Path | None = None
    best_mtime = -1.0
    for path in project_dir.glob("*.jsonl"):
        if path.name.startswith("agent-"):
            continue
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            continue
        if mtime > best_mtime:
            best = path
            best_mtime = mtime
    return best


def _extract_message_model_and_usage(obj: Any) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(obj, dict):
        return None, None
    message = obj.get("message")
    if not isinstance(message, dict):
        return None, None
    model = message.get("model")
    usage = message.get("usage")
    if isinstance(model, str) and isinstance(usage, dict):
        return model, usage
    if isinstance(usage, dict):
        return model if isinstance(model, str) else None, usage
    return model if isinstance(model, str) else None, None


def _read_last_jsonl_with_usage(path: Path) -> tuple[str | None, dict[str, Any] | None]:
    """
    Return (model, usage) from the most recent JSONL record that has message.usage.
    Reads from the end of file to avoid parsing the whole transcript.
    """
    try:
        with path.open("rb") as fp:
            fp.seek(0, os.SEEK_END)
            size = fp.tell()
            block = 64 * 1024
            buf = b""
            pos = size
            while pos > 0:
                read_size = block if pos >= block else pos
                pos -= read_size
                fp.seek(pos, os.SEEK_SET)
                buf = fp.read(read_size) + buf
                lines = buf.splitlines()
                if pos > 0 and buf and not buf.startswith(b"\n") and lines:
                    buf = lines[0]
                    lines = lines[1:]
                else:
                    buf = b""

                for raw in reversed(lines):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw.decode("utf-8", errors="replace"))
                    except Exception:
                        continue
                    model, usage = _extract_message_model_and_usage(obj)
                    if usage:
                        return model, usage
    except Exception:
        return None, None
    return None, None


def _get_context_limit_for_model(model: str | None, *, default_limit: int) -> int:
    if not model:
        return default_limit

    models_file = Path.home() / ".claude" / "ccline" / "models.toml"
    if models_file.exists():
        try:
            import tomllib  # py3.11+

            cfg = tomllib.loads(models_file.read_text(encoding="utf-8"))
            entries = cfg.get("models")
            if isinstance(entries, list):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    pattern = entry.get("pattern")
                    limit = entry.get("context_limit")
                    if not isinstance(pattern, str) or not isinstance(limit, int):
                        continue
                    try:
                        import re

                        if re.search(pattern, model):
                            return limit
                    except Exception:
                        if pattern in model:
                            return limit
        except Exception:
            pass

    lowered = model.lower()
    if "opus" in lowered:
        return 200_000
    if "sonnet" in lowered:
        return 200_000
    if "haiku" in lowered:
        return 200_000
    return default_limit


def _prompt_tokens_for_usage(usage: dict[str, Any]) -> int:
    if "prompt_tokens" in usage:
        try:
            return int(usage.get("prompt_tokens") or 0)
        except Exception:
            pass

    total = int(usage.get("input_tokens") or 0)
    total += int(usage.get("cache_creation_input_tokens") or 0)
    total += int(usage.get("cache_read_input_tokens") or 0)
    total += int(usage.get("cache_creation_prompt_tokens") or 0)
    total += int(usage.get("cache_read_prompt_tokens") or 0)
    return max(0, total)


def get_context_percent(repo: Path, *, context_limit: int = 200_000) -> int:
    project_dir = _find_project_dir(repo)
    if not project_dir:
        return 100

    session_file = _find_latest_session_jsonl(project_dir)
    if not session_file:
        return 100

    model, usage = _read_last_jsonl_with_usage(session_file)
    if not usage:
        return 100

    limit = _get_context_limit_for_model(model, default_limit=context_limit)
    if limit <= 0:
        return 100

    used = _prompt_tokens_for_usage(usage)
    percent = int(round((used / limit) * 100))
    return max(0, min(100, percent))


def _has_remaining_work(state: dict[str, Any]) -> bool:
    current = Cursor.from_state(state)
    if current.type == "none":
        return False

    steps = state.get("steps")
    if not isinstance(steps, list):
        return True

    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("status") in ("todo", "doing"):
            return True
        substeps = step.get("substeps")
        if isinstance(substeps, list):
            for sub in substeps:
                if isinstance(sub, dict) and sub.get("status") in ("todo", "doing"):
                    return True
    return False


def _acquire_lock(lock_path: Path) -> Any:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fp = lock_path.open("w")
    if fcntl is not None:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        # Windows: best-effort exclusive open (no flock available)
        import msvcrt
        try:
            msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
        except (OSError, PermissionError):
            fp.close()
            raise BlockingIOError("lock is held by another process")
    fp.write(str(os.getpid()))
    fp.flush()
    return fp


def _trigger(repo: Path, *, do_clear: bool) -> None:
    time.sleep(5)
    if do_clear:
        _lask(repo, "/clear")
        time.sleep(2)
    _lask(repo, "/tr")


def _cursor_from_json(value: Any) -> Cursor | None:
    if not isinstance(value, dict):
        return None
    return Cursor(
        type=str(value.get("type") or "none"),
        step_index=value.get("stepIndex"),
        sub_index=value.get("subIndex"),
    )


def _run_once_locked(
    repo: Path,
    state_path: Path,
    state_file: Path,
    *,
    threshold: int,
    context_limit: int,
    trigger_on_missing_state: bool,
    cooldown_s: int,
) -> tuple[int, dict[str, Any]]:
    state = _load_json(state_path)
    if not state:
        return 0, {"status": "noop", "reason": "no state.json"}

    pane_id = _get_pane_id(repo)
    if not pane_id:
        return 1, {"status": "fail", "reason": "no pane_id (.claude-session/CLAUDE_PANE_ID missing)"}

    cursor = Cursor.from_state(state)
    saved = _load_json(state_file) or {}
    last_cursor = _cursor_from_json(saved.get("last_cursor"))
    last_ts = int(saved.get("last_trigger_ts") or 0)

    if cursor.type == "none":
        _atomic_write_json(state_file, {"last_cursor": cursor.to_json(), "task_complete": True, "last_trigger_ts": last_ts})
        return 0, {"status": "ok", "taskComplete": True, "cursor": cursor.to_json()}

    if not _has_remaining_work(state):
        _atomic_write_json(state_file, {"last_cursor": cursor.to_json(), "task_complete": True, "last_trigger_ts": last_ts})
        return 0, {"status": "ok", "taskComplete": True, "cursor": cursor.to_json()}

    now = int(time.time())
    if now - last_ts < cooldown_s:
        return 0, {"status": "noop", "reason": "cooldown", "cursor": cursor.to_json()}

    should_trigger = False
    if last_cursor is None:
        should_trigger = trigger_on_missing_state
    elif cursor != last_cursor:
        should_trigger = True

    if not should_trigger:
        _atomic_write_json(state_file, {"last_cursor": cursor.to_json(), "task_complete": False, "last_trigger_ts": last_ts})
        return 0, {"status": "noop", "reason": "cursor unchanged", "cursor": cursor.to_json()}

    usage = get_context_percent(repo, context_limit=context_limit)
    do_clear = usage > threshold
    _trigger(repo, do_clear=do_clear)
    _atomic_write_json(
        state_file,
        {"last_cursor": cursor.to_json(), "task_complete": False, "last_trigger_ts": int(time.time())},
    )
    return 0, {"status": "triggered", "didClear": do_clear, "contextPercent": usage, "cursor": cursor.to_json()}


def run_once(
    repo: Path,
    state_path: Path,
    state_file: Path,
    lock_path: Path,
    *,
    threshold: int,
    context_limit: int,
    trigger_on_missing_state: bool,
    cooldown_s: int,
) -> int:
    try:
        lock_fp = _acquire_lock(lock_path)
    except BlockingIOError:
        print(json.dumps({"status": "noop", "reason": "locked"}, ensure_ascii=False), flush=True)
        return 0

    with lock_fp:
        code, summary = _run_once_locked(
            repo,
            state_path,
            state_file,
            threshold=threshold,
            context_limit=context_limit,
            trigger_on_missing_state=trigger_on_missing_state,
            cooldown_s=cooldown_s,
        )
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        return code


def daemon(
    repo: Path,
    state_path: Path,
    state_file: Path,
    lock_path: Path,
    *,
    threshold: int,
    context_limit: int,
    cooldown_s: int,
    poll_s: float,
) -> int:
    try:
        lock_fp = _acquire_lock(lock_path)
    except BlockingIOError:
        print("autoloop already running", file=sys.stderr)
        return 0

    with lock_fp:
        last_mtime: float | None = None
        while True:
            try:
                stat = state_path.stat()
            except FileNotFoundError:
                time.sleep(poll_s)
                continue

            if last_mtime is None:
                last_mtime = stat.st_mtime
                initial = _load_json(state_path)
                if initial:
                    cursor = Cursor.from_state(initial)
                    _atomic_write_json(
                        state_file,
                        {"last_cursor": cursor.to_json(), "task_complete": False, "last_trigger_ts": 0},
                    )
                    # Auto-trigger /tr on first state.json detection if work remains
                    if _has_remaining_work(initial):
                        usage = get_context_percent(repo, context_limit=context_limit)
                        do_clear = usage > threshold
                        _trigger(repo, do_clear=do_clear)
                        _atomic_write_json(
                            state_file,
                            {"last_cursor": cursor.to_json(), "task_complete": False, "last_trigger_ts": int(time.time())},
                        )
                        print(json.dumps({"status": "triggered", "reason": "initial_state", "didClear": do_clear, "contextPercent": usage, "cursor": cursor.to_json()}, ensure_ascii=False), flush=True)
                time.sleep(poll_s)
                continue

            if stat.st_mtime == last_mtime:
                time.sleep(poll_s)
                continue

            last_mtime = stat.st_mtime
            _code, summary = _run_once_locked(
                repo,
                state_path,
                state_file,
                threshold=threshold,
                context_limit=context_limit,
                trigger_on_missing_state=False,
                cooldown_s=cooldown_s,
            )
            print(json.dumps(summary, ensure_ascii=False), flush=True)
            time.sleep(poll_s)


def _resolve_repo_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return Path.cwd().resolve()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="AutoFlow autoloop daemon: trigger /tr when state advances")
    parser.add_argument("--repo-root", help="AutoFlow project root directory (default: current working directory)")
    parser.add_argument("--once", action="store_true", help="Run a single evaluation/trigger (for FileOps run op)")
    parser.add_argument("--threshold", type=int, default=70, help="Clear only if computed usage percent > threshold")
    parser.add_argument("--context-limit", type=int, default=200_000, help="Claude context limit for percent calculation")
    parser.add_argument("--cooldown", type=int, default=20, help="Minimum seconds between triggers")
    parser.add_argument("--poll", type=float, default=0.5, help="Poll interval seconds (daemon mode)")
    args = parser.parse_args(argv)

    repo = _resolve_repo_root(args.repo_root)
    state_path = repo / ".ccb" / "state.json"
    state_file = repo / ".ccb" / "autoloop_state.json"
    lock_path = repo / ".ccb" / "autoloop.lock"

    if args.once:
        return run_once(
            repo,
            state_path,
            state_file,
            lock_path,
            threshold=args.threshold,
            context_limit=args.context_limit,
            trigger_on_missing_state=True,
            cooldown_s=args.cooldown,
        )
    return daemon(
        repo,
        state_path,
        state_file,
        lock_path,
        threshold=args.threshold,
        context_limit=args.context_limit,
        cooldown_s=args.cooldown,
        poll_s=args.poll,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
