from __future__ import annotations


def write_registry_log(line: str) -> None:
    try:
        from ccbd.runtime import log_path, write_log
        from provider_core.runtime_specs import CLAUDE_RUNTIME_SPEC

        write_log(log_path(CLAUDE_RUNTIME_SPEC.log_file_name), line)
    except Exception:
        pass


__all__ = ["write_registry_log"]
