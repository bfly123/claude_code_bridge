from __future__ import annotations

from provider_backends.pane_log_support import PaneLogCommunicatorBase, PaneLogReaderBase


class CopilotLogReader(PaneLogReaderBase):
    poll_env_var = 'COPILOT_POLL_INTERVAL'


class CopilotCommunicator(PaneLogCommunicatorBase):
    provider_key = 'copilot'
    provider_label = 'Copilot'
    session_filename = '.copilot-session'
    sync_timeout_env = 'COPILOT_SYNC_TIMEOUT'
    missing_session_message = (
        "❌ No active Copilot session found. "
        "Run 'ccb copilot' (or add copilot to ccb.config) first"
    )
    unhealthy_message = (
        "❌ Session unhealthy: {status}\n"
        "Hint: run ccb copilot (or add copilot to ccb.config) to start a new session"
    )
    ping_ok_template = '✅ Copilot connection OK ({status})'
    ping_error_template = '❌ Copilot connection error: {status}'
    reader_cls = CopilotLogReader


__all__ = ['CopilotCommunicator', 'CopilotLogReader']
