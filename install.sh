#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PREFIX="${CODEX_INSTALL_PREFIX:-$HOME/.local/share/codex-dual}"
BIN_DIR="${CODEX_BIN_DIR:-$HOME/.local/bin}"
readonly REPO_ROOT INSTALL_PREFIX BIN_DIR

# i18n support
detect_lang() {
  local lang="${CCB_LANG:-auto}"
  case "$lang" in
    zh|cn|chinese) echo "zh" ;;
    en|english) echo "en" ;;
    *)
      local sys_lang="${LANG:-${LC_ALL:-${LC_MESSAGES:-}}}"
      if [[ "$sys_lang" == zh* ]] || [[ "$sys_lang" == *chinese* ]]; then
        echo "zh"
      else
        echo "en"
      fi
      ;;
  esac
}

CCB_LANG_DETECTED="$(detect_lang)"

# Message function
msg() {
  local key="$1"
  shift
  local en_msg zh_msg
  case "$key" in
    install_complete)
      en_msg="Installation complete"
      zh_msg="安装完成" ;;
    uninstall_complete)
      en_msg="Uninstall complete"
      zh_msg="卸载完成" ;;
    python_version_old)
      en_msg="Python version too old: $1"
      zh_msg="Python 版本过旧: $1" ;;
    requires_python)
      en_msg="Requires Python 3.10+"
      zh_msg="需要 Python 3.10+" ;;
    missing_dep)
      en_msg="Missing dependency: $1"
      zh_msg="缺少依赖: $1" ;;
    detected_env)
      en_msg="Detected $1 environment"
      zh_msg="检测到 $1 环境" ;;
    confirm_wsl)
      en_msg="Confirm continue installing in WSL? (y/N)"
      zh_msg="确认继续在 WSL 中安装？(y/N)" ;;
    cancelled)
      en_msg="Installation cancelled"
      zh_msg="安装已取消" ;;
    wsl_warning)
      en_msg="Detected WSL environment"
      zh_msg="检测到 WSL 环境" ;;
    same_env_required)
      en_msg="ccb/cask-w must run in the same environment as codex/gemini."
      zh_msg="ccb/cask-w 必须与 codex/gemini 在同一环境运行。" ;;
    confirm_wsl_native)
      en_msg="Please confirm: you will install and run codex/gemini in WSL (not Windows native)."
      zh_msg="请确认：你将在 WSL 中安装并运行 codex/gemini（不是 Windows 原生）。" ;;
    wezterm_recommended)
      en_msg="Recommend installing WezTerm as terminal frontend"
      zh_msg="推荐安装 WezTerm 作为终端前端" ;;
    root_error)
      en_msg="ERROR: Do not run as root/sudo. Please run as normal user."
      zh_msg="错误：请勿以 root/sudo 身份运行。请使用普通用户执行。" ;;
    *)
      en_msg="$key"
      zh_msg="$key" ;;
  esac
  if [[ "$CCB_LANG_DETECTED" == "zh" ]]; then
    echo "$zh_msg"
  else
    echo "$en_msg"
  fi
}

# Check for root/sudo - refuse to run as root
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  msg root_error >&2
  exit 1
fi

SCRIPTS_TO_LINK=(
  bin/cask
  bin/cask-w
  bin/caskd
  bin/cpend
  bin/cping
  bin/gask
  bin/gask-w
  bin/gaskd
  bin/gpend
  bin/gping
  bin/oask
  bin/oask-w
  bin/oaskd
  bin/opend
  bin/oping
  bin/ccb-layout
  ccb
)

CLAUDE_MARKDOWN=(
  cask-w.md
  cpend.md
  cping.md
  gask-w.md
  gpend.md
  gping.md
  oask-w.md
  opend.md
  oping.md
)

LEGACY_SCRIPTS=(
  cast
  cast-w
  codex-ask
  codex-pending
  codex-ping
  claude-codex-dual
  claude_codex
  claude_ai
  claude_bridge
)

usage() {
  cat <<'USAGE'
Usage:
  ./install.sh install    # Install or update Codex dual-window tools
  ./install.sh uninstall  # Uninstall installed content

Optional environment variables:
  CODEX_INSTALL_PREFIX     Install directory (default: ~/.local/share/codex-dual)
  CODEX_BIN_DIR            Executable directory (default: ~/.local/bin)
  CODEX_CLAUDE_COMMAND_DIR Custom Claude commands directory (default: auto-detect)
USAGE
}

detect_claude_dir() {
  if [[ -n "${CODEX_CLAUDE_COMMAND_DIR:-}" ]]; then
    echo "$CODEX_CLAUDE_COMMAND_DIR"
    return
  fi

  local candidates=(
    "$HOME/.claude/commands"
    "$HOME/.config/claude/commands"
    "$HOME/.local/share/claude/commands"
  )

  for dir in "${candidates[@]}"; do
    if [[ -d "$dir" ]]; then
      echo "$dir"
      return
    fi
  done

  local fallback="$HOME/.claude/commands"
  mkdir -p "$fallback"
  echo "$fallback"
}

require_command() {
  local cmd="$1"
  local pkg="${2:-$1}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Missing dependency: $cmd"
    echo "   Please install $pkg first, then re-run install.sh"
    exit 1
  fi
}

PYTHON_BIN="${CCB_PYTHON_BIN:-}"

_python_check_310() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || return 1
  "$cmd" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

pick_python_bin() {
  if [[ -n "${PYTHON_BIN}" ]] && _python_check_310 "${PYTHON_BIN}"; then
    return 0
  fi
  for cmd in python3 python; do
    if _python_check_310 "$cmd"; then
      PYTHON_BIN="$cmd"
      return 0
    fi
  done
  return 1
}

pick_any_python_bin() {
  if [[ -n "${PYTHON_BIN}" ]] && command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    return 0
  fi
  for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
      PYTHON_BIN="$cmd"
      return 0
    fi
  done
  return 1
}

require_python_version() {
  # ccb requires Python 3.10+ (PEP 604 type unions: `str | None`, etc.)
  if ! pick_python_bin; then
    echo "ERROR: Missing dependency: python (3.10+ required)"
    echo "   Please install Python 3.10+ and ensure it is on PATH, then re-run install.sh"
    exit 1
  fi
  local version
  version="$("$PYTHON_BIN" -c 'import sys; print("{}.{}.{}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2]))' 2>/dev/null || echo unknown)"
  if ! _python_check_310 "$PYTHON_BIN"; then
    echo "ERROR: Python version too old: $version"
    echo "   Requires Python 3.10+, please upgrade and retry"
    exit 1
  fi
  echo "OK: Python $version ($PYTHON_BIN)"
}

# Return linux / macos / unknown based on uname
detect_platform() {
  local name
  name="$(uname -s 2>/dev/null || echo unknown)"
  case "$name" in
    Linux) echo "linux" ;;
    Darwin) echo "macos" ;;
    *) echo "unknown" ;;
  esac
}

is_wsl() {
  [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null
}

get_wsl_version() {
  if [[ -n "${WSL_INTEROP:-}" ]]; then
    echo 2
  else
    echo 1
  fi
}

check_wsl_compatibility() {
  if is_wsl; then
    local ver
    ver="$(get_wsl_version)"
    echo "OK: Detected WSL $ver environment"
  fi
}

confirm_backend_env_wsl() {
  if ! is_wsl; then
    return
  fi

  if [[ "${CCB_INSTALL_ASSUME_YES:-}" == "1" ]]; then
    return
  fi

  if [[ ! -t 0 ]]; then
    echo "ERROR: Installing in WSL but detected non-interactive terminal; aborted to avoid env mismatch."
    echo "   If you confirm codex/gemini will be installed and run in WSL:"
    echo "   Re-run: CCB_INSTALL_ASSUME_YES=1 ./install.sh install"
    exit 1
  fi

  echo
  echo "================================================================"
  echo "WARN: Detected WSL environment"
  echo "================================================================"
  echo "ccb/cask-w must run in the same environment as codex/gemini."
  echo
  echo "Please confirm: you will install and run codex/gemini in WSL (not Windows native)."
  echo "If you plan to run codex/gemini in Windows native, exit and run on Windows side:"
  echo "   powershell -ExecutionPolicy Bypass -File .\\install.ps1 install"
  echo "================================================================"
  echo
  read -r -p "Confirm continue installing in WSL? (y/N): " reply
  case "$reply" in
    y|Y|yes|YES) ;;
    *) echo "Installation cancelled"; exit 1 ;;
  esac
}

print_tmux_install_hint() {
  local platform
  platform="$(detect_platform)"
  case "$platform" in
    macos)
      if command -v brew >/dev/null 2>&1; then
        echo "   macOS: Run 'brew install tmux'"
      else
        echo "   macOS: Homebrew not detected, install from https://brew.sh then run 'brew install tmux'"
      fi
      ;;
    linux)
      if command -v apt-get >/dev/null 2>&1; then
        echo "   Debian/Ubuntu: sudo apt-get update && sudo apt-get install -y tmux"
      elif command -v dnf >/dev/null 2>&1; then
        echo "   Fedora/CentOS/RHEL: sudo dnf install -y tmux"
      elif command -v yum >/dev/null 2>&1; then
        echo "   CentOS/RHEL: sudo yum install -y tmux"
      elif command -v pacman >/dev/null 2>&1; then
        echo "   Arch/Manjaro: sudo pacman -S tmux"
      elif command -v apk >/dev/null 2>&1; then
        echo "   Alpine: sudo apk add tmux"
      elif command -v zypper >/dev/null 2>&1; then
        echo "   openSUSE: sudo zypper install -y tmux"
      else
        echo "   Linux: Please use your distro's package manager to install tmux"
      fi
      ;;
    *)
      echo "   See https://github.com/tmux/tmux/wiki/Installing for tmux installation"
      ;;
  esac
}

# Detect if running in iTerm2 environment
is_iterm2_environment() {
  # Check ITERM_SESSION_ID environment variable
  if [[ -n "${ITERM_SESSION_ID:-}" ]]; then
    return 0
  fi
  # Check TERM_PROGRAM
  if [[ "${TERM_PROGRAM:-}" == "iTerm.app" ]]; then
    return 0
  fi
  # Check if iTerm2 is running on macOS
  if [[ "$(uname)" == "Darwin" ]] && pgrep -x "iTerm2" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

# Install it2 CLI
install_it2() {
  echo
  echo "INFO: Installing it2 CLI..."

  if ! pick_python_bin; then
    echo "ERROR: Python 3.10+ not found, cannot auto-install it2"
    echo "   Please install Python 3.10+ and retry"
    return 1
  fi
  if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    echo "ERROR: pip not found for ${PYTHON_BIN}, cannot auto-install it2"
    echo "   Please run manually: ${PYTHON_BIN} -m pip install it2"
    return 1
  fi

  # Install it2
  if "$PYTHON_BIN" -m pip install it2 --user 2>&1; then
    echo "OK: it2 CLI installed successfully"

    # Check if in PATH
    if ! command -v it2 >/dev/null 2>&1; then
      local user_bin
      user_bin="$("$PYTHON_BIN" -m site --user-base)/bin"
      echo
      echo "WARN: it2 may not be in PATH, please add the following to your shell config:"
      echo "   export PATH=\"$user_bin:\$PATH\""
    fi
    return 0
  else
    echo "ERROR: it2 installation failed"
    return 1
  fi
}

# Show iTerm2 Python API enable reminder
show_iterm2_api_reminder() {
  echo
  echo "================================================================"
  echo "IMPORTANT: Please enable Python API in iTerm2"
  echo "================================================================"
  echo "   Steps:"
  echo "   1. Open iTerm2"
  echo "   2. Go to Preferences (Cmd + ,)"
  echo "   3. Select Magic tab"
  echo "   4. Check \"Enable Python API\""
  echo "   5. Confirm the warning dialog"
  echo "================================================================"
  echo
}

require_terminal_backend() {
  local wezterm_override="${CODEX_WEZTERM_BIN:-${WEZTERM_BIN:-}}"

  # ============================================
  # Prioritize detecting current environment
  # ============================================

  # 1. If running in WezTerm environment
  if [[ -n "${WEZTERM_PANE:-}" ]]; then
    if [[ -n "${wezterm_override}" ]] && { command -v "${wezterm_override}" >/dev/null 2>&1 || [[ -f "${wezterm_override}" ]]; }; then
      echo "OK: Detected WezTerm environment (${wezterm_override})"
      return
    fi
    if command -v wezterm >/dev/null 2>&1 || command -v wezterm.exe >/dev/null 2>&1; then
      echo "OK: Detected WezTerm environment"
      return
    fi
  fi

  # 2. If running in iTerm2 environment
  if is_iterm2_environment; then
    # Check if it2 is installed
    if command -v it2 >/dev/null 2>&1; then
      echo "OK: Detected iTerm2 environment (it2 CLI installed)"
      echo "   NOTE: Please ensure iTerm2 Python API is enabled (Preferences > Magic > Enable Python API)"
      return
    fi

    # it2 not installed, ask to install
    echo "INFO: Detected iTerm2 environment but it2 CLI not installed"
    echo
    read -p "Auto-install it2 CLI? (Y/n): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
      if install_it2; then
        show_iterm2_api_reminder
        return
      fi
    else
      echo "Skipping it2 installation, will use tmux as fallback"
    fi
  fi

  # 3. If running in tmux environment
  if [[ -n "${TMUX:-}" ]]; then
    echo "OK: Detected tmux environment"
    return
  fi

  # ============================================
  # Not in specific environment, detect by availability
  # ============================================

  # 4. Check WezTerm environment variable override
  if [[ -n "${wezterm_override}" ]]; then
    if command -v "${wezterm_override}" >/dev/null 2>&1 || [[ -f "${wezterm_override}" ]]; then
      echo "OK: Detected WezTerm (${wezterm_override})"
      return
    fi
  fi

  # 5. Check WezTerm command
  if command -v wezterm >/dev/null 2>&1 || command -v wezterm.exe >/dev/null 2>&1; then
    echo "OK: Detected WezTerm"
    return
  fi

  # WSL: Windows PATH may not be injected, try common install paths
  if [[ -f "/proc/version" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
    if [[ -x "/mnt/c/Program Files/WezTerm/wezterm.exe" ]] || [[ -f "/mnt/c/Program Files/WezTerm/wezterm.exe" ]]; then
      echo "OK: Detected WezTerm (/mnt/c/Program Files/WezTerm/wezterm.exe)"
      return
    fi
    if [[ -x "/mnt/c/Program Files (x86)/WezTerm/wezterm.exe" ]] || [[ -f "/mnt/c/Program Files (x86)/WezTerm/wezterm.exe" ]]; then
      echo "OK: Detected WezTerm (/mnt/c/Program Files (x86)/WezTerm/wezterm.exe)"
      return
    fi
  fi

  # 6. Check it2 CLI
  if command -v it2 >/dev/null 2>&1; then
    echo "OK: Detected it2 CLI"
    return
  fi

  # 7. Check tmux
  if command -v tmux >/dev/null 2>&1; then
    echo "OK: Detected tmux (recommend also installing WezTerm for better experience)"
    return
  fi

  # 8. No terminal multiplexer found
  echo "ERROR: Missing dependency: WezTerm, tmux or it2 (at least one required)"
  echo "   WezTerm website: https://wezfurlong.org/wezterm/"

  # Extra hint for macOS users about iTerm2 + it2
  if [[ "$(uname)" == "Darwin" ]]; then
    echo
    echo "NOTE: macOS user recommended options:"
    echo "   - If using iTerm2, install it2 CLI: pip3 install it2"
    echo "   - Or install tmux: brew install tmux"
  fi

  print_tmux_install_hint
  exit 1
}

has_wezterm() {
  local wezterm_override="${CODEX_WEZTERM_BIN:-${WEZTERM_BIN:-}}"
  if [[ -n "${wezterm_override}" ]]; then
    command -v "${wezterm_override}" >/dev/null 2>&1 || [[ -f "${wezterm_override}" ]] && return 0
  fi
  command -v wezterm >/dev/null 2>&1 && return 0
  command -v wezterm.exe >/dev/null 2>&1 && return 0
  if [[ -f "/proc/version" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
    [[ -f "/mnt/c/Program Files/WezTerm/wezterm.exe" ]] && return 0
    [[ -f "/mnt/c/Program Files (x86)/WezTerm/wezterm.exe" ]] && return 0
  fi
  return 1
}

detect_wezterm_path() {
  local wezterm_override="${CODEX_WEZTERM_BIN:-${WEZTERM_BIN:-}}"
  if [[ -n "${wezterm_override}" ]] && [[ -f "${wezterm_override}" ]]; then
    echo "${wezterm_override}"
    return
  fi
  local found
  found="$(command -v wezterm 2>/dev/null)" && [[ -n "$found" ]] && echo "$found" && return
  found="$(command -v wezterm.exe 2>/dev/null)" && [[ -n "$found" ]] && echo "$found" && return
  if is_wsl; then
    for drive in c d e f; do
      for path in "/mnt/${drive}/Program Files/WezTerm/wezterm.exe" \
                  "/mnt/${drive}/Program Files (x86)/WezTerm/wezterm.exe"; do
        if [[ -f "$path" ]]; then
          echo "$path"
          return
        fi
      done
    done
  fi
}

save_wezterm_config() {
  local wezterm_path
  wezterm_path="$(detect_wezterm_path)"
  if [[ -n "$wezterm_path" ]]; then
    local cfg_root="${XDG_CONFIG_HOME:-$HOME/.config}"
    mkdir -p "$cfg_root/ccb"
    echo "CODEX_WEZTERM_BIN=${wezterm_path}" > "$cfg_root/ccb/env"
    echo "OK: WezTerm path cached: $wezterm_path"
  fi
}

copy_project() {
  local staging
  staging="$(mktemp -d)"
  trap 'rm -rf "$staging"' EXIT

  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude '.git/' \
      --exclude '__pycache__/' \
      --exclude '.pytest_cache/' \
      --exclude '.mypy_cache/' \
      --exclude '.venv/' \
      "$REPO_ROOT"/ "$staging"/
  else
    tar -C "$REPO_ROOT" \
      --exclude '.git' \
      --exclude '__pycache__' \
      --exclude '.pytest_cache' \
      --exclude '.mypy_cache' \
      --exclude '.venv' \
      -cf - . | tar -C "$staging" -xf -
  fi

  rm -rf "$INSTALL_PREFIX"
  mkdir -p "$(dirname "$INSTALL_PREFIX")"
  mv "$staging" "$INSTALL_PREFIX"
  trap - EXIT

  # Update GIT_COMMIT and GIT_DATE in ccb file
  local git_commit="" git_date=""

  # Method 1: From git repo
  if command -v git >/dev/null 2>&1 && [[ -d "$REPO_ROOT/.git" ]]; then
    git_commit=$(git -C "$REPO_ROOT" log -1 --format='%h' 2>/dev/null || echo "")
    git_date=$(git -C "$REPO_ROOT" log -1 --format='%cs' 2>/dev/null || echo "")
  fi

  # Method 2: From environment variables (set by ccb update)
  if [[ -z "$git_commit" && -n "${CCB_GIT_COMMIT:-}" ]]; then
    git_commit="$CCB_GIT_COMMIT"
    git_date="${CCB_GIT_DATE:-}"
  fi

  # Method 3: From GitHub API (fallback)
  if [[ -z "$git_commit" ]] && command -v curl >/dev/null 2>&1; then
    local api_response
    api_response=$(curl -fsSL "https://api.github.com/repos/bfly123/claude_code_bridge/commits/main" 2>/dev/null || echo "")
    if [[ -n "$api_response" ]]; then
      git_commit=$(echo "$api_response" | grep -o '"sha": "[^"]*"' | head -1 | cut -d'"' -f4 | cut -c1-7)
      git_date=$(echo "$api_response" | grep -o '"date": "[^"]*"' | head -1 | cut -d'"' -f4 | cut -c1-10)
    fi
  fi

  if [[ -n "$git_commit" && -f "$INSTALL_PREFIX/ccb" ]]; then
    sed -i.bak "s/^GIT_COMMIT = .*/GIT_COMMIT = \"$git_commit\"/" "$INSTALL_PREFIX/ccb"
    sed -i.bak "s/^GIT_DATE = .*/GIT_DATE = \"$git_date\"/" "$INSTALL_PREFIX/ccb"
    rm -f "$INSTALL_PREFIX/ccb.bak"
  fi
}

install_bin_links() {
  mkdir -p "$BIN_DIR"

  for path in "${SCRIPTS_TO_LINK[@]}"; do
    local name
    name="$(basename "$path")"
    if [[ ! -f "$INSTALL_PREFIX/$path" ]]; then
      echo "WARN: Script not found $INSTALL_PREFIX/$path, skipping link creation"
      continue
    fi
    chmod +x "$INSTALL_PREFIX/$path"
    if ln -sf "$INSTALL_PREFIX/$path" "$BIN_DIR/$name" 2>/dev/null; then
      :
    else
      # Windows (Git Bash) / restricted environments may not allow symlinks. Fall back to copying.
      cp -f "$INSTALL_PREFIX/$path" "$BIN_DIR/$name"
      chmod +x "$BIN_DIR/$name" 2>/dev/null || true
    fi
  done

  for legacy in "${LEGACY_SCRIPTS[@]}"; do
    rm -f "$BIN_DIR/$legacy"
  done

  echo "Created executable links in $BIN_DIR"
}

ensure_path_configured() {
  # Check if BIN_DIR is already in PATH
  if [[ ":$PATH:" == *":$BIN_DIR:"* ]]; then
    return
  fi

  local shell_rc=""
  local current_shell
  current_shell="$(basename "${SHELL:-/bin/bash}")"

  case "$current_shell" in
    zsh)  shell_rc="$HOME/.zshrc" ;;
    bash)
      if [[ -f "$HOME/.bash_profile" ]]; then
        shell_rc="$HOME/.bash_profile"
      else
        shell_rc="$HOME/.bashrc"
      fi
      ;;
    *)    shell_rc="$HOME/.profile" ;;
  esac

  local path_line="export PATH=\"\$HOME/.local/bin:\$PATH\""

  # Check if already configured in shell rc
  if [[ -f "$shell_rc" ]] && grep -qF '.local/bin' "$shell_rc" 2>/dev/null; then
    echo "PATH already configured in $shell_rc (restart terminal to apply)"
    return
  fi

  # Add to shell rc
  echo "" >> "$shell_rc"
  echo "# Added by ccb installer" >> "$shell_rc"
  echo "$path_line" >> "$shell_rc"
  echo "OK: Added $BIN_DIR to PATH in $shell_rc"
  echo "   Run: source $shell_rc  (or restart terminal)"
}

install_claude_commands() {
  local claude_dir
  claude_dir="$(detect_claude_dir)"
  mkdir -p "$claude_dir"

  for doc in "${CLAUDE_MARKDOWN[@]}"; do
    cp -f "$REPO_ROOT/commands/$doc" "$claude_dir/$doc"
    chmod 0644 "$claude_dir/$doc" 2>/dev/null || true
  done

  echo "Updated Claude commands directory: $claude_dir"
}

install_claude_skills() {
  local skills_src="$REPO_ROOT/skills"
  local skills_dst="$HOME/.claude/skills"

  if [[ ! -d "$skills_src" ]]; then
    return
  fi

  mkdir -p "$skills_dst"
  for skill_dir in "$skills_src"/*/; do
    [[ -d "$skill_dir" ]] || continue
    local skill_name
    skill_name=$(basename "$skill_dir")
    rm -rf "$skills_dst/$skill_name"
    cp -r "$skill_dir" "$skills_dst/$skill_name"
    echo "  Installed skill: $skill_name"
  done
  echo "Updated Claude skills directory: $skills_dst"
}

install_codex_skills() {
  local skills_src="$REPO_ROOT/codex_skills"
  local skills_dst="${CODEX_HOME:-$HOME/.codex}/skills"

  if [[ ! -d "$skills_src" ]]; then
    return
  fi

  mkdir -p "$skills_dst"
  for skill_dir in "$skills_src"/*/; do
    [[ -d "$skill_dir" ]] || continue
    local skill_name
    skill_name=$(basename "$skill_dir")
    rm -rf "$skills_dst/$skill_name"
    cp -r "$skill_dir" "$skills_dst/$skill_name"
    echo "  Installed Codex skill: $skill_name"
  done
  echo "Updated Codex skills directory: $skills_dst"
}

CCB_START_MARKER="<!-- CCB_CONFIG_START -->"
CCB_END_MARKER="<!-- CCB_CONFIG_END -->"
LEGACY_RULE_MARKER="## Codex 协作规则"

remove_codex_mcp() {
  local claude_config="$HOME/.claude.json"

  if [[ ! -f "$claude_config" ]]; then
    return
  fi

  if ! pick_python_bin; then
    echo "WARN: python required to detect MCP configuration"
    return
  fi

  local has_codex_mcp
  has_codex_mcp=$("$PYTHON_BIN" -c "
	import json
	try:
	    with open('$claude_config', 'r') as f:
        data = json.load(f)
    found = False
    for proj, cfg in data.get('projects', {}).items():
        servers = cfg.get('mcpServers', {})
        for name in list(servers.keys()):
            if 'codex' in name.lower():
                found = True
                break
        if found:
            break
    print('yes' if found else 'no')
	except:
	    print('no')
	" 2>/dev/null)

  if [[ "$has_codex_mcp" == "yes" ]]; then
    echo "WARN: Detected codex-related MCP configuration, removing to avoid conflicts..."
    "$PYTHON_BIN" -c "
	import json
	with open('$claude_config', 'r') as f:
	    data = json.load(f)
removed = []
for proj, cfg in data.get('projects', {}).items():
    servers = cfg.get('mcpServers', {})
    for name in list(servers.keys()):
        if 'codex' in name.lower():
            del servers[name]
            removed.append(f'{proj}: {name}')
with open('$claude_config', 'w') as f:
    json.dump(data, f, indent=2)
if removed:
    print('Removed the following MCP configurations:')
	    for r in removed:
	        print(f'  - {r}')
	"
    echo "OK: Codex MCP configuration cleaned"
  fi
}

install_claude_md_config() {
  local claude_md="$HOME/.claude/CLAUDE.md"
  mkdir -p "$HOME/.claude"
  if ! pick_python_bin; then
    echo "ERROR: python required to update CLAUDE.md"
    return 1
  fi

  # Use temp file to avoid Bash 3.2 heredoc parsing bug with single quotes
  local ccb_tmpfile=""
  ccb_tmpfile="$(mktemp)" || { echo "Failed to create temp file"; return 1; }
  trap 'rm -f "${ccb_tmpfile:-}"' RETURN
  cat > "$ccb_tmpfile" << 'AI_RULES'
<!-- CCB_CONFIG_START -->
## Collaboration Rules (Codex / Gemini / OpenCode)
Codex, Gemini, and OpenCode are other AI assistants running in separate terminal sessions (WezTerm, iTerm2, or tmux).

### Common Rules (all assistants)
Trigger (any match):
- User explicitly asks to consult one of them (e.g. "ask codex ...", "let gemini ...")
- User uses an assistant prefix (see table)
- User asks about that assistant's status (e.g. "is codex alive?")

Fast path (minimize latency):
- If the user message starts with a prefix: treat the rest as the question and dispatch immediately.
- If the user message is only the prefix (no question): ask a 1-line clarification for what to send.

Actions:
- Ask a question (default) -> `Bash(ASK_CMD "<question>", run_in_background=true)`, tell user "`ASSISTANT` processing (task: xxx)", then END your turn
- Check connectivity -> run `PING_CMD`
- Use blocking/wait or "show previous reply" commands ONLY if the user explicitly requests them

Important restrictions:
- After starting a background ask, do NOT poll for results; wait for `bash-notification`
- Do NOT use `*-w` / `*pend` / `*end` unless the user explicitly requests

### Command Map
| Assistant | Prefixes | ASK_CMD (background) | PING_CMD | Explicit-request-only |
|---|---|---|---|---|
| Codex | `@codex`, `codex:`, `ask codex`, `let codex`, `/cask` | `cask` | `cping` | `cask-w`, `cpend` |
| Gemini | `@gemini`, `gemini:`, `ask gemini`, `let gemini`, `/gask` | `gask` | `gping` | `gask-w`, `gpend` |
| OpenCode | `@opencode`, `opencode:`, `ask opencode`, `let opencode`, `/oask` | `oask` | `oping` | `oask-w`, `opend` |

Examples:
- `codex: review this code` -> `Bash(cask "...", run_in_background=true)`, END turn
- `is gemini alive?` -> `gping`
<!-- CCB_CONFIG_END -->
AI_RULES
  local ccb_content
  ccb_content="$(cat "$ccb_tmpfile")"

  if [[ -f "$claude_md" ]]; then
    if grep -q "$CCB_START_MARKER" "$claude_md" 2>/dev/null; then
      echo "Updating existing CCB config block..."
      "$PYTHON_BIN" -c "
	import re
	with open('$claude_md', 'r', encoding='utf-8') as f:
	    content = f.read()
pattern = r'<!-- CCB_CONFIG_START -->.*?<!-- CCB_CONFIG_END -->'
new_block = '''$ccb_content'''
content = re.sub(pattern, new_block, content, flags=re.DOTALL)
	with open('$claude_md', 'w', encoding='utf-8') as f:
	    f.write(content)
	"
    elif grep -qE "$LEGACY_RULE_MARKER|## Codex Collaboration Rules|## Gemini|## OpenCode" "$claude_md" 2>/dev/null; then
      echo "Removing legacy rules and adding new CCB config block..."
      "$PYTHON_BIN" -c "
	import re
	with open('$claude_md', 'r', encoding='utf-8') as f:
	    content = f.read()
patterns = [
    r'## Codex Collaboration Rules.*?(?=\n## (?!Gemini)|\Z)',
    r'## Codex 协作规则.*?(?=\n## |\Z)',
    r'## Gemini Collaboration Rules.*?(?=\n## |\Z)',
    r'## Gemini 协作规则.*?(?=\n## |\Z)',
    r'## OpenCode Collaboration Rules.*?(?=\n## |\Z)',
    r'## OpenCode 协作规则.*?(?=\n## |\Z)',
]
for p in patterns:
    content = re.sub(p, '', content, flags=re.DOTALL)
content = content.rstrip() + '\n'
	with open('$claude_md', 'w', encoding='utf-8') as f:
	    f.write(content)
	"
      echo "$ccb_content" >> "$claude_md"
    else
      echo "$ccb_content" >> "$claude_md"
    fi
  else
    echo "$ccb_content" > "$claude_md"
  fi

  echo "Updated AI collaboration rules in $claude_md"
}

install_settings_permissions() {
  local settings_file="$HOME/.claude/settings.json"
  mkdir -p "$HOME/.claude"

  local perms_to_add=(
    'Bash(cask:*)'
    'Bash(cask-w:*)'
    'Bash(cpend)'
    'Bash(cping)'
    'Bash(gask:*)'
    'Bash(gask-w:*)'
    'Bash(gpend)'
    'Bash(gping)'
    'Bash(oask:*)'
    'Bash(oask-w:*)'
    'Bash(opend)'
    'Bash(oping)'
  )

  if [[ ! -f "$settings_file" ]]; then
    cat > "$settings_file" << 'SETTINGS'
{
  "permissions": {
    "allow": [
      "Bash(cask:*)",
      "Bash(cask-w:*)",
      "Bash(cpend)",
      "Bash(cping)",
      "Bash(gask:*)",
      "Bash(gask-w:*)",
      "Bash(gpend)",
      "Bash(gping)",
      "Bash(oask:*)",
      "Bash(oask-w:*)",
      "Bash(opend)",
      "Bash(oping)"
    ],
    "deny": []
  }
}
SETTINGS
    echo "Created $settings_file with permissions"
    return
  fi

  local added=0
  for perm in "${perms_to_add[@]}"; do
    if ! grep -q "$perm" "$settings_file" 2>/dev/null; then
      if pick_python_bin; then
        "$PYTHON_BIN" -c "
	import json, sys
	with open('$settings_file', 'r') as f:
	    data = json.load(f)
	if 'permissions' not in data:
    data['permissions'] = {'allow': [], 'deny': []}
if 'allow' not in data['permissions']:
    data['permissions']['allow'] = []
if '$perm' not in data['permissions']['allow']:
    data['permissions']['allow'].append('$perm')
	with open('$settings_file', 'w') as f:
	    json.dump(data, f, indent=2)
	"
        added=1
      fi
    fi
  done

  if [[ $added -eq 1 ]]; then
    echo "Updated $settings_file permissions"
  else
    echo "Permissions already exist in $settings_file"
  fi
}

install_requirements() {
  check_wsl_compatibility
  confirm_backend_env_wsl
  require_python_version
  require_terminal_backend
  if ! has_wezterm; then
    echo
    echo "================================================================"
    echo "NOTE: Recommend installing WezTerm as terminal frontend (better experience, recommended for WSL2/Windows)"
    echo "   - Website: https://wezfurlong.org/wezterm/"
    echo "   - Benefits: Smoother split/scroll/font rendering, more stable bridging in WezTerm mode"
    echo "================================================================"
    echo
  fi
}

install_all() {
  install_requirements
  remove_codex_mcp
  save_wezterm_config
  copy_project
  install_bin_links
  ensure_path_configured
  install_claude_commands
  install_claude_skills
  install_codex_skills
  install_claude_md_config
  install_settings_permissions
  echo "OK: Installation complete"
  echo "   Project dir    : $INSTALL_PREFIX"
  echo "   Executable dir : $BIN_DIR"
  echo "   Claude commands updated"
  echo "   Global CLAUDE.md configured with Codex/Gemini/OpenCode collaboration rules"
  echo "   Global settings.json permissions added"
}

uninstall_claude_md_config() {
  local claude_md="$HOME/.claude/CLAUDE.md"

  if [[ ! -f "$claude_md" ]]; then
    return
  fi

  if grep -q "$CCB_START_MARKER" "$claude_md" 2>/dev/null; then
    echo "Removing CCB config block from CLAUDE.md..."
    if pick_any_python_bin; then
      "$PYTHON_BIN" -c "
	import re
	with open('$claude_md', 'r', encoding='utf-8') as f:
	    content = f.read()
pattern = r'\n?<!-- CCB_CONFIG_START -->.*?<!-- CCB_CONFIG_END -->\n?'
content = re.sub(pattern, '\n', content, flags=re.DOTALL)
content = content.strip() + '\n'
	with open('$claude_md', 'w', encoding='utf-8') as f:
	    f.write(content)
	"
      echo "Removed CCB config from CLAUDE.md"
    else
      echo "WARN: python required to clean CLAUDE.md, please manually remove CCB_CONFIG block"
    fi
  elif grep -qE "$LEGACY_RULE_MARKER|## Codex Collaboration Rules|## Gemini|## OpenCode" "$claude_md" 2>/dev/null; then
    echo "Removing legacy collaboration rules from CLAUDE.md..."
    if pick_any_python_bin; then
      "$PYTHON_BIN" -c "
	import re
	with open('$claude_md', 'r', encoding='utf-8') as f:
	    content = f.read()
patterns = [
    r'## Codex Collaboration Rules.*?(?=\n## (?!Gemini)|\Z)',
    r'## Codex 协作规则.*?(?=\n## |\Z)',
    r'## Gemini Collaboration Rules.*?(?=\n## |\Z)',
    r'## Gemini 协作规则.*?(?=\n## |\Z)',
    r'## OpenCode Collaboration Rules.*?(?=\n## |\Z)',
    r'## OpenCode 协作规则.*?(?=\n## |\Z)',
]
for p in patterns:
    content = re.sub(p, '', content, flags=re.DOTALL)
content = content.rstrip() + '\n'
	with open('$claude_md', 'w', encoding='utf-8') as f:
	    f.write(content)
	"
      echo "Removed collaboration rules from CLAUDE.md"
    else
      echo "WARN: python required to clean CLAUDE.md, please manually remove collaboration rules"
    fi
  fi
}

uninstall_settings_permissions() {
  local settings_file="$HOME/.claude/settings.json"

  if [[ ! -f "$settings_file" ]]; then
    return
  fi

  local perms_to_remove=(
    'Bash(cask:*)'
    'Bash(cask-w:*)'
    'Bash(cpend)'
    'Bash(cping)'
    'Bash(gask:*)'
    'Bash(gask-w:*)'
    'Bash(gpend)'
    'Bash(gping)'
    'Bash(oask:*)'
    'Bash(oask-w:*)'
    'Bash(opend)'
    'Bash(oping)'
  )

  if pick_any_python_bin; then
    local has_perms=0
    for perm in "${perms_to_remove[@]}"; do
      if grep -q "$perm" "$settings_file" 2>/dev/null; then
        has_perms=1
        break
      fi
    done

    if [[ $has_perms -eq 1 ]]; then
      echo "Removing permission configuration from settings.json..."
      "$PYTHON_BIN" -c "
	import json
	perms_to_remove = [
	    'Bash(cask:*)',
    'Bash(cask-w:*)',
    'Bash(cpend)',
    'Bash(cping)',
    'Bash(gask:*)',
    'Bash(gask-w:*)',
    'Bash(gpend)',
    'Bash(gping)',
    'Bash(oask:*)',
    'Bash(oask-w:*)',
    'Bash(opend)',
    'Bash(oping)',
]
with open('$settings_file', 'r') as f:
    data = json.load(f)
if 'permissions' in data and 'allow' in data['permissions']:
    data['permissions']['allow'] = [
        p for p in data['permissions']['allow']
        if p not in perms_to_remove
    ]
	with open('$settings_file', 'w') as f:
	    json.dump(data, f, indent=2)
	"
      echo "Removed permission configuration from settings.json"
    fi
  else
    echo "WARN: python required to clean settings.json, please manually remove related permissions"
  fi
}

uninstall_all() {
  echo "INFO: Starting ccb uninstall..."

  # 1. Remove project directory
  if [[ -d "$INSTALL_PREFIX" ]]; then
    rm -rf "$INSTALL_PREFIX"
    echo "Removed project directory: $INSTALL_PREFIX"
  fi

  # 2. Remove bin links
  for path in "${SCRIPTS_TO_LINK[@]}"; do
    local name
    name="$(basename "$path")"
    if [[ -L "$BIN_DIR/$name" || -f "$BIN_DIR/$name" ]]; then
      rm -f "$BIN_DIR/$name"
    fi
  done
  for legacy in "${LEGACY_SCRIPTS[@]}"; do
    rm -f "$BIN_DIR/$legacy"
  done
  echo "Removed bin links: $BIN_DIR"

  # 3. Remove Claude command files (clean all possible locations)
  local cmd_dirs=(
    "$HOME/.claude/commands"
    "$HOME/.config/claude/commands"
    "$HOME/.local/share/claude/commands"
  )
  for dir in "${cmd_dirs[@]}"; do
    if [[ -d "$dir" ]]; then
      for doc in "${CLAUDE_MARKDOWN[@]}"; do
        rm -f "$dir/$doc"
      done
      echo "Cleaned commands directory: $dir"
    fi
  done

  # 4. Remove collaboration rules from CLAUDE.md
  uninstall_claude_md_config

  # 5. Remove permission configuration from settings.json
  uninstall_settings_permissions

  echo "OK: Uninstall complete"
  echo "   NOTE: Dependencies (python, tmux, wezterm, it2) were not removed"
}

main() {
  if [[ $# -ne 1 ]]; then
    usage
    exit 1
  fi

  case "$1" in
    install)
      install_all
      ;;
    uninstall)
      uninstall_all
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
