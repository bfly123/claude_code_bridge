#!/usr/bin/env bash
# CCB Status Bar Script for tmux
# Shows daemon status and active AI sessions

CCB_DIR="${CCB_DIR:-$HOME/.local/share/ccb}"
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

# Check if a daemon is running by looking for its PID file or process
check_daemon() {
    local name="$1"
    local pid_file="$TMP_DIR/ccb-${name}d.pid"

    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file" 2>/dev/null)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "on"
            return
        fi
    fi

    # Optional fallback: pgrep can be expensive; keep it opt-in.
    if [[ "${CCB_STATUS_ALLOW_PGREP:-0}" == "1" ]]; then
        if pgrep -f "${name}d" >/dev/null 2>&1; then
            echo "on"
            return
        fi
    fi

    echo "off"
}

# Check if a session file exists and is recent (active session)
check_session() {
    local name="$1"
    local session_file

    case "$name" in
        claude)  session_file="$PWD/.ccb_config/.claude-session" ;;
        codex)   session_file="$PWD/.ccb_config/.codex-session" ;;
        gemini)  session_file="$PWD/.ccb_config/.gemini-session" ;;
        opencode) session_file="$PWD/.ccb_config/.opencode-session" ;;
    esac

    # Backwards compatibility: older versions stored session files in project root.
    if [[ -n "$session_file" && ! -f "$session_file" ]]; then
        local legacy="${session_file/.ccb_config\\//}"
        if [[ -f "$legacy" ]]; then
            session_file="$legacy"
        fi
    fi

    if [[ -f "$session_file" ]]; then
        echo "active"
    else
        echo "inactive"
    fi
}

cca_status_for_path() {
    local work_dir="$1"
    if [[ -z "$work_dir" || ! -d "$work_dir" ]]; then
        echo "OFF"
        return
    fi

    local autoflow_dir="$work_dir/.autoflow"
    if [[ ! -d "$autoflow_dir" ]]; then
        echo "OFF"
        return
    fi

    local role=""
    local cfg=""
    for cfg in "$autoflow_dir/roles.session.json" "$autoflow_dir/roles.json"; do
        if [[ -f "$cfg" ]]; then
            local py
            py="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
            if [[ -n "$py" ]]; then
                role="$("$py" - "$cfg" <<'PY'
import json,re,sys
path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    data = {}
providers = {
    "claude","codex","opencode","gemini","oc","cc","ge",
}
def _is_providerish(value):
    if not isinstance(value, str):
        return False
    val = value.strip()
    if not val:
        return False
    tokens = re.findall(r"[a-z0-9_]+", val.lower())
    return bool(tokens) and all(tok in providers for tok in tokens)
def _normalize(val):
    if isinstance(val, str):
        return "" if _is_providerish(val) else val
    if isinstance(val, (list, tuple)):
        items = [v for v in (_normalize(v) for v in val) if v]
        return ",".join(items)
    if isinstance(val, dict):
        for key in ("plan","scheme","role","role_type","roleType","roleset","type","profile","group","team","mode","name"):
            if key in val:
                out = _normalize(val.get(key))
                if out:
                    return out
    return ""
def _first_value(keys):
    for key in keys:
        out = _normalize(data.get(key))
        if out:
            return out
    return ""
out = _first_value(("plan","scheme","role","role_type","roleType","roleset","type","profile","group","team","mode","roles"))
if out:
    print(out)
PY
)"
            else
                role="$(grep -Eo '"(plan|scheme|role_type|roleType|roleset|role|type|profile|group|team|mode|roles)"\\s*:\\s*"[^"]+"' "$cfg" 2>/dev/null | head -n1 | sed -E 's/.*:"([^"]+)"/\\1/' || true)"
                if [[ -n "$role" ]]; then
                    local role_lc
                    role_lc="$(printf '%s' "$role" | tr '[:upper:]' '[:lower:]')"
                    local tokens
                    tokens="$(printf '%s' "$role_lc" | tr '+,/' '   ' | tr -c 'a-z0-9_ ' ' ')"
                    local providerish=1
                    local t
                    for t in $tokens; do
                        case "$t" in
                            claude|codex|opencode|gemini|oc|cc|ge) ;;
                            *) providerish=0; break ;;
                        esac
                    done
                    if (( providerish )); then
                        role=""
                    fi
                fi
            fi
            break
        fi
    done

    if [[ -n "$role" ]]; then
        echo "$role"
    else
        echo "OFF"
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
    if [[ "$mode" == "cca" ]]; then
        cache_key="$(printf '%s' "${2:-}" | cksum 2>/dev/null | awk '{print $1}')"
    fi
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

            out=" ${claude_s}${codex_s}${gemini_s}${opencode_s} "
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

            out="${output}"
            ;;

        pane)
            # Show pane-specific info (for status-left)
            local pane_title="${TMUX_PANE_TITLE:-}"
            if [[ "$pane_title" == CCB-* ]]; then
                local ai_name="${pane_title#CCB-}"
                case "$ai_name" in
                    claude|codex) echo "${C_ORANGE}[$ai_name]${C_RESET}" ;;
                    gemini)       echo "${C_BLUE}[$ai_name]${C_RESET}" ;;
                    opencode)     echo "${C_PURPLE}[$ai_name]${C_RESET}" ;;
                    *)            echo "[$ai_name]" ;;
                esac
            fi
            ;;
        cca)
            local work_dir="${2:-}"
            out="$(cca_status_for_path "$work_dir")"
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
