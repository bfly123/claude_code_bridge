"""
Tests for the memory module.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from memory import (
    ConversationEntry,
    TransferContext,
    ConversationDeduper,
    ContextFormatter,
    ClaudeSessionParser,
    SessionNotFoundError,
)


class TestConversationDeduper:
    """Tests for ConversationDeduper."""

    def setup_method(self):
        self.deduper = ConversationDeduper()

    def test_strip_protocol_markers_ccb_req_id(self):
        text = "Hello\nCCB_REQ_ID: 20260202-123456-001-1-1\nWorld"
        result = self.deduper.strip_protocol_markers(text)
        assert "CCB_REQ_ID" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strip_protocol_markers_ccb_begin(self):
        text = "Start\nCCB_BEGIN: 20260202-123456-001-1-1\nEnd"
        result = self.deduper.strip_protocol_markers(text)
        assert "CCB_BEGIN" not in result

    def test_strip_protocol_markers_ccb_done(self):
        text = "Start\nCCB_DONE: 20260202-123456-001-1-1\nEnd"
        result = self.deduper.strip_protocol_markers(text)
        assert "CCB_DONE" not in result

    def test_strip_protocol_markers_async_submitted(self):
        text = "Start\n[CCB_ASYNC_SUBMITTED provider=codex]\nEnd"
        result = self.deduper.strip_protocol_markers(text)
        assert "CCB_ASYNC_SUBMITTED" not in result

    def test_strip_system_noise_system_reminder(self):
        text = "Hello <system-reminder>noise</system-reminder> World"
        result = self.deduper.strip_system_noise(text)
        assert "<system-reminder>" not in result
        assert "noise" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strip_system_noise_env(self):
        text = "Hello <env>environment</env> World"
        result = self.deduper.strip_system_noise(text)
        assert "<env>" not in result

    def test_strip_system_noise_ccb_config(self):
        text = "Hello <!-- CCB_CONFIG_START -->config<!-- CCB_CONFIG_END --> World"
        result = self.deduper.strip_system_noise(text)
        assert "CCB_CONFIG" not in result

    def test_clean_content_combined(self):
        text = """Hello
CCB_REQ_ID: 20260202-123456-001-1-1
<system-reminder>noise</system-reminder>
World"""
        result = self.deduper.clean_content(text)
        assert "CCB_REQ_ID" not in result
        assert "<system-reminder>" not in result
        assert "Hello" in result
        assert "World" in result

    def test_dedupe_messages_removes_duplicates(self):
        entries = [
            ConversationEntry(role="user", content="Hello"),
            ConversationEntry(role="user", content="Hello"),
            ConversationEntry(role="assistant", content="Hi there"),
        ]
        result = self.deduper.dedupe_messages(entries)
        assert len(result) == 2

    def test_dedupe_messages_keeps_different(self):
        entries = [
            ConversationEntry(role="user", content="Hello"),
            ConversationEntry(role="assistant", content="Hi"),
            ConversationEntry(role="user", content="How are you?"),
        ]
        result = self.deduper.dedupe_messages(entries)
        assert len(result) == 3

    def test_dedupe_messages_empty(self):
        result = self.deduper.dedupe_messages([])
        assert result == []

    def test_collapse_tool_calls_read(self):
        entries = [
            ConversationEntry(
                role="assistant",
                content="Let me read the file.",
                tool_calls=[
                    {"name": "Read", "input": {"file_path": "/path/to/file.py"}},
                ],
            ),
        ]
        result = self.deduper.collapse_tool_calls(entries)
        assert len(result) == 1
        assert "Read 1 file(s)" in result[0].content
        assert "file.py" in result[0].content

    def test_collapse_tool_calls_multiple(self):
        entries = [
            ConversationEntry(
                role="assistant",
                content="",
                tool_calls=[
                    {"name": "Read", "input": {"file_path": "/a.py"}},
                    {"name": "Read", "input": {"file_path": "/b.py"}},
                    {"name": "Bash", "input": {"command": "ls"}},
                ],
            ),
        ]
        result = self.deduper.collapse_tool_calls(entries)
        assert "Read 2 file(s)" in result[0].content
        assert "Bash 1 command(s)" in result[0].content


class TestContextFormatter:
    """Tests for ContextFormatter."""

    def setup_method(self):
        self.formatter = ContextFormatter(max_tokens=1000)

    def test_estimate_tokens(self):
        text = "a" * 400  # 400 chars = ~100 tokens
        tokens = self.formatter.estimate_tokens(text)
        assert tokens == 100

    def test_truncate_to_limit(self):
        # Create conversations that exceed limit
        conversations = [
            ("a" * 400, "b" * 400),  # ~200 tokens
            ("c" * 400, "d" * 400),  # ~200 tokens
            ("e" * 400, "f" * 400),  # ~200 tokens
        ]
        result = self.formatter.truncate_to_limit(conversations, max_tokens=500)
        # Should keep only 2 pairs (400 tokens)
        assert len(result) == 2
        # Should keep newest (last) pairs
        assert result[-1] == ("e" * 400, "f" * 400)

    def test_format_markdown(self):
        context = TransferContext(
            conversations=[("Hello", "Hi there")],
            source_session_id="test-session",
            token_estimate=10,
        )
        result = self.formatter.format_markdown(context)
        assert "## Context Transfer from Claude" in result
        assert "test-session" in result
        assert "Hello" in result
        assert "Hi there" in result

    def test_format_plain(self):
        context = TransferContext(
            conversations=[("Hello", "Hi there")],
            source_session_id="test-session",
            token_estimate=10,
        )
        result = self.formatter.format_plain(context)
        assert "=== Context Transfer from Claude ===" in result
        assert "test-session" in result

    def test_format_json(self):
        context = TransferContext(
            conversations=[("Hello", "Hi there")],
            source_session_id="test-session",
            token_estimate=10,
        )
        result = self.formatter.format_json(context)
        data = json.loads(result)
        assert data["source_session_id"] == "test-session"
        assert len(data["conversations"]) == 1


class TestClaudeSessionParser:
    """Tests for ClaudeSessionParser."""

    def test_parse_session_not_found(self):
        parser = ClaudeSessionParser()
        with pytest.raises(SessionNotFoundError):
            parser.parse_session(Path("/nonexistent/session.jsonl"))

    def test_parse_session_valid(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "Hello"},
                "uuid": "1",
            }) + "\n")
            f.write(json.dumps({
                "type": "assistant",
                "message": {"content": "Hi there"},
                "uuid": "2",
                "parentUuid": "1",
            }) + "\n")
            f.flush()
            temp_path = f.name

        parser = ClaudeSessionParser()
        entries = parser.parse_session(Path(temp_path))

        assert len(entries) == 2
        assert entries[0].role == "user"
        assert entries[0].content == "Hello"
        assert entries[1].role == "assistant"
        assert entries[1].content == "Hi there"

        Path(temp_path).unlink()

    def test_parse_session_with_content_blocks(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Part 1"},
                        {"type": "text", "text": "Part 2"},
                    ]
                },
                "uuid": "1",
            }) + "\n")
            f.flush()
            temp_path = f.name

        parser = ClaudeSessionParser()
        entries = parser.parse_session(Path(temp_path))

        assert len(entries) == 1
        assert "Part 1" in entries[0].content
        assert "Part 2" in entries[0].content

        Path(temp_path).unlink()

    def test_parse_session_corrupted_tolerant(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            # Write some valid and some invalid lines
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "Hello"},
            }) + "\n")
            f.write("invalid json\n")
            f.write(json.dumps({
                "type": "assistant",
                "message": {"content": "Hi"},
            }) + "\n")
            f.flush()
            temp_path = f.name

        parser = ClaudeSessionParser()
        entries = parser.parse_session(Path(temp_path))

        # Should still parse valid entries
        assert len(entries) == 2

        Path(temp_path).unlink()

    def test_get_session_info(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write("{}\n")
            f.flush()
            temp_path = f.name

        parser = ClaudeSessionParser()
        info = parser.get_session_info(Path(temp_path))

        assert info.session_id == Path(temp_path).stem
        assert info.session_path == temp_path

        Path(temp_path).unlink()


class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_full_pipeline_dry_run(self):
        """Test the full pipeline with a mock session."""
        from memory import ContextTransfer

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock session file
            session_path = Path(tmpdir) / "test-session.jsonl"
            with open(session_path, "w") as f:
                f.write(json.dumps({
                    "type": "user",
                    "message": {"content": "What is 2+2?"},
                    "uuid": "1",
                }) + "\n")
                f.write(json.dumps({
                    "type": "assistant",
                    "message": {"content": "2+2 equals 4."},
                    "uuid": "2",
                    "parentUuid": "1",
                }) + "\n")

            transfer = ContextTransfer(work_dir=Path(tmpdir))
            context = transfer.extract_conversations(
                session_path=session_path,
                last_n=5,
            )

            assert len(context.conversations) == 1
            assert context.conversations[0][0] == "What is 2+2?"
            assert context.conversations[0][1] == "2+2 equals 4."

            # Test formatting
            output = transfer.format_output(context, "markdown")
            assert "What is 2+2?" in output
            assert "2+2 equals 4." in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
