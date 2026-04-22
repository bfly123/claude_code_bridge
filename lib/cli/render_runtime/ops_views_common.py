from __future__ import annotations


def binding_line(agent) -> str:
    return (
        f'binding: status={agent["binding_status"]} runtime={agent["runtime_ref"]} session={agent["session_ref"]} '
        f'session_file={agent.get("session_file")} session_id={agent.get("session_id")} '
        f'source={agent.get("binding_source")} workspace={agent["workspace_path"]} terminal={agent.get("terminal")} '
        f'runtime_pid={agent.get("runtime_pid")} runtime_root={agent.get("runtime_root")} '
        f'job={agent.get("job_id")} job_owner={agent.get("job_owner_pid")} '
        f'socket={agent.get("tmux_socket_name")} socket_path={agent.get("tmux_socket_path")} '
        f'pane={agent.get("pane_id")} active_pane={agent.get("active_pane_id")} '
        f'pane_state={agent.get("pane_state")} marker={agent.get("pane_title_marker")}'
    )


__all__ = ['binding_line']
