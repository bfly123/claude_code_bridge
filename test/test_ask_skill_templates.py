from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_shell_ask_skill_templates_use_short_ask_command() -> None:
    for relative_path in (
        'claude_skills/ask/SKILL.md',
        'claude_skills/ask/RUNTIME.md',
        'codex_skills/ask/SKILL.md',
        'droid_skills/ask/SKILL.md',
        'droid_skills/ask.md',
    ):
        text = (REPO_ROOT / relative_path).read_text(encoding='utf-8')
        assert 'command ask ' in text
        assert 'command ccb ask' not in text
        assert 'canonical `ccb ask`' not in text
        assert 'compatibility alias' not in text


def test_powershell_ask_skill_template_uses_short_ask_command() -> None:
    text = (REPO_ROOT / 'claude_skills/ask/SKILL.md.powershell').read_text(encoding='utf-8')

    assert 'FilePath "ask"' in text
    assert 'ccb ask' not in text
    assert 'compatibility alias' not in text
