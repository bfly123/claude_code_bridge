"""
Mail configuration management for CCB.

Configuration is stored in ~/.ccb/mail/config.json
Credentials are stored separately in system keyring.

Version 3: ASK-based mail system
- Routes emails to ASK system instead of panes
- Provider prefix in body: "CLAUDE: message" -> /ask claude message
- Replies via ccb-completion-hook with CCB_CALLER=email

Version 2 (deprecated): Pane-based mail notification system
- service_account: CCB's service mailbox for sending/receiving
- target_email: User's phone email for notifications
- pane_hooks: Per-pane notification settings
- notification: Email formatting settings
- polling: IMAP polling settings
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, Literal, List

# Default configuration directory
DEFAULT_CONFIG_DIR = Path.home() / ".ccb" / "mail"
CONFIG_FILE = "config.json"
THREADS_FILE = "threads.json"

# Current config version
CURRENT_CONFIG_VERSION = 3

# Supported AI providers
SUPPORTED_PROVIDERS = ["claude", "codex", "gemini", "opencode", "droid", "copilot", "codebuddy", "qwen"]

# Notification modes
NotifyMode = Literal["on_completion", "realtime", "periodic", "on_request"]

# Provider presets for email servers
PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "gmail": {
        "imap": {"host": "imap.gmail.com", "port": 993, "ssl": True},
        "smtp": {"host": "smtp.gmail.com", "port": 587, "starttls": True},
    },
    "outlook": {
        "imap": {"host": "outlook.office365.com", "port": 993, "ssl": True},
        "smtp": {"host": "smtp.office365.com", "port": 587, "starttls": True},
    },
    "qq": {
        "imap": {"host": "imap.qq.com", "port": 993, "ssl": True},
        "smtp": {"host": "smtp.qq.com", "port": 465, "ssl": True},
    },
    "163": {
        "imap": {"host": "imap.163.com", "port": 993, "ssl": True},
        "smtp": {"host": "smtp.163.com", "port": 465, "ssl": True},
    },
}


@dataclass
class ImapConfig:
    """IMAP server configuration."""
    host: str = ""
    port: int = 993
    ssl: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImapConfig":
        return cls(
            host=data.get("host", ""),
            port=data.get("port", 993),
            ssl=data.get("ssl", True),
        )


@dataclass
class SmtpConfig:
    """SMTP server configuration."""
    host: str = ""
    port: int = 587
    ssl: bool = False
    starttls: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SmtpConfig":
        return cls(
            host=data.get("host", ""),
            port=data.get("port", 587),
            ssl=data.get("ssl", False),
            starttls=data.get("starttls", True),
        )


@dataclass
class ServiceAccountConfig:
    """Service email account configuration (CCB's mailbox)."""
    provider: str = "custom"  # gmail, outlook, qq, custom
    email: str = ""
    imap: ImapConfig = field(default_factory=ImapConfig)
    smtp: SmtpConfig = field(default_factory=SmtpConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "email": self.email,
            "imap": self.imap.to_dict(),
            "smtp": self.smtp.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceAccountConfig":
        return cls(
            provider=data.get("provider", "custom"),
            email=data.get("email", ""),
            imap=ImapConfig.from_dict(data.get("imap", {})),
            smtp=SmtpConfig.from_dict(data.get("smtp", {})),
        )

    @classmethod
    def from_preset(cls, provider: str, email: str) -> "ServiceAccountConfig":
        """Create account config from a provider preset."""
        if provider not in PROVIDER_PRESETS:
            raise ValueError(f"Unknown provider: {provider}")
        preset = PROVIDER_PRESETS[provider]
        return cls(
            provider=provider,
            email=email,
            imap=ImapConfig.from_dict(preset["imap"]),
            smtp=SmtpConfig.from_dict(preset["smtp"]),
        )


# Alias for backward compatibility
AccountConfig = ServiceAccountConfig


@dataclass
class PaneHookConfig:
    """Configuration for a single pane's mail notification hook."""
    enabled: bool = False
    notify_mode: NotifyMode = "on_completion"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "notify_mode": self.notify_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaneHookConfig":
        return cls(
            enabled=data.get("enabled", False),
            notify_mode=data.get("notify_mode", "on_completion"),
        )


@dataclass
class NotificationConfig:
    """Email notification formatting settings."""
    include_context_lines: int = 50
    max_email_length: int = 10000
    subject_prefix: str = "[CCB]"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationConfig":
        return cls(
            include_context_lines=data.get("include_context_lines", 50),
            max_email_length=data.get("max_email_length", 10000),
            subject_prefix=data.get("subject_prefix", "[CCB]"),
        )


@dataclass
class PollingConfig:
    """IMAP polling configuration."""
    interval_seconds: int = 30
    folder: str = "INBOX"
    mark_as_read: bool = True
    use_idle: bool = True  # Use IMAP IDLE for real-time notifications
    idle_timeout: int = 300  # IDLE timeout in seconds (re-issue IDLE after this)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PollingConfig":
        return cls(
            interval_seconds=data.get("interval_seconds", 30),
            folder=data.get("folder", "INBOX"),
            mark_as_read=data.get("mark_as_read", True),
            use_idle=data.get("use_idle", True),
            idle_timeout=data.get("idle_timeout", 300),
        )


def _default_pane_hooks() -> Dict[str, PaneHookConfig]:
    """Create default pane hooks configuration."""
    return {provider: PaneHookConfig() for provider in SUPPORTED_PROVIDERS}


@dataclass
class MailConfig:
    """Main mail configuration (version 2)."""
    version: int = CURRENT_CONFIG_VERSION
    enabled: bool = False
    service_account: ServiceAccountConfig = field(default_factory=ServiceAccountConfig)
    target_email: str = ""
    pane_hooks: Dict[str, PaneHookConfig] = field(default_factory=_default_pane_hooks)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    polling: PollingConfig = field(default_factory=PollingConfig)

    # Backward-compatible alias: older code expects config.account
    @property
    def account(self) -> ServiceAccountConfig:
        return self.service_account

    @account.setter
    def account(self, value: ServiceAccountConfig) -> None:
        self.service_account = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "enabled": self.enabled,
            "service_account": self.service_account.to_dict(),
            "target_email": self.target_email,
            "pane_hooks": {k: v.to_dict() for k, v in self.pane_hooks.items()},
            "notification": self.notification.to_dict(),
            "polling": self.polling.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MailConfig":
        # Parse pane_hooks
        pane_hooks_data = data.get("pane_hooks", {})
        pane_hooks = _default_pane_hooks()
        for provider, hook_data in pane_hooks_data.items():
            if provider in SUPPORTED_PROVIDERS:
                pane_hooks[provider] = PaneHookConfig.from_dict(hook_data)

        return cls(
            version=data.get("version", CURRENT_CONFIG_VERSION),
            enabled=data.get("enabled", False),
            service_account=ServiceAccountConfig.from_dict(data.get("service_account", {})),
            target_email=data.get("target_email", ""),
            pane_hooks=pane_hooks,
            notification=NotificationConfig.from_dict(data.get("notification", {})),
            polling=PollingConfig.from_dict(data.get("polling", {})),
        )

    def get_hook(self, provider: str) -> Optional[PaneHookConfig]:
        """Get hook config for a provider."""
        return self.pane_hooks.get(provider)

    def set_hook_enabled(self, provider: str, enabled: bool) -> bool:
        """Enable or disable a pane hook."""
        if provider not in self.pane_hooks:
            return False
        self.pane_hooks[provider].enabled = enabled
        return True

    def get_enabled_hooks(self) -> List[str]:
        """Get list of providers with enabled hooks."""
        return [p for p, h in self.pane_hooks.items() if h.enabled]


# Alias for backward compatibility
MailConfigV2 = MailConfig


@dataclass
class MailConfigV3(MailConfig):
    """Mail configuration version 3 (ASK-based).

    V3 routes emails to ASK system instead of panes.
    Provider is extracted from body prefix: "CLAUDE: message"
    """
    # V3 specific fields
    default_work_dir: str = ""
    default_provider: str = "claude"
    provider_prefix_pattern: str = r"^(\w+)"
    case_insensitive: bool = True

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["default_work_dir"] = self.default_work_dir
        data["default_provider"] = self.default_provider
        data["provider_prefix_pattern"] = self.provider_prefix_pattern
        data["case_insensitive"] = self.case_insensitive
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MailConfigV3":
        # Parse pane_hooks (kept for compatibility)
        pane_hooks_data = data.get("pane_hooks", {})
        pane_hooks = _default_pane_hooks()
        for provider, hook_data in pane_hooks_data.items():
            if provider in SUPPORTED_PROVIDERS:
                pane_hooks[provider] = PaneHookConfig.from_dict(hook_data)

        return cls(
            version=data.get("version", CURRENT_CONFIG_VERSION),
            enabled=data.get("enabled", False),
            service_account=ServiceAccountConfig.from_dict(data.get("service_account", {})),
            target_email=data.get("target_email", ""),
            pane_hooks=pane_hooks,
            notification=NotificationConfig.from_dict(data.get("notification", {})),
            polling=PollingConfig.from_dict(data.get("polling", {})),
            default_work_dir=data.get("default_work_dir", ""),
            default_provider=data.get("default_provider", "claude"),
            provider_prefix_pattern=data.get("provider_prefix_pattern", r"^(\w+)"),
            case_insensitive=data.get("case_insensitive", True),
        )


def get_config_dir() -> Path:
    """Get the mail configuration directory."""
    config_dir = Path(os.environ.get("CCB_MAIL_CONFIG_DIR", DEFAULT_CONFIG_DIR))
    return config_dir


def ensure_config_dir() -> Path:
    """Ensure the configuration directory exists with proper permissions."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    # Set directory permissions to 700 (owner only)
    config_dir.chmod(0o700)
    return config_dir


def get_config_path() -> Path:
    """Get the path to the configuration file."""
    return get_config_dir() / CONFIG_FILE


def _migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate version 1 config to version 2 format."""
    v2_data = {
        "version": 2,
        "enabled": data.get("enabled", False),
        "polling": data.get("polling", {}),
    }

    # Migrate account -> service_account
    if "account" in data:
        v2_data["service_account"] = data["account"]

    # Migrate routing.reply_to_address -> target_email
    routing = data.get("routing", {})
    if routing.get("reply_to_address"):
        v2_data["target_email"] = routing["reply_to_address"]
    elif routing.get("allowed_senders"):
        # Use first allowed sender as target
        v2_data["target_email"] = routing["allowed_senders"][0]

    # Create default pane_hooks
    v2_data["pane_hooks"] = {}
    for provider in SUPPORTED_PROVIDERS:
        v2_data["pane_hooks"][provider] = {
            "enabled": False,
            "notify_mode": "on_completion",
        }

    # Default notification settings
    v2_data["notification"] = {
        "include_context_lines": 50,
        "max_email_length": 10000,
        "subject_prefix": "[CCB]",
    }

    return v2_data


def _migrate_v2_to_v3(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate version 2 config to version 3 format."""
    v3_data = dict(data)
    v3_data["version"] = CURRENT_CONFIG_VERSION

    # Add v3 specific fields with defaults
    v3_data.setdefault("default_work_dir", "")
    v3_data.setdefault("default_provider", "claude")
    v3_data.setdefault("provider_prefix_pattern", r"^(\w+)")
    v3_data.setdefault("case_insensitive", True)

    # pane_hooks are kept for compatibility but not used in v3
    return v3_data


def load_config() -> MailConfigV3:
    """Load mail configuration from file, migrating if necessary."""
    config_path = get_config_path()
    if not config_path.exists():
        return MailConfigV3()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check version and migrate if needed
        version = data.get("version", 1)
        if version < CURRENT_CONFIG_VERSION:
            if version == 1:
                data = _migrate_v1_to_v2(data)
                version = 2
            if version == 2:
                data = _migrate_v2_to_v3(data)
            # Save migrated config
            config = MailConfigV3.from_dict(data)
            save_config(config)
            return config

        return MailConfigV3.from_dict(data)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load mail config: {e}")
        return MailConfigV3()


def save_config(config: "MailConfig") -> None:
    """Save mail configuration to file."""
    ensure_config_dir()
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
    # Set file permissions to 600 (owner read/write only)
    config_path.chmod(0o600)


def get_threads_path() -> Path:
    """Get the path to the threads mapping file."""
    return get_config_dir() / THREADS_FILE


def validate_config(config: MailConfig) -> List[str]:
    """Validate configuration and return list of errors."""
    errors = []

    if config.enabled:
        if not config.service_account.email:
            errors.append("Service account email is required")
        if not config.service_account.imap.host:
            errors.append("IMAP host is required")
        if not config.service_account.smtp.host:
            errors.append("SMTP host is required")
        if not config.target_email:
            errors.append("Target email is required")

    return errors


def is_configured() -> bool:
    """Check if mail system is properly configured."""
    config = load_config()
    return bool(
        config.service_account.email
        and config.service_account.imap.host
        and config.service_account.smtp.host
        and config.target_email
    )
