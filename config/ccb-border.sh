#!/usr/bin/env bash
# CCB Border Color Script - syncs active pane border from pane metadata

arg="$1"
pane_id=""

if [[ "$arg" == %* ]]; then
  pane_id="$arg"
else
  exit 0
fi

style="$(tmux display-message -p -t "$pane_id" "#{@ccb_active_border_style}" 2>/dev/null | tr -d '\r')"
if [[ -z "$style" ]]; then
  style="$(tmux display-message -p -t "$pane_id" "#{@ccb_border_style}" 2>/dev/null | tr -d '\r')"
fi
if [[ -z "$style" ]]; then
  style="fg=#7aa2f7,bold"
fi

set_border() {
  local style="$1"
  if [[ -n "$pane_id" ]]; then
    # Use set-option -p for pane-level option with pane_id target
    tmux set-option -p -t "$pane_id" pane-active-border-style "$style" 2>/dev/null || \
    tmux set-window-option pane-active-border-style "$style" 2>/dev/null || true
  else
    tmux set-window-option pane-active-border-style "$style" 2>/dev/null || true
  fi
}

set_border "$style"
