from __future__ import annotations

from pathlib import Path

from provider_backends.claude.protocol_runtime.skills import default_claude_skills_dir, load_claude_skills_from_dir


def test_load_claude_skills_prefers_runtime_prompt_file(tmp_path) -> None:
    skills_dir = tmp_path / 'claude_skills'
    runtime_path = skills_dir / 'ask' / 'RUNTIME.md'
    runtime_path.parent.mkdir(parents=True)
    runtime_path.write_text('RUNTIME ASK RULES', encoding='utf-8')
    (skills_dir / 'ask' / 'SKILL.md').write_text('SHOULD NOT WIN', encoding='utf-8')

    loaded = load_claude_skills_from_dir(skills_dir)

    assert loaded == 'RUNTIME ASK RULES'


def test_load_claude_skills_falls_back_to_skill_body_without_front_matter(tmp_path) -> None:
    skills_dir = tmp_path / 'claude_skills'
    skill_path = skills_dir / 'ask' / 'SKILL.md'
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        '---\n'
        'name: ask\n'
        'description: demo\n'
        '---\n'
        '\n'
        '# Ask\n'
        '\n'
        'Rule body\n',
        encoding='utf-8',
    )

    loaded = load_claude_skills_from_dir(skills_dir)

    assert loaded == '# Ask\n\nRule body'


def test_default_claude_skills_dir_points_to_repo_root() -> None:
    skills_dir = default_claude_skills_dir()

    assert skills_dir.name == 'claude_skills'
    assert (skills_dir / 'ask' / 'SKILL.md').is_file()
    assert skills_dir == Path(__file__).resolve().parents[1] / 'claude_skills'
