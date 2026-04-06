from __future__ import annotations


def handle_config_validate(context, command, out, services) -> int:
    del command
    summary = services.validate_config_context(context)
    services.write_lines(out, services.render_config_validate(summary))
    return 0


def handle_start(context, command, out, services) -> int:
    summary = services.start_agents(context, command)
    if services.should_auto_open_after_start(command, out=out):
        open_summary = services.open_project(context, services.ParsedOpenCommand(project=command.project))
        services.write_lines(out, services.render_open(open_summary))
        return 0
    services.write_lines(out, services.render_start(summary))
    return 0


__all__ = ['handle_config_validate', 'handle_start']
