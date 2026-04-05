from __future__ import annotations

import io
from pathlib import Path

from ccbd.api_models import DeliveryScope, JobRecord, JobStatus, MessageEnvelope
from cli.phase2 import maybe_handle_phase2
from fault_injection import ConsumedFault, FaultInjectionService
from project.resolver import bootstrap_project
from provider_execution.registry import build_default_execution_registry
from provider_execution.service import ExecutionService
from storage.paths import PathLayout


def _job(*, task_id: str, provider: str = 'fake') -> JobRecord:
    return JobRecord(
        job_id='job_drill',
        submission_id=None,
        agent_name='agent1',
        provider=provider,
        request=MessageEnvelope(
            project_id='proj',
            to_agent='agent1',
            from_actor='user',
            body='run drill',
            task_id=task_id,
            reply_to=None,
            message_type='ask',
            delivery_scope=DeliveryScope.SINGLE,
        ),
        status=JobStatus.RUNNING,
        terminal_decision=None,
        cancel_requested_at=None,
        created_at='2026-03-31T00:00:00Z',
        updated_at='2026-03-31T00:00:00Z',
    )


def test_fault_injection_service_arm_consume_and_clear(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-fault-service'
    project_root.mkdir()
    bootstrap_project(project_root)
    layout = PathLayout(project_root)
    ticks = iter(
        [
            '2026-03-31T00:00:00Z',
            '2026-03-31T00:00:01Z',
            '2026-03-31T00:00:02Z',
        ]
    )
    service = FaultInjectionService(layout, clock=lambda: next(ticks))

    rule = service.arm_rule(agent_name='agent1', task_id='drill-1', reason='api_error', count=2)
    assert rule.agent_name == 'agent1'
    assert rule.remaining_count == 2
    assert len(service.list_rules()) == 1

    first = service.consume_for_job(_job(task_id='drill-1'), now='2026-03-31T00:00:10Z')
    assert first is not None
    assert first.rule_id == rule.rule_id
    assert first.remaining_count == 1
    assert service.list_rules()[0].remaining_count == 1

    second = service.consume_for_job(_job(task_id='drill-1'), now='2026-03-31T00:00:11Z')
    assert second is not None
    assert second.remaining_count == 0
    assert service.list_rules() == ()

    cleared = service.clear_rule('all')
    assert cleared == ()


class _InjectedOnlyFaults:
    def __init__(self) -> None:
        self.calls = 0

    def consume_for_job(self, job: JobRecord, *, now: str | None = None):
        del now
        self.calls += 1
        return ConsumedFault(
            rule_id='flt_demo',
            agent_name=job.agent_name,
            task_id=str(job.request.task_id),
            reason='api_error',
            error_message='fault injection drill',
            remaining_count=0,
            injected_at='2026-03-31T00:00:00Z',
        )

    def build_terminal_replay(self, job: JobRecord, fault: ConsumedFault):
        return FaultInjectionService.build_terminal_replay(job, fault)


def test_execution_service_short_circuits_provider_with_fault_injection() -> None:
    service = ExecutionService(
        build_default_execution_registry(),
        clock=lambda: '2026-03-31T00:00:00Z',
        fault_injection=_InjectedOnlyFaults(),
    )
    service.start(_job(task_id='drill-2'))

    updates = service.poll()
    assert len(updates) == 1
    update = updates[0]
    assert update.job_id == 'job_drill'
    assert len(update.items) == 1
    assert update.items[0].kind.value == 'error'
    assert update.items[0].payload['error_type'] == 'fault_injection'
    assert update.decision is not None
    assert update.decision.status.value == 'failed'
    assert update.decision.reason == 'api_error'
    assert update.decision.diagnostics['fault_rule_id'] == 'flt_demo'


def _run_phase2_local(args: list[str], *, cwd: Path) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = maybe_handle_phase2(args, cwd=cwd, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_phase2_fault_commands_manage_rules(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-fault-cli'
    project_root.mkdir()
    bootstrap_project(project_root)

    code, stdout, stderr = _run_phase2_local(
        ['fault', 'arm', 'agent1', '--task-id', 'drill-3', '--reason', 'api_error', '--count', '2'],
        cwd=project_root,
    )
    assert code == 0
    assert stderr == ''
    assert 'fault_status: armed' in stdout
    assert 'task_id: drill-3' in stdout

    code, stdout, stderr = _run_phase2_local(['fault', 'list'], cwd=project_root)
    assert code == 0
    assert stderr == ''
    assert 'fault_status: ok' in stdout
    assert 'rule_count: 1' in stdout
    assert 'task=drill-3' in stdout

    code, stdout, stderr = _run_phase2_local(['fault', 'clear', 'all'], cwd=project_root)
    assert code == 0
    assert stderr == ''
    assert 'fault_status: cleared' in stdout
    assert 'cleared_count: 1' in stdout
