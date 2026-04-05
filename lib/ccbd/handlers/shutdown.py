from __future__ import annotations

from ccbd.models import CcbdShutdownReport

def build_shutdown_handler(app):
    def handle(payload: dict) -> dict:
        del payload
        app.request_shutdown()
        lease = app.mount_manager.load_state()
        inspection = app.ownership_guard.inspect()
        app.shutdown_report_store.save(
            CcbdShutdownReport(
                project_id=app.project_id,
                generated_at=app.clock(),
                trigger='shutdown',
                status='ok',
                forced=False,
                stopped_agents=(),
                daemon_generation=inspection.generation if inspection.generation is not None else (lease.generation if lease else app.lease.generation if app.lease else None),
                reason='shutdown',
                inspection_after=inspection.to_record(),
                actions_taken=('request_shutdown',),
                cleanup_summaries=(),
                runtime_snapshots=(),
                failure_reason=None,
            )
        )
        return {
            'project_id': app.project_id,
            'state': 'unmounted',
            'generation': lease.generation if lease else app.lease.generation if app.lease else None,
        }

    return handle
