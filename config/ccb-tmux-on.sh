#!/usr/bin/env bash
set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
  exit 0
fi
if [[ -z "${TMUX:-}" ]]; then
  exit 0
fi

session="$(tmux display-message -p '#{session_name}' 2>/dev/null || true)"
if [[ -z "$session" ]]; then
  exit 0
fi

bin_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
status_script="$bin_dir/ccb-status.sh"
border_script="$bin_dir/ccb-border.sh"
git_script="$bin_dir/ccb-git.sh"

resolve_ccb_exec() {
  if [[ -x "$bin_dir/ccb" ]]; then
    printf '%s\n' "$bin_dir/ccb"
    return 0
  fi
  if [[ -x "$bin_dir/../ccb" && -d "$bin_dir/../lib" ]]; then
    printf '%s\n' "$bin_dir/../ccb"
    return 0
  fi
  command -v ccb 2>/dev/null || true
}

render_theme_exports() {
  local ccb_exec="$1"
  local ccb_version="$2"
  local py=""
  py="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
  if [[ -z "$py" || -z "$ccb_exec" ]]; then
    return 1
  fi
  "$py" - "$ccb_exec" "$ccb_version" "$status_script" "$git_script" <<'PY'
import os
from pathlib import Path
import sys

ccb_exec = Path(sys.argv[1]).resolve()
ccb_version = sys.argv[2]
status_script = sys.argv[3] or None
git_script = sys.argv[4] or None


def candidate_roots() -> list[Path]:
    roots: list[Path] = []
    env_root = str(os.environ.get('CODEX_INSTALL_PREFIX') or '').strip()
    if env_root:
        roots.append(Path(env_root).expanduser())
    roots.append(ccb_exec.parent)
    roots.append(ccb_exec.parent.parent)
    return roots


for root in candidate_roots():
    lib_dir = root / 'lib'
    if (lib_dir / 'terminal_runtime' / 'tmux_theme.py').is_file():
        sys.path.insert(0, str(lib_dir))
        break
else:
    raise SystemExit(1)

from terminal_runtime.tmux_theme import shell_exports

print(
    shell_exports(
        ccb_version=ccb_version,
        status_script=status_script,
        git_script=git_script,
    )
)
PY
}

save_sopt() {
  local opt="$1"
  local key="$2"
  local val=""
  val="$(tmux show-options -t "$session" -v "$opt" 2>/dev/null || true)"
  tmux set-option -t "$session" "$key" "$val" >/dev/null 2>&1 || true
}

save_wopt() {
  local opt="$1"
  local key="$2"
  local val=""
  val="$(tmux show-window-options -t "$session" -v "$opt" 2>/dev/null || true)"
  tmux set-option -t "$session" "$key" "$val" >/dev/null 2>&1 || true
}

save_hook() {
  local hook="$1"
  local key="$2"
  local line=""
  line="$(tmux show-hooks -t "$session" "$hook" 2>/dev/null | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    tmux set-option -t "$session" "$key" "" >/dev/null 2>&1 || true
    return 0
  fi
  # Drop leading "hook[0] " prefix; keep the command string as tmux expects.
  local cmd="${line#* }"
  tmux set-option -t "$session" "$key" "$cmd" >/dev/null 2>&1 || true
}

# Save current per-session/per-window UI settings so we can restore on exit.
save_sopt status @ccb_prev_status
save_sopt status-position @ccb_prev_status_position
save_sopt status-justify @ccb_prev_status_justify
save_sopt status-interval @ccb_prev_status_interval
save_sopt status-style @ccb_prev_status_style
save_sopt 'status-format[0]' @ccb_prev_status_format_0
save_sopt 'status-format[1]' @ccb_prev_status_format_1
save_sopt status-left-length @ccb_prev_status_left_length
save_sopt status-right-length @ccb_prev_status_right_length
save_sopt status-left @ccb_prev_status_left
save_sopt status-right @ccb_prev_status_right
save_sopt window-status-format @ccb_prev_window_status_format
save_sopt window-status-current-format @ccb_prev_window_status_current_format
save_sopt window-status-separator @ccb_prev_window_status_separator

save_wopt pane-border-status @ccb_prev_pane_border_status
save_wopt pane-border-format @ccb_prev_pane_border_format
save_wopt pane-border-style @ccb_prev_pane_border_style
save_wopt pane-active-border-style @ccb_prev_pane_active_border_style
save_wopt window-style @ccb_prev_window_style
save_wopt window-active-style @ccb_prev_window_active_style

save_hook after-select-pane @ccb_prev_hook_after_select_pane

tmux set-option -t "$session" @ccb_active "1" >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
# CCB UI Theme (applies only to this tmux session)
# ---------------------------------------------------------------------------

# Right: < Focus:AI < CCB:ver < ○○○○ < HH:MM
ccb_version="$(ccb --print-version 2>/dev/null || true)"
if [[ -z "$ccb_version" ]]; then
  ccb_path="$(command -v ccb 2>/dev/null || true)"
  if [[ -n "$ccb_path" && -f "$ccb_path" ]]; then
    ccb_version="$(grep -oE 'VERSION = \"[0-9]+\\.[0-9]+\\.[0-9]+\"' "$ccb_path" 2>/dev/null | head -n 1 | sed -E 's/.*\"([0-9]+\\.[0-9]+\\.[0-9]+)\"/v\\1/' || true)"
  fi
fi
[[ -n "$ccb_version" ]] || ccb_version="?"
theme_exports=""
ccb_exec="$(resolve_ccb_exec)"
if [[ -n "$ccb_exec" ]]; then
  theme_exports="$(render_theme_exports "$ccb_exec" "$ccb_version" 2>/dev/null || true)"
fi
if [[ -n "$theme_exports" ]]; then
  eval "$theme_exports"
fi

default_status_format_1='#[align=centre,bg=#1e1e2e,fg=#6c7086]Copy: MouseDrag  Paste: Shift-Ctrl-v  Focus: Ctrl-b o'
default_status_format_0='#[align=left bg=#1e1e2e]#{T:status-left}#[align=centre fg=#6c7086]#{b:pane_current_path}#[align=right]#{T:status-right}'
default_status_left='#[fg=#1e1e2e,bg=#{?client_prefix,#f38ba8,#{?pane_in_mode,#fab387,#f5c2e7}},bold] #{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}} #[fg=#{?client_prefix,#f38ba8,#{?pane_in_mode,#fab387,#f5c2e7}},bg=#cba6f7]#[fg=#1e1e2e,bg=#cba6f7] - #[fg=#cba6f7,bg=#1e1e2e]'
default_status_right="#[fg=#f38ba8,bg=#1e1e2e]#[fg=#1e1e2e,bg=#f38ba8,bold] #{?#{@ccb_agent},#{@ccb_agent},-} #[fg=#cba6f7,bg=#f38ba8]#[fg=#1e1e2e,bg=#cba6f7,bold] CCB:#{@ccb_version} #[fg=#89b4fa,bg=#cba6f7]#[fg=#cdd6f4,bg=#89b4fa] #(${status_script} modern) #[fg=#fab387,bg=#89b4fa]#[fg=#1e1e2e,bg=#fab387,bold] %m/%d %a %H:%M #[default]"
default_pane_border_format='#{?#{@ccb_agent},#{?#{@ccb_label_style},#{@ccb_label_style},#[fg=#1e1e2e]#[bg=#7aa2f7]#[bold]} #{@ccb_agent} #[default],#[fg=#565f89] #{pane_title} #[default]}'

tmux set-option -t "$session" status-position "${CCB_TMUX_RENDERED_STATUS_POSITION:-bottom}" >/dev/null 2>&1 || true
tmux set-option -t "$session" status-interval "${CCB_TMUX_RENDERED_STATUS_INTERVAL:-5}" >/dev/null 2>&1 || true
tmux set-option -t "$session" status-style "${CCB_TMUX_RENDERED_STATUS_STYLE:-bg=#1e1e2e fg=#cdd6f4}" >/dev/null 2>&1 || true
tmux set-option -t "$session" status "${CCB_TMUX_RENDERED_STATUS_LINES:-2}" >/dev/null 2>&1 || true
tmux set-option -t "$session" @ccb_theme_profile "${CCB_TMUX_RENDERED_THEME_PROFILE:-default}" >/dev/null 2>&1 || true
tmux set-option -t "$session" status-left-length "${CCB_TMUX_RENDERED_STATUS_LEFT_LENGTH:-80}" >/dev/null 2>&1 || true
tmux set-option -t "$session" status-right-length "${CCB_TMUX_RENDERED_STATUS_RIGHT_LENGTH:-120}" >/dev/null 2>&1 || true
tmux set-option -t "$session" 'status-format[1]' "${CCB_TMUX_RENDERED_STATUS_FORMAT_1:-$default_status_format_1}" >/dev/null 2>&1 || true
tmux set-option -t "$session" 'status-format[0]' "${CCB_TMUX_RENDERED_STATUS_FORMAT_0:-$default_status_format_0}" >/dev/null 2>&1 || true
tmux set-option -t "$session" status-left "${CCB_TMUX_RENDERED_STATUS_LEFT:-$default_status_left}" >/dev/null 2>&1 || true
tmux set-option -t "$session" @ccb_version "$ccb_version" >/dev/null 2>&1 || true
tmux set-option -t "$session" status-right "${CCB_TMUX_RENDERED_STATUS_RIGHT:-$default_status_right}" >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-format "${CCB_TMUX_RENDERED_WINDOW_STATUS_FORMAT:-}" >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-current-format "${CCB_TMUX_RENDERED_WINDOW_STATUS_CURRENT_FORMAT:-}" >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-separator "${CCB_TMUX_RENDERED_WINDOW_STATUS_SEPARATOR:-}" >/dev/null 2>&1 || true

# Pane titles and borders (window options)
# Prefer logical agent names from `@ccb_agent` so pane headers stay name-first.
tmux set-window-option -t "$session" pane-border-status "${CCB_TMUX_RENDERED_PANE_BORDER_STATUS:-top}" >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-border-style "${CCB_TMUX_RENDERED_PANE_BORDER_STYLE:-fg=#3b4261,bold}" >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-active-border-style "${CCB_TMUX_RENDERED_PANE_ACTIVE_BORDER_STYLE:-fg=#7aa2f7,bold}" >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-border-format "${CCB_TMUX_RENDERED_PANE_BORDER_FORMAT:-$default_pane_border_format}" >/dev/null 2>&1 || true
if [[ -n "${CCB_TMUX_RENDERED_WINDOW_STYLE:-}" ]]; then
  tmux set-window-option -t "$session" window-style "$CCB_TMUX_RENDERED_WINDOW_STYLE" >/dev/null 2>&1 || true
fi
if [[ -n "${CCB_TMUX_RENDERED_WINDOW_ACTIVE_STYLE:-}" ]]; then
  tmux set-window-option -t "$session" window-active-style "$CCB_TMUX_RENDERED_WINDOW_ACTIVE_STYLE" >/dev/null 2>&1 || true
fi

# Dynamic active-border color based on active pane agent (per-session hook).
tmux set-hook -t "$session" after-select-pane "run-shell \"${border_script} \\\"#{pane_id}\\\"\"" >/dev/null 2>&1 || true

# Apply once for current active pane (best-effort).
pane_id="$(tmux display-message -p '#{pane_id}' 2>/dev/null || true)"
if [[ -n "$pane_id" && -x "$border_script" ]]; then
  "$border_script" "$pane_id" >/dev/null 2>&1 || true
fi
