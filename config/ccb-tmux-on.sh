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
tmux set-option -t "$session" status-interval 5 >/dev/null 2>&1 || true
tmux set-option -t "$session" status-style 'bg=#1e1e2e fg=#cdd6f4' >/dev/null 2>&1 || true

tmux set-option -t "$session" status-left-length 50 >/dev/null 2>&1 || true
tmux set-option -t "$session" status-right-length 120 >/dev/null 2>&1 || true

tmux set-option -t "$session" status-left '#[fg=#1e1e2e,bg=#f5c2e7,bold]  #S #[fg=#f5c2e7,bg=#cba6f7]#[fg=#1e1e2e,bg=#cba6f7] CCB #[fg=#cba6f7,bg=#1e1e2e]' >/dev/null 2>&1 || true

# Prefer the stable pane user option `@ccb_agent` (set by ccb) over volatile `pane_title`.
tmux set-option -t "$session" status-right '#{?#{==:#{@ccb_agent},Codex},#[fg=#1e1e2e]#[bg=#ff9e64]#[bold] Codex #[default],#{?#{==:#{@ccb_agent},Gemini},#[fg=#1e1e2e]#[bg=#a6e3a1]#[bold] Gemini #[default],#{?#{==:#{@ccb_agent},OpenCode},#[fg=#1e1e2e]#[bg=#ff79c6]#[bold] OpenCode #[default],#{?#{==:#{@ccb_agent},Claude},#[fg=#1e1e2e]#[bg=#f38ba8]#[bold] Claude #[default],#[fg=#6c7086] #{pane_title} #[default]}}}} #[fg=#1e1e2e,bg=#89b4fa,bold] AI #(~/.local/bin/ccb-status.sh compact) #[default] #[fg=#1e1e2e,bg=#a6e3a1,bold] %H:%M #[default] #[fg=#1e1e2e,bg=#fab387,bold] %m/%d #[default]' >/dev/null 2>&1 || true

tmux set-option -t "$session" window-status-format '#[fg=#6c7086] #I:#W ' >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-current-format '#[fg=#1e1e2e,bg=#89b4fa,bold] #I:#W #[fg=#89b4fa,bg=#1e1e2e]' >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-separator '' >/dev/null 2>&1 || true

# Pane titles and borders (window options)
tmux set-window-option -t "$session" pane-border-status top >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-border-style 'fg=#3b4261,bold' >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-active-border-style 'fg=#7aa2f7,bold' >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-border-format '#{?#{==:#{@ccb_agent},Claude},#[fg=#1e1e2e]#[bg=#f38ba8]#[bold] #P Claude #[default],#{?#{==:#{@ccb_agent},Codex},#[fg=#1e1e2e]#[bg=#ff9e64]#[bold] #P Codex #[default],#{?#{==:#{@ccb_agent},Gemini},#[fg=#1e1e2e]#[bg=#a6e3a1]#[bold] #P Gemini #[default],#{?#{==:#{@ccb_agent},OpenCode},#[fg=#1e1e2e]#[bg=#ff79c6]#[bold] #P OpenCode #[default],#[fg=#565f89] #P #{pane_title} #[default]}}}}' >/dev/null 2>&1 || true

# Dynamic active-border color based on active pane agent (per-session hook).
tmux set-hook -t "$session" after-select-pane 'run-shell "~/.local/bin/ccb-border.sh \"#{pane_id}\""' >/dev/null 2>&1 || true

# Apply once for current active pane (best-effort).
pane_id="$(tmux display-message -p '#{pane_id}' 2>/dev/null || true)"
if [[ -n "$pane_id" && -x "$HOME/.local/bin/ccb-border.sh" ]]; then
  "$HOME/.local/bin/ccb-border.sh" "$pane_id" >/dev/null 2>&1 || true
fi

