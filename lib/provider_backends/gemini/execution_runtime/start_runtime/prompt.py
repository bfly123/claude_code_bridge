from __future__ import annotations

from pathlib import Path

from provider_execution.common import send_prompt_to_runtime_target


def send_prompt(backend: object, pane_id: str, text: str) -> None:
    send_prompt_to_runtime_target(backend, pane_id, text)


def write_request_file(*, session, req_id: str, message: str) -> Path:
    work_dir_root = (
        str(getattr(session, 'work_dir', '') or '')
        or str(getattr(session, 'runtime_dir', '') or '')
        or '.'
    )
    work_dir = Path(work_dir_root).expanduser()
    request_dir = work_dir / '.ccb-requests'
    request_dir.mkdir(parents=True, exist_ok=True)
    request_path = request_dir / f'{req_id}.md'
    request_path.write_text(str(message or ''), encoding='utf-8')
    return request_path


def build_exact_prompt(*, session, req_id: str, message: str) -> str:
    request_path = write_request_file(session=session, req_id=req_id, message=message)
    return f'CCB_REQ_ID: {req_id} Execute the full request from @{request_path} and reply directly.'


__all__ = ['build_exact_prompt', 'send_prompt', 'write_request_file']
