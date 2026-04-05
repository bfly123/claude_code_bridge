from __future__ import annotations

import os
from pathlib import Path


def get_latest_gemini_project_hash(factory) -> tuple[str | None, bool, Path | None]:
    import hashlib

    gemini_root = Path(os.environ.get("GEMINI_ROOT") or (Path.home() / ".gemini" / "tmp")).expanduser()
    candidates: list[str] = []
    try:
        candidates.append(str(Path.cwd().absolute()))
    except Exception:
        pass
    try:
        candidates.append(str(Path.cwd().resolve()))
    except Exception:
        pass
    try:
        candidates.append(str(factory.project_root.absolute()))
    except Exception:
        candidates.append(str(factory.project_root))
    try:
        candidates.append(str(factory.project_root.resolve()))
    except Exception:
        pass
    env_pwd = (os.environ.get("PWD") or "").strip()
    if env_pwd:
        try:
            candidates.append(os.path.abspath(os.path.expanduser(env_pwd)))
        except Exception:
            candidates.append(env_pwd)

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        project_hash = hashlib.sha256(candidate.encode()).hexdigest()
        chats_dir = gemini_root / project_hash / "chats"
        if not chats_dir.exists():
            continue
        session_files = list(chats_dir.glob("session-*.json"))
        if session_files:
            resume_dir = None
            try:
                path = Path(candidate)
                if path.is_dir():
                    resume_dir = path
            except Exception:
                resume_dir = None
            return project_hash, True, resume_dir
    return None, False, None


def build_gemini_start_cmd(factory) -> str:
    cmd = "gemini --yolo" if factory.auto else "gemini"
    if factory.resume:
        _, has_history, resume_dir = factory.get_latest_gemini_project_hash()
        if has_history:
            if resume_dir:
                cmd = f"{factory.build_cd_cmd_fn(resume_dir)}{cmd} --resume latest"
            else:
                cmd = f"{cmd} --resume latest"
            print(f"🔁 {factory.translate_fn('resuming_session', provider='Gemini', session_id='')}")
        else:
            print(f"ℹ️ {factory.translate_fn('no_history_fresh', provider='Gemini')}")
    return cmd
