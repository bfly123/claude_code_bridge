from __future__ import annotations

from provider_backends.pane_log_support import PaneLogCommunicatorBase, PaneLogReaderBase


class CodebuddyLogReader(PaneLogReaderBase):
    poll_env_var = 'CODEBUDDY_POLL_INTERVAL'


class CodebuddyCommunicator(PaneLogCommunicatorBase):
    provider_key = 'codebuddy'
    provider_label = 'CodeBuddy'
    session_filename = '.codebuddy-session'
    sync_timeout_env = 'CODEBUDDY_SYNC_TIMEOUT'
    missing_session_message = (
        "No active CodeBuddy session found. "
        "Run 'ccb codebuddy' (or add codebuddy to ccb.config) first"
    )
    unhealthy_message = (
        "Session unhealthy: {status}\n"
        "Hint: run ccb codebuddy (or add codebuddy to ccb.config) to start a new session"
    )
    ping_ok_template = 'CodeBuddy connection OK ({status})'
    ping_error_template = 'CodeBuddy connection error: {status}'
    reader_cls = CodebuddyLogReader


__all__ = ['CodebuddyCommunicator', 'CodebuddyLogReader']
