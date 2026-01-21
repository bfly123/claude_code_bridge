#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import sys
import time
import uuid
from pathlib import Path

REQ_ID_RE = re.compile(r"^CCB_REQ_ID:\s*(\S+)")
DONE_RE = re.compile(r"^CCB_DONE:\s*(\S+)")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _delay(provider: str) -> float:
    for key in (f"{provider.upper()}_STUB_DELAY", "STUB_DELAY"):
        raw = os.environ.get(key)
        if not raw:
            continue
        try:
            return max(0.0, float(raw))
        except Exception:
            continue
    return 0.0


def _project_hash(path: Path) -> str:
    try:
        normalized = str(path.expanduser().absolute())
    except Exception:
        normalized = str(path)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _claude_project_key(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _codex_log_path() -> Path:
    explicit = (os.environ.get("CODEX_LOG_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = Path(os.environ.get("CODEX_SESSION_ROOT") or (Path.home() / ".codex" / "sessions")).expanduser()
    sid = (os.environ.get("CODEX_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
    return root / sid / f"{sid}.jsonl"


def _ensure_codex_meta(path: Path, cwd: str) -> None:
    try:
        if path.exists() and path.stat().st_size > 0:
            return
    except OSError:
        return
    meta = {"type": "session_meta", "payload": {"cwd": cwd}}
    _append_jsonl(path, meta)


def _handle_codex(req_id: str, prompt: str, delay_s: float) -> None:
    log_path = _codex_log_path()
    _ensure_codex_meta(log_path, os.getcwd())
    user_entry = {"type": "event_msg", "payload": {"type": "user_message", "message": prompt}}
    _append_jsonl(log_path, user_entry)
    if delay_s:
        time.sleep(delay_s)
    reply = f"stub reply for {req_id}\nCCB_DONE: {req_id}"
    assistant_entry = {
        "type": "event_msg",
        "payload": {"type": "assistant_message", "role": "assistant", "message": reply},
    }
    _append_jsonl(log_path, assistant_entry)


def _gemini_session_path() -> Path:
    explicit = (os.environ.get("GEMINI_SESSION_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = Path(os.environ.get("GEMINI_ROOT") or (Path.home() / ".gemini" / "tmp")).expanduser()
    project_hash = _project_hash(Path.cwd())
    sid = (os.environ.get("GEMINI_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
    return root / project_hash / "chats" / f"session-{sid}.json"


def _load_gemini_messages(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    messages = data.get("messages") if isinstance(data, dict) else None
    return messages if isinstance(messages, list) else []


def _write_gemini_session(path: Path, session_id: str, messages: list[dict]) -> None:
    payload = {"sessionId": session_id, "messages": messages}
    _write_json_atomic(path, payload)


def _claude_session_path() -> Path:
    explicit = (os.environ.get("CLAUDE_SESSION_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = Path(os.environ.get("CLAUDE_PROJECTS_ROOT") or (Path.home() / ".claude" / "projects")).expanduser()
    key = _claude_project_key(Path.cwd())
    sid = (os.environ.get("CLAUDE_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
    return root / key / f"{sid}.jsonl"


def _handle_claude(req_id: str, prompt: str, delay_s: float, session_path: Path) -> None:
    user_entry = {
        "type": "event_msg",
        "payload": {"type": "assistant_message", "role": "user", "message": prompt},
    }
    _append_jsonl(session_path, user_entry)
    if delay_s:
        time.sleep(delay_s)
    reply = f"stub reply for {req_id}\nCCB_DONE: {req_id}"
    assistant_entry = {
        "type": "event_msg",
        "payload": {"type": "assistant_message", "role": "assistant", "message": reply},
    }
    _append_jsonl(session_path, assistant_entry)


def _opencode_storage_root() -> Path:
    return Path(os.environ.get("OPENCODE_STORAGE_ROOT") or (Path.home() / ".opencode" / "storage")).expanduser()


def _opencode_ids() -> tuple[str, str]:
    project_id = (os.environ.get("OPENCODE_PROJECT_ID") or "").strip()
    if not project_id:
        project_id = f"proj-{_project_hash(Path.cwd())[:12]}"
    session_id = (os.environ.get("OPENCODE_SESSION_ID") or "").strip()
    if not session_id:
        session_id = f"ses_{project_id}"
    return project_id, session_id


def _write_opencode_storage(root: Path, project_id: str, session_id: str, reply: str, msg_index: int) -> None:
    root = root.expanduser()
    now = _now_ms()
    work_dir = str(Path.cwd())

    project_payload = {"id": project_id, "worktree": work_dir, "time": {"updated": now}}
    session_payload = {"id": session_id, "directory": work_dir, "time": {"updated": now}}

    msg_id = f"msg_{msg_index}"
    part_id = f"prt_{msg_index}"
    msg_payload = {"id": msg_id, "sessionID": session_id, "role": "assistant", "time": {"created": now, "completed": now}}
    part_payload = {"id": part_id, "messageID": msg_id, "type": "text", "text": reply, "time": {"start": now}}

    (root / "project").mkdir(parents=True, exist_ok=True)
    (root / "session" / project_id).mkdir(parents=True, exist_ok=True)
    (root / "message" / session_id).mkdir(parents=True, exist_ok=True)
    (root / "part" / msg_id).mkdir(parents=True, exist_ok=True)

    (root / "project" / f"{project_id}.json").write_text(json.dumps(project_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    (root / "session" / project_id / f"{session_id}.json").write_text(
        json.dumps(session_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    (root / "message" / session_id / f"{msg_id}.json").write_text(
        json.dumps(msg_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    (root / "part" / msg_id / f"{part_id}.json").write_text(
        json.dumps(part_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )


def _handle_opencode(req_id: str, delay_s: float, state: dict) -> None:
    if delay_s:
        time.sleep(delay_s)
    reply = f"stub reply for {req_id}\nCCB_DONE: {req_id}"
    state["msg_index"] += 1
    root = state["storage_root"]
    project_id = state["project_id"]
    session_id = state["session_id"]
    _write_opencode_storage(root, project_id, session_id, reply, state["msg_index"])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--provider", default="")
    args, _unknown = parser.parse_known_args(argv[1:])

    provider = (args.provider or Path(argv[0]).name).strip().lower()
    if provider not in ("codex", "gemini", "claude", "opencode"):
        print(f"[stub] unknown provider: {provider}", file=sys.stderr)
        return 2

    delay_s = _delay(provider)

    # Provider-specific initialization.
    gemini_messages: list[dict] = []
    gemini_session_id = ""
    gemini_session_path = None
    claude_session_path = None
    opencode_state: dict | None = None

    if provider == "gemini":
        gemini_session_path = _gemini_session_path()
        gemini_session_id = (os.environ.get("GEMINI_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
        gemini_messages = _load_gemini_messages(gemini_session_path)
        _write_gemini_session(gemini_session_path, gemini_session_id, gemini_messages)
    elif provider == "claude":
        claude_session_path = _claude_session_path()
        claude_session_path.parent.mkdir(parents=True, exist_ok=True)
        if not claude_session_path.exists():
            claude_session_path.write_text("", encoding="utf-8")
    elif provider == "opencode":
        project_id, session_id = _opencode_ids()
        opencode_state = {
            "storage_root": _opencode_storage_root(),
            "project_id": project_id,
            "session_id": session_id,
            "msg_index": 0,
        }

    def _handle_request(req_id: str, prompt: str) -> None:
        if provider == "codex":
            _handle_codex(req_id, prompt, delay_s)
            return
        if provider == "gemini":
            if delay_s:
                time.sleep(delay_s)
            reply = f"stub reply for {req_id}\nCCB_DONE: {req_id}"
            assert gemini_session_path is not None
            gemini_messages.append({"type": "user", "content": prompt})
            gemini_messages.append({"type": "gemini", "content": reply, "id": f"stub-{len(gemini_messages)}"})
            _write_gemini_session(gemini_session_path, gemini_session_id, gemini_messages)
            return
        if provider == "claude":
            assert claude_session_path is not None
            _handle_claude(req_id, prompt, delay_s, claude_session_path)
            return
        if provider == "opencode":
            assert opencode_state is not None
            _handle_opencode(req_id, delay_s, opencode_state)
            return

    def _signal_handler(_signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    current_lines: list[str] = []
    current_req = ""

    while True:
        line = sys.stdin.readline()
        if line == "":
            time.sleep(0.05)
            continue
        line = line.rstrip("\n")
        if not line and not current_lines:
            continue

        m = REQ_ID_RE.match(line)
        if m:
            current_req = m.group(1).strip()

        current_lines.append(line)

        m_done = DONE_RE.match(line)
        if m_done:
            if not current_req:
                current_req = m_done.group(1).strip()
            req_id = current_req or m_done.group(1).strip()
            prompt = "\n".join(current_lines).strip()
            _handle_request(req_id, prompt)
            current_lines = []
            current_req = ""

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
