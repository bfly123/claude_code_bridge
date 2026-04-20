from __future__ import annotations


def _resolve_requested_job(dispatcher, payload: dict):
    job_id = payload.get('job_id')
    agent_name = payload.get('agent_name')
    if job_id:
        return dispatcher.get(str(job_id))
    if agent_name:
        return dispatcher.latest_for_agent(str(agent_name))
    raise ValueError('get requires job_id or agent_name')


def _build_result_payload(job, snapshot) -> dict:
    latest_decision = snapshot.latest_decision if snapshot is not None else None
    return {
        'job_id': job.job_id,
        'agent_name': job.agent_name,
        'target_kind': job.target_kind.value,
        'target_name': job.target_name,
        'provider_instance': job.provider_instance,
        'provider': job.provider,
        'status': job.status.value,
        'job': job.to_record(),
        'snapshot': snapshot.to_record() if snapshot else None,
        'reply': latest_decision.reply if latest_decision else '',
        'completion_reason': latest_decision.reason if latest_decision else None,
        'completion_confidence': latest_decision.confidence.value if latest_decision and latest_decision.confidence else None,
        'updated_at': snapshot.updated_at if snapshot else job.updated_at,
    }


def _append_generation(result: dict, health_monitor) -> dict:
    if health_monitor is None:
        return result
    inspection = health_monitor.daemon_health()
    result = dict(result)
    result['generation'] = inspection.generation
    return result


def build_get_handler(dispatcher, *, health_monitor=None):
    def handle(payload: dict) -> dict:
        job = _resolve_requested_job(dispatcher, payload)
        if job is None:
            raise ValueError('job not found')
        snapshot = dispatcher.get_snapshot(job.job_id)
        result = _build_result_payload(job, snapshot)
        return _append_generation(result, health_monitor)

    return handle
