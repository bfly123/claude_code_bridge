from __future__ import annotations

from ccbd.models import CcbdShutdownReport, cleanup_summaries_from_objects

def build_stop_all_handler(app):
    def handle(payload: dict) -> dict:
        forced = bool(payload.get('force'))
        summary = app.runtime_supervisor.stop_all(force=forced)
        app.request_shutdown()
        inspection = app.ownership_guard.inspect()
        prior = app.shutdown_report_store.load()
        prior_actions = tuple(prior.actions_taken) if prior is not None else ()
        prior_snapshots = tuple(prior.runtime_snapshots) if prior is not None else ()
        app.shutdown_report_store.save(
            CcbdShutdownReport(
                project_id=app.project_id,
                generated_at=app.clock(),
                trigger='stop_all',
                status='ok',
                forced=forced,
                stopped_agents=tuple(summary.stopped_agents),
                daemon_generation=inspection.generation,
                reason='stop_all',
                inspection_after=inspection.to_record(),
                actions_taken=prior_actions + ('request_shutdown',),
                cleanup_summaries=cleanup_summaries_from_objects(summary.cleanup_summaries),
                runtime_snapshots=prior_snapshots,
                failure_reason=None,
            )
        )
        return summary.to_record()

    return handle
