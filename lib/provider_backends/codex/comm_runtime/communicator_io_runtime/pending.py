from __future__ import annotations

from ui_text import t

from .common import remember_log_hint


def consume_pending(comm, *, display: bool = True, n: int = 1):
    remember_log_hint(comm, {"log_path": comm.log_reader.current_log_path()})

    if n > 1:
        conversations = comm.log_reader.latest_conversations(n)
        if not conversations:
            if display:
                print(t("no_reply_available", provider="Codex"))
            return None
        if display:
            _display_conversations(conversations)
        return conversations

    message = comm.log_reader.latest_message()
    if message:
        remember_log_hint(comm, {"log_path": comm.log_reader.current_log_path()})
    if not message:
        if display:
            print(t("no_reply_available", provider="Codex"))
        return None
    if display:
        print(message)
    return message


def _display_conversations(conversations) -> None:
    for i, (question, reply) in enumerate(conversations):
        if question:
            print(f"Q: {question}")
        print(f"A: {reply}")
        if i < len(conversations) - 1:
            print("---")


__all__ = ["consume_pending"]
