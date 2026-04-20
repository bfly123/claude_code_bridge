from __future__ import annotations

from provider_backends.claude.protocol import extract_reply_for_req, wrap_claude_prompt, wrap_claude_turn_prompt


def test_extract_reply_for_req_uses_begin_and_done_window() -> None:
    text = (
        'CCB_BEGIN: job_old123\n'
        'old reply\n'
        'CCB_DONE: job_old123\n'
        '\n'
        'CCB_BEGIN: job_new123\n'
        'new reply line 1\n'
        'new reply line 2\n'
        'CCB_DONE: job_new123\n'
    )

    assert extract_reply_for_req(text, 'job_new123') == 'new reply line 1\nnew reply line 2'


def test_wrap_claude_prompt_includes_language_and_markdown_hint(monkeypatch) -> None:
    monkeypatch.setenv('CCB_REPLY_LANG', 'zh')
    monkeypatch.setattr('provider_backends.claude.protocol_runtime.prompt.load_claude_skills', lambda: '')

    prompt = wrap_claude_prompt('Please return a markdown table', 'req_1')

    assert 'Reply in Chinese.' in prompt
    assert 'pipe-and-dash Markdown table syntax' in prompt
    assert 'CCB_BEGIN: req_1' in prompt
    assert 'CCB_DONE: req_1' in prompt


def test_wrap_claude_turn_prompt_prefixes_loaded_skills(monkeypatch) -> None:
    monkeypatch.delenv('CCB_REPLY_LANG', raising=False)
    monkeypatch.delenv('CCB_LANG', raising=False)
    monkeypatch.setattr('provider_backends.claude.protocol_runtime.prompt.load_claude_skills', lambda: 'SKILL BLOCK')

    prompt = wrap_claude_turn_prompt('hello', 'req_2')

    assert prompt.startswith('CCB_REQ_ID: req_2\n\nSKILL BLOCK\n\nhello')
