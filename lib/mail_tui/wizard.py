"""
TUI configuration wizard for CCB Mail.

Uses textual for terminal UI.
"""

import sys
from typing import Optional

# Check if textual is available
try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import (
        Button, Footer, Header, Input, Label,
        ListItem, ListView, Static, Select
    )
    from textual.screen import Screen
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from mail.config import (
    MailConfig, AccountConfig, PollingConfig,
    ImapConfig, SmtpConfig, PROVIDER_PRESETS, load_config, save_config,
)
from mail.credentials import store_password, has_password
from mail.poller import ImapPoller
from mail.sender import SmtpSender
from mail.adapters.gmail import GmailAdapter
from mail.adapters.outlook import OutlookAdapter
from mail.adapters.qq import QQMailAdapter


ADAPTERS = {
    "gmail": GmailAdapter(),
    "outlook": OutlookAdapter(),
    "qq": QQMailAdapter(),
}


def run_simple_wizard() -> bool:
    """Run a simple text-based wizard (fallback when textual unavailable)."""
    print("\n=== CCB Mail Setup Wizard ===\n")

    # Load existing config
    config = load_config()

    # Step 1: Select provider
    print("Select your email provider:")
    print("  1. Gmail")
    print("  2. Outlook / Microsoft 365")
    print("  3. QQ Mail")
    print("  4. Custom")

    choice = input("\nEnter choice [1-4]: ").strip()
    provider_map = {"1": "gmail", "2": "outlook", "3": "qq", "4": "custom"}
    provider = provider_map.get(choice, "custom")

    # Show auth instructions
    if provider in ADAPTERS:
        adapter = ADAPTERS[provider]
        print(f"\n{adapter.get_auth_instructions()}\n")

    # Step 2: Enter email
    default_email = config.account.email or ""
    email = input(f"Enter your email address [{default_email}]: ").strip()
    if not email:
        email = default_email
    if not email:
        print("Error: Email address is required")
        return False

    # Step 3: Enter password
    has_existing = has_password(email)
    if has_existing:
        print(f"Password already stored for {email}")
        change = input("Change password? [y/N]: ").strip().lower()
        if change == "y":
            import getpass
            password = getpass.getpass("Enter app password: ")
            if password:
                store_password(email, password)
    else:
        import getpass
        password = getpass.getpass("Enter app password: ")
        if not password:
            print("Error: Password is required")
            return False
        store_password(email, password)

    # Step 4: Configure routing
    print("\nSelect routing mode:")
    print("  1. Plus-alias (user+claude@gmail.com)")
    print("  2. Subject prefix ([claude] message)")

    route_choice = input("\nEnter choice [1-2]: ").strip()
    _routing_mode = "subject_prefix" if route_choice == "2" else "plus_alias"

    # Step 5: Default provider
    print("\nSelect default AI provider:")
    print("  1. Claude")
    print("  2. Codex")
    print("  3. Gemini")
    print("  4. OpenCode")
    print("  5. Droid")

    default_choice = input("\nEnter choice [1-5]: ").strip()
    default_map = {"1": "claude", "2": "codex", "3": "gemini", "4": "opencode", "5": "droid"}
    default_provider = default_map.get(default_choice, "claude")

    # Step 6: Allowed senders (whitelist)
    print("\n允许的发件人 (安全白名单):")
    print("  只有白名单中的邮箱发来的邮件才会被处理")
    print("  留空表示接受所有发件人")
    allowed_input = input("\n输入允许的邮箱地址 (多个用逗号分隔): ").strip()
    allowed_senders = [s.strip() for s in allowed_input.split(",") if s.strip()] if allowed_input else []

    # Step 7: Reply address
    print("\n回复地址设置:")
    print("  默认: 回复到原始发件人")
    print("  可设置固定地址: 所有回复都发到指定邮箱")
    reply_to = input("\n固定回复地址 (留空使用默认): ").strip()

    # Build config
    if provider in PROVIDER_PRESETS:
        config.account = AccountConfig.from_preset(provider, email)
    else:
        # Custom provider
        print("\nCustom IMAP settings:")
        imap_host = input("IMAP host: ").strip()
        imap_port = int(input("IMAP port [993]: ").strip() or "993")

        print("\nCustom SMTP settings:")
        smtp_host = input("SMTP host: ").strip()
        smtp_port = int(input("SMTP port [587]: ").strip() or "587")

        config.account = AccountConfig(
            provider="custom",
            email=email,
            imap=ImapConfig(host=imap_host, port=imap_port, ssl=True),
            smtp=SmtpConfig(host=smtp_host, port=smtp_port, starttls=True),
        )

    config.account.email = email

    # V3 config no longer has RoutingConfig.
    # Keep setup inputs mapped to current fields:
    # - default provider stays explicit
    # - target_email acts as the authorized/reply address
    config.default_provider = default_provider
    if reply_to:
        config.target_email = reply_to
    elif allowed_senders:
        config.target_email = allowed_senders[0]

    # Step 8: Test connection
    print("\nTesting connection...")

    poller = ImapPoller(config)
    imap_ok, imap_msg = poller.test_connection()
    print(f"  IMAP: {imap_msg}")

    sender = SmtpSender(config)
    smtp_ok, smtp_msg = sender.test_connection()
    print(f"  SMTP: {smtp_msg}")

    if not (imap_ok and smtp_ok):
        save_anyway = input("\nConnection test failed. Save config anyway? [y/N]: ").strip().lower()
        if save_anyway != "y":
            return False

    # Save config
    config.enabled = True
    save_config(config)
    print("\nConfiguration saved!")

    # Start service?
    start = input("\nStart mail service now? [Y/n]: ").strip().lower()
    if start != "n":
        from mail.daemon import start_daemon
        print("Starting mail daemon...")
        start_daemon(foreground=False)

    return True


# Textual TUI App (if available)
if TEXTUAL_AVAILABLE:
    class WelcomeScreen(Screen):
        """Welcome screen."""

        def compose(self) -> ComposeResult:
            yield Header()
            yield Container(
                Static("Welcome to CCB Mail Setup", classes="title"),
                Static(
                    "This wizard will help you configure email integration "
                    "for CCB, allowing you to interact with AI providers via email.",
                    classes="description",
                ),
                Static(
                    "\nFeatures:\n"
                    "• Send messages to AI providers via email\n"
                    "• Receive AI responses in your inbox\n"
                    "• Route messages using plus-alias or subject prefix\n"
                    "• Support for Gmail, Outlook, QQ Mail, and custom servers",
                    classes="features",
                ),
                Horizontal(
                    Button("Continue", id="continue", variant="primary"),
                    Button("Cancel", id="cancel"),
                    classes="buttons",
                ),
                id="welcome",
            )
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "continue":
                self.app.push_screen("provider")
            else:
                self.app.exit()

    class ProviderScreen(Screen):
        """Provider selection screen."""

        def compose(self) -> ComposeResult:
            yield Header()
            yield Container(
                Static("Select Email Provider", classes="title"),
                ListView(
                    ListItem(Label("Gmail"), id="gmail"),
                    ListItem(Label("Outlook / Microsoft 365"), id="outlook"),
                    ListItem(Label("QQ 邮箱"), id="qq"),
                    ListItem(Label("Custom Server"), id="custom"),
                    id="provider-list",
                ),
                Horizontal(
                    Button("Back", id="back"),
                    Button("Next", id="next", variant="primary"),
                    classes="buttons",
                ),
                id="provider",
            )
            yield Footer()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "back":
                self.app.pop_screen()
            elif event.button.id == "next":
                self.app.push_screen("account")

    class MailSetupApp(App):
        """Mail setup TUI application."""

        CSS = """
        .title {
            text-align: center;
            text-style: bold;
            margin: 1 0;
        }
        .description {
            margin: 1 2;
        }
        .features {
            margin: 1 2;
        }
        .buttons {
            margin: 2 0;
            align: center middle;
        }
        Button {
            margin: 0 1;
        }
        """

        SCREENS = {
            "welcome": WelcomeScreen,
            "provider": ProviderScreen,
        }

        def on_mount(self) -> None:
            self.push_screen("welcome")


def run_wizard() -> bool:
    """Run the mail setup wizard."""
    if TEXTUAL_AVAILABLE:
        try:
            app = MailSetupApp()
            app.run()
            return True
        except Exception as e:
            print(f"TUI error: {e}, falling back to simple wizard")

    return run_simple_wizard()
