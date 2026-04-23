from __future__ import annotations

from ccbd.handlers.attach import build_attach_handler


def test_build_attach_handler_forwards_runtime_binding_fields() -> None:
    captured = {}

    class _RuntimeService:
        def attach(self, **kwargs):
            captured.update(kwargs)

            class _Runtime:
                def to_record(self):
                    return {'ok': True, 'slot_key': kwargs.get('slot_key')}

            return _Runtime()

    handler = build_attach_handler(_RuntimeService())
    payload = {
        'agent_name': 'agent1',
        'workspace_path': '/tmp/workspace',
        'backend_type': 'pane-backed',
        'tmux_socket_path': '/tmp/project.sock',
        'slot_key': 'agent-slot',
        'window_id': '@7',
        'workspace_epoch': 9,
        'job_id': 'job-object-1',
        'job_owner_pid': 321,
    }

    result = handler(payload)

    assert result == {'ok': True, 'slot_key': 'agent-slot'}
    assert captured['tmux_socket_path'] == '/tmp/project.sock'
    assert captured['slot_key'] == 'agent-slot'
    assert captured['window_id'] == '@7'
    assert captured['workspace_epoch'] == 9
    assert captured['job_id'] == 'job-object-1'
    assert captured['job_owner_pid'] == 321
