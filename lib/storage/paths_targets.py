from __future__ import annotations

from ccbd.api_models import TargetKind

from .path_helpers import normalized_segment, target_segment


class TargetPathMixin:
    def target_dir(self, target_kind: TargetKind | str, target_name: str):
        segment = target_segment(target_kind, target_name)
        if TargetKind(target_kind) is TargetKind.AGENT:
            return self.agent_dir(segment)
        return self.ccbd_dir / 'targets' / segment

    def target_jobs_path(self, target_kind: TargetKind | str, target_name: str):
        return self.target_dir(target_kind, target_name) / 'jobs.jsonl'

    def target_events_path(self, target_kind: TargetKind | str, target_name: str):
        return self.target_dir(target_kind, target_name) / 'events.jsonl'

    def snapshot_path(self, job_id: str):
        return self.ccbd_snapshots_dir / f'{job_id}.json'

    def cursor_path(self, job_id: str):
        return self.ccbd_cursors_dir / f'{job_id}.json'

    def execution_state_path(self, job_id: str):
        return self.ccbd_executions_dir / f'{job_id}.json'

    def heartbeat_subject_dir(self, subject_kind: str):
        return self.ccbd_heartbeats_dir / normalized_segment(
            subject_kind,
            label='subject_kind',
        )

    def heartbeat_subject_path(self, subject_kind: str, subject_id: str):
        normalized_id = normalized_segment(subject_id, label='subject_id')
        return self.heartbeat_subject_dir(subject_kind) / f'{normalized_id}.json'

    def provider_health_path(self, job_id: str):
        normalized_job_id = str(job_id or '').strip()
        if not normalized_job_id:
            raise ValueError('job_id cannot be empty')
        return self.ccbd_provider_health_dir / f'{normalized_job_id}.jsonl'

    def support_bundle_path(self, bundle_id: str):
        normalized_bundle = normalized_segment(bundle_id, label='bundle_id')
        return self.ccbd_support_dir / f'{normalized_bundle}.tar.gz'


__all__ = ['TargetPathMixin']
