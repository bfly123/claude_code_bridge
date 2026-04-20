#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import shlex
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REQ_ID_RE = re.compile(r"^CCB_REQ_ID:\s*(\S+)")
DONE_RE = re.compile(r"^CCB_DONE:\s*(\S+)")
REQUEST_PATH_RE = re.compile(r"@(\S+\.md)\b")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _iter_hook_commands(provider: str, workspace: Path) -> list[str]:
    if provider == "gemini":
        settings = _load_json(workspace / ".gemini" / "settings.json")
        hooks = settings.get("hooks")
        groups = hooks.get("AfterAgent") if isinstance(hooks, dict) else None
        if isinstance(groups, list):
            return _extract_hook_commands(groups)
        return []
    if provider == "claude":
        settings = _load_json(workspace / ".claude" / "settings.local.json")
        hooks = settings.get("hooks")
        groups = hooks.get("Stop") if isinstance(hooks, dict) else None
        if isinstance(groups, list):
            return _extract_hook_commands(groups)
        return []
    return []


def _extract_hook_commands(groups: list[object]) -> list[str]:
    commands: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        hooks = group.get("hooks")
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict):
                continue
            if str(hook.get("type") or "").strip().lower() != "command":
                continue
            command = str(hook.get("command") or "").strip()
            if command:
                commands.append(command)
    return commands


def _hook_context(provider: str, workspace: Path) -> tuple[Path, str, Path] | None:
    for command in _iter_hook_commands(provider, workspace):
        try:
            parts = shlex.split(command)
        except Exception:
            continue
        completion_dir = ""
        agent_name = ""
        workspace_path = ""
        index = 0
        while index < len(parts):
            token = parts[index]
            if token == "--completion-dir" and index + 1 < len(parts):
                completion_dir = parts[index + 1]
                index += 2
                continue
            if token == "--agent-name" and index + 1 < len(parts):
                agent_name = parts[index + 1]
                index += 2
                continue
            if token == "--workspace" and index + 1 < len(parts):
                workspace_path = parts[index + 1]
                index += 2
                continue
            index += 1
        if completion_dir and agent_name and workspace_path:
            return (
                Path(completion_dir).expanduser(),
                agent_name,
                Path(workspace_path).expanduser(),
            )
    return None


def _write_hook_event(provider: str, workspace: Path, req_id: str, reply: str) -> None:
    context = _hook_context(provider, workspace)
    if context is None:
        return
    completion_dir, agent_name, workspace_path = context
    try:
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root / "lib"))
        from provider_hooks.artifacts import write_event
    except Exception:
        return

    try:
        write_event(
            provider=provider,
            completion_dir=completion_dir,
            agent_name=agent_name,
            workspace_path=str(workspace_path),
            req_id=req_id,
            status="completed",
            reply=reply,
            session_id=f"stub-{provider}-{req_id}",
            hook_event_name="AfterAgent" if provider == "gemini" else "Stop",
            diagnostics={"source": "provider_stub"},
        )
    except Exception:
        return


def _request_message(prompt: str) -> str:
    raw = str(prompt or "").strip()
    if not raw:
        return ""
    match = REQUEST_PATH_RE.search(raw)
    if not match:
        lines = raw.splitlines()
        body = [line for line in lines[1:] if line.strip()]
        return "\n".join(body).strip() or raw
    request_path = Path(match.group(1)).expanduser()
    try:
        return request_path.read_text(encoding="utf-8").strip()
    except Exception:
        return raw


def _looks_like_exact_turn_prompt(provider: str, line: str, current_lines: list[str], current_req: str) -> bool:
    if not current_req:
        return False
    if provider == "codex":
        prefix = f"CCB_REQ_ID: {current_req}"
        if line.startswith(prefix) and line[len(prefix) :].strip():
            return True
        if len(current_lines) >= 3 and not current_lines[1].strip() and line.strip():
            return True
    if provider == "gemini":
        return "Execute the full request from @" in line
    if provider in {"claude", "codex"}:
        if line.strip():
            return False
        body_lines = [item for item in current_lines[1:] if item.strip()]
        return bool(body_lines)
    return False


def _codex_log_path() -> Path:
    explicit = (os.environ.get("CODEX_LOG_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = Path(os.environ.get("CODEX_SESSION_ROOT") or (Path.home() / ".codex" / "sessions")).expanduser()
    sid = (os.environ.get("CCB_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
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
    turn_id = f"turn-{req_id}"
    task_id = f"task-{req_id}"
    reply = f"stub reply for {req_id}"
    user_entry = {
        "timestamp": _now_iso(),
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "turn_id": turn_id,
            "task_id": task_id,
            "content": [{"type": "input_text", "text": prompt}],
        },
    }
    _append_jsonl(log_path, user_entry)
    if delay_s:
        time.sleep(delay_s)
    assistant_entry = {
        "timestamp": _now_iso(),
        "type": "event_msg",
        "payload": {
            "type": "agent_message",
            "role": "assistant",
            "turn_id": turn_id,
            "task_id": task_id,
            "phase": "final_answer",
            "message": reply,
        },
    }
    terminal_entry = {
        "timestamp": _now_iso(),
        "type": "event_msg",
        "payload": {
            "type": "task_complete",
            "turn_id": turn_id,
            "task_id": task_id,
            "reason": "task_complete",
            "last_agent_message": reply,
        },
    }
    _append_jsonl(log_path, assistant_entry)
    _append_jsonl(log_path, terminal_entry)


def _gemini_session_path() -> Path:
    explicit = (os.environ.get("GEMINI_SESSION_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = Path(os.environ.get("GEMINI_ROOT") or (Path.home() / ".gemini" / "tmp")).expanduser()
    project_hash = _project_hash(Path.cwd())
    sid = (os.environ.get("CCB_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
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
    session_id = (os.environ.get("CCB_SESSION_ID") or "").strip()
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


def _droid_sessions_root() -> Path:
    root = (os.environ.get("DROID_SESSIONS_ROOT") or os.environ.get("FACTORY_SESSIONS_ROOT") or "").strip()
    if root:
        return Path(root).expanduser()
    return (Path.home() / ".factory" / "sessions").expanduser()


def _droid_slug(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _droid_session_path() -> Path:
    explicit = (os.environ.get("DROID_SESSION_PATH") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = _droid_sessions_root()
    slug = _droid_slug(Path.cwd())
    sid = (os.environ.get("CCB_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
    return root / slug / f"{sid}.jsonl"


def _ensure_droid_session_start(path: Path, session_id: str, cwd: str) -> None:
    try:
        if path.exists() and path.stat().st_size > 0:
            return
    except OSError:
        return
    entry = {"type": "session_start", "id": session_id, "cwd": cwd}
    _append_jsonl(path, entry)


def _handle_droid(req_id: str, prompt: str, delay_s: float, session_path: Path, session_id: str) -> None:
    _ensure_droid_session_start(session_path, session_id, os.getcwd())
    user_entry = {
        "type": "message",
        "id": f"msg-{uuid.uuid4().hex}",
        "message": {"role": "user", "content": [{"type": "text", "text": prompt}]},
    }
    _append_jsonl(session_path, user_entry)
    if delay_s:
        time.sleep(delay_s)
    reply = f"stub reply for {req_id}\nCCB_DONE: {req_id}"
    assistant_entry = {
        "type": "message",
        "id": f"msg-{uuid.uuid4().hex}",
        "message": {"role": "assistant", "content": [{"type": "text", "text": reply}]},
    }
    _append_jsonl(session_path, assistant_entry)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--provider", default="")
    args, _unknown = parser.parse_known_args(argv[1:])

    provider = (args.provider or Path(argv[0]).name).strip().lower()
    if provider not in ("codex", "gemini", "claude", "opencode", "droid", "copilot", "codebuddy", "qwen"):
        print(f"[stub] unknown provider: {provider}", file=sys.stderr)
        return 2

    delay_s = _delay(provider)

    # Provider-specific initialization.
    gemini_messages: list[dict] = []
    gemini_session_id = ""
    gemini_session_path = None
    claude_session_path = None
    opencode_state: dict | None = None
    droid_session_path: Path | None = None
    droid_session_id = ""
    copilot_session_path: Path | None = None
    copilot_session_id = ""
    codebuddy_session_path: Path | None = None
    codebuddy_session_id = ""
    qwen_session_path: Path | None = None
    qwen_session_id = ""

    if provider == "gemini":
        gemini_session_path = _gemini_session_path()
        gemini_session_id = (os.environ.get("CCB_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
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
    elif provider == "droid":
        droid_session_path = _droid_session_path()
        droid_session_id = (os.environ.get("CCB_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
        _ensure_droid_session_start(droid_session_path, droid_session_id, os.getcwd())
    elif provider == "copilot":
        copilot_session_id = (os.environ.get("COPILOT_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
        explicit = (os.environ.get("COPILOT_SESSION_PATH") or "").strip()
        if explicit:
            copilot_session_path = Path(explicit).expanduser()
        else:
            root = _droid_sessions_root()
            slug = _droid_slug(Path.cwd())
            copilot_session_path = root / slug / f"copilot-{copilot_session_id}.jsonl"
        _ensure_droid_session_start(copilot_session_path, copilot_session_id, os.getcwd())
    elif provider == "codebuddy":
        codebuddy_session_id = (os.environ.get("CODEBUDDY_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
        explicit = (os.environ.get("CODEBUDDY_SESSION_PATH") or "").strip()
        if explicit:
            codebuddy_session_path = Path(explicit).expanduser()
        else:
            root = _droid_sessions_root()
            slug = _droid_slug(Path.cwd())
            codebuddy_session_path = root / slug / f"codebuddy-{codebuddy_session_id}.jsonl"
        _ensure_droid_session_start(codebuddy_session_path, codebuddy_session_id, os.getcwd())
    elif provider == "qwen":
        qwen_session_id = (os.environ.get("QWEN_SESSION_ID") or "").strip() or f"stub-{uuid.uuid4().hex}"
        explicit = (os.environ.get("QWEN_SESSION_PATH") or "").strip()
        if explicit:
            qwen_session_path = Path(explicit).expanduser()
        else:
            root = _droid_sessions_root()
            slug = _droid_slug(Path.cwd())
            qwen_session_path = root / slug / f"qwen-{qwen_session_id}.jsonl"
        _ensure_droid_session_start(qwen_session_path, qwen_session_id, os.getcwd())

    def _handle_request(req_id: str, prompt: str) -> None:
        if provider == "codex":
            _handle_codex(req_id, prompt, delay_s)
            return
        if provider == "gemini":
            if delay_s:
                time.sleep(delay_s)
            reply = f"stub reply for {req_id}\nCCB_DONE: {req_id}"
            assert gemini_session_path is not None
            gemini_messages.append({"type": "user", "content": _request_message(prompt) or prompt})
            gemini_messages.append({"type": "gemini", "content": reply, "id": f"stub-{len(gemini_messages)}"})
            _write_gemini_session(gemini_session_path, gemini_session_id, gemini_messages)
            _write_hook_event(provider, Path.cwd(), req_id, f"stub reply for {req_id}")
            return
        if provider == "claude":
            assert claude_session_path is not None
            _handle_claude(req_id, _request_message(prompt) or prompt, delay_s, claude_session_path)
            _write_hook_event(provider, Path.cwd(), req_id, f"stub reply for {req_id}")
            return
        if provider == "opencode":
            assert opencode_state is not None
            _handle_opencode(req_id, delay_s, opencode_state)
            return
        if provider == "droid":
            assert droid_session_path is not None
            _handle_droid(req_id, prompt, delay_s, droid_session_path, droid_session_id)
            return
        if provider == "copilot":
            assert copilot_session_path is not None
            _handle_droid(req_id, prompt, delay_s, copilot_session_path, copilot_session_id)
            return
        if provider == "codebuddy":
            assert codebuddy_session_path is not None
            _handle_droid(req_id, prompt, delay_s, codebuddy_session_path, codebuddy_session_id)
            return
        if provider == "qwen":
            assert qwen_session_path is not None
            _handle_droid(req_id, prompt, delay_s, qwen_session_path, qwen_session_id)
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
            continue

        if _looks_like_exact_turn_prompt(provider, line, current_lines, current_req):
            prompt = "\n".join(current_lines).strip()
            _handle_request(current_req, prompt)
            current_lines = []
            current_req = ""

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
