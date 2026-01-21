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

ARTIFACT_ROOT="${TEST_DIR1}/_comm_${RUN_ID}"
STUB_BIN="${ARTIFACT_ROOT}/bin"
STUB_PROVIDER="${ROOT}/test/stubs/provider_stub.py"
CODEX_ROOT="${ARTIFACT_ROOT}/codex_sessions"
GEMINI_ROOT="${ARTIFACT_ROOT}/gemini_tmp"
CLAUDE_ROOT="${ARTIFACT_ROOT}/claude_projects"
OPENCODE_ROOT="${ARTIFACT_ROOT}/opencode_storage"
RUNTIME_ROOT="${ARTIFACT_ROOT}/runtime"
RUN_DIR_BASE="${ARTIFACT_ROOT}/run"

mkdir -p "${STUB_BIN}" "${CODEX_ROOT}" "${GEMINI_ROOT}" "${CLAUDE_ROOT}" "${OPENCODE_ROOT}" "${RUNTIME_ROOT}" "${RUN_DIR_BASE}" "${TEST_DIR1}" "${TEST_DIR2}"

cat >"${STUB_BIN}/codex" <<EOF
#!/usr/bin/env bash
exec "${PYTHON}" "${STUB_PROVIDER}" --provider codex "\$@"
EOF
cat >"${STUB_BIN}/gemini" <<EOF
#!/usr/bin/env bash
exec "${PYTHON}" "${STUB_PROVIDER}" --provider gemini "\$@"
EOF
cat >"${STUB_BIN}/claude" <<EOF
#!/usr/bin/env bash
exec "${PYTHON}" "${STUB_PROVIDER}" --provider claude "\$@"
EOF
cat >"${STUB_BIN}/opencode" <<EOF
#!/usr/bin/env bash
exec "${PYTHON}" "${STUB_PROVIDER}" --provider opencode "\$@"
EOF
chmod +x "${STUB_BIN}/codex" "${STUB_BIN}/gemini" "${STUB_BIN}/claude" "${STUB_BIN}/opencode"

export PATH="${STUB_BIN}:${PATH}"
export GEMINI_ROOT
export CLAUDE_PROJECTS_ROOT="${CLAUDE_ROOT}"
export OPENCODE_STORAGE_ROOT="${OPENCODE_ROOT}"
export CODEX_SESSION_ROOT="${CODEX_ROOT}"
export CCB_GASKD=1
export CCB_GASKD_AUTOSTART=1
export CCB_LASKD=1
export CCB_LASKD_AUTOSTART=1
export CCB_OASKD=1
export CCB_OASKD_AUTOSTART=1
export CCB_CASKD=1
export CCB_CASKD_AUTOSTART=1
export CCB_SYNC_TIMEOUT=20
export CCB_SESSION_FILE=
unset CODEX_SESSION_ID CODEX_RUNTIME_DIR CODEX_INPUT_FIFO CODEX_OUTPUT_FIFO CODEX_TMUX_SESSION CODEX_WEZTERM_PANE
unset GEMINI_SESSION_ID GEMINI_RUNTIME_DIR GEMINI_TMUX_SESSION GEMINI_WEZTERM_PANE
unset OPENCODE_SESSION_ID OPENCODE_RUNTIME_DIR OPENCODE_TMUX_SESSION OPENCODE_WEZTERM_PANE

FAIL=0
SESSIONS=()
PIDS=()
RUN_DIRS=()

log() { echo "== $*"; }
ok() { echo "[OK] $*"; }
fail() { echo "[FAIL] $*"; FAIL=1; }
skip() { echo "[SKIP] $*"; }

match_text() {
  local pattern="$1"
  local file="$2"
  if command -v rg >/dev/null 2>&1; then
    rg -q "${pattern}" "${file}"
  else
    grep -q "${pattern}" "${file}"
  fi
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

compute_project_id() {
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

compute_run_dir() {
  "${PYTHON}" - "${ROOT}" "$1" "${RUN_DIR_BASE}" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
work_dir = Path(sys.argv[2])
base = Path(sys.argv[3])
sys.path.insert(0, str(root / "lib"))
from project_id import compute_ccb_project_id

pid = compute_ccb_project_id(work_dir)
print(str(base / pid[:16]))
PY
}

gemini_hash() {
  "${PYTHON}" - "$1" <<'PY'
import hashlib
import sys
from pathlib import Path

work_dir = Path(sys.argv[1])
try:
    normalized = str(work_dir.expanduser().absolute())
except Exception:
    normalized = str(work_dir)
print(hashlib.sha256(normalized.encode("utf-8")).hexdigest())
PY
}

claude_key() {
  "${PYTHON}" - "$1" <<'PY'
import re
import sys
from pathlib import Path

work_dir = Path(sys.argv[1])
print(re.sub(r"[^A-Za-z0-9]", "-", str(work_dir)))
PY
}

record_run_dir() {
  local dir="$1"
  for item in "${RUN_DIRS[@]}"; do
    if [ "${item}" = "${dir}" ]; then
      return 0
    fi
  done
  RUN_DIRS+=("${dir}")
}

start_tmux_provider() {
  local name="$1"
  local work_dir="$2"
  local provider="$3"
  local out_var="$4"
  shift 4
  tmux new-session -d -s "${name}" -c "${work_dir}" env PATH="${PATH}" "$@" "${provider}"
  SESSIONS+=("${name}")
  local pane_id
  pane_id="$(tmux list-panes -t "${name}" -F "#{pane_id}" | head -n 1)"
  printf -v "${out_var}" '%s' "${pane_id}"
}

mkfifo_if_missing() {
  local path="$1"
  if [ -p "${path}" ]; then
    return 0
  fi
  rm -f "${path}"
  mkfifo "${path}"
}

write_gemini_session() {
  "${PYTHON}" - "$1" "$2" "$3" "$4" "$5" <<'PY'
import json
import sys
from pathlib import Path

proj = Path(sys.argv[1])
pane_id = sys.argv[2]
runtime_dir = sys.argv[3]
session_path = sys.argv[4]
project_id = sys.argv[5]

data = {
    "session_id": Path(session_path).stem,
    "terminal": "tmux",
    "pane_id": pane_id,
    "runtime_dir": runtime_dir,
    "work_dir": str(proj),
    "gemini_session_path": session_path,
    "gemini_session_id": Path(session_path).stem,
    "active": True,
    "ccb_project_id": project_id,
}
path = proj / ".ccb_config" / ".gemini-session"
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

write_claude_session() {
  "${PYTHON}" - "$1" "$2" "$3" "$4" "$5" <<'PY'
import json
import sys
from pathlib import Path

proj = Path(sys.argv[1])
pane_id = sys.argv[2]
runtime_dir = sys.argv[3]
session_path = sys.argv[4]
project_id = sys.argv[5]

data = {
    "terminal": "tmux",
    "pane_id": pane_id,
    "runtime_dir": runtime_dir,
    "work_dir": str(proj),
    "claude_session_path": session_path,
    "claude_session_id": Path(session_path).stem,
    "active": True,
    "ccb_project_id": project_id,
}
path = proj / ".ccb_config" / ".claude-session"
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

write_opencode_session() {
  "${PYTHON}" - "$1" "$2" "$3" "$4" "$5" "$6" <<'PY'
import json
import sys
from pathlib import Path

proj = Path(sys.argv[1])
pane_id = sys.argv[2]
runtime_dir = sys.argv[3]
project_id = sys.argv[4]
opencode_project_id = sys.argv[5]
opencode_session_id = sys.argv[6]

data = {
    "session_id": opencode_session_id,
    "terminal": "tmux",
    "pane_id": pane_id,
    "runtime_dir": runtime_dir,
    "work_dir": str(proj),
    "opencode_project_id": opencode_project_id,
    "opencode_session_id": opencode_session_id,
    "active": True,
    "ccb_project_id": project_id,
}
path = proj / ".ccb_config" / ".opencode-session"
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

write_codex_session() {
  "${PYTHON}" - "$1" "$2" "$3" "$4" "$5" "$6" "$7" <<'PY'
import json
import sys
from pathlib import Path

proj = Path(sys.argv[1])
pane_id = sys.argv[2]
runtime_dir = sys.argv[3]
input_fifo = sys.argv[4]
log_path = sys.argv[5]
session_id = sys.argv[6]
project_id = sys.argv[7]

data = {
    "session_id": session_id,
    "terminal": "tmux",
    "pane_id": pane_id,
    "runtime_dir": runtime_dir,
    "input_fifo": input_fifo,
    "codex_session_path": log_path,
    "codex_session_id": session_id,
    "work_dir": str(proj),
    "active": True,
    "ccb_project_id": project_id,
}
path = proj / ".ccb_config" / ".codex-session"
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

cleanup() {
  for session in "${SESSIONS[@]}"; do
    tmux kill-session -t "${session}" >/dev/null 2>&1 || true
  done
  for pid in "${PIDS[@]}"; do
    kill "${pid}" >/dev/null 2>&1 || true
  done
  for run_dir in "${RUN_DIRS[@]}"; do
    CCB_RUN_DIR="${run_dir}" "${PYTHON}" "${ROOT}/bin/gaskd" --shutdown >/dev/null 2>&1 || true
    CCB_RUN_DIR="${run_dir}" "${PYTHON}" "${ROOT}/bin/laskd" --shutdown >/dev/null 2>&1 || true
    CCB_RUN_DIR="${run_dir}" "${PYTHON}" "${ROOT}/bin/oaskd" --shutdown >/dev/null 2>&1 || true
    CCB_RUN_DIR="${run_dir}" "${PYTHON}" "${ROOT}/bin/caskd" --shutdown >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

log "Test: new project auto-create"
PROJ_NEW="${TEST_DIR1}/new_${RUN_ID}"
mkdir -p "${PROJ_NEW}"
NEW_PARENT="${PROJ_NEW%/*}"
PARENT_ANCHOR=0
CUR="${NEW_PARENT}"
while [ "${CUR}" != "/" ]; do
  if [ -d "${CUR}/.ccb_config" ]; then
    PARENT_ANCHOR=1
    break
  fi
  CUR="$(dirname "${CUR}")"
done
if [ "${PARENT_ANCHOR}" -ne 0 ]; then
  skip "parent anchor exists; auto-create is blocked by design"
else
  RUN_DIR_NEW="${RUN_DIR_BASE}/auto-${RUN_ID}"
  record_run_dir "${RUN_DIR_NEW}"
  NEW_SESSION="ccb-new-${RUN_ID}"
  tmux new-session -d -s "${NEW_SESSION}" -c "${PROJ_NEW}" bash -lc "env PATH=\"${PATH}\" GEMINI_ROOT=\"${GEMINI_ROOT}\" CCB_RUN_DIR=\"${RUN_DIR_NEW}\" CCB_GASKD=1 CCB_GASKD_AUTOSTART=1 ${ROOT}/ccb gemini >\"${PROJ_NEW}/ccb.out\" 2>\"${PROJ_NEW}/ccb.err\""
  SESSIONS+=("${NEW_SESSION}")
  if wait_for_file "${PROJ_NEW}/.ccb_config/.gemini-session" 10; then
    ok "auto-create created .ccb_config"
  else
    fail "auto-create missing .gemini-session"
  fi
fi

log "Setup: mixed provider project"
PROJ_MIX="${TEST_DIR1}/mix_${RUN_ID}"
mkdir -p "${PROJ_MIX}/.ccb_config"
PID_MIX="$(compute_project_id "${PROJ_MIX}")"
RUN_DIR_MIX="$(compute_run_dir "${PROJ_MIX}")"
record_run_dir "${RUN_DIR_MIX}"
mkdir -p "${RUN_DIR_MIX}"

CODEX_LOG_MIX="${CODEX_ROOT}/codex-${RUN_ID}-mix.jsonl"
CODEX_SESSION_ID_MIX="stub-codex-${RUN_ID}-mix"
CODEX_RUNTIME_MIX="${RUNTIME_ROOT}/mix-codex"
CODEX_FIFO_MIX="${CODEX_RUNTIME_MIX}/input.fifo"
mkdir -p "${CODEX_RUNTIME_MIX}"
mkfifo_if_missing "${CODEX_FIFO_MIX}"
CODEX_SESSION_NAME_MIX="stub-codex-${RUN_ID}-mix"
start_tmux_provider "${CODEX_SESSION_NAME_MIX}" "${PROJ_MIX}" codex CODEX_PANE_MIX \
  CODEX_LOG_PATH="${CODEX_LOG_MIX}" CODEX_SESSION_ROOT="${CODEX_ROOT}" CODEX_SESSION_ID="${CODEX_SESSION_ID_MIX}" CODEX_STUB_DELAY="0.2"
CODEX_PANE_PID_MIX="$(tmux list-panes -t "${CODEX_SESSION_NAME_MIX}" -F "#{pane_pid}" | head -n 1)"
echo "${CODEX_PANE_PID_MIX}" >"${CODEX_RUNTIME_MIX}/codex.pid"
echo "${CODEX_PANE_PID_MIX}" >"${CODEX_RUNTIME_MIX}/bridge.pid"
write_codex_session "${PROJ_MIX}" "${CODEX_PANE_MIX}" "${CODEX_RUNTIME_MIX}" "${CODEX_FIFO_MIX}" "${CODEX_LOG_MIX}" "${CODEX_SESSION_ID_MIX}" "${PID_MIX}"

GEMINI_HASH_MIX="$(gemini_hash "${PROJ_MIX}")"
GEMINI_SESSION_MIX="${GEMINI_ROOT}/${GEMINI_HASH_MIX}/chats/session-${RUN_ID}-mix.json"
GEMINI_RUNTIME_MIX="${RUNTIME_ROOT}/mix-gemini"
mkdir -p "${GEMINI_RUNTIME_MIX}" "$(dirname "${GEMINI_SESSION_MIX}")"
start_tmux_provider "stub-gemini-${RUN_ID}-mix" "${PROJ_MIX}" gemini GEMINI_PANE_MIX \
  GEMINI_ROOT="${GEMINI_ROOT}" GEMINI_SESSION_PATH="${GEMINI_SESSION_MIX}" GEMINI_STUB_DELAY="0.25"
write_gemini_session "${PROJ_MIX}" "${GEMINI_PANE_MIX}" "${GEMINI_RUNTIME_MIX}" "${GEMINI_SESSION_MIX}" "${PID_MIX}"

CLAUDE_KEY_MIX="$(claude_key "${PROJ_MIX}")"
CLAUDE_SESSION_MIX="${CLAUDE_ROOT}/${CLAUDE_KEY_MIX}/session-${RUN_ID}-mix.jsonl"
CLAUDE_RUNTIME_MIX="${RUNTIME_ROOT}/mix-claude"
mkdir -p "${CLAUDE_RUNTIME_MIX}" "$(dirname "${CLAUDE_SESSION_MIX}")"
start_tmux_provider "stub-claude-${RUN_ID}-mix" "${PROJ_MIX}" claude CLAUDE_PANE_MIX \
  CLAUDE_PROJECTS_ROOT="${CLAUDE_ROOT}" CLAUDE_SESSION_PATH="${CLAUDE_SESSION_MIX}" CLAUDE_SESSION_ID="session-${RUN_ID}-mix" CLAUDE_STUB_DELAY="0.25"
write_claude_session "${PROJ_MIX}" "${CLAUDE_PANE_MIX}" "${CLAUDE_RUNTIME_MIX}" "${CLAUDE_SESSION_MIX}" "${PID_MIX}"

OPENCODE_PROJECT_MIX="proj-${RUN_ID}-mix"
OPENCODE_SESSION_MIX="ses_${RUN_ID}_mix"
OPENCODE_RUNTIME_MIX="${RUNTIME_ROOT}/mix-opencode"
mkdir -p "${OPENCODE_RUNTIME_MIX}"
start_tmux_provider "stub-opencode-${RUN_ID}-mix" "${PROJ_MIX}" opencode OPENCODE_PANE_MIX \
  OPENCODE_STORAGE_ROOT="${OPENCODE_ROOT}" OPENCODE_PROJECT_ID="${OPENCODE_PROJECT_MIX}" OPENCODE_SESSION_ID="${OPENCODE_SESSION_MIX}" OPENCODE_STUB_DELAY="0.25"
write_opencode_session "${PROJ_MIX}" "${OPENCODE_PANE_MIX}" "${OPENCODE_RUNTIME_MIX}" "${PID_MIX}" "${OPENCODE_PROJECT_MIX}" "${OPENCODE_SESSION_MIX}"

log "Test: ping commands"
for ping in gping lping oping cping; do
  if (cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" "${PYTHON}" "${ROOT}/bin/${ping}" >/tmp/ccb_${ping}_${RUN_ID}.out 2>/tmp/ccb_${ping}_${RUN_ID}.err); then
    ok "${ping}"
  else
    fail "${ping}"
  fi
done

log "Test: ask commands"
ASK_OUT="$(cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" "${PYTHON}" "${ROOT}/bin/gask" --sync "hi gemini" 2>/tmp/ccb_gask_${RUN_ID}.err)" || fail "gask rc"
if [ -n "${ASK_OUT}" ]; then
  ok "gask reply"
else
  fail "gask reply"
fi

ASK_OUT="$(cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" "${PYTHON}" "${ROOT}/bin/lask" --sync "hi claude" 2>/tmp/ccb_lask_${RUN_ID}.err)" || fail "lask rc"
if [ -n "${ASK_OUT}" ]; then
  ok "lask reply"
else
  fail "lask reply"
fi

ASK_OUT="$(cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" OPENCODE_PROJECT_ID="${OPENCODE_PROJECT_MIX}" "${PYTHON}" "${ROOT}/bin/oask" --sync "hi opencode" 2>/tmp/ccb_oask_${RUN_ID}.err)" || fail "oask rc"
if [ -n "${ASK_OUT}" ]; then
  ok "oask reply"
else
  fail "oask reply"
fi

ASK_OUT="$(cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" "${PYTHON}" "${ROOT}/bin/cask" --sync "hi codex" 2>/tmp/ccb_cask_${RUN_ID}.err)" || fail "cask rc"
if [ -n "${ASK_OUT}" ]; then
  ok "cask reply"
else
  fail "cask reply"
fi

log "Test: pend commands"
PEND_OUT="$(cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" "${PYTHON}" "${ROOT}/bin/gpend" 2>/tmp/ccb_gpend_${RUN_ID}.err)" || fail "gpend rc"
if echo "${PEND_OUT}" | grep -q "stub reply"; then
  ok "gpend output"
else
  fail "gpend output"
fi

PEND_OUT="$(cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" "${PYTHON}" "${ROOT}/bin/lpend" 2>/tmp/ccb_lpend_${RUN_ID}.err)" || fail "lpend rc"
if echo "${PEND_OUT}" | grep -q "stub reply"; then
  ok "lpend output"
else
  fail "lpend output"
fi

PEND_OUT="$(cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" "${PYTHON}" "${ROOT}/bin/opend" 2>/tmp/ccb_opend_${RUN_ID}.err)" || fail "opend rc"
if echo "${PEND_OUT}" | grep -q "stub reply"; then
  ok "opend output"
else
  fail "opend output"
fi

PEND_OUT="$(cd "${PROJ_MIX}" && CCB_RUN_DIR="${RUN_DIR_MIX}" "${PYTHON}" "${ROOT}/bin/cpend" 2>/tmp/ccb_cpend_${RUN_ID}.err)" || fail "cpend rc"
if echo "${PEND_OUT}" | grep -q "stub reply"; then
  ok "cpend output"
else
  fail "cpend output"
fi

log "Test: large payload via lask"
LARGE_RC=0
"${PYTHON}" - "${ROOT}" "${PROJ_MIX}" "${RUN_DIR_MIX}" <<'PY' || LARGE_RC=$?
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
proj = Path(sys.argv[2])
run_dir = sys.argv[3]

payload = "X" * 12000
cmd = [sys.executable, str(root / "bin" / "lask"), "--sync"]

env = dict(os.environ)
env["CCB_RUN_DIR"] = run_dir
env["CCB_SYNC_TIMEOUT"] = "20"
proc = subprocess.run(cmd, cwd=str(proj), env=env, input=payload.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if proc.returncode != 0:
    sys.exit(2)
if b"stub reply" not in proc.stdout:
    sys.exit(3)
PY
if [ "${LARGE_RC}" -eq 0 ]; then
  ok "large payload"
else
  fail "large payload"
fi

log "Test: nested project isolation"
PROJ_NEST_PARENT="${TEST_DIR1}/nest_${RUN_ID}"
PROJ_NEST_CHILD="${PROJ_NEST_PARENT}/child"
mkdir -p "${PROJ_NEST_PARENT}/.ccb_config" "${PROJ_NEST_CHILD}/.ccb_config"
PID_PARENT="$(compute_project_id "${PROJ_NEST_PARENT}")"
PID_CHILD="$(compute_project_id "${PROJ_NEST_CHILD}")"
if [ "${PID_PARENT}" != "${PID_CHILD}" ]; then
  ok "project id differs for nested anchors"
else
  fail "project id differs for nested anchors"
fi
RUN_DIR_PARENT="$(compute_run_dir "${PROJ_NEST_PARENT}")"
RUN_DIR_CHILD="$(compute_run_dir "${PROJ_NEST_CHILD}")"
record_run_dir "${RUN_DIR_PARENT}"
record_run_dir "${RUN_DIR_CHILD}"

GEMINI_HASH_PARENT="$(gemini_hash "${PROJ_NEST_PARENT}")"
GEMINI_SESSION_PARENT="${GEMINI_ROOT}/${GEMINI_HASH_PARENT}/chats/session-${RUN_ID}-parent.json"
GEMINI_RUNTIME_PARENT="${RUNTIME_ROOT}/nest-parent-gemini"
mkdir -p "${GEMINI_RUNTIME_PARENT}" "$(dirname "${GEMINI_SESSION_PARENT}")"
start_tmux_provider "stub-gemini-${RUN_ID}-parent" "${PROJ_NEST_PARENT}" gemini PANE_PARENT \
  GEMINI_ROOT="${GEMINI_ROOT}" GEMINI_SESSION_PATH="${GEMINI_SESSION_PARENT}" GEMINI_STUB_DELAY="0.15"
write_gemini_session "${PROJ_NEST_PARENT}" "${PANE_PARENT}" "${GEMINI_RUNTIME_PARENT}" "${GEMINI_SESSION_PARENT}" "${PID_PARENT}"

GEMINI_HASH_CHILD="$(gemini_hash "${PROJ_NEST_CHILD}")"
GEMINI_SESSION_CHILD="${GEMINI_ROOT}/${GEMINI_HASH_CHILD}/chats/session-${RUN_ID}-child.json"
GEMINI_RUNTIME_CHILD="${RUNTIME_ROOT}/nest-child-gemini"
mkdir -p "${GEMINI_RUNTIME_CHILD}" "$(dirname "${GEMINI_SESSION_CHILD}")"
start_tmux_provider "stub-gemini-${RUN_ID}-child" "${PROJ_NEST_CHILD}" gemini PANE_CHILD \
  GEMINI_ROOT="${GEMINI_ROOT}" GEMINI_SESSION_PATH="${GEMINI_SESSION_CHILD}" GEMINI_STUB_DELAY="0.15"
write_gemini_session "${PROJ_NEST_CHILD}" "${PANE_CHILD}" "${GEMINI_RUNTIME_CHILD}" "${GEMINI_SESSION_CHILD}" "${PID_CHILD}"

OUT_PARENT="$(cd "${PROJ_NEST_PARENT}" && CCB_RUN_DIR="${RUN_DIR_PARENT}" "${PYTHON}" "${ROOT}/bin/gask" --sync "parent" 2>/tmp/ccb_parent_${RUN_ID}.err)" || true
OUT_CHILD="$(cd "${PROJ_NEST_CHILD}" && CCB_RUN_DIR="${RUN_DIR_CHILD}" "${PYTHON}" "${ROOT}/bin/gask" --sync "child" 2>/tmp/ccb_child_${RUN_ID}.err)" || true
if [ -n "${OUT_PARENT}" ] && [ -n "${OUT_CHILD}" ] && [ "${OUT_PARENT}" != "${OUT_CHILD}" ]; then
  ok "nested isolation replies"
else
  fail "nested isolation replies"
fi

log "Test: old project restore (gask + gpend)"
PROJ_RESTORE="${TEST_DIR1}/restore_${RUN_ID}"
mkdir -p "${PROJ_RESTORE}/.ccb_config"
PID_RESTORE="$(compute_project_id "${PROJ_RESTORE}")"
RUN_DIR_RESTORE="$(compute_run_dir "${PROJ_RESTORE}")"
record_run_dir "${RUN_DIR_RESTORE}"
GEMINI_HASH_RESTORE="$(gemini_hash "${PROJ_RESTORE}")"
GEMINI_SESSION_RESTORE="${GEMINI_ROOT}/${GEMINI_HASH_RESTORE}/chats/session-${RUN_ID}-restore.json"
GEMINI_RUNTIME_RESTORE="${RUNTIME_ROOT}/restore-gemini"
mkdir -p "${GEMINI_RUNTIME_RESTORE}" "$(dirname "${GEMINI_SESSION_RESTORE}")"
start_tmux_provider "stub-gemini-${RUN_ID}-restore" "${PROJ_RESTORE}" gemini PANE_RESTORE \
  GEMINI_ROOT="${GEMINI_ROOT}" GEMINI_SESSION_PATH="${GEMINI_SESSION_RESTORE}" GEMINI_STUB_DELAY="0.15"
write_gemini_session "${PROJ_RESTORE}" "${PANE_RESTORE}" "${GEMINI_RUNTIME_RESTORE}" "${GEMINI_SESSION_RESTORE}" "${PID_RESTORE}"

OUT_RESTORE="$(cd "${PROJ_RESTORE}" && CCB_RUN_DIR="${RUN_DIR_RESTORE}" "${PYTHON}" "${ROOT}/bin/gask" --sync "restore" 2>/tmp/ccb_restore_${RUN_ID}.err)" || true
if [ -n "${OUT_RESTORE}" ]; then
  ok "restore ask"
else
  fail "restore ask"
fi
CCB_RUN_DIR="${RUN_DIR_RESTORE}" "${PYTHON}" "${ROOT}/bin/gaskd" --shutdown >/dev/null 2>&1 || true
PEND_RESTORE="$(cd "${PROJ_RESTORE}" && CCB_RUN_DIR="${RUN_DIR_RESTORE}" "${PYTHON}" "${ROOT}/bin/gpend" 2>/tmp/ccb_restore_pend_${RUN_ID}.err)" || true
if echo "${PEND_RESTORE}" | grep -q "stub reply"; then
  ok "restore pend"
else
  fail "restore pend"
fi

log "Test: parallel and serialized gask"
PROJ_PAR_A="${TEST_DIR1}/par_${RUN_ID}_a"
PROJ_PAR_B="${TEST_DIR2}/par_${RUN_ID}_b"
mkdir -p "${PROJ_PAR_A}/.ccb_config" "${PROJ_PAR_B}/.ccb_config"
RUN_DIR_PAR_A="$(compute_run_dir "${PROJ_PAR_A}")"
RUN_DIR_PAR_B="$(compute_run_dir "${PROJ_PAR_B}")"
record_run_dir "${RUN_DIR_PAR_A}"
record_run_dir "${RUN_DIR_PAR_B}"
PID_PAR_A="$(compute_project_id "${PROJ_PAR_A}")"
PID_PAR_B="$(compute_project_id "${PROJ_PAR_B}")"
GEMINI_HASH_PAR_A="$(gemini_hash "${PROJ_PAR_A}")"
GEMINI_HASH_PAR_B="$(gemini_hash "${PROJ_PAR_B}")"
GEMINI_SESSION_PAR_A="${GEMINI_ROOT}/${GEMINI_HASH_PAR_A}/chats/session-${RUN_ID}-par-a.json"
GEMINI_SESSION_PAR_B="${GEMINI_ROOT}/${GEMINI_HASH_PAR_B}/chats/session-${RUN_ID}-par-b.json"
mkdir -p "$(dirname "${GEMINI_SESSION_PAR_A}")" "$(dirname "${GEMINI_SESSION_PAR_B}")"
start_tmux_provider "stub-gemini-${RUN_ID}-par-a" "${PROJ_PAR_A}" gemini PANE_PAR_A \
  GEMINI_ROOT="${GEMINI_ROOT}" GEMINI_SESSION_PATH="${GEMINI_SESSION_PAR_A}" GEMINI_STUB_DELAY="1.0"
start_tmux_provider "stub-gemini-${RUN_ID}-par-b" "${PROJ_PAR_B}" gemini PANE_PAR_B \
  GEMINI_ROOT="${GEMINI_ROOT}" GEMINI_SESSION_PATH="${GEMINI_SESSION_PAR_B}" GEMINI_STUB_DELAY="1.0"
write_gemini_session "${PROJ_PAR_A}" "${PANE_PAR_A}" "${RUNTIME_ROOT}/par-a-gemini" "${GEMINI_SESSION_PAR_A}" "${PID_PAR_A}"
write_gemini_session "${PROJ_PAR_B}" "${PANE_PAR_B}" "${RUNTIME_ROOT}/par-b-gemini" "${GEMINI_SESSION_PAR_B}" "${PID_PAR_B}"

for warm_proj in "${PROJ_PAR_A}" "${PROJ_PAR_B}"; do
  run_dir="${RUN_DIR_PAR_A}"
  if [ "${warm_proj}" = "${PROJ_PAR_B}" ]; then
    run_dir="${RUN_DIR_PAR_B}"
  fi
  "${PYTHON}" - "${ROOT}" "${warm_proj}" "${run_dir}" <<'PY' >/dev/null 2>&1 || true
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
proj = Path(sys.argv[2])
run_dir = sys.argv[3]
cmd = [sys.executable, str(root / "bin" / "gask"), "--sync", "warm"]
env = dict(os.environ)
env["CCB_RUN_DIR"] = run_dir
subprocess.run(cmd, cwd=str(proj), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PY
done

PAR_RC=0
PAR_OUT="$(
"${PYTHON}" - "${ROOT}" "${PROJ_PAR_A}" "${RUN_DIR_PAR_A}" "${PROJ_PAR_B}" "${RUN_DIR_PAR_B}" <<'PY'
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
proj_a = Path(sys.argv[2])
run_a = sys.argv[3]
proj_b = Path(sys.argv[4])
run_b = sys.argv[5]
cmd = [sys.executable, str(root / "bin" / "gask"), "--sync", "parallel"]

env_a = dict(os.environ)
env_a["CCB_RUN_DIR"] = run_a
env_b = dict(os.environ)
env_b["CCB_RUN_DIR"] = run_b

start = time.monotonic()
p1 = subprocess.Popen(cmd, cwd=str(proj_a), env=env_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
p2 = subprocess.Popen(cmd, cwd=str(proj_b), env=env_b, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
rc1 = p1.wait()
rc2 = p2.wait()
elapsed = time.monotonic() - start
print(f"elapsed={elapsed:.2f}")
if rc1 != 0 or rc2 != 0:
    sys.exit(2)
if elapsed > 1.6:
    sys.exit(3)
PY
)" || PAR_RC=$?
if [ "${PAR_RC}" -eq 0 ]; then
  ok "parallel gask (${PAR_OUT})"
else
  fail "parallel gask (rc=${PAR_RC}, ${PAR_OUT})"
fi

SER_RC=0
SER_OUT="$(
"${PYTHON}" - "${ROOT}" "${PROJ_PAR_A}" "${RUN_DIR_PAR_A}" <<'PY'
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
proj = Path(sys.argv[2])
run_dir = sys.argv[3]
cmd = [sys.executable, str(root / "bin" / "gask"), "--sync", "serial"]

env = dict(os.environ)
env["CCB_RUN_DIR"] = run_dir

start = time.monotonic()
p1 = subprocess.Popen(cmd, cwd=str(proj), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
p2 = subprocess.Popen(cmd, cwd=str(proj), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
rc1 = p1.wait()
rc2 = p2.wait()
elapsed = time.monotonic() - start
print(f"elapsed={elapsed:.2f}")
if rc1 != 0 or rc2 != 0:
    sys.exit(2)
if elapsed < 1.7:
    sys.exit(3)
PY
)" || SER_RC=$?
if [ "${SER_RC}" -eq 0 ]; then
  ok "serialized gask (${SER_OUT})"
else
  fail "serialized gask (rc=${SER_RC}, ${SER_OUT})"
fi

log "Test: stress gask"
PROJ_STRESS="${TEST_DIR1}/stress_${RUN_ID}"
mkdir -p "${PROJ_STRESS}/.ccb_config"
RUN_DIR_STRESS="$(compute_run_dir "${PROJ_STRESS}")"
record_run_dir "${RUN_DIR_STRESS}"
PID_STRESS="$(compute_project_id "${PROJ_STRESS}")"
GEMINI_HASH_STRESS="$(gemini_hash "${PROJ_STRESS}")"
GEMINI_SESSION_STRESS="${GEMINI_ROOT}/${GEMINI_HASH_STRESS}/chats/session-${RUN_ID}-stress.json"
mkdir -p "$(dirname "${GEMINI_SESSION_STRESS}")"
start_tmux_provider "stub-gemini-${RUN_ID}-stress" "${PROJ_STRESS}" gemini PANE_STRESS \
  GEMINI_ROOT="${GEMINI_ROOT}" GEMINI_SESSION_PATH="${GEMINI_SESSION_STRESS}" GEMINI_STUB_DELAY="0.05"
write_gemini_session "${PROJ_STRESS}" "${PANE_STRESS}" "${RUNTIME_ROOT}/stress-gemini" "${GEMINI_SESSION_STRESS}" "${PID_STRESS}"

STRESS_RC=0
"${PYTHON}" - "${ROOT}" "${PROJ_STRESS}" "${RUN_DIR_STRESS}" <<'PY' || STRESS_RC=$?
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
proj = Path(sys.argv[2])
run_dir = sys.argv[3]
cmd = [sys.executable, str(root / "bin" / "gask"), "--sync"]

env = dict(os.environ)
env["CCB_RUN_DIR"] = run_dir

for i in range(25):
    message = f"stress-{i}"
    proc = subprocess.run(cmd + [message], cwd=str(proj), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode != 0:
        sys.exit(2)
PY
if [ "${STRESS_RC}" -eq 0 ]; then
  ok "stress gask"
else
  fail "stress gask"
fi

if [ "${FAIL}" -ne 0 ]; then
  echo "FAILURES DETECTED"
  cleanup
  exit 1
fi

cleanup
echo "ALL TESTS PASSED"
