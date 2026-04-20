from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderRuntimeSpec:
    provider_key: str
    service_name: str
    rpc_prefix: str
    state_file_name: str
    log_file_name: str
    idle_timeout_env: str
    lock_name: str


@dataclass(frozen=True)
class ProviderClientSpec:
    provider_key: str
    enabled_env: str
    autostart_env: str
    state_file_env: str
    session_filename: str


def _env_stem(provider_key: str) -> str:
    return str(provider_key or "").strip().upper().replace("-", "_")


def provider_env_name(provider_key: str, *parts: str) -> str:
    suffix = "_".join(str(part or "").strip().upper() for part in parts if str(part or "").strip())
    base = f"CCB_{_env_stem(provider_key)}"
    return f"{base}_{suffix}" if suffix else base


def provider_marker_prefix(provider_key: str) -> str:
    return str(provider_key or "").strip().lower()


def _provider_runtime_spec(provider_key: str) -> ProviderRuntimeSpec:
    env_stem = _env_stem(provider_key)
    return ProviderRuntimeSpec(
        provider_key=provider_key,
        service_name=provider_key,
        rpc_prefix=provider_key,
        state_file_name=f"{provider_key}-runtime.json",
        log_file_name=f"{provider_key}-runtime.log",
        idle_timeout_env=f"CCB_{env_stem}_RUNTIME_IDLE_TIMEOUT_S",
        lock_name=f"{provider_key}-runtime",
    )


def _client_spec(*, provider_key: str, session_filename: str) -> ProviderClientSpec:
    env_stem = _env_stem(provider_key)
    return ProviderClientSpec(
        provider_key=provider_key,
        enabled_env=f"CCB_{env_stem}",
        autostart_env=f"CCB_{env_stem}_AUTOSTART",
        state_file_env=f"CCB_{env_stem}_STATE_FILE",
        session_filename=session_filename,
    )


CODEX_RUNTIME_SPEC = _provider_runtime_spec("codex")
GEMINI_RUNTIME_SPEC = _provider_runtime_spec("gemini")
OPENCODE_RUNTIME_SPEC = _provider_runtime_spec("opencode")
CLAUDE_RUNTIME_SPEC = _provider_runtime_spec("claude")
DROID_RUNTIME_SPEC = _provider_runtime_spec("droid")
COPILOT_RUNTIME_SPEC = _provider_runtime_spec("copilot")
CODEBUDDY_RUNTIME_SPEC = _provider_runtime_spec("codebuddy")
QWEN_RUNTIME_SPEC = _provider_runtime_spec("qwen")

CODEX_CLIENT_SPEC = _client_spec(
    provider_key="codex",
    session_filename=".codex-session",
)
GEMINI_CLIENT_SPEC = _client_spec(
    provider_key="gemini",
    session_filename=".gemini-session",
)
OPENCODE_CLIENT_SPEC = _client_spec(
    provider_key="opencode",
    session_filename=".opencode-session",
)
CLAUDE_CLIENT_SPEC = _client_spec(
    provider_key="claude",
    session_filename=".claude-session",
)
DROID_CLIENT_SPEC = _client_spec(
    provider_key="droid",
    session_filename=".droid-session",
)
COPILOT_CLIENT_SPEC = _client_spec(
    provider_key="copilot",
    session_filename=".copilot-session",
)
CODEBUDDY_CLIENT_SPEC = _client_spec(
    provider_key="codebuddy",
    session_filename=".codebuddy-session",
)
QWEN_CLIENT_SPEC = _client_spec(
    provider_key="qwen",
    session_filename=".qwen-session",
)

RUNTIME_SPECS_BY_PROVIDER = {
    "codex": CODEX_RUNTIME_SPEC,
    "gemini": GEMINI_RUNTIME_SPEC,
    "opencode": OPENCODE_RUNTIME_SPEC,
    "claude": CLAUDE_RUNTIME_SPEC,
    "droid": DROID_RUNTIME_SPEC,
    "copilot": COPILOT_RUNTIME_SPEC,
    "codebuddy": CODEBUDDY_RUNTIME_SPEC,
    "qwen": QWEN_RUNTIME_SPEC,
}

CLIENT_SPECS_BY_PROVIDER = {
    "codex": CODEX_CLIENT_SPEC,
    "gemini": GEMINI_CLIENT_SPEC,
    "opencode": OPENCODE_CLIENT_SPEC,
    "claude": CLAUDE_CLIENT_SPEC,
    "droid": DROID_CLIENT_SPEC,
    "copilot": COPILOT_CLIENT_SPEC,
    "codebuddy": CODEBUDDY_CLIENT_SPEC,
    "qwen": QWEN_CLIENT_SPEC,
}


def parse_qualified_provider(key: str) -> tuple[str, str | None]:
    key = (key or "").strip().lower()
    if not key:
        return ("", None)
    parts = key.split(":", 1)
    base = parts[0].strip()
    instance = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return (base, instance)


def make_qualified_key(base: str, instance: str | None) -> str:
    base = (base or "").strip().lower()
    if instance:
        return f"{base}:{instance.strip()}"
    return base


__all__ = [
    "CLAUDE_CLIENT_SPEC",
    "CLAUDE_RUNTIME_SPEC",
    "CLIENT_SPECS_BY_PROVIDER",
    "CODEBUDDY_CLIENT_SPEC",
    "CODEBUDDY_RUNTIME_SPEC",
    "CODEX_CLIENT_SPEC",
    "CODEX_RUNTIME_SPEC",
    "COPILOT_CLIENT_SPEC",
    "COPILOT_RUNTIME_SPEC",
    "DROID_CLIENT_SPEC",
    "DROID_RUNTIME_SPEC",
    "GEMINI_CLIENT_SPEC",
    "GEMINI_RUNTIME_SPEC",
    "OPENCODE_CLIENT_SPEC",
    "OPENCODE_RUNTIME_SPEC",
    "ProviderClientSpec",
    "ProviderRuntimeSpec",
    "QWEN_CLIENT_SPEC",
    "QWEN_RUNTIME_SPEC",
    "RUNTIME_SPECS_BY_PROVIDER",
    "make_qualified_key",
    "parse_qualified_provider",
    "provider_env_name",
    "provider_marker_prefix",
]
