from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderDaemonSpec:
    daemon_key: str
    protocol_prefix: str
    state_file_name: str
    log_file_name: str
    idle_timeout_env: str
    lock_name: str


@dataclass
class ProviderClientSpec:
    protocol_prefix: str
    enabled_env: str
    autostart_env_primary: str
    autostart_env_legacy: str
    state_file_env: str
    session_filename: str
    daemon_bin_name: str
    daemon_module: str


CASKD_SPEC = ProviderDaemonSpec(
    daemon_key="caskd",
    protocol_prefix="cask",
    state_file_name="caskd.json",
    log_file_name="caskd.log",
    idle_timeout_env="CCB_CASKD_IDLE_TIMEOUT_S",
    lock_name="caskd",
)


GASKD_SPEC = ProviderDaemonSpec(
    daemon_key="gaskd",
    protocol_prefix="gask",
    state_file_name="gaskd.json",
    log_file_name="gaskd.log",
    idle_timeout_env="CCB_GASKD_IDLE_TIMEOUT_S",
    lock_name="gaskd",
)


OASKD_SPEC = ProviderDaemonSpec(
    daemon_key="oaskd",
    protocol_prefix="oask",
    state_file_name="oaskd.json",
    log_file_name="oaskd.log",
    idle_timeout_env="CCB_OASKD_IDLE_TIMEOUT_S",
    lock_name="oaskd",
)


LASKD_SPEC = ProviderDaemonSpec(
    daemon_key="laskd",
    protocol_prefix="lask",
    state_file_name="laskd.json",
    log_file_name="laskd.log",
    idle_timeout_env="CCB_LASKD_IDLE_TIMEOUT_S",
    lock_name="laskd",
)


LOASKD_SPEC = ProviderDaemonSpec(
    daemon_key="loaskd",
    protocol_prefix="loask",
    state_file_name="loaskd.json",
    log_file_name="loaskd.log",
    idle_timeout_env="CCB_LOASKD_IDLE_TIMEOUT_S",
    lock_name="loaskd",
)


LSASKD_SPEC = ProviderDaemonSpec(
    daemon_key="lsaskd",
    protocol_prefix="lsask",
    state_file_name="lsaskd.json",
    log_file_name="lsaskd.log",
    idle_timeout_env="CCB_LSASKD_IDLE_TIMEOUT_S",
    lock_name="lsaskd",
)


DASKD_SPEC = ProviderDaemonSpec(
    daemon_key="daskd",
    protocol_prefix="dask",
    state_file_name="daskd.json",
    log_file_name="daskd.log",
    idle_timeout_env="CCB_DASKD_IDLE_TIMEOUT_S",
    lock_name="daskd",
)


CASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="cask",
    enabled_env="CCB_CASKD",
    autostart_env_primary="CCB_CASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_CASKD",
    state_file_env="CCB_CASKD_STATE_FILE",
    session_filename=".codex-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


GASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="gask",
    enabled_env="CCB_GASKD",
    autostart_env_primary="CCB_GASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_GASKD",
    state_file_env="CCB_GASKD_STATE_FILE",
    session_filename=".gemini-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


OASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="oask",
    enabled_env="CCB_OASKD",
    autostart_env_primary="CCB_OASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_OASKD",
    state_file_env="CCB_OASKD_STATE_FILE",
    session_filename=".opencode-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


LASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="lask",
    enabled_env="CCB_LASKD",
    autostart_env_primary="CCB_LASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_LASKD",
    state_file_env="CCB_LASKD_STATE_FILE",
    session_filename=".claude-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


LOASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="loask",
    enabled_env="CCB_LOASKD",
    autostart_env_primary="CCB_LOASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_LOASKD",
    state_file_env="CCB_LOASKD_STATE_FILE",
    session_filename=".claude-opus-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


LSASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="lsask",
    enabled_env="CCB_LSASKD",
    autostart_env_primary="CCB_LSASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_LSASKD",
    state_file_env="CCB_LSASKD_STATE_FILE",
    session_filename=".claude-sonnet-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


DASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="dask",
    enabled_env="CCB_DASKD",
    autostart_env_primary="CCB_DASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_DASKD",
    state_file_env="CCB_DASKD_STATE_FILE",
    session_filename=".droid-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


# Copilot (GitHub Copilot CLI)
HASKD_SPEC = ProviderDaemonSpec(
    daemon_key="haskd",
    protocol_prefix="hask",
    state_file_name="haskd.json",
    log_file_name="haskd.log",
    idle_timeout_env="CCB_HASKD_IDLE_TIMEOUT_S",
    lock_name="haskd",
)


HASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="hask",
    enabled_env="CCB_HASKD",
    autostart_env_primary="CCB_HASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_HASKD",
    state_file_env="CCB_HASKD_STATE_FILE",
    session_filename=".copilot-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


# CodeBuddy (Tencent CodeBuddy CLI)
BASKD_SPEC = ProviderDaemonSpec(
    daemon_key="baskd",
    protocol_prefix="bask",
    state_file_name="baskd.json",
    log_file_name="baskd.log",
    idle_timeout_env="CCB_BASKD_IDLE_TIMEOUT_S",
    lock_name="baskd",
)


BASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="bask",
    enabled_env="CCB_BASKD",
    autostart_env_primary="CCB_BASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_BASKD",
    state_file_env="CCB_BASKD_STATE_FILE",
    session_filename=".codebuddy-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


# ── Qwen (qwen-code CLI) ──────────────────────────────────────────────────────
QASKD_SPEC = ProviderDaemonSpec(
    daemon_key="qaskd",
    protocol_prefix="qask",
    state_file_name="qaskd.json",
    log_file_name="qaskd.log",
    idle_timeout_env="CCB_QASKD_IDLE_TIMEOUT_S",
    lock_name="qaskd",
)

QASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="qask",
    enabled_env="CCB_QASKD",
    autostart_env_primary="CCB_QASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_QASKD",
    state_file_env="CCB_QASKD_STATE_FILE",
    session_filename=".qwen-session",
    daemon_bin_name="askd",
    daemon_module="askd.daemon",
)


# ── Multi-instance provider utilities ────────────────────────────────────────


def parse_qualified_provider(key: str) -> tuple[str, str | None]:
    """Parse 'codex:auth' -> ('codex', 'auth'); 'codex' -> ('codex', None)."""
    key = (key or "").strip().lower()
    if not key:
        return ("", None)
    # Only split on first colon to separate provider from instance
    parts = key.split(":", 1)
    base = parts[0].strip()
    instance = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return (base, instance)


def make_qualified_key(base: str, instance: str | None) -> str:
    """Combine base provider and instance: 'codex' + 'auth' -> 'codex:auth'."""
    base = (base or "").strip().lower()
    if instance:
        return f"{base}:{instance.strip()}"
    return base


def session_filename_for_instance(base_filename: str, instance: str | None) -> str:
    """Derive instance-specific session filename.

    '.codex-session' + 'auth' -> '.codex-auth-session'
    '.codex-session' + None  -> '.codex-session'
    """
    if not instance:
        return base_filename
    instance = instance.strip()
    if not instance:
        return base_filename
    # Insert instance before '-session' suffix
    if base_filename.endswith("-session"):
        prefix = base_filename[:-len("-session")]
        return f"{prefix}-{instance}-session"
    # Fallback: append instance before extension
    return f"{base_filename}-{instance}"
