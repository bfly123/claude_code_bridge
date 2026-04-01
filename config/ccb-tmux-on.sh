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

# Detect terminal background to choose appropriate color palette
detect_theme() {
  local theme="${CCB_THEME:-auto}"
  case "$theme" in
    light|dark) echo "$theme" ;;
    auto|"")
      # Try to detect terminal background color via OSC 11 escape sequence
      # Timeout quickly to avoid blocking tmux startup
      local bg_rgb=""
      if command -v timeout >/dev/null 2>&1; then
        bg_rgb="$(timeout 0.3s bash -c 'printf "\033]11;?\033\\"; read -t 0.2 -r bg; echo "${bg#*;}"' 2>/dev/null || true)"
      fi
      if [[ -n "$bg_rgb" && "$bg_rgb" =~ rgb: ]]; then
        # Parse RGB values and calculate luminance (simplified)
        local hex="${bg_rgb#rgb:}"
        hex="${hex//\//}" # Remove slashes
        if [[ ${#hex} -ge 12 ]]; then
          local r=$((0x${hex:0:4} / 256))
          local g=$((0x${hex:4:4} / 256))
          local b=$((0x${hex:8:4} / 256))
          local luma=$(( (r * 299 + g * 587 + b * 114) / 1000 ))
          if [[ $luma -gt 128 ]]; then
            echo "light"
          else
            echo "dark"
          fi
        else
          echo "dark"
        fi
      else
        # Fallback: check common environment hints
        case "${COLORFGBG:-}" in
          *";15"|*";7") echo "light" ;;  # Light background
          *) echo "dark" ;;              # Dark or unknown
        esac
      fi
      ;;
    *) echo "dark" ;;
  esac
}

theme="$(detect_theme)"

# Color palettes
if [[ "$theme" == "light" ]]; then
  # Light theme colors (high contrast on light background)
  bg_main="#f8f9fa"      # Light gray background
  fg_main="#2d3748"      # Dark text
  bg_accent="#e2e8f0"    # Slightly darker gray
  fg_muted="#718096"     # Muted text

  # Accent colors (vibrant but readable on light bg)
  color_red="#d53f8c"    # Bright pink/red
  color_orange="#dd6b20" # Orange
  color_yellow="#d69e2e" # Gold
  color_green="#38a169"  # Green
  color_blue="#3182ce"   # Blue
  color_purple="#805ad5" # Purple
  color_teal="#319795"   # Teal
else
  # Dark theme colors (Catppuccin Mocha)
  bg_main="#1e1e2e"      # Dark background
  fg_main="#cdd6f4"      # Light text
  bg_accent="#313244"    # Lighter dark
  fg_muted="#6c7086"     # Muted text

  # Accent colors
  color_red="#f38ba8"    # Pink
  color_orange="#fab387" # Peach
  color_yellow="#f9e2af" # Yellow
  color_green="#a6e3a1"  # Green
  color_blue="#89b4fa"   # Blue
  color_purple="#cba6f7" # Mauve
  color_teal="#94e2d5"   # Teal
fi

tmux set-option -t "$session" status-position bottom >/dev/null 2>&1 || true
status_interval="${CCB_TMUX_STATUS_INTERVAL:-5}"
tmux set-option -t "$session" status-interval "$status_interval" >/dev/null 2>&1 || true
tmux set-option -t "$session" status-style "bg=${bg_main} fg=${fg_main}" >/dev/null 2>&1 || true
tmux set-option -t "$session" status 2 >/dev/null 2>&1 || true

tmux set-option -t "$session" status-left-length 80 >/dev/null 2>&1 || true
tmux set-option -t "$session" status-right-length 120 >/dev/null 2>&1 || true

# Second status line: quick hints
status_format_1="#[align=centre,bg=${bg_main},fg=${fg_muted}]Copy: MouseDrag  Paste: Shift-Ctrl-v  Focus: Ctrl-b o"
tmux set-option -t "$session" 'status-format[1]' "$status_format_1" >/dev/null 2>&1 || true

# First status line: left + center(folder) + right
status_format_0="#[align=left bg=${bg_main}]#{T:status-left}#[align=centre fg=${fg_muted}]#{b:pane_current_path}#[align=right]#{T:status-right}"
tmux set-option -t "$session" 'status-format[0]' "$status_format_0" >/dev/null 2>&1 || true

# Mode-aware status-left: [MODE] > [git-branch]
accent="#{?client_prefix,${color_red},#{?pane_in_mode,${color_orange},${color_purple}}}"
label='#{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}}'
git_info='-'
if [[ -x "$git_script" ]]; then
  # Cached to avoid blocking tmux (git can be slow in big repos).
  git_info="#(${git_script} \"#{pane_current_path}\")"
fi
tmux set-option -t "$session" status-left "#[fg=${bg_main},bg=${accent},bold] ${label} #[fg=${accent},bg=${color_purple}]#[fg=${bg_main},bg=${color_purple}] ${git_info} #[fg=${color_purple},bg=${bg_main}]" >/dev/null 2>&1 || true

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
status_right="#[fg=${color_red},bg=${bg_main}]#[fg=${bg_main},bg=${color_red},bold] ${focus_agent} #[fg=${color_purple},bg=${color_red}]#[fg=${bg_main},bg=${color_purple},bold] CCB:#{@ccb_version} #[fg=${color_blue},bg=${color_purple}]#[fg=${fg_main},bg=${color_blue}] #(${status_script} modern) #[fg=${color_orange},bg=${color_blue}]#[fg=${bg_main},bg=${color_orange},bold] %m/%d %a %H:%M #[default]"
tmux set-option -t "$session" status-right "$status_right" >/dev/null 2>&1 || true

tmux set-option -t "$session" window-status-format '' >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-current-format '' >/dev/null 2>&1 || true
tmux set-option -t "$session" window-status-separator '' >/dev/null 2>&1 || true

# Pane titles and borders (window options)
tmux set-window-option -t "$session" pane-border-status top >/dev/null 2>&1 || true

# Adaptive border colors based on theme
if [[ "$theme" == "light" ]]; then
  border_inactive="fg=#cbd5e0,bold"         # Light gray for inactive panes
  border_active="fg=${color_blue},bold"     # Blue for active pane
  pane_default_fg="#4a5568"                 # Dark text for pane titles
else
  border_inactive="fg=#3b4261,bold"         # Dark gray for inactive panes
  border_active="fg=#7aa2f7,bold"           # Light blue for active pane
  pane_default_fg="#565f89"                 # Light gray text for pane titles
fi

tmux set-window-option -t "$session" pane-border-style "$border_inactive" >/dev/null 2>&1 || true
tmux set-window-option -t "$session" pane-active-border-style "$border_active" >/dev/null 2>&1 || true

# Agent-specific pane title colors (consistent across themes)
pane_format='#{?#{==:#{@ccb_agent},Claude},#[fg='${bg_main}']#[bg='${color_red}']#[bold] #P Claude #[default],'
pane_format+='#{?#{==:#{@ccb_agent},Codex},#[fg='${bg_main}']#[bg='${color_orange}']#[bold] #P Codex #[default],'
pane_format+='#{?#{==:#{@ccb_agent},Gemini},#[fg='${bg_main}']#[bg='${color_green}']#[bold] #P Gemini #[default],'
pane_format+='#{?#{==:#{@ccb_agent},OpenCode},#[fg='${bg_main}']#[bg='${color_purple}']#[bold] #P OpenCode #[default],'
pane_format+='#{?#{==:#{@ccb_agent},Droid},#[fg='${bg_main}']#[bg='${color_yellow}']#[bold] #P Droid #[default],'
pane_format+='#{?#{==:#{@ccb_agent},Cmd},#[fg='${bg_main}']#[bg='${color_teal}']#[bold] #P Cmd #[default],'
pane_format+='#[fg='${pane_default_fg}'] #P #{pane_title} #[default]}}}}}}'

tmux set-window-option -t "$session" pane-border-format "$pane_format" >/dev/null 2>&1 || true

# Dynamic active-border color based on active pane agent (per-session hook).
tmux set-hook -t "$session" after-select-pane "run-shell \"${border_script} \\\"#{pane_id}\\\"\"" >/dev/null 2>&1 || true

# Apply once for current active pane (best-effort).
pane_id="$(tmux display-message -p '#{pane_id}' 2>/dev/null || true)"
if [[ -n "$pane_id" && -x "$border_script" ]]; then
  "$border_script" "$pane_id" >/dev/null 2>&1 || true
fi
