from __future__ import annotations

from pathlib import Path

from ui_text import t

from .common import remember_session_path


def consume_pending(comm, *, display: bool = True, n: int = 1):
    current_session = comm.log_reader.current_session_path()
    if isinstance(current_session, Path):
        comm._remember_gemini_session(current_session)

    if n > 1:
        conversations = comm.log_reader.latest_conversations(n)
        if not conversations:
            if display:
                print(t("no_reply_available", provider="Gemini"))
            return None
        if display:
            _display_conversations(conversations)
        return conversations

    message = comm.log_reader.latest_message()
    if not message:
        if display:
            print(t("no_reply_available", provider="Gemini"))
        return None
    if display:
        print(message)
    remember_session_path(comm, {"session_path": current_session})
    return message


def _display_conversations(conversations) -> None:
    for i, (question, reply) in enumerate(conversations):
        if question:
            print(f"Q: {question}")
        print(f"A: {reply}")
        if i < len(conversations) - 1:
            print("---")


__all__ = ["consume_pending"]
