from __future__ import annotations

import os
import shutil
import subprocess
from typing import Callable


def find_all_zombie_sessions(*, is_pid_alive: Callable[[int], bool]) -> list[dict]:
    import re

    pattern = re.compile(r"^(codex|gemini|opencode|claude|droid)-(\d+)-")
    zombies = []

    if os.name == "nt" or not shutil.which("tmux"):
        return []

    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    for session in result.stdout.strip().split("\n"):
        if not session:
            continue
        match = pattern.match(session)
        if not match:
            continue

        provider, parent_pid_str = match.groups()
        try:
            parent_pid = int(parent_pid_str)
        except ValueError:
            continue
        if is_pid_alive(parent_pid):
            continue
        zombies.append(
            {
                "session": session,
                "provider": provider,
                "parent_pid": parent_pid,
            }
        )

    return zombies


def kill_global_zombies(
    *,
    yes: bool,
    is_pid_alive: Callable[[int], bool],
    find_all_zombie_sessions_fn: Callable[..., list[dict]],
) -> int:
    zombies = find_all_zombie_sessions_fn(is_pid_alive=is_pid_alive)
    if not zombies:
        print("✅ No zombie sessions found")
        return 0

    print(f"Found {len(zombies)} zombie session(s):")
    for zombie in zombies:
        print(f"  - {zombie['session']} (parent PID {zombie['parent_pid']} exited)")

    if not yes:
        try:
            reply = input("\nClean up these sessions? [y/N] ")
            if reply.lower() != "y":
                print("❌ Cancelled")
                return 1
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Cancelled")
            return 1

    killed = 0
    failed = 0
    for zombie in zombies:
        try:
            result = subprocess.run(
                ["tmux", "kill-session", "-t", zombie["session"]],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                killed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    if failed > 0:
        print(f"✅ Cleaned up {killed} zombie session(s), {failed} failed")
    else:
        print(f"✅ Cleaned up {killed} zombie session(s)")
    return 0


__all__ = ["find_all_zombie_sessions", "kill_global_zombies"]
