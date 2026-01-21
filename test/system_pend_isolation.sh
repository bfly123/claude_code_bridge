#!/usr/bin/env bash
set -u
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "${PYTHON}" ]; then
  echo "python not found"
  exit 1
fi

RUN_ID="$(date +%Y%m%d%H%M%S)-$$"
TEST_PARENT="$(cd "${ROOT}/.." && pwd)"
TEST_DIR1="${TEST_PARENT}/test_ccb"
TEST_DIR2="${TEST_PARENT}/test_ccb2"
PROJ_A="${TEST_DIR1}/pend_${RUN_ID}_a"
PROJ_B="${TEST_DIR2}/pend_${RUN_ID}_b"

mkdir -p "${PROJ_A}/.ccb_config" "${PROJ_B}/.ccb_config"

FAIL=0
log() { echo "== $*"; }
ok() { echo "[OK] $*"; }
fail() { echo "[FAIL] $*"; FAIL=1; }

compute_pid() {
  "${PYTHON}" - "${ROOT}" "$1" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
work_dir = Path(sys.argv[2])
sys.path.insert(0, str(root / "lib"))
from project_id import compute_ccb_project_id

print(compute_ccb_project_id(work_dir))
PY
}

PID_A="$(compute_pid "${PROJ_A}")"
PID_B="$(compute_pid "${PROJ_B}")"

OUT_DIR="${TEST_DIR1}/_pend_out_${RUN_ID}"
mkdir -p "${OUT_DIR}"

log "Setup: Codex logs + .codex-session"
CODEX_LOG_DIR="${TEST_DIR1}/_codex_pend_${RUN_ID}"
CODEX_LOG_A="${CODEX_LOG_DIR}/codex-a.jsonl"
CODEX_LOG_B="${CODEX_LOG_DIR}/codex-b.jsonl"
mkdir -p "${CODEX_LOG_DIR}"
printf '%s\n' '{"type":"event_msg","payload":{"type":"assistant_message","message":"codex-A","role":"assistant"}}' > "${CODEX_LOG_A}"
printf '%s\n' '{"type":"event_msg","payload":{"type":"assistant_message","message":"codex-B","role":"assistant"}}' > "${CODEX_LOG_B}"

"${PYTHON}" - "${PROJ_A}" "${PROJ_B}" "${CODEX_LOG_A}" "${CODEX_LOG_B}" <<'PY'
import json
import sys
from pathlib import Path

proj_a = Path(sys.argv[1])
proj_b = Path(sys.argv[2])
log_a = Path(sys.argv[3])
log_b = Path(sys.argv[4])

def write_session(proj: Path, log_path: Path, sid: str) -> None:
    path = proj / ".ccb_config" / ".codex-session"
    data = {"codex_session_path": str(log_path), "codex_session_id": sid, "active": True}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

write_session(proj_a, log_a, "codex-session-a")
write_session(proj_b, log_b, "codex-session-b")
PY

CODEX_REG_ID="codex-reg-${RUN_ID}"
REG_DIR="${HOME}/.ccb/run"
mkdir -p "${REG_DIR}"
"${PYTHON}" - "${REG_DIR}" "${CODEX_REG_ID}" "${PID_B}" "${PROJ_B}" "${CODEX_LOG_B}" <<'PY'
import json
import sys
from pathlib import Path

reg_dir = Path(sys.argv[1])
session_id = sys.argv[2]
pid_b = sys.argv[3]
work_dir = sys.argv[4]
log_path = sys.argv[5]

payload = {
    "ccb_session_id": session_id,
    "ccb_project_id": pid_b,
    "work_dir": work_dir,
    "providers": {
        "codex": {
            "codex_session_path": log_path,
            "codex_session_id": session_id,
        }
    },
}
path = reg_dir / f"ccb-session-{session_id}.json"
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

log "Setup: Gemini sessions"
GEMINI_ROOT="${TEST_DIR1}/_gemini_pend_${RUN_ID}"
"${PYTHON}" - "${GEMINI_ROOT}" "${PROJ_A}" "${PROJ_B}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
proj_a = Path(sys.argv[2])
proj_b = Path(sys.argv[3])

def project_hash(work_dir: Path) -> str:
    try:
        normalized = str(work_dir.expanduser().absolute())
    except Exception:
        normalized = str(work_dir)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def write_session(proj: Path, label: str) -> None:
    chats = root / project_hash(proj) / "chats"
    chats.mkdir(parents=True, exist_ok=True)
    session_path = chats / f"session-{label}.json"
    payload = {
        "sessionId": f"stub-{label}",
        "messages": [
            {"type": "user", "content": f"q-{label}"},
            {"type": "gemini", "content": f"gemini-{label}"},
        ],
    }
    session_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

write_session(proj_a, "A")
write_session(proj_b, "B")
PY

log "Setup: Claude sessions"
CLAUDE_ROOT="${TEST_DIR1}/_claude_pend_${RUN_ID}"
"${PYTHON}" - "${ROOT}" "${CLAUDE_ROOT}" "${PROJ_A}" "${PROJ_B}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
claude_root = Path(sys.argv[2])
proj_a = Path(sys.argv[3])
proj_b = Path(sys.argv[4])
sys.path.insert(0, str(root / "lib"))
from claude_comm import _project_key_for_path

def write_session(proj: Path, label: str) -> Path:
    key = _project_key_for_path(proj)
    project_dir = claude_root / key
    project_dir.mkdir(parents=True, exist_ok=True)
    session_path = project_dir / f"session-{label}.jsonl"
    entry = {"type": "assistant", "content": f"claude-{label}"}
    session_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
    return session_path

def write_binding(proj: Path, session_path: Path) -> None:
    path = proj / ".ccb_config" / ".claude-session"
    data = {"claude_session_path": str(session_path), "claude_session_id": session_path.stem, "active": True}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

sa = write_session(proj_a, "A")
sb = write_session(proj_b, "B")
write_binding(proj_a, sa)
write_binding(proj_b, sb)
PY

CLAUDE_REG_ID="claude-reg-${RUN_ID}"
"${PYTHON}" - "${REG_DIR}" "${CLAUDE_REG_ID}" "${PID_B}" "${PROJ_B}" "${CLAUDE_ROOT}" "${PROJ_B}" <<'PY'
import json
import sys
from pathlib import Path

reg_dir = Path(sys.argv[1])
session_id = sys.argv[2]
pid_b = sys.argv[3]
work_dir = sys.argv[4]
claude_root = Path(sys.argv[5])
proj_b = Path(sys.argv[6])

from re import sub
key = sub(r"[^A-Za-z0-9]", "-", str(proj_b))
session_path = claude_root / key / "session-B.jsonl"

payload = {
    "ccb_session_id": session_id,
    "ccb_project_id": pid_b,
    "work_dir": work_dir,
    "providers": {
        "claude": {
            "claude_session_path": str(session_path),
            "claude_session_id": "session-B",
        }
    },
}
path = reg_dir / f"ccb-session-{session_id}.json"
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

log "Setup: OpenCode storage"
OPENCODE_ROOT="${TEST_DIR1}/_opencode_pend_${RUN_ID}/storage"
"${PYTHON}" - "${OPENCODE_ROOT}" "${PROJ_A}" "${PROJ_B}" <<'PY'
import json
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
proj_a = Path(sys.argv[2])
proj_b = Path(sys.argv[3])

def write_opencode(proj: Path, label: str, updated: int) -> None:
    project_id = f"proj{label}"
    session_id = f"ses_{label}"
    msg_id = f"msg_{label}"
    part_id = f"prt_{label}"

    (root / "project").mkdir(parents=True, exist_ok=True)
    (root / "session" / project_id).mkdir(parents=True, exist_ok=True)
    (root / "message" / session_id).mkdir(parents=True, exist_ok=True)
    (root / "part" / msg_id).mkdir(parents=True, exist_ok=True)

    project_payload = {"id": project_id, "worktree": str(proj), "time": {"updated": updated}}
    (root / "project" / f"{project_id}.json").write_text(
        json.dumps(project_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    session_payload = {"id": session_id, "directory": str(proj), "time": {"updated": updated}}
    (root / "session" / project_id / f"{session_id}.json").write_text(
        json.dumps(session_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    msg_payload = {
        "id": msg_id,
        "sessionID": session_id,
        "role": "assistant",
        "time": {"created": updated, "completed": updated},
    }
    (root / "message" / session_id / f"{msg_id}.json").write_text(
        json.dumps(msg_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    part_payload = {"id": part_id, "messageID": msg_id, "type": "text", "text": f"opencode-{label}", "time": {"start": updated}}
    (root / "part" / msg_id / f"{part_id}.json").write_text(
        json.dumps(part_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

now = int(time.time() * 1000)
write_opencode(proj_a, "A", now - 1000)
write_opencode(proj_b, "B", now)
PY

"${PYTHON}" - "${PROJ_A}" "${PROJ_B}" <<'PY'
import json
import sys
from pathlib import Path

proj_a = Path(sys.argv[1])
proj_b = Path(sys.argv[2])

def write_session(proj: Path, label: str) -> None:
    path = proj / ".ccb_config" / ".opencode-session"
    data = {"opencode_session_id": f"ses_{label}", "opencode_project_id": f"proj{label}", "active": True}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

write_session(proj_a, "A")
write_session(proj_b, "B")
PY

log "Test: cpend isolation"
CPEND_OUT="$(
  cd "${PROJ_A}" && \
  env CODEX_SESSION_ID="${CODEX_REG_ID}" CCB_SESSION_FILE= \
    "${PYTHON}" "${ROOT}/bin/cpend" 2>"${OUT_DIR}/cpend.err"
)"
CPEND_RC=$?
if [ "${CPEND_RC}" -ne 0 ]; then
  fail "cpend rc=${CPEND_RC}"
elif [ "${CPEND_OUT}" = "codex-A" ]; then
  ok "cpend isolation"
else
  fail "cpend output mismatch: ${CPEND_OUT}"
fi

log "Test: gpend isolation"
GPEND_OUT="$(
  cd "${PROJ_A}" && \
  env GEMINI_ROOT="${GEMINI_ROOT}" CCB_SESSION_FILE= \
    "${PYTHON}" "${ROOT}/bin/gpend" 2>"${OUT_DIR}/gpend.err"
)"
GPEND_RC=$?
if [ "${GPEND_RC}" -ne 0 ]; then
  fail "gpend rc=${GPEND_RC}"
elif [ "${GPEND_OUT}" = "gemini-A" ]; then
  ok "gpend isolation"
else
  fail "gpend output mismatch: ${GPEND_OUT}"
fi

log "Test: lpend isolation"
LPEND_OUT="$(
  cd "${PROJ_A}" && \
  env CLAUDE_PROJECTS_ROOT="${CLAUDE_ROOT}" CCB_SESSION_ID="${CLAUDE_REG_ID}" CCB_SESSION_FILE= \
    "${PYTHON}" "${ROOT}/bin/lpend" 2>"${OUT_DIR}/lpend.err"
)"
LPEND_RC=$?
if [ "${LPEND_RC}" -ne 0 ]; then
  fail "lpend rc=${LPEND_RC}"
elif [ "${LPEND_OUT}" = "claude-A" ]; then
  ok "lpend isolation"
else
  fail "lpend output mismatch: ${LPEND_OUT}"
fi

log "Test: opend isolation"
OPEND_OUT="$(
  cd "${PROJ_A}" && \
  env OPENCODE_STORAGE_ROOT="${OPENCODE_ROOT}" OPENCODE_PROJECT_ID= CCB_SESSION_FILE= \
    "${PYTHON}" "${ROOT}/bin/opend" 2>"${OUT_DIR}/opend.err"
)"
OPEND_RC=$?
if [ "${OPEND_RC}" -ne 0 ]; then
  fail "opend rc=${OPEND_RC}"
elif [ "${OPEND_OUT}" = "opencode-A" ]; then
  ok "opend isolation"
else
  fail "opend output mismatch: ${OPEND_OUT}"
fi

if [ "${FAIL}" -ne 0 ]; then
  echo "FAILURES DETECTED"
  exit 1
fi
echo "ALL TESTS PASSED"
