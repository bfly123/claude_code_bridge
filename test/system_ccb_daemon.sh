#!/usr/bin/env bash
set -u
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "${PYTHON}" ]; then
  echo "python not found"
  exit 1
fi
if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found"
  exit 1
fi

RUN_ID="$(date +%Y%m%d%H%M%S)-$$"
TEST_PARENT="$(cd "${ROOT}/.." && pwd)"
TEST_DIR1="${TEST_PARENT}/test_ccb"
TEST_DIR2="${TEST_PARENT}/test_ccb2"
PROJ_A="${TEST_DIR1}/proj_${RUN_ID}"
PROJ_B="${TEST_DIR2}/proj_${RUN_ID}"
LOCK_DIR="${TEST_DIR1}/lock_${RUN_ID}"
ANCHOR_PARENT="${TEST_DIR1}/anchor_${RUN_ID}"
ANCHOR_CHILD="${ANCHOR_PARENT}/child"
STUB_BIN="${TEST_DIR1}/_stub_bin"
GEMINI_ROOT="${TEST_DIR1}/_gemini_tmp"
STUB_DELAY="1.0"

mkdir -p "${STUB_BIN}" "${GEMINI_ROOT}"
mkdir -p "${PROJ_A}/.ccb_config" "${PROJ_B}/.ccb_config"
mkdir -p "${LOCK_DIR}/.ccb_config"
mkdir -p "${ANCHOR_PARENT}/.ccb_config" "${ANCHOR_CHILD}"

cat >"${STUB_BIN}/codex" <<'EOF'
#!/usr/bin/env bash
trap 'exit 0' INT TERM
while true; do sleep 3600; done
EOF
chmod +x "${STUB_BIN}/codex"

cat >"${STUB_BIN}/gemini" <<'PY'
#!/usr/bin/env python3
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path


def _project_hash(work_dir: str) -> str:
    try:
        normalized = str(Path(work_dir).expanduser().absolute())
    except Exception:
        normalized = str(work_dir)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def main() -> int:
    root = Path(os.environ.get("GEMINI_ROOT") or (Path.home() / ".gemini" / "tmp")).expanduser()
    project = _project_hash(os.getcwd())
    chats = root / project / "chats"
    chats.mkdir(parents=True, exist_ok=True)
    session_path = chats / f"session-{int(time.time())}-{os.getpid()}.json"
    session_id = "stub-" + uuid.uuid4().hex
    messages = []

    def write_session() -> None:
        payload = {"sessionId": session_id, "messages": messages}
        tmp = session_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(session_path)

    write_session()

    delay = float(os.environ.get("GEMINI_STUB_DELAY") or "0.5")
    current_lines = []
    current_req_id = ""
    msg_index = 0

    while True:
        line = sys.stdin.readline()
        if line == "":
            time.sleep(0.1)
            continue
        line = line.rstrip("\n")
        if not line and not current_lines:
            continue

        if line.startswith("CCB_REQ_ID:"):
            current_req_id = line.split(":", 1)[1].strip()
        if line.startswith("CCB_DONE:") and not current_req_id:
            current_req_id = line.split(":", 1)[1].strip()

        current_lines.append(line)

        if line.startswith("CCB_DONE:") and current_req_id:
            prompt = "\n".join(current_lines).strip()
            messages.append({"type": "user", "content": prompt})
            time.sleep(delay)
            msg_index += 1
            reply = f"stub reply for {current_req_id}\nCCB_DONE: {current_req_id}"
            messages.append({"type": "gemini", "content": reply, "id": f"stub-{msg_index}"})
            write_session()
            current_lines = []
            current_req_id = ""

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
PY
chmod +x "${STUB_BIN}/gemini"

STUB_PATH="${STUB_BIN}:${PATH}"

FAIL=0
SESSIONS=()

cleanup() {
  for session in "${SESSIONS[@]}"; do
    tmux kill-session -t "${session}" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

log() { echo "== $*"; }
ok() { echo "[OK] $*"; }
fail() { echo "[FAIL] $*"; FAIL=1; }

match_text() {
  local pattern="$1"
  local file="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -q "${pattern}" "${file}"
  else
    grep -q "${pattern}" "${file}"
  fi
}

start_tmux() {
  local name="$1"
  local work_dir="$2"
  local cmd="$3"
  tmux new-session -d -s "${name}" -c "${work_dir}" bash -lc "${cmd}"
  SESSIONS+=("${name}")
}

wait_for_file() {
  local path="$1"
  local timeout="$2"
  local start
  start="$(date +%s)"
  while [ "$(( $(date +%s) - start ))" -lt "${timeout}" ]; do
    if [ -s "${path}" ]; then
      return 0
    fi
    sleep 0.1
  done
  return 1
}

pid_alive() {
  local pid="$1"
  if [ -z "${pid}" ]; then
    return 1
  fi
  kill -0 "${pid}" >/dev/null 2>&1
}

compute_run_dir() {
  "${PYTHON}" - "${ROOT}" "$1" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
work_dir = Path(sys.argv[2])
sys.path.insert(0, str(root / "lib"))
from project_id import compute_ccb_project_id

pid = compute_ccb_project_id(work_dir)
print(str(Path.home() / ".cache" / "ccb" / "projects" / pid[:16]))
PY
}

json_get() {
  "${PYTHON}" - "$1" "$2" <<'PY'
import json
import sys

path = sys.argv[1]
key = sys.argv[2]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
val = data.get(key)
if isinstance(val, bool):
    print("true" if val else "false")
elif val is None:
    print("")
else:
    print(val)
PY
}

log "Test: parent anchor auto-create blocked"
ANCHOR_ERR="${ANCHOR_CHILD}/ccb.err"
ANCHOR_RC="${ANCHOR_CHILD}/ccb.rc"
ANCHOR_SESSION="ccb-anchor-${RUN_ID}"
start_tmux "${ANCHOR_SESSION}" \
  "${ANCHOR_CHILD}" \
  "env PATH=\"${STUB_PATH}\" GEMINI_ROOT=\"${GEMINI_ROOT}\" \
  \"${ROOT}/ccb\" codex \
  >\"${ANCHOR_CHILD}/ccb.out\" 2>\"${ANCHOR_ERR}\"; echo \$? >\"${ANCHOR_RC}\"; sleep 1"
if wait_for_file "${ANCHOR_RC}" 5; then
  rc="$(tr -d '[:space:]' < "${ANCHOR_RC}")"
  if [ "${rc}" = "2" ] && match_text "Auto-create blocked" "${ANCHOR_ERR}"; then
    ok "parent anchor block"
  else
    fail "parent anchor block (rc=${rc})"
  fi
else
  fail "parent anchor block (timeout)"
fi

log "Test: single-instance lock"
LOCK_ERR="${LOCK_DIR}/ccb2.err"
LOCK_RC="${LOCK_DIR}/ccb2.rc"
LOCK_SESSION_1="ccb-lock1-${RUN_ID}"
LOCK_SESSION_2="ccb-lock2-${RUN_ID}"
start_tmux "${LOCK_SESSION_1}" \
  "${LOCK_DIR}" \
  "env PATH=\"${STUB_PATH}\" GEMINI_ROOT=\"${GEMINI_ROOT}\" \
  \"${ROOT}/ccb\" codex \
  >\"${LOCK_DIR}/ccb1.out\" 2>\"${LOCK_DIR}/ccb1.err\""
sleep 1
start_tmux "${LOCK_SESSION_2}" \
  "${LOCK_DIR}" \
  "env PATH=\"${STUB_PATH}\" GEMINI_ROOT=\"${GEMINI_ROOT}\" \
  \"${ROOT}/ccb\" codex \
  >\"${LOCK_DIR}/ccb2.out\" 2>\"${LOCK_ERR}\"; echo \$? >\"${LOCK_RC}\"; sleep 1"
if wait_for_file "${LOCK_RC}" 5; then
  rc="$(tr -d '[:space:]' < "${LOCK_RC}")"
  if [ "${rc}" = "2" ] && match_text "Another ccb instance" "${LOCK_ERR}"; then
    ok "single-instance lock"
  else
    fail "single-instance lock (rc=${rc})"
  fi
else
  fail "single-instance lock (timeout)"
fi
tmux kill-session -t "${LOCK_SESSION_1}" >/dev/null 2>&1 || true

log "Test: gemini daemon autostart and isolation"
SESSION_A="ccb-gemini-a-${RUN_ID}"
SESSION_B="ccb-gemini-b-${RUN_ID}"
start_tmux "${SESSION_A}" \
  "${PROJ_A}" \
  "env PATH=\"${STUB_PATH}\" GEMINI_ROOT=\"${GEMINI_ROOT}\" GEMINI_STUB_DELAY=\"${STUB_DELAY}\" \
  CCB_GASKD=1 CCB_GASKD_AUTOSTART=1 \
  \"${ROOT}/ccb\" gemini \
  >\"${PROJ_A}/ccb.out\" 2>\"${PROJ_A}/ccb.err\""
start_tmux "${SESSION_B}" \
  "${PROJ_B}" \
  "env PATH=\"${STUB_PATH}\" GEMINI_ROOT=\"${GEMINI_ROOT}\" GEMINI_STUB_DELAY=\"${STUB_DELAY}\" \
  CCB_GASKD=1 CCB_GASKD_AUTOSTART=1 \
  \"${ROOT}/ccb\" gemini \
  >\"${PROJ_B}/ccb.out\" 2>\"${PROJ_B}/ccb.err\""

if ! wait_for_file "${PROJ_A}/.ccb_config/.gemini-session" 10; then
  fail "gemini session file A"
fi
if ! wait_for_file "${PROJ_B}/.ccb_config/.gemini-session" 10; then
  fail "gemini session file B"
fi

RUN_DIR_A="$(compute_run_dir "${PROJ_A}")"
RUN_DIR_B="$(compute_run_dir "${PROJ_B}")"
STATE_A="${RUN_DIR_A}/gaskd.json"
STATE_B="${RUN_DIR_B}/gaskd.json"

if [ "${RUN_DIR_A}" != "${RUN_DIR_B}" ]; then
  ok "run dir isolation"
else
  fail "run dir isolation"
fi

if wait_for_file "${STATE_A}" 10; then
  managed="$(json_get "${STATE_A}" "managed")"
  pid="$(json_get "${STATE_A}" "pid")"
  parent_pid="$(json_get "${STATE_A}" "parent_pid")"
  if [ "${managed}" = "true" ] && pid_alive "${pid}" && pid_alive "${parent_pid}"; then
    ok "gaskd managed A"
  else
    fail "gaskd managed A"
  fi
else
  fail "gaskd state A"
fi

if wait_for_file "${STATE_B}" 10; then
  managed="$(json_get "${STATE_B}" "managed")"
  pid="$(json_get "${STATE_B}" "pid")"
  parent_pid="$(json_get "${STATE_B}" "parent_pid")"
  if [ "${managed}" = "true" ] && pid_alive "${pid}" && pid_alive "${parent_pid}"; then
    ok "gaskd managed B"
  else
    fail "gaskd managed B"
  fi
else
  fail "gaskd state B"
fi

PROJECT_ID_A="$("${PYTHON}" - "${PROJ_A}/.ccb_config/.gemini-session" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
print(data.get("ccb_project_id", ""))
PY
)"
PROJECT_ID_B="$("${PYTHON}" - "${PROJ_B}/.ccb_config/.gemini-session" <<'PY'
import json
import sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)
print(data.get("ccb_project_id", ""))
PY
)"
if [ -n "${PROJECT_ID_A}" ] && [ -n "${PROJECT_ID_B}" ] && [ "${PROJECT_ID_A}" != "${PROJECT_ID_B}" ]; then
  ok "project id isolation"
else
  fail "project id isolation"
fi

log "Test: gaskd queue serialization"
QUEUE_RC=0
QUEUE_OUT="$("${PYTHON}" - "${ROOT}" "${PROJ_A}" "${RUN_DIR_A}" "${GEMINI_ROOT}" "${STUB_DELAY}" <<'PY'
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
proj = Path(sys.argv[2])
run_dir = sys.argv[3]
gemini_root = sys.argv[4]
delay = float(sys.argv[5])

gask = root / "bin" / "gask"
env = dict(os.environ)
env["CCB_RUN_DIR"] = run_dir
env["GEMINI_ROOT"] = gemini_root
env["CCB_SYNC_TIMEOUT"] = "30"
env["CCB_GASKD"] = "1"
env["CCB_GASKD_AUTOSTART"] = "1"

out1 = proj / "_gask1.out"
out2 = proj / "_gask2.out"
err1 = proj / "_gask1.err"
err2 = proj / "_gask2.err"

cmd1 = [sys.executable, str(gask), "--sync", "queue-test-1"]
cmd2 = [sys.executable, str(gask), "--sync", "queue-test-2"]

start = time.monotonic()
p1 = subprocess.Popen(cmd1, cwd=str(proj), env=env, stdout=open(out1, "w"), stderr=open(err1, "w"))
p2 = subprocess.Popen(cmd2, cwd=str(proj), env=env, stdout=open(out2, "w"), stderr=open(err2, "w"))
rc1 = p1.wait()
rc2 = p2.wait()
elapsed = time.monotonic() - start
print(f"elapsed={elapsed:.2f}")

if rc1 != 0 or rc2 != 0:
    sys.exit(2)

min_elapsed = delay * 1.8
if elapsed < min_elapsed:
    sys.exit(3)
PY
)" || QUEUE_RC=$?
if [ "${QUEUE_RC}" -eq 0 ]; then
  ok "queue serialization (${QUEUE_OUT})"
else
  fail "queue serialization (rc=${QUEUE_RC}, ${QUEUE_OUT})"
fi

PID_A="$(json_get "${STATE_A}" "pid")"
PID_B="$(json_get "${STATE_B}" "pid")"
tmux kill-session -t "${SESSION_A}" >/dev/null 2>&1 || true
tmux kill-session -t "${SESSION_B}" >/dev/null 2>&1 || true

log "Test: daemon exit on ccb exit"
deadline="$(($(date +%s) + 8))"
while [ "$(date +%s)" -lt "${deadline}" ]; do
  if ! pid_alive "${PID_A}" && ! pid_alive "${PID_B}"; then
    ok "daemon exit on ccb exit"
    break
  fi
  sleep 0.2
done
if pid_alive "${PID_A}" || pid_alive "${PID_B}"; then
  fail "daemon exit on ccb exit"
fi

if [ "${FAIL}" -ne 0 ]; then
  echo "FAILURES DETECTED"
  exit 1
fi
echo "ALL TESTS PASSED"
