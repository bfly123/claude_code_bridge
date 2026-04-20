from __future__ import annotations

import subprocess

from terminal_runtime.tmux_respawn_service import TmuxRespawnService


def _cp(*, stdout: str = '', returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=['tmux'], returncode=returncode, stdout=stdout, stderr='')


def test_tmux_respawn_service_builds_respawn_and_remain_calls() -> None:
    calls: list[list[str]] = []
    service = TmuxRespawnService(
        tmux_run_fn=lambda args, **kwargs: calls.append(args) or (
            _cp(stdout='/bin/bash\n') if args == ['show-option', '-gqv', 'default-shell'] else _cp()
        ),
        ensure_pane_log_fn=lambda pane_id: None,
        normalize_start_dir_fn=lambda cwd: cwd,
        append_stderr_redirection_fn=lambda cmd, path: (cmd + ' 2>>/tmp/err.log', path),
        resolve_shell_fn=lambda **kwargs: '/bin/bash',
        resolve_shell_flags_fn=lambda **kwargs: ['-lc'],
        build_shell_command_fn=lambda **kwargs: '/bin/bash -lc "echo hi"',
        build_respawn_tmux_args_fn=lambda **kwargs: ['respawn-pane', '-k', '-t', kwargs['pane_id'], '/bin/bash -lc "echo hi"'],
        default_shell_fn=lambda: ('bash', '-c'),
        env={'SHELL': '/bin/bash'},
    )

    service.respawn_pane('%9', cmd='echo hi', cwd='/tmp/demo', stderr_log_path='/tmp/err.log', remain_on_exit=True)

    assert calls[0] == ['show-option', '-gqv', 'default-shell']
    assert ['set-option', '-p', '-t', '%9', 'remain-on-exit', 'on'] in calls
    assert ['respawn-pane', '-k', '-t', '%9', '/bin/bash -lc "echo hi"'] in calls


def test_tmux_respawn_service_requires_pane_and_cmd() -> None:
    service = TmuxRespawnService(
        tmux_run_fn=lambda args, **kwargs: _cp(),
        ensure_pane_log_fn=lambda pane_id: None,
        normalize_start_dir_fn=lambda cwd: cwd,
        append_stderr_redirection_fn=lambda cmd, path: (cmd, path),
        resolve_shell_fn=lambda **kwargs: '/bin/bash',
        resolve_shell_flags_fn=lambda **kwargs: ['-lc'],
        build_shell_command_fn=lambda **kwargs: 'x',
        build_respawn_tmux_args_fn=lambda **kwargs: ['respawn-pane'],
        default_shell_fn=lambda: ('bash', '-c'),
        env={},
    )

    try:
        service.respawn_pane('', cmd='echo hi')
        assert False
    except ValueError:
        pass

    try:
        service.respawn_pane('%1', cmd='  ')
        assert False
    except ValueError:
        pass
