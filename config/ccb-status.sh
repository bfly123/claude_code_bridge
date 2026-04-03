#!/usr/bin/env bash
# CCB Status Bar Script for tmux
# Shows daemon status and active AI sessions

CCB_DIR="${CCB_DIR:-$HOME/.local/share/ccb}"
CCB_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/ccb"
TMP_DIR="${TMPDIR:-/tmp}"

# Color codes for tmux status bar (Tokyo Night palette)
C_GREEN="#[fg=#9ece6a,bold]"
C_RED="#[fg=#f7768e,bold]"
C_YELLOW="#[fg=#e0af68,bold]"
C_BLUE="#[fg=#7aa2f7,bold]"
C_PURPLE="#[fg=#bb9af7,bold]"
C_ORANGE="#[fg=#ff9e64,bold]"
C_PINK="#[fg=#ff007c,bold]"
C_TEAL="#[fg=#7dcfff,bold]"
C_RESET="#[fg=default,nobold]"
C_DIM="#[fg=#565f89]"

# Check if a daemon is running via pgrep
check_daemon() {
    local name="$1"
    if pgrep -f "bin/${name}d$" >/dev/null 2>&1; then
        echo "on"
    else
        echo "off"
    fi
}

# Check if a session file exists and is recent (active session)
check_session() {
    local name="$1"
    local session_file
    local suffix=""
    if [[ -n "$CCB_SESSION_NAME" ]]; then
        suffix="-${CCB_SESSION_NAME}"
    fi

    case "$name" in
        claude)  session_file="$PWD/.ccb/.claude${suffix}-session" ;;
        codex)   session_file="$PWD/.ccb/.codex${suffix}-session" ;;
        gemini)  session_file="$PWD/.ccb/.gemini${suffix}-session" ;;
        opencode) session_file="$PWD/.ccb/.opencode${suffix}-session" ;;
        droid)   session_file="$PWD/.ccb/.droid${suffix}-session" ;;
    esac

    # Backwards compatibility: legacy config dir or root-level session file.
    if [[ -n "$session_file" && ! -f "$session_file" ]]; then
        local legacy_dir="${session_file/.ccb\\//.ccb_config/}"
        if [[ -f "$legacy_dir" ]]; then
            session_file="$legacy_dir"
        else
            local legacy="${session_file/.ccb\\//}"
            if [[ -f "$legacy" ]]; then
                session_file="$legacy"
            fi
        fi
    fi

    if [[ -f "$session_file" ]]; then
        echo "active"
    else
        echo "inactive"
    fi
}

# Get queue depth for a daemon (if available)
get_queue_depth() {
    local name="$1"
    local queue_file="$TMP_DIR/ccb-${name}d.queue"

    if [[ -f "$queue_file" ]]; then
        wc -l < "$queue_file" 2>/dev/null | tr -d ' '
    else
        echo "0"
    fi
}

# Format status for a single AI
format_ai_status() {
    local name="$1"
    local icon="$2"
    local color="$3"
    local daemon_status

    daemon_status=$(check_daemon "$name")

    if [[ "$daemon_status" == "on" ]]; then
        echo "${color}${icon}${C_RESET}"
    else
        echo "#[fg=colour240]${icon}${C_RESET}"
    fi
}

# Main status output
main() {
    local mode="${1:-full}"
    local cache_s="${CCB_STATUS_CACHE_S:-1}"
    local cache_key=""
    local cache_suffix="${cache_key:-default}"
    local cache_file="$TMP_DIR/ccb-status.${mode}.${cache_suffix}.cache"

    # Simple cache to avoid hammering the system on frequent tmux redraws.
    if [[ "$cache_s" =~ ^[0-9]+$ ]] && (( cache_s > 0 )) && [[ -f "$cache_file" ]]; then
        local now ts cached
        now="$(date +%s 2>/dev/null || echo 0)"
        ts="$(head -n 1 "$cache_file" 2>/dev/null || true)"
        if [[ "$ts" =~ ^[0-9]+$ ]] && (( now - ts < cache_s )); then
            cached="$(sed -n '2p' "$cache_file" 2>/dev/null || true)"
            if [[ -n "$cached" ]]; then
                echo "$cached"
                return 0
            fi
        fi
    fi

    case "$mode" in
        full)
            # Full status with all AIs
            local claude_s=$(format_ai_status "cask" "C" "$C_ORANGE")
            local codex_s=$(format_ai_status "cask" "X" "$C_GREEN")
            local gemini_s=$(format_ai_status "gask" "G" "$C_BLUE")
            local opencode_s=$(format_ai_status "oask" "O" "$C_PURPLE")
            local droid_s=$(format_ai_status "dask" "D" "$C_YELLOW")

            out=" ${claude_s}${codex_s}${gemini_s}${opencode_s}${droid_s} "
            ;;

        daemons)
            # Just daemon status icons
            local output=""

            if [[ $(check_daemon "cask") == "on" ]]; then
                output+="${C_GREEN}X${C_RESET}"
            fi
            if [[ $(check_daemon "gask") == "on" ]]; then
                output+="${C_BLUE}G${C_RESET}"
            fi
            if [[ $(check_daemon "oask") == "on" ]]; then
                output+="${C_PURPLE}O${C_RESET}"
            fi
            if [[ $(check_daemon "dask") == "on" ]]; then
                output+="${C_YELLOW}D${C_RESET}"
            fi

            if [[ -n "$output" ]]; then
                out=" $output "
            fi
            ;;

        compact)
            # Compact colorful status with individual daemon icons
            local output="${C_PINK}CCB${C_RESET} "
            local icons=""

            # Use circles/dots for status
            if [[ $(check_daemon "cask") == "on" ]]; then
                icons+="${C_ORANGE}●${C_RESET} "
            else
                icons+="${C_DIM}○${C_RESET} "
            fi
            if [[ $(check_daemon "gask") == "on" ]]; then
                icons+="${C_TEAL}●${C_RESET} "
            else
                icons+="${C_DIM}○${C_RESET} "
            fi
            if [[ $(check_daemon "oask") == "on" ]]; then
                icons+="${C_PURPLE}●${C_RESET}"
            else
                icons+="${C_DIM}○${C_RESET}"
            fi
            if [[ $(check_daemon "dask") == "on" ]]; then
                icons+=" ${C_YELLOW}●${C_RESET}"
            else
                icons+=" ${C_DIM}○${C_RESET}"
            fi

            out="${output}${icons}"
            ;;

        modern)
            # Modern status: C X G O with dots (● = online, ○ = offline)
            local output=""

            # C - Claude (no daemon, always dim)
            output+="${C_DIM}○${C_RESET} "

            # X - Codex (cask daemon)
            if [[ $(check_daemon "cask") == "on" ]]; then
                output+="${C_ORANGE}●${C_RESET} "
            else
                output+="${C_DIM}○${C_RESET} "
            fi

            # G - Gemini (gask daemon)
            if [[ $(check_daemon "gask") == "on" ]]; then
                output+="${C_TEAL}●${C_RESET} "
            else
                output+="${C_DIM}○${C_RESET} "
            fi

            # O - OpenCode (oask daemon)
            if [[ $(check_daemon "oask") == "on" ]]; then
                output+="${C_PURPLE}●${C_RESET}"
            else
                output+="${C_DIM}○${C_RESET}"
            fi

            # D - Droid (dask daemon)
            if [[ $(check_daemon "dask") == "on" ]]; then
                output+=" ${C_YELLOW}●${C_RESET}"
            else
                output+=" ${C_DIM}○${C_RESET}"
            fi

            out="${output}"
            ;;

        pane)
            # Show pane-specific info (for status-left)
            local pane_title="${TMUX_PANE_TITLE:-}"
            local pane_title_lc
            pane_title_lc="$(printf '%s' "$pane_title" | tr '[:upper:]' '[:lower:]')"
            if [[ "$pane_title_lc" == ccb-* ]]; then
                local ai_name="${pane_title#CCB-}"
                ai_name="${ai_name#ccb-}"
                local ai_key
                ai_key="$(printf '%s' "$ai_name" | tr '[:upper:]' '[:lower:]')"
                case "$ai_key" in
                    claude|codex) echo "${C_ORANGE}[$ai_name]${C_RESET}" ;;
                    gemini)       echo "${C_BLUE}[$ai_name]${C_RESET}" ;;
                    opencode)     echo "${C_PURPLE}[$ai_name]${C_RESET}" ;;
                    droid)        echo "${C_YELLOW}[$ai_name]${C_RESET}" ;;
                    cmd)          echo "${C_TEAL}[$ai_name]${C_RESET}" ;;
                    *)            echo "[$ai_name]" ;;
                esac
            fi
            ;;
    esac

    if [[ -n "${out:-}" ]]; then
        if [[ "$cache_s" =~ ^[0-9]+$ ]] && (( cache_s > 0 )); then
            now="$(date +%s 2>/dev/null || echo 0)"
            tmp="${cache_file}.tmp.$$"
            {
                echo "$now"
                echo "$out"
            } > "$tmp" 2>/dev/null || true
            mv -f "$tmp" "$cache_file" 2>/dev/null || true
        fi
        echo "$out"
    fi
}

main "$@"
