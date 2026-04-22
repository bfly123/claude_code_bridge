from __future__ import annotations


def build_attach_handler(runtime_service):
    def handle(payload: dict) -> dict:
        runtime = runtime_service.attach(
            agent_name=payload['agent_name'],
            workspace_path=payload['workspace_path'],
            backend_type=payload['backend_type'],
            pid=payload.get('pid'),
            runtime_ref=payload.get('runtime_ref'),
            session_ref=payload.get('session_ref'),
            health=payload.get('health'),
            provider=payload.get('provider'),
            runtime_root=payload.get('runtime_root'),
            runtime_pid=payload.get('runtime_pid'),
            job_id=payload.get('job_id'),
            job_owner_pid=payload.get('job_owner_pid'),
            terminal_backend=payload.get('terminal_backend'),
            pane_id=payload.get('pane_id'),
            active_pane_id=payload.get('active_pane_id'),
            pane_title_marker=payload.get('pane_title_marker'),
            pane_state=payload.get('pane_state'),
            tmux_socket_name=payload.get('tmux_socket_name'),
            tmux_socket_path=payload.get('tmux_socket_path'),
            session_file=payload.get('session_file'),
            session_id=payload.get('session_id'),
            slot_key=payload.get('slot_key'),
            window_id=payload.get('window_id'),
            workspace_epoch=payload.get('workspace_epoch'),
            lifecycle_state=payload.get('lifecycle_state'),
            managed_by=payload.get('managed_by'),
            binding_source=payload.get('binding_source'),
        )
        return runtime.to_record()

    return handle
