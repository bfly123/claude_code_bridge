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
save_sopt status-position @ccb_prev_status_position
save_sopt status-interval @ccb_prev_status_interval
save_sopt status-style @ccb_prev_status_style
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

save_hook after-select-pane @ccb_prev_hook_after_select_pane

tmux set-option -t "$session" @ccb_active "1" >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
# CCB UI Theme (applies only to this tmux session)
# ---------------------------------------------------------------------------

tmux set-option -t "$session" status-position bottom >/dev/null 2>&1 || true
status_interval="${CCB_TMUX_STATUS_INTERVAL:-5}"
tmux set-option -t "$session" status-interval "$status_interval" >/dev/null 2>&1 || true
tmux set-option -t "$session" status-style 'bg=#1e1e2e fg=#cdd6f4' >/dev/null 2>&1 || true
tmux set-option -t "$session" status 2 >/dev/null 2>&1 || true

tmux set-option -t "$session" status-left-length 80 >/dev/null 2>&1 || true
tmux set-option -t "$session" status-right-length 120 >/dev/null 2>&1 || true

# Second status line: quick hints
status_format_1="#[align=centre,bg=#1e1e2e,fg=#6c7086]Copy: MouseDrag  Paste: Shift-Ctrl-v  Focus: Ctrl-b o"
tmux set-option -t "$session" 'status-format[1]' "$status_format_1" >/dev/null 2>&1 || true

# First status line: left + center(folder) + right
status_format_0="#[align=left bg=#1e1e2e]#{T:status-left}#[align=centre fg=#6c7086]#{b:pane_current_path}#[align=right]#{T:status-right}"
tmux set-option -t "$session" 'status-format[0]' "$status_format_0" >/dev/null 2>&1 || true

# Mode-aware status-left: [MODE] > [git-branch]
accent='#{?client_prefix,#f38ba8,#{?pane_in_mode,#fab387,#f5c2e7}}'
label='#{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}}'
git_info='-'
if [[ -x "$git_script" ]]; then
  # Cached to avoid blocking tmux (git can be slow in big repos).
  git_info="#(${git_script} \"#{pane_current_path}\")"
fi
tmux set-option -t "$session" status-left "#[fg=#1e1e2e,bg=${accent},bold] ${label} #[fg=${accent},bg=#cba6f7]#[fg=#1e1e2e,bg=#cba6f7] ${git_info} #[fg=#cba6f7,bg=#1e1e2e]" >/dev/null 2>&1 || true

# Right: < Focus:AI < CCB:ver < ○○○○ < HH:MM
ccb_version="$(ccb --print-version 2>/dev/null || true)"
if [[ -z "$ccb_version" ]]; then
  ccb_path="$(command -v ccb 2>/dev/null || true)"
  if [[ -n "$ccb_path" && -f "$ccb_path" ]]; then
    ccb_version="$(grep -oE 'VERSION = \"[0-9]+\\.[0-9]+\\.[0-9]+\"' "$ccb_path" 2>/dev/null | head -n 1 | sed -E 's/.*\"([0-9]+\\.[0-9]+\\.[0-9]+)\"/v\\1/' || true)"
  fi
fi
[[ -n "$ccb_version" ]] || ccb_version="?"
tmux set-option -t "$session" @ccb_version "$ccb_version" >/dev/null 2>&1 || true

focus_agent='#{?#{@ccb_agent},#{@ccb_agent},-}'
status_right="#[fg=#f38ba8,bg=#1e1e2e]#[fg=#1e1e2e,bg=#f38ba8,bold] ${focus_agent} #[fg=#cba6f7,bg=#f38ba8]#[fg=#1e1e2e,bg=#cba6f7,bold] CCB:#{@ccb_version} #[fg=#89b4fa,bg=#cba6f7]#[fg=#cdd6f4,bg=#89b4fa] #(${status_script} modern) #[fg=#fab387,bg=#89b4fa]#[fg=#1e1e2e,bg=#fab387,bold] %m/%d %a %H:%M #[default]"
tmux set-option -t "$session" status-right "$status_right" >/dev/null 2>&1 || true

tmux set-option -t "$session" window-status-format '' >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-current-format '' >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-separator '' >/dev/null 2>&1 || true

# Pane titles and borders (window options)
# Prefer logical agent names from `@ccb_agent` so pane headers stay name-first.
tmux set-window-option -t "$session" pane-border-status top >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-border-style 'fg=#3b4261,bold' >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-active-border-style 'fg=#7aa2f7,bold' >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-border-format '#{?#{@ccb_agent},#{?#{@ccb_label_style},#{@ccb_label_style},#[fg=#1e1e2e]#[bg=#7aa2f7]#[bold]} #{@ccb_agent} #[default],#[fg=#565f89] #{pane_title} #[default]}' >/dev/null 2>&1 || true

# Dynamic active-border color based on active pane agent (per-session hook).
tmux set-hook -t "$session" after-select-pane "run-shell \"${border_script} \\\"#{pane_id}\\\"\"" >/dev/null 2>&1 || true

# Apply once for current active pane (best-effort).
pane_id="$(tmux display-message -p '#{pane_id}' 2>/dev/null || true)"
if [[ -n "$pane_id" && -x "$border_script" ]]; then
  "$border_script" "$pane_id" >/dev/null 2>&1 || true
fi
