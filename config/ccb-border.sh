#!/usr/bin/env bash
# CCB Border Color Script - sets active pane border based on pane title

arg="$1"
pane_id=""
title=""
agent=""

if [[ "$arg" == %* ]]; then
  pane_id="$arg"
  agent="$(tmux display-message -p -t "$pane_id" "#{@ccb_agent}" 2>/dev/null | tr -d '\r')"
  title="$(tmux display-message -p -t "$pane_id" "#{pane_title}" 2>/dev/null | tr -d '\r')"
else
  title="$arg"
fi

key="$(echo "${agent:-}" | tr -d '\n')"

set_border() {
  local style="$1"
  if [[ -n "$pane_id" ]]; then
    tmux set-window-option -t "$pane_id" pane-active-border-style "$style"
  else
    tmux set-window-option pane-active-border-style "$style"
  fi
}

case "$key" in
    Codex)
        set_border "fg=#ff9e64,bold"
        ;;
    Gemini)
        set_border "fg=#a6e3a1,bold"
        ;;
    Claude)
        set_border "fg=#f38ba8,bold"
        ;;
    OpenCode)
        set_border "fg=#ff79c6,bold"
        ;;
    *)
        case "$title" in
            CCB-Codex*)
                set_border "fg=#ff9e64,bold"
                ;;
            CCB-Gemini*)
                set_border "fg=#a6e3a1,bold"
                ;;
            Claude*)
                set_border "fg=#f38ba8,bold"
                ;;
            CCB-OpenCode*)
                set_border "fg=#ff79c6,bold"
                ;;
            *)
                set_border "fg=#7aa2f7,bold"
                ;;
        esac
        ;;
esac
