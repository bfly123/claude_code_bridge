from __future__ import annotations

from provider_backends.claude.execution_runtime.start import looks_ready


def test_looks_ready_rejects_welcome_banner_without_prompt_shortcuts() -> None:
    text = """
╭─ Claude Code ────────────────────────────╮
│                                          │
│              Welcome back!               │
│                                          │
│                Sonnet 4.6                │
│            API Usage Billing             │
╰──────────────────────────────────────────╯
"""

    assert looks_ready(text) is False


def test_looks_ready_accepts_idle_prompt_with_shortcuts() -> None:
    text = """
╭─── Claude Code v2.1.89 ─────────────────╮
│               Welcome back!             │
╰─────────────────────────────────────────╯

───────────────────────────────────────────
❯
───────────────────────────────────────────
  ? for shortcuts
"""

    assert looks_ready(text) is True


def test_looks_ready_accepts_busy_prompt() -> None:
    text = """
❯ 1+1=

✽ Blanching…

───────────────────────────────────────────
❯
───────────────────────────────────────────
  esc to interrupt
"""

    assert looks_ready(text) is True
