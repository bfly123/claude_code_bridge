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
    daemon_bin_name="caskd",
    daemon_module="caskd_daemon",
)


GASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="gask",
    enabled_env="CCB_GASKD",
    autostart_env_primary="CCB_GASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_GASKD",
    state_file_env="CCB_GASKD_STATE_FILE",
    session_filename=".gemini-session",
    daemon_bin_name="gaskd",
    daemon_module="gaskd_daemon",
)


OASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="oask",
    enabled_env="CCB_OASKD",
    autostart_env_primary="CCB_OASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_OASKD",
    state_file_env="CCB_OASKD_STATE_FILE",
    session_filename=".opencode-session",
    daemon_bin_name="oaskd",
    daemon_module="oaskd_daemon",
)


LASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="lask",
    enabled_env="CCB_LASKD",
    autostart_env_primary="CCB_LASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_LASKD",
    state_file_env="CCB_LASKD_STATE_FILE",
    session_filename=".claude-session",
    daemon_bin_name="laskd",
    daemon_module="laskd_daemon",
)


DASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="dask",
    enabled_env="CCB_DASKD",
    autostart_env_primary="CCB_DASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_DASKD",
    state_file_env="CCB_DASKD_STATE_FILE",
    session_filename=".droid-session",
    daemon_bin_name="daskd",
    daemon_module="daskd_daemon",
)


# Cursor uses simplified architecture (no daemon needed)
# cursor-agent is a one-shot CLI, not a TUI
CURASK_CLIENT_SPEC = ProviderClientSpec(
    protocol_prefix="curask",
    enabled_env="CCB_CURASKD",
    autostart_env_primary="CCB_CURASKD_AUTOSTART",
    autostart_env_legacy="CCB_AUTO_CURASKD",
    state_file_env="CCB_CURASKD_STATE_FILE",
    session_filename=".cursor-session",
    daemon_bin_name="curaskd",  # Not used - cursor doesn't need daemon
    daemon_module="curaskd_daemon",  # Not used - cursor doesn't need daemon
)
