from __future__ import annotations

import os


_CONTROL_PLANE_ALLOWLIST = {
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_AUTH_TOKEN',
    'ANTHROPIC_BASE_URL',
    'CCB_BACKEND_ENV',
    'CCB_CCBD_MIN_POLL_INTERVAL_S',
    'CCB_DEBUG',
    'CCB_KEEPER_PID',
    'CCB_KEEPER_PING_TIMEOUT_S',
    'CCB_LANG',
    'CCB_NO_ATTACH',
    'CCB_REPLY_LANG',
    'CCB_STDIN_ENCODING',
    'CCB_TMUX_SOCKET',
    'CCB_TMUX_SOCKET_PATH',
    'CCB_VERSION',
    'GEMINI_API_KEY',
    'GOOGLE_API_BASE',
    'GOOGLE_API_KEY',
    'GOOGLE_GENAI_USE_VERTEXAI',
    'HOME',
    'LANG',
    'LC_ALL',
    'LC_MESSAGES',
    'LOCALAPPDATA',
    'OPENAI_API_BASE',
    'OPENAI_API_KEY',
    'OPENAI_BASE_URL',
    'OPENAI_ORG_ID',
    'OPENAI_ORGANIZATION',
    'PATH',
    'PYTHONPATH',
    'PYTHONUNBUFFERED',
    'SHELL',
    'SYSTEMROOT',
    'TERM',
    'TMP',
    'TEMP',
    'TMPDIR',
    'USER',
    'USERPROFILE',
    'XDG_CACHE_HOME',
    'XDG_CONFIG_HOME',
    'XDG_DATA_HOME',
    'XDG_RUNTIME_DIR',
}

_CONTROL_PLANE_BLOCKED_PREFIXES = (
    'CODEX_',
    'CLAUDE_',
    'GEMINI_',
    'OPENCODE_',
    'DROID_',
    'CCB_CALLER_',
)

_CONTROL_PLANE_BLOCKED_EXACT = {
    'CCB_SESSION_FILE',
    'CCB_SESSION_ID',
}


def control_plane_env(*, extra: dict[str, str] | None = None) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in _CONTROL_PLANE_BLOCKED_EXACT:
            continue
        if key in _CONTROL_PLANE_ALLOWLIST:
            env[key] = value
            continue
        if any(key.startswith(prefix) for prefix in _CONTROL_PLANE_BLOCKED_PREFIXES):
            continue
        if key.startswith(('PYTHON', 'VIRTUAL_ENV', 'CONDA')):
            env[key] = value
    if extra:
        for key, value in extra.items():
            if value is None:
                env.pop(key, None)
                continue
            env[key] = str(value)
    return env


__all__ = ['control_plane_env']
