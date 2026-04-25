from __future__ import annotations

from ccbd.start_runtime.layout import cmd_bootstrap_command


def test_cmd_bootstrap_command_runs_via_posix_shell_and_prefers_user_shell() -> None:
    command = cmd_bootstrap_command()

    assert command.startswith("exec sh -lc ")
    assert command.index('if [ -n "${SHELL:-}" ]; then exec "$SHELL" -l; fi;') < command.index('if command -v bash >/dev/null 2>&1; then exec bash -l; fi;')
    assert 'if [ -n "${SHELL:-}" ]; then exec "$SHELL" -l; fi;' in command
    assert "if command -v bash >/dev/null 2>&1; then exec bash -l; fi;" in command
    assert command.endswith("exec sh'")
