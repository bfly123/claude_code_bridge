from .decoding import decode_stdin_bytes
from .stdio import read_stdin_text, setup_windows_encoding

__all__ = [
    "decode_stdin_bytes",
    "read_stdin_text",
    "setup_windows_encoding",
]
