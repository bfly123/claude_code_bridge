from __future__ import annotations


def handle_ask(context, command, out, services) -> int:
    summary = services.submit_ask(context, command)
    if not command.wait:
        services.write_lines(out, services.render_ask(summary))
        return 0
    if len(summary.jobs) != 1:
        raise RuntimeError('ccb ask --wait requires exactly one accepted job')
    terminal = services.watch_ask_job(
        context,
        summary.jobs[0]['job_id'],
        out,
        timeout=command.timeout_s,
        emit_output=command.output_path is None,
    )
    reply = terminal.reply or ''
    if command.output_path is not None:
        services.write_ask_output(command.output_path, reply)
    return services.exit_code_for_ask_status(terminal.status, reply=reply)


def handle_ask_wait(context, command, out, services) -> int:
    terminal = services.watch_ask_job(
        context,
        command.job_id,
        out,
        timeout=command.timeout_s,
        emit_output=True,
    )
    return services.exit_code_for_ask_status(terminal.status, reply=terminal.reply or '')


__all__ = ['handle_ask', 'handle_ask_wait']
