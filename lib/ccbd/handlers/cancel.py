from __future__ import annotations


def build_cancel_handler(dispatcher):
    def handle(payload: dict) -> dict:
        job_id = str(payload.get('job_id') or '').strip()
        if not job_id:
            raise ValueError('cancel requires job_id')
        return dispatcher.cancel(job_id).to_record()

    return handle
