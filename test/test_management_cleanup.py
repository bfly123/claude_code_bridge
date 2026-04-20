from __future__ import annotations


def test_cleanup_command_docs_cover_wrapper_registries() -> None:
    from cli.management_runtime.claude_home_cleanup import CLAUDE_COMMAND_DOCS

    assert "cask.md" in CLAUDE_COMMAND_DOCS
    assert "gpend.md" in CLAUDE_COMMAND_DOCS
    assert "qpend.md" in CLAUDE_COMMAND_DOCS
    assert "cping.md" in CLAUDE_COMMAND_DOCS
    assert "hping.md" in CLAUDE_COMMAND_DOCS


def test_cleanup_permissions_cover_wrapper_registries() -> None:
    from cli.management_runtime.claude_home_cleanup import _retired_permission_allow_entries

    entries = _retired_permission_allow_entries()

    assert "Bash(cask:*)" in entries
    assert "Bash(cpend)" in entries
    assert "Bash(qpend)" in entries
    assert "Bash(cping)" in entries
    assert "Bash(hping)" in entries
