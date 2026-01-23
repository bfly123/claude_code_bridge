"""Tests for curask module and cursor_utils."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cursor_utils import extract_chat_id_fallback, parse_json_output


class TestParseJsonOutput:
    """Tests for parse_json_output function."""

    def test_parse_valid_success_response(self) -> None:
        """Test parsing a valid success JSON response."""
        json_output = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "duration_ms": 5000,
            "result": "Hello, world!",
            "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "request_id": "req-123"
        })

        session_id, result_text, is_error = parse_json_output(json_output)

        assert session_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert result_text == "Hello, world!"
        assert is_error is False

    def test_parse_valid_error_response(self) -> None:
        """Test parsing a valid error JSON response."""
        json_output = json.dumps({
            "type": "result",
            "subtype": "error",
            "is_error": True,
            "result": "Something went wrong",
            "session_id": "error-session-id-1234-5678-901234567890",
        })

        session_id, result_text, is_error = parse_json_output(json_output)

        assert session_id == "error-session-id-1234-5678-901234567890"
        assert result_text == "Something went wrong"
        assert is_error is True

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON returns None tuple."""
        invalid_outputs = [
            "not json at all",
            "{broken json",
            "",
            "   ",
        ]

        for invalid in invalid_outputs:
            session_id, result_text, is_error = parse_json_output(invalid)
            assert session_id is None
            assert result_text is None
            assert is_error is None

    def test_parse_json_missing_fields(self) -> None:
        """Test parsing JSON with missing optional fields."""
        # Minimal valid JSON
        json_output = json.dumps({"type": "result"})

        session_id, result_text, is_error = parse_json_output(json_output)

        assert session_id is None  # Missing session_id
        assert result_text == ""   # Missing result defaults to empty string
        assert is_error is False   # Missing is_error defaults to False

    def test_parse_json_with_whitespace(self) -> None:
        """Test parsing JSON with leading/trailing whitespace."""
        json_output = "  \n" + json.dumps({
            "result": "test",
            "session_id": "12345678-1234-1234-1234-123456789012",
            "is_error": False,
        }) + "\n  "

        session_id, result_text, is_error = parse_json_output(json_output)

        assert session_id == "12345678-1234-1234-1234-123456789012"
        assert result_text == "test"
        assert is_error is False


class TestExtractChatIdFallback:
    """Tests for extract_chat_id_fallback function."""

    def test_extract_session_id_format(self) -> None:
        """Test extracting session_id from JSON-like text."""
        text = 'Some output with "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890" in it'
        result = extract_chat_id_fallback(text)
        assert result == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_extract_chat_id_format(self) -> None:
        """Test extracting chatId from various formats."""
        test_cases = [
            ('"chatId": "12345678-1234-1234-1234-123456789012"', "12345678-1234-1234-1234-123456789012"),
            ('chatId: 12345678-1234-1234-1234-123456789012', "12345678-1234-1234-1234-123456789012"),
            ('chat_id=12345678-1234-1234-1234-123456789012', "12345678-1234-1234-1234-123456789012"),
        ]

        for text, expected in test_cases:
            result = extract_chat_id_fallback(text)
            assert result == expected, f"Failed for input: {text}"

    def test_extract_no_match(self) -> None:
        """Test that no match returns None."""
        text = "No UUID here at all"
        result = extract_chat_id_fallback(text)
        assert result is None

    def test_extract_case_insensitive(self) -> None:
        """Test case insensitive matching."""
        test_cases = [
            '"CHATID": "12345678-1234-1234-1234-123456789012"',
            '"ChatId": "12345678-1234-1234-1234-123456789012"',
            'CHAT_ID=12345678-1234-1234-1234-123456789012',
        ]

        for text in test_cases:
            result = extract_chat_id_fallback(text)
            assert result == "12345678-1234-1234-1234-123456789012", f"Failed for input: {text}"


class TestCuraskIntegration:
    """Integration tests for curask with mocked subprocess."""

    def test_json_output_parsing_integration(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test full flow with mocked cursor-agent returning JSON."""
        import subprocess
        import sys
        from unittest.mock import MagicMock

        # Add bin to path for curask import
        bin_dir = Path(__file__).resolve().parents[1] / "bin"

        # Create a simple test script that mimics curask behavior
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Mock subprocess.run to return JSON output
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Test response",
            "session_id": "mock-session-1234-5678-901234567890",
        })
        mock_result.stderr = ""
        mock_result.returncode = 0

        # Test parse_json_output with the mock result
        session_id, result_text, is_error = parse_json_output(mock_result.stdout)

        assert session_id == "mock-session-1234-5678-901234567890"
        assert result_text == "Test response"
        assert is_error is False

    def test_fallback_when_json_fails(self) -> None:
        """Test fallback to regex when JSON parsing fails."""
        # Non-JSON output with chatId
        raw_output = 'Some text output with chatId: 12345678-1234-1234-1234-123456789012'

        # JSON parsing should fail
        session_id, result_text, is_error = parse_json_output(raw_output)
        assert session_id is None
        assert result_text is None

        # Fallback should work
        chat_id = extract_chat_id_fallback(raw_output)
        assert chat_id == "12345678-1234-1234-1234-123456789012"

    def test_error_response_sets_error_flag(self) -> None:
        """Test that is_error=True is correctly detected."""
        json_output = json.dumps({
            "type": "result",
            "subtype": "error",
            "is_error": True,
            "result": "Error message",
            "session_id": "error-session-uuid-1234-567890123456",
        })

        session_id, result_text, is_error = parse_json_output(json_output)

        assert is_error is True
        assert result_text == "Error message"
        assert session_id == "error-session-uuid-1234-567890123456"
