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
if ! command -v git >/dev/null 2>&1; then
  echo "git not found"
  exit 1
fi

RUN_ID="$(date +%Y%m%d%H%M%S)-$$"
TEST_PARENT="$(cd "${ROOT}/.." && pwd)"
TEST_DIR1="${TEST_PARENT}/test_ccb"
TEST_DIR2="${TEST_PARENT}/test_ccb2"

ARTIFACT_ROOT="${TEST_DIR1}/_agent_first_comm_${RUN_ID}"
HOME_DIR="${ARTIFACT_ROOT}/home"
STUB_BIN="${ARTIFACT_ROOT}/bin"
STUB_PROVIDER="${ROOT}/test/stubs/provider_stub.py"
GEMINI_ROOT="${ARTIFACT_ROOT}/gemini"
CLAUDE_ROOT="${ARTIFACT_ROOT}/claude"
OPENCODE_ROOT="${ARTIFACT_ROOT}/opencode"
DROID_ROOT="${ARTIFACT_ROOT}/droid"
CODEX_ROOT="${ARTIFACT_ROOT}/codex"
TMUX_SOCKET="ccb-sys-${RUN_ID}"
STUB_DELAY="0.2"

mkdir -p "${ARTIFACT_ROOT}" "${HOME_DIR}" "${STUB_BIN}" "${GEMINI_ROOT}" "${CLAUDE_ROOT}" "${OPENCODE_ROOT}" "${DROID_ROOT}" "${CODEX_ROOT}" "${TEST_DIR1}" "${TEST_DIR2}"

export HOME="${HOME_DIR}"
export PATH="${STUB_BIN}:${PATH}"
export GEMINI_ROOT
export CLAUDE_PROJECTS_ROOT="${CLAUDE_ROOT}"
export OPENCODE_STORAGE_ROOT="${OPENCODE_ROOT}"
export DROID_SESSIONS_ROOT="${DROID_ROOT}"
export CODEX_SESSION_ROOT="${CODEX_ROOT}"
export CODEX_START_CMD="${STUB_BIN}/codex"
export GEMINI_START_CMD="${STUB_BIN}/gemini"
export CLAUDE_START_CMD="${STUB_BIN}/claude"
export CCB_TMUX_SOCKET="${TMUX_SOCKET}"
export CCB_REPLY_LANG="en"
export CCB_CLAUDE_SKILLS=0
export CCB_SYNC_TIMEOUT=30
export CCB_WATCH_TIMEOUT_S=30
export CCB_WATCH_POLL_INTERVAL_S=0.1
export CCB_GEMINI_READY_TIMEOUT_S=0.5
export CCB_CLAUDE_READY_TIMEOUT_S=0.5
export STUB_DELAY
unset CCB_SESSION_FILE

FAIL=0
SESSIONS=()

log() { echo "== $*"; }
ok() { echo "[OK] $*"; }
fail() { echo "[FAIL] $*"; FAIL=1; }

q() {
  printf '%q' "$1"
}

tmux_cmd() {
  tmux -L "${TMUX_SOCKET}" "$@"
}

cleanup() {
  local project
  for project in "${TEST_DIR1}/mixed_${RUN_ID}" "${TEST_DIR1}/dual_codex_${RUN_ID}" "${TEST_DIR1}/dual_claude_${RUN_ID}" "${TEST_DIR1}/dual_gemini_${RUN_ID}" "${TEST_DIR1}/proj_a_${RUN_ID}" "${TEST_DIR2}/proj_b_${RUN_ID}"; do
    if [ -d "${project}" ]; then
      env HOME="${HOME}" PATH="${PATH}" CCB_TMUX_SOCKET="${CCB_TMUX_SOCKET}" "${ROOT}/ccb" --project "${project}" kill >/dev/null 2>&1 || true
    fi
  done
  for session in "${SESSIONS[@]}"; do
    tmux_cmd kill-session -t "${session}" >/dev/null 2>&1 || true
  done
  tmux_cmd kill-server >/dev/null 2>&1 || true
}
trap cleanup EXIT

install_stub_providers() {
  local provider
  for provider in codex gemini claude opencode droid; do
    cat >"${STUB_BIN}/${provider}" <<EOF
#!/usr/bin/env bash
exec "${PYTHON}" "${STUB_PROVIDER}" --provider ${provider} "\$@"
EOF
    chmod +x "${STUB_BIN}/${provider}"
  done
}

bootstrap_tmux_server() {
  local bootstrap="bootstrap-${RUN_ID}"
  tmux_cmd new-session -d -s "${bootstrap}" -c "${ARTIFACT_ROOT}" "sleep 3600"
  SESSIONS+=("${bootstrap}")
  tmux_cmd set-environment -g HOME "${HOME}"
  tmux_cmd set-environment -g PATH "${PATH}"
  tmux_cmd set-environment -g GEMINI_ROOT "${GEMINI_ROOT}"
  tmux_cmd set-environment -g CLAUDE_PROJECTS_ROOT "${CLAUDE_PROJECTS_ROOT}"
  tmux_cmd set-environment -g OPENCODE_STORAGE_ROOT "${OPENCODE_STORAGE_ROOT}"
  tmux_cmd set-environment -g DROID_SESSIONS_ROOT "${DROID_SESSIONS_ROOT}"
  tmux_cmd set-environment -g CODEX_SESSION_ROOT "${CODEX_SESSION_ROOT}"
  tmux_cmd set-environment -g CODEX_START_CMD "${CODEX_START_CMD}"
  tmux_cmd set-environment -g GEMINI_START_CMD "${GEMINI_START_CMD}"
  tmux_cmd set-environment -g CLAUDE_START_CMD "${CLAUDE_START_CMD}"
  tmux_cmd set-environment -g CCB_GEMINI_READY_TIMEOUT_S "${CCB_GEMINI_READY_TIMEOUT_S}"
  tmux_cmd set-environment -g CCB_CLAUDE_READY_TIMEOUT_S "${CCB_CLAUDE_READY_TIMEOUT_S}"
  tmux_cmd set-environment -g CCB_TMUX_SOCKET "${CCB_TMUX_SOCKET}"
  tmux_cmd set-environment -g STUB_DELAY "${STUB_DELAY}"
}

init_git_repo() {
  local project="$1"
  mkdir -p "${project}/.ccb"
  (
    cd "${project}" || exit 1
    git init -q
    git config user.email "ccb@example.test"
    git config user.name "ccb-system"
    printf '%s\n' "# ${RUN_ID}" > README.md
    git add README.md
    git commit -qm "init"
  )
}

write_mixed_config() {
  local project="$1"
  cat >"${project}/.ccb/ccb.config" <<'EOF'
writer:codex,reviewer:claude,analyst:gemini
EOF
}

write_dual_provider_config() {
  local project="$1"
  local provider="$2"
  local agent_a="$3"
  local agent_b="$4"
  cat >"${project}/.ccb/ccb.config" <<EOF
${agent_a}:${provider},${agent_b}:${provider}
EOF
}

write_cross_project_config() {
  local project="$1"
  cat >"${project}/.ccb/ccb.config" <<'EOF'
writer:codex,reviewer:gemini
EOF
}

start_project() {
  local session="$1"
  local project="$2"
  local start_out="${project}/start.out"
  local start_err="${project}/start.err"
  local cmd
  cmd="env HOME=$(q "${HOME}") PATH=$(q "${PATH}") GEMINI_ROOT=$(q "${GEMINI_ROOT}") CLAUDE_PROJECTS_ROOT=$(q "${CLAUDE_PROJECTS_ROOT}") OPENCODE_STORAGE_ROOT=$(q "${OPENCODE_STORAGE_ROOT}") DROID_SESSIONS_ROOT=$(q "${DROID_SESSIONS_ROOT}") CODEX_SESSION_ROOT=$(q "${CODEX_SESSION_ROOT}") CODEX_START_CMD=$(q "${CODEX_START_CMD}") GEMINI_START_CMD=$(q "${GEMINI_START_CMD}") CLAUDE_START_CMD=$(q "${CLAUDE_START_CMD}") CCB_GEMINI_READY_TIMEOUT_S=$(q "${CCB_GEMINI_READY_TIMEOUT_S}") CCB_CLAUDE_READY_TIMEOUT_S=$(q "${CCB_CLAUDE_READY_TIMEOUT_S}") STUB_DELAY=$(q "${STUB_DELAY}") CCB_TMUX_SOCKET=$(q "${CCB_TMUX_SOCKET}") CCB_CLAUDE_SKILLS=0 CCB_REPLY_LANG=en $(q "${ROOT}/ccb") -a >$(q "${start_out}") 2>$(q "${start_err}"); exec sleep 3600"
  tmux_cmd new-session -d -s "${session}" -c "${project}" bash -lc "${cmd}"
  SESSIONS+=("${session}")
}

wait_for_start() {
  local project="$1"
  local timeout="$2"
  local start
  start="$(date +%s)"
  while [ "$(( $(date +%s) - start ))" -lt "${timeout}" ]; do
    if [ -s "${project}/start.out" ] && grep -q '^start_status: ok$' "${project}/start.out"; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

wait_for_mount() {
  local project="$1"
  local timeout="$2"
  local start
  start="$(date +%s)"
  while [ "$(( $(date +%s) - start ))" -lt "${timeout}" ]; do
    if ccb_project "${project}" ps >"${project}/ps.wait.out" 2>"${project}/ps.wait.err"; then
      if grep -q '^ccbd_state: mounted$' "${project}/ps.wait.out"; then
        return 0
      fi
    fi
    sleep 0.2
  done
  return 1
}

ccb_project() {
  local project="$1"
  shift
  env HOME="${HOME}" PATH="${PATH}" GEMINI_ROOT="${GEMINI_ROOT}" CLAUDE_PROJECTS_ROOT="${CLAUDE_PROJECTS_ROOT}" OPENCODE_STORAGE_ROOT="${OPENCODE_STORAGE_ROOT}" DROID_SESSIONS_ROOT="${DROID_SESSIONS_ROOT}" CODEX_SESSION_ROOT="${CODEX_SESSION_ROOT}" CODEX_START_CMD="${CODEX_START_CMD}" GEMINI_START_CMD="${GEMINI_START_CMD}" CLAUDE_START_CMD="${CLAUDE_START_CMD}" CCB_GEMINI_READY_TIMEOUT_S="${CCB_GEMINI_READY_TIMEOUT_S}" CCB_CLAUDE_READY_TIMEOUT_S="${CCB_CLAUDE_READY_TIMEOUT_S}" CCB_TMUX_SOCKET="${CCB_TMUX_SOCKET}" CCB_CLAUDE_SKILLS=0 CCB_REPLY_LANG=en "${ROOT}/ccb" --project "${project}" "$@"
}

assert_contains() {
  local text="$1"
  local needle="$2"
  local label="$3"
  if printf '%s\n' "${text}" | grep -F -q -- "${needle}"; then
    ok "${label}"
  else
    fail "${label}"
  fi
}

extract_job_pairs() {
  local out="$1"
  printf '%s\n' "${out}" | awk '
    /^accepted job=/ {
      job=""
      target=""
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^job=/) {
          job = $i
          sub(/^job=/, "", job)
        } else if ($i ~ /^target=/) {
          target = $i
          sub(/^target=/, "", target)
        }
      }
      if (job != "") {
        print job, target
      }
      exit
    }
    /^accepted jobs=/ {
      line = $0
      sub(/^accepted jobs=/, "", line)
      count = split(line, items, ",")
      for (i = 1; i <= count; i++) {
        split(items[i], pair, "@")
        if (pair[1] != "") {
          print pair[1], pair[2]
        }
      }
      exit
    }
    /^job: / {
      print $2, $3
    }
  '
}

extract_job_ids() {
  local out="$1"
  extract_job_pairs "${out}" | awk '{print $1}'
}

ask_job() {
  local project="$1"
  local target="$2"
  local sender="$3"
  local message="$4"
  local out
  out="$(ccb_project "${project}" ask "${target}" from "${sender}" "${message}")" || return 1
  printf '%s\n' "${out}" >"${project}/ask-${target}-$(date +%s%N).out"
  extract_job_ids "${out}" | head -n 1
}

ask_all_jobs() {
  local project="$1"
  local sender="$2"
  local message="$3"
  ccb_project "${project}" ask all from "${sender}" "${message}"
}

watch_job() {
  local project="$1"
  local job_id="$2"
  env CCB_WATCH_TIMEOUT_S=30 CCB_WATCH_POLL_INTERVAL_S=0.1 HOME="${HOME}" PATH="${PATH}" GEMINI_ROOT="${GEMINI_ROOT}" CLAUDE_PROJECTS_ROOT="${CLAUDE_PROJECTS_ROOT}" OPENCODE_STORAGE_ROOT="${OPENCODE_STORAGE_ROOT}" DROID_SESSIONS_ROOT="${DROID_SESSIONS_ROOT}" CODEX_SESSION_ROOT="${CODEX_SESSION_ROOT}" CODEX_START_CMD="${CODEX_START_CMD}" GEMINI_START_CMD="${GEMINI_START_CMD}" CLAUDE_START_CMD="${CLAUDE_START_CMD}" CCB_GEMINI_READY_TIMEOUT_S="${CCB_GEMINI_READY_TIMEOUT_S}" CCB_CLAUDE_READY_TIMEOUT_S="${CCB_CLAUDE_READY_TIMEOUT_S}" CCB_TMUX_SOCKET="${CCB_TMUX_SOCKET}" CCB_CLAUDE_SKILLS=0 CCB_REPLY_LANG=en "${ROOT}/ccb" --project "${project}" watch "${job_id}"
}

watch_reply() {
  local project="$1"
  local job_id="$2"
  local out
  out="$(watch_job "${project}" "${job_id}")" || return 1
  printf '%s\n' "${out}" >"${project}/watch-${job_id}.out"
  printf '%s\n' "${out}" | awk -F': ' '/^reply: /{print $2; exit}'
}

pend_reply() {
  local project="$1"
  local target="$2"
  local out
  out="$(ccb_project "${project}" pend "${target}")" || return 1
  printf '%s\n' "${out}" >"${project}/pend-${target}.out"
  printf '%s\n' "${out}" | awk -F': ' '/^reply: /{print $2; exit}'
}

check_agent_binding() {
  local project="$1"
  local agent="$2"
  local provider="$3"
  local ps_out
  ps_out="$(ccb_project "${project}" ps)" || {
    fail "ps ${project} ${agent}"
    return
  }
  assert_contains "${ps_out}" "agent: name=${agent} state=idle provider=${provider} queue=0" "ps ${agent}"
  assert_contains "${ps_out}" "workspace=${project}/.ccb/workspaces/${agent}" "workspace ${agent}"
}

check_agent_ping() {
  local project="$1"
  local agent="$2"
  local provider="$3"
  local out
  out="$(ccb_project "${project}" ping "${agent}")" || {
    fail "ping ${agent}"
    return
  }
  assert_contains "${out}" "agent_name: ${agent}" "ping ${agent} name"
  assert_contains "${out}" "provider: ${provider}" "ping ${agent} provider"
  assert_contains "${out}" "mount_state: mounted" "ping ${agent} mounted"
}

check_workspace_binding() {
  local project="$1"
  local agent="$2"
  local workspace="${project}/.ccb/workspaces/${agent}"
  local binding="${workspace}/.ccb-workspace.json"
  if [ ! -f "${binding}" ]; then
    fail "binding file ${agent}"
    return
  fi
  if [ ! -f "${workspace}/.git" ] && [ ! -d "${workspace}/.git" ]; then
    fail "git worktree ${agent}"
    return
  fi
  if "${PYTHON}" - "${binding}" "${project}" "${workspace}" "${agent}" <<'PY'
import json
import sys
from pathlib import Path

binding_path = Path(sys.argv[1])
project = Path(sys.argv[2]).resolve()
workspace = Path(sys.argv[3]).resolve()
agent = sys.argv[4]
data = json.loads(binding_path.read_text(encoding='utf-8'))
assert Path(str(data.get('target_project'))).resolve() == project
assert Path(str(data.get('workspace_path'))).resolve() == workspace
assert str(data.get('agent_name')) == agent
PY
  then
    ok "workspace binding ${agent}"
  else
    fail "workspace binding ${agent}"
  fi
  if [ "$(git -C "${workspace}" rev-parse --show-toplevel 2>/dev/null)" = "${workspace}" ]; then
    ok "worktree root ${agent}"
  else
    fail "worktree root ${agent}"
  fi
  if [ "$(git -C "${workspace}" branch --show-current 2>/dev/null)" = "ccb/${agent}" ]; then
    ok "worktree branch ${agent}"
  else
    fail "worktree branch ${agent}"
  fi
}

check_tmux_title() {
  local agent="$1"
  local pane_out
  pane_out="$(tmux_cmd list-panes -a -F '#{pane_title} #{@ccb_agent} #{pane_current_path}')" || {
    fail "tmux pane list"
    return
  }
  if printf '%s\n' "${pane_out}" | grep -E -q "CCB-${agent}-[0-9a-f]{8} ${agent} .*workspaces/${agent}\$"; then
    ok "tmux title ${agent}"
  else
    fail "tmux title ${agent}"
  fi
}

check_reply_flow() {
  local project="$1"
  local target="$2"
  local sender="$3"
  local message="$4"
  local label="$5"
  local job_id
  local reply_watch
  local reply_pend
  job_id="$(ask_job "${project}" "${target}" "${sender}" "${message}")" || {
    fail "${label} ask"
    return
  }
  if [ -z "${job_id}" ]; then
    fail "${label} job id"
    return
  fi
  reply_watch="$(watch_reply "${project}" "${job_id}")" || {
    fail "${label} watch"
    return
  }
  if printf '%s\n' "${reply_watch}" | grep -F -q "stub reply for"; then
    ok "${label} watch"
  else
    fail "${label} watch"
  fi
  reply_pend="$(pend_reply "${project}" "${target}")" || {
    fail "${label} pend"
    return
  }
  if [ "${reply_watch}" = "${reply_pend}" ]; then
    ok "${label} pend"
  else
    fail "${label} pend"
  fi
}

check_broadcast_excludes_sender() {
  local project="$1"
  local out
  out="$(ask_all_jobs "${project}" "writer" "broadcast-pass")" || {
    fail "broadcast submit"
    return
  }
  printf '%s\n' "${out}" >"${project}/broadcast.out"
  if extract_job_pairs "${out}" | awk '$2 == "writer" { found = 1 } END { exit(found ? 0 : 1) }'; then
    fail "broadcast excludes sender"
    return
  fi
  local job_count
  job_count="$(extract_job_ids "${out}" | awk 'END{print NR+0}')"
  if [ "${job_count}" = "2" ]; then
    ok "broadcast excludes sender"
  else
    fail "broadcast excludes sender"
    return
  fi
  local job_id
  while read -r job_id; do
    if [ -n "${job_id}" ]; then
      reply="$(watch_reply "${project}" "${job_id}")" || {
        fail "broadcast watch ${job_id}"
        continue
      }
      if printf '%s\n' "${reply}" | grep -F -q "stub reply for"; then
        ok "broadcast watch ${job_id}"
      else
        fail "broadcast watch ${job_id}"
      fi
    fi
  done < <(extract_job_ids "${out}")
}

run_mixed_matrix() {
  local project="${TEST_DIR1}/mixed_${RUN_ID}"
  local session="mixed-${RUN_ID}"
  log "Mixed providers: codex + claude + gemini"
  init_git_repo "${project}"
  write_mixed_config "${project}"
  start_project "${session}" "${project}"
  if wait_for_start "${project}" 20 && wait_for_mount "${project}" 20; then
    ok "mixed project start"
  else
    fail "mixed project start"
    return
  fi
  check_agent_binding "${project}" "writer" "codex"
  check_agent_binding "${project}" "reviewer" "claude"
  check_agent_binding "${project}" "analyst" "gemini"
  check_agent_ping "${project}" "writer" "codex"
  check_agent_ping "${project}" "reviewer" "claude"
  check_agent_ping "${project}" "analyst" "gemini"
  check_workspace_binding "${project}" "writer"
  check_workspace_binding "${project}" "reviewer"
  check_workspace_binding "${project}" "analyst"
  check_tmux_title "writer"
  check_tmux_title "reviewer"
  check_tmux_title "analyst"
  check_reply_flow "${project}" "writer" "user" "mixed-codex" "mixed writer"
  check_reply_flow "${project}" "reviewer" "writer" "mixed-claude" "mixed reviewer"
  check_reply_flow "${project}" "analyst" "reviewer" "mixed-gemini" "mixed analyst"
  check_broadcast_excludes_sender "${project}"
}

run_dual_provider_matrix() {
  local provider="$1"
  local project="$2"
  local session="$3"
  local agent_a="$4"
  local agent_b="$5"
  log "Dual ${provider}: ${agent_a} + ${agent_b}"
  init_git_repo "${project}"
  write_dual_provider_config "${project}" "${provider}" "${agent_a}" "${agent_b}"
  start_project "${session}" "${project}"
  if wait_for_start "${project}" 20 && wait_for_mount "${project}" 20; then
    ok "dual ${provider} start"
  else
    fail "dual ${provider} start"
    return
  fi
  check_agent_binding "${project}" "${agent_a}" "${provider}"
  check_agent_binding "${project}" "${agent_b}" "${provider}"
  check_workspace_binding "${project}" "${agent_a}"
  check_workspace_binding "${project}" "${agent_b}"
  check_tmux_title "${agent_a}"
  check_tmux_title "${agent_b}"

  local job_a job_b
  job_a="$(ask_job "${project}" "${agent_a}" "user" "${provider}-A")" || {
    fail "dual ${provider} ask ${agent_a}"
    return
  }
  job_b="$(ask_job "${project}" "${agent_b}" "user" "${provider}-B")" || {
    fail "dual ${provider} ask ${agent_b}"
    return
  }

  watch_reply "${project}" "${job_a}" >"${project}/reply-${job_a}.txt" &
  local pid_a=$!
  watch_reply "${project}" "${job_b}" >"${project}/reply-${job_b}.txt" &
  local pid_b=$!
  wait "${pid_a}" || fail "dual ${provider} watch ${agent_a}"
  wait "${pid_b}" || fail "dual ${provider} watch ${agent_b}"

  local reply_a reply_b
  reply_a="$(cat "${project}/reply-${job_a}.txt" 2>/dev/null || true)"
  reply_b="$(cat "${project}/reply-${job_b}.txt" 2>/dev/null || true)"
  if [ -n "${reply_a}" ] && [ -n "${reply_b}" ] && [ "${reply_a}" != "${reply_b}" ]; then
    ok "dual ${provider} distinct replies"
  else
    fail "dual ${provider} distinct replies"
  fi

  local pend_a pend_b
  pend_a="$(pend_reply "${project}" "${agent_a}")" || pend_a=""
  pend_b="$(pend_reply "${project}" "${agent_b}")" || pend_b=""
  if [ "${pend_a}" = "${reply_a}" ]; then
    ok "dual ${provider} pend ${agent_a}"
  else
    fail "dual ${provider} pend ${agent_a}"
  fi
  if [ "${pend_b}" = "${reply_b}" ]; then
    ok "dual ${provider} pend ${agent_b}"
  else
    fail "dual ${provider} pend ${agent_b}"
  fi
}

run_cross_project_matrix() {
  local project_a="${TEST_DIR1}/proj_a_${RUN_ID}"
  local project_b="${TEST_DIR2}/proj_b_${RUN_ID}"
  local session_a="proj-a-${RUN_ID}"
  local session_b="proj-b-${RUN_ID}"
  log "Cross-project isolation with same agent names"
  init_git_repo "${project_a}"
  init_git_repo "${project_b}"
  write_cross_project_config "${project_a}"
  write_cross_project_config "${project_b}"
  start_project "${session_a}" "${project_a}"
  start_project "${session_b}" "${project_b}"
  if wait_for_start "${project_a}" 20 && wait_for_mount "${project_a}" 20; then
    ok "project A start"
  else
    fail "project A start"
    return
  fi
  if wait_for_start "${project_b}" 20 && wait_for_mount "${project_b}" 20; then
    ok "project B start"
  else
    fail "project B start"
    return
  fi

  local ps_a ps_b
  ps_a="$(ccb_project "${project_a}" ps)" || ps_a=""
  ps_b="$(ccb_project "${project_b}" ps)" || ps_b=""
  local pid_a pid_b
  pid_a="$(printf '%s\n' "${ps_a}" | awk -F': ' '/^project_id: /{print $2; exit}')"
  pid_b="$(printf '%s\n' "${ps_b}" | awk -F': ' '/^project_id: /{print $2; exit}')"
  if [ -n "${pid_a}" ] && [ -n "${pid_b}" ] && [ "${pid_a}" != "${pid_b}" ]; then
    ok "cross-project ids"
  else
    fail "cross-project ids"
  fi

  local job_a job_b reply_a reply_b pend_a pend_b
  job_a="$(ask_job "${project_a}" "writer" "user" "project-a")" || {
    fail "cross-project ask A"
    return
  }
  job_b="$(ask_job "${project_b}" "writer" "user" "project-b")" || {
    fail "cross-project ask B"
    return
  }
  reply_a="$(watch_reply "${project_a}" "${job_a}")" || reply_a=""
  reply_b="$(watch_reply "${project_b}" "${job_b}")" || reply_b=""
  pend_a="$(pend_reply "${project_a}" "writer")" || pend_a=""
  pend_b="$(pend_reply "${project_b}" "writer")" || pend_b=""
  if [ -n "${reply_a}" ] && [ -n "${reply_b}" ] && [ "${reply_a}" != "${reply_b}" ]; then
    ok "cross-project distinct replies"
  else
    fail "cross-project distinct replies"
  fi
  if [ "${pend_a}" = "${reply_a}" ] && [ "${pend_b}" = "${reply_b}" ]; then
    ok "cross-project pend isolation"
  else
    fail "cross-project pend isolation"
  fi
}

run_kill_check() {
  local project="$1"
  log "Project kill cleanup"
  if ccb_project "${project}" kill >"${project}/kill.out" 2>"${project}/kill.err"; then
    ok "kill command"
  else
    fail "kill command"
    return
  fi
  local ping_out
  ping_out="$(ccb_project "${project}" ping ccbd)" || ping_out=""
  if printf '%s\n' "${ping_out}" | grep -F -q 'mount_state: unmounted'; then
    ok "kill unmounted ccbd"
  else
    fail "kill unmounted ccbd"
  fi
}

install_stub_providers
bootstrap_tmux_server
run_mixed_matrix
run_dual_provider_matrix "codex" "${TEST_DIR1}/dual_codex_${RUN_ID}" "dual-codex-${RUN_ID}" "codex_a" "codex_b"
run_dual_provider_matrix "claude" "${TEST_DIR1}/dual_claude_${RUN_ID}" "dual-claude-${RUN_ID}" "claude_a" "claude_b"
run_dual_provider_matrix "gemini" "${TEST_DIR1}/dual_gemini_${RUN_ID}" "dual-gemini-${RUN_ID}" "gemini_a" "gemini_b"
run_cross_project_matrix
run_kill_check "${TEST_DIR1}/mixed_${RUN_ID}"

if [ "${FAIL}" -ne 0 ]; then
  echo "FAILURES DETECTED"
  exit 1
fi
echo "ALL TESTS PASSED"
