from __future__ import annotations

from provider_core.runtime_specs import CODEX_CLIENT_SPEC, CODEX_RUNTIME_SPEC, provider_env_name, provider_marker_prefix


def test_runtime_specs_use_provider_native_names() -> None:
    assert CODEX_RUNTIME_SPEC.provider_key == "codex"
    assert CODEX_RUNTIME_SPEC.service_name == "codex"
    assert CODEX_RUNTIME_SPEC.state_file_name == "codex-runtime.json"
    assert CODEX_RUNTIME_SPEC.log_file_name == "codex-runtime.log"
    assert CODEX_RUNTIME_SPEC.idle_timeout_env == "CCB_CODEX_RUNTIME_IDLE_TIMEOUT_S"
    assert CODEX_RUNTIME_SPEC.lock_name == "codex-runtime"

    assert CODEX_CLIENT_SPEC.provider_key == "codex"
    assert CODEX_CLIENT_SPEC.enabled_env == "CCB_CODEX"
    assert CODEX_CLIENT_SPEC.autostart_env == "CCB_CODEX_AUTOSTART"
    assert CODEX_CLIENT_SPEC.state_file_env == "CCB_CODEX_STATE_FILE"
    assert CODEX_CLIENT_SPEC.session_filename == ".codex-session"
    assert provider_env_name("claude", "PANE_CHECK_INTERVAL") == "CCB_CLAUDE_PANE_CHECK_INTERVAL"
    assert provider_env_name("codebuddy", "REBIND_TAIL_BYTES") == "CCB_CODEBUDDY_REBIND_TAIL_BYTES"
    assert provider_marker_prefix("opencode") == "opencode"
