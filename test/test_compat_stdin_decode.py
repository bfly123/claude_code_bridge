from __future__ import annotations

import locale

import compat


def test_decode_stdin_bytes_prefers_utf8_when_valid(monkeypatch) -> None:
    monkeypatch.setattr(locale, "getpreferredencoding", lambda _do_setlocale=False: "gbk")
    raw = "你好".encode("utf-8")
    assert compat.decode_stdin_bytes(raw) == "你好"


def test_decode_stdin_bytes_falls_back_to_preferred_encoding(monkeypatch) -> None:
    monkeypatch.setattr(locale, "getpreferredencoding", lambda _do_setlocale=False: "gbk")
    raw = "你好Codex！这是一条中文消息".encode("gbk")
    assert compat.decode_stdin_bytes(raw) == "你好Codex！这是一条中文消息"


def test_decode_stdin_bytes_never_emits_surrogates() -> None:
    # Invalid UTF-8 byte 0x80 should not end up as a lone surrogate (e.g. \udc80).
    out = compat.decode_stdin_bytes(b"abc\x80def")
    assert "\udc80" not in out


def test_decode_stdin_bytes_honors_utf16le_bom() -> None:
    raw = b"\xff\xfe" + "你好".encode("utf-16le")
    assert compat.decode_stdin_bytes(raw) == "你好"

