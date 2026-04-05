#!/usr/bin/env bash
set -euo pipefail

# Fast git branch indicator for tmux status line.
#
# Design goals:
# - Must return quickly even in huge repos.
# - Does expensive git calls in a background refresh.
# - Prints cached value when available; prints "-" as fallback.

path="${1:-}"

ttl_s_raw="${CCB_TMUX_GIT_TTL_S:-3}"
ttl_s=3
if [[ "$ttl_s_raw" =~ ^[0-9]+$ ]]; then
  ttl_s="$ttl_s_raw"
fi
if (( ttl_s < 0 )); then
  ttl_s=0
fi

cache_root="${XDG_CACHE_HOME:-$HOME/.cache}/ccb"
mkdir -p "$cache_root" 2>/dev/null || true

key="$(printf '%s' "$path" | cksum | awk '{print $1}' 2>/dev/null || echo 0)"
cache_file="$cache_root/tmux-git-${key}.cache"
lock_dir="$cache_root/tmux-git-${key}.lock"

now="$(date +%s 2>/dev/null || echo 0)"

read_cache() {
  local out="-"
  if [[ -f "$cache_file" ]]; then
    local ts=""
    ts="$(head -n 1 "$cache_file" 2>/dev/null || true)"
    if [[ "$ts" =~ ^[0-9]+$ ]] && (( ttl_s > 0 )) && (( now - ts < ttl_s )); then
      out="$(sed -n '2p' "$cache_file" 2>/dev/null || echo '-')"
      [[ -n "$out" ]] || out="-"
      echo "$out"
      return 0
    fi
    out="$(sed -n '2p' "$cache_file" 2>/dev/null || echo '-')"
    [[ -n "$out" ]] || out="-"
  fi
  echo "$out"
}

run_with_timeout() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 0.25 "$@"
  else
    "$@"
  fi
}

refresh_cache_async() {
  if [[ -z "$path" || ! -d "$path" ]]; then
    return 0
  fi

  if ! mkdir "$lock_dir" 2>/dev/null; then
    return 0
  fi

  (
    trap 'rmdir "$lock_dir" 2>/dev/null || true' EXIT
    local ts out branch dirty
    ts="$(date +%s 2>/dev/null || echo 0)"
    out="-"
    branch="$(GIT_OPTIONAL_LOCKS=0 run_with_timeout git -C "$path" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if [[ -n "$branch" ]]; then
      dirty=""
      if ! GIT_OPTIONAL_LOCKS=0 run_with_timeout git -C "$path" diff --quiet --ignore-submodules -- 2>/dev/null; then
        dirty="*"
      elif ! GIT_OPTIONAL_LOCKS=0 run_with_timeout git -C "$path" diff --cached --quiet --ignore-submodules -- 2>/dev/null; then
        dirty="*"
      fi
      out="${branch}${dirty}"
    fi
    tmp="${cache_file}.tmp.$$"
    {
      echo "$ts"
      echo "$out"
    } > "$tmp" 2>/dev/null || true
    mv -f "$tmp" "$cache_file" 2>/dev/null || true
  ) >/dev/null 2>&1 &
}

cached="$(read_cache)"
refresh_cache_async
echo "${cached:-"-"}"

