#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ROLE_SOURCE_ROOT = (
    REPO_ROOT / 'docs' / 'plantree' / 'plans' / 'agentic-loop-workflow' / 'drafts'
)
ROLE_IDS = (
    'agentroles.ccb_frontdesk',
    'agentroles.ccb_planner',
    'agentroles.ccb_task_detailer',
    'agentroles.ccb_orchestrator',
    'agentroles.ccb_round_reviewer',
    'agentroles.coder',
    'agentroles.code_reviewer',
)
PLAN_SLUG = 'g5-fake-fullflow'
TASK_ID = 'g5-multi-workgroup-task'
TERMINAL_JOB_STATUSES = {'completed', 'failed', 'cancelled', 'timed_out'}
TERMINAL_TASK_STATUSES = {'done', 'partial', 'blocked', 'replan_required'}
TERMINAL_SCHEDULER_STATUSES = {'pass', 'partial', 'blocked', 'replan_required'}
SCENARIO_SCHEMA = 'ccb.g5.source_fake_runtime_scenario.v1'
REPORT_SCHEMA = 'ccb.g5.source_fake_runtime_report.v1'
SCENARIO_EXPECTATIONS = {
    'pass': {
        'classification': 'pass',
        'task_status': 'done',
        'round_result': 'pass',
        'round_source': 'round_reviewer_reply',
    },
    'reviewer_rework_pass': {
        'classification': 'pass',
        'task_status': 'done',
        'round_result': 'pass',
        'round_source': 'round_reviewer_reply',
    },
    'reviewer_rework_exhausted_blocked': {
        'classification': 'valid_non_success',
        'task_status': 'blocked',
        'round_result': 'blocked',
        'round_source': 'required_node_failure',
    },
    'worker_failure_partial': {
        'classification': 'valid_non_success',
        'task_status': 'partial',
        'round_result': 'partial',
        'round_source': 'required_node_failure',
    },
    'all_workers_failed_blocked': {
        'classification': 'valid_non_success',
        'task_status': 'blocked',
        'round_result': 'blocked',
        'round_source': 'required_node_failure',
    },
    'reviewer_provider_failure': {
        'classification': 'valid_non_success',
        'task_status': 'partial',
        'round_result': 'partial',
        'round_source': 'required_node_failure',
    },
    'round_reviewer_blocked': {
        'classification': 'valid_non_success',
        'task_status': 'blocked',
        'round_result': 'blocked',
        'round_source': 'round_reviewer_reply',
    },
    'integration_verification_failure': {
        'classification': 'valid_non_success',
        'task_status': 'replan_required',
        'round_result': 'replan_required',
        'round_source': 'integration_verification_failed',
    },
    'root_verification_failure': {
        'classification': 'valid_non_success',
        'task_status': 'replan_required',
        'round_result': 'replan_required',
        'round_source': 'root_verification_failed',
    },
    'restart_replay_pass': {
        'classification': 'pass',
        'task_status': 'done',
        'round_result': 'pass',
        'round_source': 'round_reviewer_reply',
    },
}


class SmokeFailure(RuntimeError):
    pass


def build_v3_config() -> str:
    return '''version = 3

[workflow]
mode = "agentic-loop"
profile = "agentic_loop_v1"
entry_role = "frontdesk"

[workflow.defaults]
provider = "fake"

[workflow.defaults.resident]
workspace_mode = "inplace"

[workflow.defaults.dynamic]
workspace_mode = "inplace"
reuse = "always_new"

[workflow.runtime]
max_workgroups = 4
max_parallel_workgroups = 4
max_active_dynamic_agents = 9
max_node_rework_rounds = 1
execution_window_max_panes = 6
multi_workgroup_workspace = "git-worktree-required"
integration_policy = "controller-owned"
default_lifetime = "current_activation"
name_template = "loop-{loop_id}-{node_id}-{profile}"
release_policy = "auto"
window_policy = "auto"

[workflow.resident.frontdesk]
role = "agentroles.ccb_frontdesk"

[workflow.resident.planner]
role = "agentroles.ccb_planner"

[workflow.dynamic.task_detailer]
role = "agentroles.ccb_task_detailer"
max_instances = 1

[workflow.dynamic.orchestrator]
role = "agentroles.ccb_orchestrator"
max_instances = 1

[workflow.dynamic.coder]
role = "agentroles.coder"
provider = "fake"
workspace_mode = "git-worktree"
max_instances = 4
legacy_aliases = ["worker"]

[workflow.dynamic.code_reviewer]
role = "agentroles.code_reviewer"
provider = "fake"
workspace_mode = "git-worktree"
max_instances = 4

[workflow.dynamic.ccb_round_reviewer]
role = "agentroles.ccb_round_reviewer"
provider = "fake"
max_instances = 1
'''


def run_smoke(
    *,
    project_root: Path,
    count: int,
    shape: str,
    ccb_test: Path,
    scenario: str = 'pass',
    keep_running: bool = False,
    command_timeout_s: int = 240,
) -> dict[str, Any]:
    project_root = project_root.expanduser().resolve(strict=False)
    test_root = project_root.parent
    ccb_test = ccb_test.expanduser().resolve(strict=True)
    _validate_matrix(count=count, shape=shape, scenario=scenario)
    if project_root.exists():
        raise SmokeFailure(f'fresh project root already exists: {project_root}')
    project_root.mkdir(parents=True)
    role_store = project_root / 'roles'
    source_home = project_root / '.source-home'
    source_home.mkdir()
    logs_dir = project_root / '.ccb' / 'evidence' / 'g5-fake-fullflow' / 'logs'
    logs_dir.mkdir(parents=True)
    command_log: list[dict[str, Any]] = []
    env = _smoke_env(
        test_root=test_root,
        project_root=project_root,
        role_store=role_store,
        source_home=source_home,
    )
    report_path = project_root / '.ccb' / 'evidence' / 'g5-fake-fullflow' / 'report.json'
    cleanup_result: dict[str, Any] | None = None
    try:
        _prepare_repository(project_root)
        _write_config_and_plan(project_root)
        for role_id in ROLE_IDS:
            _run_logged(
                command_log,
                f'role_install_{role_id.rsplit(".", 1)[-1]}',
                _role_install_command(ccb_test, role_id),
                cwd=test_root,
                env=env,
                logs_dir=logs_dir,
                timeout_s=command_timeout_s,
            )
        config_validate = _run_logged(
            command_log,
            'config_validate',
            [str(ccb_test), '--project', str(project_root), 'config', 'validate', '--json'],
            cwd=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=command_timeout_s,
        )
        start = _run_logged(
            command_log,
            'start',
            [str(ccb_test), '--project', str(project_root)],
            cwd=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=command_timeout_s,
        )
        task_create = _run_logged(
            command_log,
            'task_create',
            [
                str(ccb_test), '--project', str(project_root), 'plan', 'task-create',
                '--plan', PLAN_SLUG, '--title', 'G5 fake multi-workgroup full-flow task',
                '--task-id', TASK_ID, '--json',
            ],
            cwd=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=command_timeout_s,
        )
        artifacts = _write_task_inputs(
            project_root,
            count=count,
            shape=shape,
            scenario=scenario,
        )
        artifact_results = {}
        for kind in ('task_packet', 'execution_contract'):
            artifact_results[kind] = _run_logged(
                command_log,
                f'artifact_{kind}',
                [
                    str(ccb_test), '--project', str(project_root), 'plan', 'task-artifact',
                    '--task', TASK_ID, '--kind', kind, '--file', str(artifacts[kind]), '--json',
                ],
                cwd=test_root,
                env=env,
                logs_dir=logs_dir,
                timeout_s=command_timeout_s,
            )
        _git_commit_authority(project_root)
        root_preflight = _root_authority(project_root)
        ready = _run_logged(
            command_log,
            'ready_for_orchestration',
            [
                str(ccb_test), '--project', str(project_root), 'plan', 'task-status',
                '--task', TASK_ID, '--status', 'ready_for_orchestration',
                '--next-owner', 'orchestrator', '--activation-reason', 'g5_fake_fullflow', '--json',
            ],
            cwd=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=command_timeout_s,
        )
        if scenario == 'restart_replay_pass':
            runner_results, restart_evidence = _run_restart_replay(
                command_log,
                ccb_test=ccb_test,
                project_root=project_root,
                test_root=test_root,
                env=env,
                logs_dir=logs_dir,
                timeout_s=command_timeout_s,
            )
        else:
            runner_results = _run_until_terminal(
                command_log,
                ccb_test=ccb_test,
                project_root=project_root,
                test_root=test_root,
                env=env,
                logs_dir=logs_dir,
                timeout_s=command_timeout_s,
            )
            restart_evidence = None
        task_show = _task_show(
            command_log,
            ccb_test=ccb_test,
            project_root=project_root,
            test_root=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=command_timeout_s,
            label='task_show_final',
        )
        ps_result = _run_logged(
            command_log,
            'ps_final',
            [str(ccb_test), '--project', str(project_root), 'ps'],
            cwd=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=command_timeout_s,
        )
        report = _build_report(
            project_root=project_root,
            role_store=role_store,
            count=count,
            shape=shape,
            scenario=scenario,
            root_preflight=root_preflight,
            restart_evidence=restart_evidence,
            config_validate=_json_object(config_validate['stdout']),
            start_stdout=start['stdout'],
            task_create=_json_object(task_create['stdout']),
            artifact_results={key: _json_object(value['stdout']) for key, value in artifact_results.items()},
            ready=_json_object(ready['stdout']),
            runner_results=runner_results,
            task_show=task_show,
            ps_text=ps_result['stdout'],
            command_log=command_log,
        )
        if not keep_running:
            cleanup_result = _run_logged(
                command_log,
                'external_cleanup',
                [str(ccb_test), '--project', str(project_root), 'kill', '-f'],
                cwd=test_root,
                env=env,
                logs_dir=logs_dir,
                timeout_s=command_timeout_s,
                allow_failure=True,
            )
            report['external_cleanup'] = _compact_command(cleanup_result)
            report['post_cleanup'] = _post_cleanup_evidence(project_root)
            report['checks']['external_cleanup_succeeded'] = cleanup_result['returncode'] == 0
            report['checks']['process_residue_absent'] = not report['post_cleanup']['owned_processes']
            report['checks']['socket_residue_absent'] = not report['post_cleanup']['connectable_sockets']
            report['checks']['socket_filesystem_entries_absent'] = not report['post_cleanup']['socket_entries']
            report['checks']['child_worktree_residue_absent'] = not report['post_cleanup']['child_worktrees']
            report['command_log'] = [_compact_command(item) for item in command_log]
        else:
            report['external_cleanup'] = None
            report['post_cleanup'] = None
        report['status'] = 'pass' if all(report['checks'].values()) else 'failed'
        _write_json(report_path, report)
        _require_report_pass(report)
        return report
    except Exception as exc:
        failure = {
            'schema': REPORT_SCHEMA,
            'status': 'failed',
            'project_root': str(project_root),
            'count': count,
            'shape': shape,
            'scenario': scenario,
            'error': str(exc),
            'command_log': [_compact_command(item) for item in command_log],
        }
        preserved = _read_json(report_path)
        if preserved.get('schema') != REPORT_SCHEMA or 'checks' not in preserved:
            _write_json(report_path, failure)
        if not keep_running and cleanup_result is None:
            try:
                cleanup_result = _run_logged(
                    command_log,
                    'failure_cleanup',
                    [str(ccb_test), '--project', str(project_root), 'kill', '-f'],
                    cwd=test_root,
                    env=env,
                    logs_dir=logs_dir,
                    timeout_s=command_timeout_s,
                    allow_failure=True,
                )
            except Exception as cleanup_exc:
                failure['cleanup_error'] = str(cleanup_exc)
            failure['external_cleanup'] = (
                _compact_command(cleanup_result) if cleanup_result is not None else None
            )
            failure['command_log'] = [_compact_command(item) for item in command_log]
            try:
                failure['post_cleanup'] = _post_cleanup_evidence(project_root)
            except Exception as cleanup_exc:
                failure['cleanup_evidence_error'] = str(cleanup_exc)
            if preserved.get('schema') != REPORT_SCHEMA or 'checks' not in preserved:
                _write_json(report_path, failure)
        raise


def _role_install_command(ccb_test: Path, role_id: str) -> list[str]:
    source_path = ROLE_SOURCE_ROOT / role_id
    if not (source_path / 'role.toml').is_file():
        raise SmokeFailure(f'G5 role source is unavailable: {source_path}')
    return [
        str(ccb_test),
        'roles',
        'install',
        role_id,
        '--path',
        str(source_path),
        '--skip-tools',
    ]


def _build_report(
    *,
    project_root: Path,
    role_store: Path,
    count: int,
    shape: str,
    scenario: str,
    root_preflight: dict[str, Any],
    restart_evidence: dict[str, Any] | None,
    config_validate: dict[str, Any],
    start_stdout: str,
    task_create: dict[str, Any],
    artifact_results: dict[str, dict[str, Any]],
    ready: dict[str, Any],
    runner_results: list[dict[str, Any]],
    task_show: dict[str, Any],
    ps_text: str,
    command_log: list[dict[str, Any]],
) -> dict[str, Any]:
    expectation = SCENARIO_EXPECTATIONS[scenario]
    task = _task_record(task_show)
    bundle_artifact = _mapping(_mapping(task.get('artifacts')).get('orchestration_bundle'))
    bundle_path = project_root / str(bundle_artifact.get('path') or '')
    bundle = _read_json(bundle_path)
    loop_id = str(_mapping(task.get('current_loop')).get('loop_id') or '')
    if not loop_id:
        loop_id = _find_loop_id(project_root, TASK_ID)
    loop_dir = project_root / '.ccb' / 'runtime' / 'loops' / loop_id
    scheduler_state_path = loop_dir / 'workgroup_scheduler_state.json'
    round_path = loop_dir / 'round.json'
    integration_path = loop_dir / 'git-transaction.json'
    scheduler = _read_json(scheduler_state_path)
    round_record = _read_json(round_path)
    integration = _read_json(integration_path)
    jobs = _collect_jobs(project_root)
    node_records = []
    for node_id in sorted(_mapping(scheduler.get('nodes'))):
        node = _mapping(_mapping(scheduler['nodes']).get(node_id))
        integration_node = _mapping(_mapping(integration.get('nodes')).get(node_id))
        worker = _mapping(node.get('worker'))
        worker_rework = _mapping(node.get('worker_rework'))
        reviewer = _mapping(node.get('reviewer'))
        reviewer_recheck = _mapping(node.get('reviewer_recheck'))
        chain_evidence = [
            _mapping(item)
            for item in worker.get('chain_evidence') or ()
            if isinstance(item, dict)
        ]
        node_records.append(
            {
                'node_id': node_id,
                'dependencies': list(node.get('depends_on') or ()),
                'status': node.get('status'),
                'integration_status': integration_node.get('status'),
                'worker_agent': node.get('worker_agent'),
                'reviewer_agent': node.get('reviewer_agent'),
                'worker_job_id': worker.get('job_id'),
                'worker_job_status': worker.get('status'),
                'worker_rework_job_id': worker_rework.get('job_id'),
                'worker_rework_job_status': worker_rework.get('status'),
                'reviewer_job_id': reviewer.get('job_id'),
                'reviewer_job_status': reviewer.get('status'),
                'reviewer_recheck_job_id': reviewer_recheck.get('job_id'),
                'reviewer_recheck_job_status': reviewer_recheck.get('status'),
                'review_chain': chain_evidence,
                'review_chain_job_ids': [
                    str(item.get('child_job_id') or '')
                    for item in chain_evidence
                    if str(item.get('child_job_id') or '')
                ],
                'rework_count': node.get('rework_count'),
                'rework_history': node.get('rework_history'),
                'review_history': integration_node.get('reviews'),
                'terminal_failure': integration_node.get('terminal_failure'),
                'failure': node.get('failure'),
                'worktree_path': integration_node.get('worktree_path'),
                'worktree_exists_after_cleanup': Path(str(integration_node.get('worktree_path') or '')).exists(),
                'branch': integration_node.get('branch'),
                'base_commit': integration_node.get('base_commit'),
                'reviewed_commit': integration_node.get('reviewed_commit'),
                'tree_digest': integration_node.get('tree_digest'),
                'layer': integration_node.get('layer'),
                'integration_order': integration_node.get('integration_order'),
            }
        )
    round_reviewer = _mapping(scheduler.get('round_reviewer'))
    topology = _mapping(round_record.get('topology'))
    release = _mapping(round_record.get('release') or topology.get('release'))
    observed_evidence = _mapping(topology.get('observed_evidence'))
    observed_path = Path(str(observed_evidence.get('path') or ''))
    raw_observed = _read_json(observed_path)
    integration_section = _mapping(integration.get('integration'))
    root_section = _mapping(integration.get('root'))
    expected_merge_order = _expected_bundle_merge_order(bundle)
    expected_paths = [f'g5_outputs/node-{index:03d}.txt' for index in range(1, count + 1)]
    actual_paths = [path for path in expected_paths if (project_root / path).is_file()]
    selected_path = expected_paths[0]
    if scenario in {
        'worker_failure_partial',
        'reviewer_provider_failure',
        'reviewer_rework_exhausted_blocked',
        'all_workers_failed_blocked',
        'round_reviewer_blocked',
        'integration_verification_failure',
        'root_verification_failure',
    }:
        expected_root_paths = []
    else:
        expected_root_paths = expected_paths
    dynamic_lines = [
        line for line in ps_text.splitlines()
        if 'source=loop' in line or 'loop-' + loop_id in line
    ]
    orchestrator_jobs = [
        item for item in jobs.values()
        if item.get('agent_name') and 'orchestrator' in str(item.get('agent_name'))
    ]
    referenced_job_ids = []
    for item in node_records:
        if item.get('worker_job_id'):
            referenced_job_ids.append(str(item['worker_job_id']))
        referenced_job_ids.extend(str(value) for value in item['review_chain_job_ids'])
    if round_reviewer.get('job_id'):
        referenced_job_ids.append(str(round_reviewer['job_id']))
    referenced_job_evidence = {
        job_id: jobs.get(job_id, {}) for job_id in referenced_job_ids
    }
    controller_intents = _controller_submission_intents(loop_dir)
    controller_intent_ids = [
        str(item.get('intent_id') or '')
        for item in controller_intents
        if item.get('status') == 'accepted'
    ]
    expected_controller_intent_count = sum(
        1 for item in node_records if item.get('worker_job_id')
    ) + (1 if round_reviewer.get('job_id') else 0)
    runner_steps = [
        step
        for result in runner_results
        for step in result.get('steps') or ()
        if isinstance(step, dict)
    ]
    runner_steps.extend(
        result
        for result in runner_results
        if isinstance(result, dict) and result.get('scheduler_action')
    )
    initial_frontier = next(
        (
            step for step in runner_steps
            if step.get('scheduler_action') == 'submitted_ready_frontier'
        ),
        {},
    )
    expected_initial_frontier_size = count if shape == 'parallel' else count - 1
    root_after = _root_authority(project_root)
    observed_classification = _observed_classification(
        task_status=str(task.get('status') or ''),
        round_result=str(round_record.get('round_result') or ''),
    )
    rework_node = next((item for item in node_records if item['node_id'] == 'node-001'), {})
    all_referenced_jobs_terminal = all(
        str(record.get('status') or '') in TERMINAL_JOB_STATUSES
        for record in referenced_job_evidence.values()
    ) and len(referenced_job_evidence) == len(referenced_job_ids)
    failed_node_ids = _expected_failed_node_ids(scenario=scenario, count=count)
    expected_scenario_merge_order = _expected_scenario_merge_order(
        expected_merge_order,
        failed_node_ids=failed_node_ids,
    )
    failed_node_records = [
        item for item in node_records if item['node_id'] in failed_node_ids
    ]
    checks = {
        'config_v3_valid': (
            config_validate.get('config_version') == 3
            and config_validate.get('config_status') == 'valid'
        ),
        'start_succeeded': 'start_status: ok' in start_stdout,
        'task_created': bool(task_create),
        'task_artifacts_imported': all(bool(payload) for payload in artifact_results.values()),
        'ready_for_orchestration': ready.get('status') == 'ready_for_orchestration',
        'bundle_schema': bundle.get('schema') == 'ccb.loop.orchestration_bundle.v1',
        'bundle_node_count': len(bundle.get('nodes') or ()) == count,
        'bundle_capacity_digest': bool(bundle.get('capacity_digest')),
        'scheduler_terminal': scheduler.get('status') not in {
            None, 'created', 'executing', 'topology_pending', 'round_review_pending'
        },
        'task_status_matches': task.get('status') == expectation['task_status'],
        'round_result_matches': round_record.get('round_result') == expectation['round_result'],
        'round_source_matches': round_record.get('round_result_source') == expectation['round_source'],
        'classification_matches': observed_classification == expectation['classification'],
        'referenced_jobs_unique': len(referenced_job_ids) == len(set(referenced_job_ids)),
        'scheduler_job_intents_unique': all(
            controller_intent_ids.count(intent_id) == 1
            for intent_id in set(controller_intent_ids)
        ) and len(controller_intent_ids) == expected_controller_intent_count,
        'referenced_jobs_terminal': all_referenced_jobs_terminal,
        'root_paths_match_scenario': actual_paths == expected_root_paths,
        'failed_scope_absent': selected_path not in actual_paths if failed_node_ids else True,
        'nonpass_root_authority_restored': (
            root_after == root_preflight
            if expectation['classification'] == 'valid_non_success'
            else True
        ),
        'merge_order_exact': (
            list(integration_section.get('merge_order') or ())
            == expected_scenario_merge_order
        ),
        'expected_failed_nodes_complete': len(failed_node_records) == len(failed_node_ids),
        'expected_failed_nodes_quarantined': all(
            _node_failure_evidence_valid(
                item,
                loop_id=loop_id,
                expected_path=f'g5_outputs/{item["node_id"]}.txt',
            )
            for item in failed_node_records
        ),
        'reviewed_commits_present_for_integrated_nodes': all(
            bool(item['reviewed_commit'])
            for item in node_records
            if item['status'] == 'integrated'
        ),
        'rework_exactly_once': (
            int(rework_node.get('rework_count') or 0) == 1
            and len(rework_node.get('review_chain') or ()) == 2
            and [
                _mapping(item).get('decision')
                for item in rework_node.get('rework_history') or ()
            ] == ['rework_required', 'pass']
            and [_mapping(item).get('result') for item in rework_node.get('review_history') or ()]
            == ['pass']
        ) if scenario == 'reviewer_rework_pass' else (
            int(rework_node.get('rework_count') or 0) == 1
            and len(rework_node.get('review_chain') or ()) == 2
            and [
                _mapping(item).get('decision')
                for item in rework_node.get('rework_history') or ()
            ] == ['rework_required', 'rework_required']
            and not (rework_node.get('review_history') or ())
        ) if scenario == 'reviewer_rework_exhausted_blocked' else all(
            int(item.get('rework_count') or 0) == 0 for item in node_records
        ),
        'release_clean': release.get('loop_topology_status') == 'released'
        and int(release.get('retained_count') or 0) == 0
        and int(release.get('release_incomplete_count') or 0) == 0,
        'raw_observed_exists': observed_path.is_file(),
        'raw_authority_files_present': all(
            path.is_file()
            for path in (
                bundle_path,
                scheduler_state_path,
                round_path,
                integration_path,
                observed_path,
            )
        ),
        'raw_observed_no_live_agents': not _live_observed_agents(raw_observed),
        'dynamic_residue_absent': not dynamic_lines,
        'orchestrator_job_completed': any(item.get('status') == 'completed' for item in orchestrator_jobs),
        'initial_frontier_submitted_in_parallel': (
            len(initial_frontier.get('pending_job_ids') or ()) == expected_initial_frontier_size
        ),
        'git_root_not_drifted': not _git_status(project_root),
        'restart_replay_identity_preserved': (
            _restart_evidence_valid(restart_evidence, referenced_job_ids)
            if scenario == 'restart_replay_pass'
            else restart_evidence is None
        ),
    }
    return {
        'schema': REPORT_SCHEMA,
        'status': 'pass' if all(checks.values()) else 'failed',
        'execution_mode': 'source_fake_runtime',
        'coverage': {
            'provider': 'fake',
            'real_provider': False,
            'live_provider': False,
            'disclaimer': 'Source/fake runtime evidence only; this report does not cover live or real providers.',
        },
        'project_root': str(project_root),
        'project_id': task_show.get('project_id'),
        'role_store': str(role_store),
        'provider': 'fake',
        'scenario': scenario,
        'expected': expectation,
        'observed': {
            'classification': observed_classification,
            'task_status': task.get('status'),
            'round_result': round_record.get('round_result'),
            'round_source': round_record.get('round_result_source'),
        },
        'config_version': 3,
        'matrix': {'requested_count': count, 'requested_shape': shape},
        'task_id': TASK_ID,
        'loop_id': loop_id,
        'bundle': {
            'path': str(bundle_path),
            'bundle_revision': bundle.get('bundle_revision'),
            'bundle_digest': round_record.get('bundle_digest'),
            'task_digest': bundle.get('task_digest'),
            'capacity_digest': bundle.get('capacity_digest'),
            'node_count': len(bundle.get('nodes') or ()),
            'selection': bundle.get('selection'),
            'dependencies': {
                str(node.get('node_id')): list(node.get('depends_on') or ())
                for node in bundle.get('nodes') or () if isinstance(node, dict)
            },
        },
        'jobs': {
            'orchestrator': orchestrator_jobs,
            'nodes': node_records,
            'round_reviewer': round_reviewer,
            'referenced': referenced_job_evidence,
            'controller_intent_ids': controller_intent_ids,
            'expected_controller_intent_count': expected_controller_intent_count,
        },
        'integration': {
            'state_path': str(integration_path),
            'status': integration.get('status'),
            'merge_order': integration_section.get('merge_order'),
            'expected_merge_order': expected_merge_order,
            'scenario_expected_merge_order': expected_scenario_merge_order,
            'checks': integration_section.get('checks'),
            'root': root_section,
        },
        'task': {
            'status': task.get('status'),
            'next_owner': task.get('next_owner'),
            'current_loop': task.get('current_loop'),
        },
        'round': {
            'path': str(round_path),
            'result': round_record.get('round_result'),
            'source': round_record.get('round_result_source'),
            'round_reviewer_job_id': round_reviewer.get('job_id'),
        },
        'release': {
            'released_count': release.get('released_count'),
            'retained_count': release.get('retained_count'),
            'release_incomplete_count': release.get('release_incomplete_count'),
            'observed_path': str(observed_path),
            'observed_agents': raw_observed.get('agents'),
            'live_agents': _live_observed_agents(raw_observed),
            'dynamic_residue': dynamic_lines,
        },
        'root_changes': {
            'expected_paths': expected_paths,
            'actual_paths': actual_paths,
            'git_status': _git_status(project_root),
            'preflight_authority': root_preflight,
            'final_authority': root_after,
        },
        'runner_results': runner_results,
        'execution': {
            'initial_frontier_job_ids': list(initial_frontier.get('pending_job_ids') or ()),
            'expected_initial_frontier_size': expected_initial_frontier_size,
            'restart': restart_evidence,
        },
        'checks': checks,
        'paths': {
            'report': str(project_root / '.ccb' / 'evidence' / 'g5-fake-fullflow' / 'report.json'),
            'bundle': str(bundle_path),
            'scheduler_state': str(scheduler_state_path),
            'round': str(round_path),
            'integration_state': str(integration_path),
            'raw_observed': str(observed_path),
        },
        'raw_evidence_sha256': {
            'bundle': _sha256_file(bundle_path),
            'scheduler_state': _sha256_file(scheduler_state_path),
            'round': _sha256_file(round_path),
            'integration_state': _sha256_file(integration_path),
            'raw_observed': _sha256_file(observed_path),
        },
        'command_log': [_compact_command(item) for item in command_log],
    }


def _prepare_repository(project_root: Path) -> None:
    (project_root / '.gitignore').write_text(
        '/.ccb/\n/roles/\n/.source-home/\n/bin/\n'
        f'/docs/plantree/plans/{PLAN_SLUG}/tasks/\n',
        encoding='utf-8',
    )
    _git(project_root, 'init')
    _git(project_root, 'config', 'user.name', 'G5 Smoke')
    _git(project_root, 'config', 'user.email', 'g5-smoke@localhost')


def _write_config_and_plan(project_root: Path) -> None:
    config_path = project_root / '.ccb' / 'ccb.config'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(build_v3_config(), encoding='utf-8')
    plan_root = project_root / 'docs' / 'plantree' / 'plans' / PLAN_SLUG
    plan_root.mkdir(parents=True)
    (plan_root / 'README.md').write_text('# G5 Fake Full-Flow Plan\n', encoding='utf-8')
    _git(project_root, 'add', '.gitignore', 'docs')
    _git(project_root, 'commit', '-m', 'G5 smoke base')


def _write_task_inputs(
    project_root: Path,
    *,
    count: int,
    shape: str,
    scenario: str,
) -> dict[str, Path]:
    inputs = project_root / '.ccb' / 'evidence' / 'g5-fake-fullflow' / 'inputs'
    inputs.mkdir(parents=True, exist_ok=True)
    paths = [f'g5_outputs/node-{index:03d}.txt' for index in range(1, count + 1)]
    contract = json.dumps(
        {
            'schema': SCENARIO_SCHEMA,
            'task_id': TASK_ID,
            'scenario': scenario,
            'count': count,
            'shape': shape,
            'selected_node': 'node-001',
            'restart_latency_ms': 10000 if scenario == 'restart_replay_pass' else 0,
        },
        separators=(',', ':'),
    )
    allowed_lines = '\n'.join(f'- {path}' for path in paths)
    accepted_paths = paths[1:] if scenario in {
        'worker_failure_partial', 'reviewer_provider_failure'
    } else paths
    normal_verification = '\n'.join(
        '- python -c "from pathlib import Path; assert Path(\'' + path + '\').is_file()"'
        for path in accepted_paths
    )
    integration_verification = (
        '- python -c "raise SystemExit(19)"'
        if scenario == 'integration_verification_failure'
        else normal_verification
    )
    root_verification = (
        '- python -c "raise SystemExit(23)"'
        if scenario == 'root_verification_failure'
        else normal_verification
    )
    task_packet = inputs / 'task_packet.md'
    execution_contract = inputs / 'execution_contract.md'
    task_packet.write_text(
        '# Task Packet\n\n'
        f'g5_multi_workgroup_smoke: {contract}\n\n'
        'Goal: exercise the real G3 scheduler, R2 integration, and T1 topology with fake provider jobs.\n\n'
        'Allowed Change Paths:\n'
        f'{allowed_lines}\n\n'
        '## Verification Commands\n'
        f'{integration_verification}\n',
        encoding='utf-8',
    )
    execution_contract.write_text(
        '# Execution Contract\n\n'
        f'g5_multi_workgroup_smoke: {contract}\n\n'
        'allowed_change_paths:\n'
        f'{allowed_lines}\n\n'
        '## Verification Commands\n'
        f'{root_verification}\n',
        encoding='utf-8',
    )
    return {'task_packet': task_packet, 'execution_contract': execution_contract}


def _git_commit_authority(project_root: Path) -> None:
    status = _git_status(project_root)
    if status:
        raise SmokeFailure(f'project root dirty before scheduler preflight: {status}')


def _task_show(
    command_log: list[dict[str, Any]],
    *,
    ccb_test: Path,
    project_root: Path,
    test_root: Path,
    env: dict[str, str],
    logs_dir: Path,
    timeout_s: int,
    label: str,
) -> dict[str, Any]:
    result = _run_logged(
        command_log,
        label,
        [str(ccb_test), '--project', str(project_root), 'plan', 'task-show', '--task', TASK_ID, '--json'],
        cwd=test_root,
        env=env,
        logs_dir=logs_dir,
        timeout_s=timeout_s,
    )
    return _json_object(result['stdout'])


def _run_until_terminal(
    command_log: list[dict[str, Any]],
    *,
    ccb_test: Path,
    project_root: Path,
    test_root: Path,
    env: dict[str, str],
    logs_dir: Path,
    timeout_s: int,
    label_prefix: str = 'loop_runner_auto',
) -> list[dict[str, Any]]:
    results = []
    last_task_status = ''
    last_scheduler_status = ''
    for attempt in range(1, 97):
        runner = _run_logged(
            command_log,
            f'{label_prefix}_{attempt}',
            [
                str(ccb_test), '--project', str(project_root), 'loop', 'runner', '--once', '--json',
            ],
            cwd=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=timeout_s,
            allow_failure=True,
        )
        results.append(_json_object(runner['stdout']))
        _submit_pending_worker_reviews(
            command_log,
            ccb_test=ccb_test,
            project_root=project_root,
            test_root=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=timeout_s,
            attempt=attempt,
        )
        shown = _task_show(
            command_log,
            ccb_test=ccb_test,
            project_root=project_root,
            test_root=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=timeout_s,
            label=f'{label_prefix}_task_show_{attempt}',
        )
        last_task_status = str(_task_record(shown).get('status') or '')
        loop_id = _find_loop_id(project_root, TASK_ID)
        if loop_id:
            state = _read_json(
                project_root / '.ccb' / 'runtime' / 'loops' / loop_id / 'workgroup_scheduler_state.json'
            )
            last_scheduler_status = str(state.get('status') or '')
        if (
            last_task_status in TERMINAL_TASK_STATUSES
            and _terminal_release_complete(project_root)
        ):
            return results
        time.sleep(0.1)
    raise SmokeFailure(
        'loop runner did not reach terminal task authority in 96 activations: '
        f'task_status={last_task_status or "missing"}, '
        f'scheduler_status={last_scheduler_status or "missing"}'
    )


def _submit_pending_worker_reviews(
    command_log: list[dict[str, Any]],
    *,
    ccb_test: Path,
    project_root: Path,
    test_root: Path,
    env: dict[str, str],
    logs_dir: Path,
    timeout_s: int,
    attempt: int,
) -> list[dict[str, Any]]:
    loop_id = _find_loop_id(project_root, TASK_ID)
    if not loop_id:
        return []
    state = _read_json(
        project_root / '.ccb' / 'runtime' / 'loops' / loop_id / 'workgroup_scheduler_state.json'
    )
    nodes = _mapping(state.get('nodes'))
    maximum = int(_mapping(_mapping(state.get('bundle')).get('policy')).get('max_node_rework_rounds') or 0)
    commands: list[tuple[str, list[str]]] = []
    for node_id in sorted(nodes):
        node = _mapping(nodes.get(node_id))
        if node.get('status') not in {'worker_pending', 'worker_submission_unknown'}:
            continue
        worker = str(node.get('worker_agent') or '')
        reviewer = str(node.get('reviewer_agent') or '')
        if not worker or not reviewer:
            continue
        edges = _review_edges(project_root, reviewer=reviewer)
        if edges:
            latest = edges[-1]
            decision = _callback_edge_decision(project_root, latest)
            if decision != 'rework_required' or len(edges) >= maximum + 1:
                continue
            purpose = 'reviewer_recheck'
        else:
            purpose = 'reviewer'
        task_packet = next(
            project_root.glob(
                f'docs/plantree/plans/*/tasks/{TASK_ID}/task_packet.md'
            ),
            None,
        )
        marker = ''
        if task_packet is not None:
            marker = next(
                (
                    line.strip()
                    for line in task_packet.read_text(encoding='utf-8').splitlines()
                    if line.strip().startswith('g5_multi_workgroup_smoke:')
                ),
                '',
            )
        message = (
            f'Task: {TASK_ID}\nNode: {node_id}\nPurpose: {purpose}\n'
            f'Role: code_reviewer\nWorktree: {node.get("worktree_path")}\n'
            f'{marker}\nReview the current node tree against its canonical packet.\n'
            'First non-empty line must be status: pass|rework_required|blocked|non_converged.'
        )
        commands.append(
            (
                f'worker_chain_{node_id}_{len(edges) + 1}_{attempt}',
                [
                    str(ccb_test), '--project', str(project_root), 'ask', '--chain',
                    '--artifact-reply', reviewer, 'from', worker, '--', message,
                ],
            )
        )
    submitted = []
    for result in _run_chain_commands_with_parent_retry(
        command_log,
        commands,
        cwd=test_root,
        env=env,
        logs_dir=logs_dir,
        timeout_s=timeout_s,
    ):
        if result['returncode'] == 0:
            submitted.append(_json_object(result['stdout']))
    return submitted


def _run_chain_commands_with_parent_retry(
    command_log: list[dict[str, Any]],
    commands: list[tuple[str, list[str]]],
    *,
    cwd: Path,
    env: dict[str, str],
    logs_dir: Path,
    timeout_s: int,
    retry_attempts: int = 31,
    retry_delay_s: float = 0.1,
) -> list[dict[str, Any]]:
    pending = list(commands)
    submitted: list[dict[str, Any]] = []
    for retry_index in range(retry_attempts):
        if not pending:
            break
        if retry_index:
            time.sleep(retry_delay_s)
        attempted = [
            (
                label if retry_index == 0 else f'{label}_parent_retry_{retry_index}',
                argv,
            )
            for label, argv in pending
        ]
        records = _run_logged_concurrent(
            command_log,
            attempted,
            cwd=cwd,
            env=env,
            logs_dir=logs_dir,
            timeout_s=timeout_s,
            allow_failure=True,
        )
        retry_pending: list[tuple[str, list[str]]] = []
        for original, record in zip(pending, records):
            if record['returncode'] == 0:
                submitted.append(record)
                continue
            error = f'{record.get("stderr") or ""}\n{record.get("stdout") or ""}'
            if 'ask --chain requires an active parent job for the sender' in error:
                retry_pending.append(original)
        pending = retry_pending
    return submitted


def _terminal_release_complete(project_root: Path) -> bool:
    loop_id = _find_loop_id(project_root, TASK_ID)
    if not loop_id:
        return False
    state = _read_json(
        project_root / '.ccb' / 'runtime' / 'loops' / loop_id / 'workgroup_scheduler_state.json'
    )
    if str(state.get('status') or '') not in TERMINAL_SCHEDULER_STATUSES:
        return False
    release = _mapping(_mapping(state.get('topology')).get('release'))
    observed = _mapping(release.get('observed'))
    return (
        release.get('loop_topology_status') == 'released'
        and int(release.get('retained_count') or 0) == 0
        and int(release.get('release_incomplete_count') or 0) == 0
        and not _live_observed_agents(observed)
    )


def _review_edges(project_root: Path, *, reviewer: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    path = project_root / '.ccb' / 'ccbd' / 'callbacks' / 'edges.jsonl'
    if not path.is_file():
        return []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        edge_id = str(record.get('edge_id') or '')
        child = str(_mapping(record.get('diagnostics')).get('child_agent') or '')
        if edge_id and child == reviewer:
            latest[edge_id] = record
    return sorted(latest.values(), key=lambda item: (str(item.get('created_at') or ''), str(item.get('edge_id') or '')))


def _controller_submission_intents(loop_dir: Path) -> list[dict[str, Any]]:
    path = loop_dir / 'ask_first_submission_intents.jsonl'
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _callback_edge_decision(project_root: Path, edge: dict[str, Any]) -> str:
    reply_id = str(edge.get('child_reply_id') or '')
    if not reply_id:
        return 'pending'
    latest: dict[str, Any] | None = None
    path = project_root / '.ccb' / 'ccbd' / 'replies' / 'replies.jsonl'
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and str(record.get('reply_id') or '') == reply_id:
                latest = record
    reply_text = str(_mapping(latest).get('reply') or '')
    artifact = _mapping(_mapping(latest).get('reply_artifact'))
    artifact_path = Path(str(artifact.get('path') or ''))
    if artifact_path.is_file():
        body = artifact_path.read_bytes()
        if hashlib.sha256(body).hexdigest() == str(artifact.get('sha256') or ''):
            reply_text = body.decode('utf-8')
    for line in reply_text.splitlines():
        text = line.strip().lower()
        if text.startswith('status:'):
            return text.split(':', 1)[1].strip()
    return 'malformed'


def _run_restart_replay(
    command_log: list[dict[str, Any]],
    *,
    ccb_test: Path,
    project_root: Path,
    test_root: Path,
    env: dict[str, str],
    logs_dir: Path,
    timeout_s: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    pending_job: dict[str, Any] | None = None
    pending_edge: dict[str, Any] | None = None
    loop_id = ''
    for attempt in range(1, 9):
        runner = _run_logged(
            command_log,
            f'restart_prepare_once_{attempt}',
            [
                str(ccb_test), '--project', str(project_root), 'loop', 'runner', '--once', '--json',
            ],
            cwd=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=timeout_s,
            allow_failure=True,
        )
        results.append(_json_object(runner['stdout']))
        _submit_pending_worker_reviews(
            command_log,
            ccb_test=ccb_test,
            project_root=project_root,
            test_root=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=timeout_s,
            attempt=attempt,
        )
        loop_id = _find_loop_id(project_root, TASK_ID)
        if loop_id:
            state = _read_json(
                project_root / '.ccb' / 'runtime' / 'loops' / loop_id / 'workgroup_scheduler_state.json'
            )
            node = _mapping(_mapping(state.get('nodes')).get('node-001'))
            reviewer = str(node.get('reviewer_agent') or '')
            edges = _review_edges(project_root, reviewer=reviewer) if reviewer else []
            if edges:
                candidate_edge = edges[-1]
                child_job_id = str(candidate_edge.get('child_job_id') or '')
                candidate_job = _collect_jobs(project_root).get(child_job_id)
                if (
                    candidate_job is not None
                    and str(candidate_job.get('status') or '') not in TERMINAL_JOB_STATUSES
                ):
                    pending_edge = candidate_edge
                    pending_job = candidate_job
                    break
        time.sleep(0.25)
    if pending_job is None or pending_edge is None:
        raise SmokeFailure('restart replay did not establish a durable pending reviewer job')
    _wait_for_restart_target_isolation(
        project_root,
        pending_job_id=str(pending_job.get('job_id') or ''),
        timeout_s=5.0,
    )

    lease_path = project_root / '.ccb' / 'ccbd' / 'lease.json'
    lease_before = _read_json(lease_path)
    daemon_pid = int(lease_before.get('ccbd_pid') or lease_before.get('pid') or 0)
    if daemon_pid <= 1:
        raise SmokeFailure(f'restart replay missing daemon pid in {lease_path}')
    os.kill(daemon_pid, signal.SIGKILL)
    _record_script_action(
        command_log,
        logs_dir=logs_dir,
        label='restart_daemon_sigkill',
        payload={
            'pid': daemon_pid,
            'pending_job_id': pending_job.get('job_id'),
            'pending_edge_id': pending_edge.get('edge_id'),
            'loop_id': loop_id,
        },
    )
    if not _wait_pid_exit(daemon_pid, timeout_s=10.0):
        raise SmokeFailure(f'restart replay daemon did not exit after SIGKILL: {daemon_pid}')
    restarted = _run_logged(
        command_log,
        'restart_project',
        [str(ccb_test), '--project', str(project_root)],
        cwd=test_root,
        env=env,
        logs_dir=logs_dir,
        timeout_s=timeout_s,
    )
    lease_after = _read_json(lease_path)
    daemon_after = int(lease_after.get('ccbd_pid') or lease_after.get('pid') or 0)
    results.extend(
        _run_until_terminal(
            command_log,
            ccb_test=ccb_test,
            project_root=project_root,
            test_root=test_root,
            env=env,
            logs_dir=logs_dir,
            timeout_s=timeout_s,
            label_prefix='restart_resume_auto',
        )
    )
    return results, {
        'loop_id': loop_id,
        'pending_job_id': pending_job.get('job_id'),
        'pending_edge_id': pending_edge.get('edge_id'),
        'pending_submission_identity': pending_edge.get('edge_id'),
        'pending_status_before_restart': pending_job.get('status'),
        'daemon_pid_before': daemon_pid,
        'daemon_pid_after': daemon_after,
        'restart_returncode': restarted['returncode'],
    }


def _wait_for_restart_target_isolation(
    project_root: Path,
    *,
    pending_job_id: str,
    timeout_s: float,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        loop_id = _find_loop_id(project_root, TASK_ID)
        state = _read_json(
            project_root / '.ccb' / 'runtime' / 'loops' / loop_id / 'workgroup_scheduler_state.json'
        )
        nodes = _mapping(state.get('nodes'))
        child_job_ids: list[str] = []
        for node in nodes.values():
            reviewer = str(_mapping(node).get('reviewer_agent') or '')
            if not reviewer:
                continue
            child_job_ids.extend(
                str(edge.get('child_job_id') or '')
                for edge in _review_edges(project_root, reviewer=reviewer)
                if str(edge.get('child_job_id') or '')
            )
        jobs = _collect_jobs(project_root)
        pending = jobs.get(pending_job_id, {})
        others = [job_id for job_id in child_job_ids if job_id != pending_job_id]
        if (
            len(set(child_job_ids)) == len(nodes)
            and str(pending.get('status') or '') not in TERMINAL_JOB_STATUSES
            and all(
                str(jobs.get(job_id, {}).get('status') or '') in TERMINAL_JOB_STATUSES
                for job_id in others
            )
        ):
            return
        if str(pending.get('status') or '') in TERMINAL_JOB_STATUSES:
            break
        time.sleep(0.05)
    raise SmokeFailure(
        'restart replay could not isolate one resumable reviewer job before daemon termination'
    )


def _record_script_action(
    command_log: list[dict[str, Any]],
    *,
    logs_dir: Path,
    label: str,
    payload: dict[str, Any],
) -> None:
    if any(item.get('label') == label for item in command_log):
        raise SmokeFailure(f'duplicate command label: {label}')
    stdout_path = logs_dir / f'{label}.stdout'
    stderr_path = logs_dir / f'{label}.stderr'
    stdout_path.write_text(json.dumps(payload, sort_keys=True) + '\n', encoding='utf-8')
    stderr_path.write_text('', encoding='utf-8')
    command_log.append(
        {
            'label': label,
            'argv': ['script-owned-sigkill', str(payload.get('pid') or '')],
            'cwd': str(logs_dir),
            'returncode': 0,
            'stdout': stdout_path.read_text(encoding='utf-8'),
            'stderr': '',
            'stdout_path': str(stdout_path),
            'stderr_path': str(stderr_path),
        }
    )


def _wait_pid_exit(pid: int, *, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _run_logged(
    command_log: list[dict[str, Any]],
    label: str,
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    logs_dir: Path,
    timeout_s: int,
    allow_failure: bool = False,
) -> dict[str, Any]:
    if any(item.get('label') == label for item in command_log):
        raise SmokeFailure(f'duplicate command label: {label}')
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_s,
    )
    stdout_path = logs_dir / f'{label}.stdout'
    stderr_path = logs_dir / f'{label}.stderr'
    stdout_path.write_text(completed.stdout, encoding='utf-8')
    stderr_path.write_text(completed.stderr, encoding='utf-8')
    record = {
        'label': label,
        'argv': argv,
        'cwd': str(cwd),
        'returncode': completed.returncode,
        'stdout': completed.stdout,
        'stderr': completed.stderr,
        'stdout_path': str(stdout_path),
        'stderr_path': str(stderr_path),
    }
    command_log.append(record)
    if completed.returncode != 0 and not allow_failure:
        raise SmokeFailure(
            f'{label} failed rc={completed.returncode}: {completed.stderr or completed.stdout}'
        )
    return record


def _run_logged_concurrent(
    command_log: list[dict[str, Any]],
    commands: list[tuple[str, list[str]]],
    *,
    cwd: Path,
    env: dict[str, str],
    logs_dir: Path,
    timeout_s: int,
    allow_failure: bool = False,
) -> list[dict[str, Any]]:
    if not commands:
        return []
    existing_labels = {str(item.get('label') or '') for item in command_log}
    labels = [label for label, _argv in commands]
    duplicate_labels = sorted(label for label in set(labels) if labels.count(label) > 1 or label in existing_labels)
    if duplicate_labels:
        raise SmokeFailure(f'duplicate command label: {duplicate_labels[0]}')

    launched: list[tuple[str, list[str], subprocess.Popen[str], float]] = []
    for label, argv in commands:
        launched.append(
            (
                label,
                argv,
                subprocess.Popen(
                    argv,
                    cwd=str(cwd),
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ),
                time.monotonic(),
            )
        )

    records: list[dict[str, Any]] = []
    for label, argv, process, started_at in launched:
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=max(0.1, timeout_s - (time.monotonic() - started_at)))
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate()
        if timed_out:
            stderr = (stderr or '') + f'\ncommand timed out after {timeout_s}s'
        stdout_path = logs_dir / f'{label}.stdout'
        stderr_path = logs_dir / f'{label}.stderr'
        stdout_path.write_text(stdout or '', encoding='utf-8')
        stderr_path.write_text(stderr or '', encoding='utf-8')
        record = {
            'label': label,
            'argv': argv,
            'cwd': str(cwd),
            'returncode': process.returncode,
            'stdout': stdout or '',
            'stderr': stderr or '',
            'stdout_path': str(stdout_path),
            'stderr_path': str(stderr_path),
        }
        command_log.append(record)
        records.append(record)
        if process.returncode != 0 and not allow_failure:
            raise SmokeFailure(
                f'{label} failed rc={process.returncode}: {record["stderr"] or record["stdout"]}'
            )
    return records


def _smoke_env(*, test_root: Path, project_root: Path, role_store: Path, source_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            'HOME': str(source_home),
            'CCB_SOURCE_HOME': str(source_home),
            'CCB_TEST_ROOTS': str(test_root),
            'CCB_SOURCE_ALLOWED_ROOTS': str(test_root),
            'AGENT_ROLES_STORE': str(role_store),
            'CCB_NO_ATTACH': '1',
            'CCB_REPLY_LANG': 'en',
            'CCB_RUNTIME_ACCELERATOR_CODEX': '0',
        }
    )
    return env


def _collect_jobs(project_root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for path in project_root.glob('.ccb/**/jobs.jsonl'):
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            job_id = str(payload.get('job_id') or '')
            if job_id:
                latest[job_id] = payload
    for path in project_root.glob('.ccb/**/snapshots/job_*.json'):
        payload = _read_json(path)
        job_id = str(payload.get('job_id') or '')
        decision = _mapping(payload.get('latest_decision'))
        if job_id and job_id not in latest and decision.get('terminal'):
            latest[job_id] = {
                'job_id': job_id,
                'agent_name': payload.get('agent_name'),
                'status': decision.get('status'),
                'reason': decision.get('reason'),
                'evidence_source': 'completion_snapshot',
                'snapshot_path': str(path),
            }
    return latest


def _find_loop_id(project_root: Path, task_id: str) -> str:
    for path in sorted((project_root / '.ccb' / 'runtime' / 'loops').glob('*/workgroup_scheduler_state.json')):
        payload = _read_json(path)
        if payload.get('task_id') == task_id:
            return str(payload.get('loop_id') or path.parent.name)
    return ''


def _expected_bundle_merge_order(bundle: dict[str, Any]) -> list[str]:
    nodes = {
        str(node.get('node_id') or ''): node
        for value in bundle.get('nodes') or ()
        if isinstance(value, dict)
        for node in (value,)
        if str(node.get('node_id') or '')
    }
    ordered: list[str] = []
    remaining = set(nodes)
    completed: set[str] = set()
    while remaining:
        layer = [
            node_id
            for node_id in remaining
            if set(str(item) for item in nodes[node_id].get('depends_on') or ()) <= completed
        ]
        if not layer:
            return []
        layer.sort(
            key=lambda node_id: (
                int(nodes[node_id].get('integration_order') or 0),
                node_id,
            )
        )
        ordered.extend(layer)
        completed.update(layer)
        remaining.difference_update(layer)
    return ordered


def _expected_failed_node_ids(*, scenario: str, count: int) -> set[str]:
    if scenario == 'all_workers_failed_blocked':
        return {f'node-{index:03d}' for index in range(1, count + 1)}
    if scenario in {
        'worker_failure_partial',
        'reviewer_provider_failure',
        'reviewer_rework_exhausted_blocked',
    }:
        return {'node-001'}
    return set()


def _expected_scenario_merge_order(
    ordered_node_ids: list[str],
    *,
    failed_node_ids: set[str],
) -> list[str]:
    return [node_id for node_id in ordered_node_ids if node_id not in failed_node_ids]


def _node_failure_evidence_valid(
    node: dict[str, Any],
    *,
    loop_id: str,
    expected_path: str,
) -> bool:
    terminal = _mapping(node.get('terminal_failure'))
    scheduler_failure = _mapping(node.get('failure'))
    failure_job = _mapping(scheduler_failure.get('job'))
    job_id = str(terminal.get('job_id') or '')
    if job_id:
        authority_valid = (
            terminal.get('authority_id') == f'job:{job_id}'
            and failure_job.get('job_id') == job_id
        )
    else:
        authority_valid = terminal.get('authority_id') == (
            f'controller:{loop_id}:{node.get("node_id")}:{node.get("status")}'
        )
    worktree_status = terminal.get('worktree_status')
    quarantine = _mapping(terminal.get('quarantine'))
    manifest_path = Path(str(quarantine.get('manifest_path') or ''))
    manifest = _read_json(manifest_path)
    manifest_digest = str(manifest.get('digest') or '')
    digest_payload = dict(manifest)
    digest_payload.pop('digest', None)
    expected_digest = 'sha256:' + hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    return (
        node.get('integration_status') == 'excluded'
        and terminal.get('schema') == 'ccb.loop.workgroup_node_failure.v1'
        and terminal.get('status') == 'restored'
        and terminal.get('source') == scheduler_failure.get('source')
        and authority_valid
        and isinstance(worktree_status, list)
        and bool(worktree_status)
        and quarantine.get('status') == 'preserved'
        and manifest_path.is_file()
        and manifest.get('schema') == 'ccb.loop.node_failure_quarantine.v1'
        and manifest.get('evidence_kind') == 'node-failure'
        and manifest.get('project_root') == node.get('worktree_path')
        and manifest.get('changed_paths') == [expected_path]
        and manifest_digest == expected_digest
        and quarantine.get('manifest_digest') == manifest_digest
    )


def _live_observed_agents(observed: dict[str, Any]) -> list[dict[str, Any]]:
    terminal = {'released', 'missing', 'removed', 'unloaded'}
    return [
        item for item in observed.get('agents') or ()
        if isinstance(item, dict) and str(item.get('observed_state') or '') not in terminal
    ]


def _root_authority(project_root: Path) -> dict[str, Any]:
    return {
        'head': _git(project_root, 'rev-parse', 'HEAD'),
        'tree': _git(project_root, 'rev-parse', 'HEAD^{tree}'),
        'status': _git_status(project_root),
    }


def _observed_classification(*, task_status: str, round_result: str) -> str:
    if task_status == 'done' and round_result == 'pass':
        return 'pass'
    if task_status in {'partial', 'blocked', 'replan_required'} and round_result in {
        'partial', 'blocked', 'replan_required'
    }:
        return 'valid_non_success'
    return 'system_failure'


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ''
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _restart_evidence_valid(
    evidence: dict[str, Any] | None,
    referenced_job_ids: list[str],
) -> bool:
    if not evidence:
        return False
    pending_job_id = str(evidence.get('pending_job_id') or '')
    return (
        bool(pending_job_id)
        and referenced_job_ids.count(pending_job_id) == 1
        and bool(evidence.get('pending_submission_identity'))
        and evidence.get('pending_submission_identity') == evidence.get('pending_edge_id')
        and int(evidence.get('daemon_pid_before') or 0) > 1
        and int(evidence.get('daemon_pid_after') or 0) > 1
        and evidence.get('daemon_pid_before') != evidence.get('daemon_pid_after')
        and evidence.get('restart_returncode') == 0
    )


def _post_cleanup_evidence(project_root: Path) -> dict[str, Any]:
    owned_processes = []
    excluded_pids = _current_process_lineage()
    proc_root = Path('/proc')
    if proc_root.is_dir():
        for proc in proc_root.iterdir():
            if not proc.name.isdigit():
                continue
            if int(proc.name) in excluded_pids:
                continue
            cmdline: str | None = None
            cwd: Path | None = None
            try:
                cmdline = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(
                    'utf-8', errors='replace'
                ).strip()
            except (FileNotFoundError, OSError, PermissionError):
                pass
            try:
                cwd = (proc / 'cwd').resolve(strict=True)
            except (FileNotFoundError, OSError, PermissionError):
                pass
            command_owned = cmdline is not None and str(project_root) in cmdline
            cwd_owned = cwd is not None and (cwd == project_root or project_root in cwd.parents)
            if command_owned or cwd_owned:
                owned_processes.append(
                    {
                        'pid': int(proc.name),
                        'cmdline': cmdline,
                        'cwd': str(cwd) if cwd is not None else None,
                    }
                )

    socket_entries = []
    for path in project_root.rglob('*'):
        try:
            mode = path.lstat().st_mode
        except OSError:
            continue
        if stat.S_ISSOCK(mode):
            socket_entries.append(str(path))
    connectable_sockets = []
    for path_text in socket_entries:
        path = Path(path_text)
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(0.1)
        try:
            client.connect(str(path))
        except OSError:
            pass
        else:
            connectable_sockets.append(str(path))
        finally:
            client.close()

    child_worktrees = []
    completed = subprocess.run(
        ['git', 'worktree', 'list', '--porcelain'],
        cwd=str(project_root),
        text=True,
        capture_output=True,
    )
    if completed.returncode == 0:
        for line in completed.stdout.splitlines():
            if not line.startswith('worktree '):
                continue
            path = Path(line.split(' ', 1)[1]).resolve(strict=False)
            if path != project_root:
                child_worktrees.append(str(path))
    return {
        'owned_processes': owned_processes,
        'socket_entries': socket_entries,
        'connectable_sockets': connectable_sockets,
        'child_worktrees': child_worktrees,
    }


def _current_process_lineage() -> set[int]:
    lineage = {os.getpid()}
    pid = os.getppid()
    while pid > 1 and pid not in lineage:
        lineage.add(pid)
        try:
            stat = (Path('/proc') / str(pid) / 'stat').read_text(encoding='utf-8')
            pid = int(stat.rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return lineage


def _require_report_pass(report: dict[str, Any]) -> None:
    failed = [name for name, value in _mapping(report.get('checks')).items() if value is not True]
    if report.get('status') != 'pass' or failed:
        raise SmokeFailure(f'G5 full-flow report checks failed: {failed}')


def _task_record(payload: dict[str, Any]) -> dict[str, Any]:
    task = payload.get('task')
    return task if isinstance(task, dict) else {}


def _json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _compact_command(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ('label', 'argv', 'cwd', 'returncode', 'stdout_path', 'stderr_path')
    }


def _git(project_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ['git', *args],
        cwd=str(project_root),
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise SmokeFailure(f'git {" ".join(args)} failed: {completed.stderr or completed.stdout}')
    return completed.stdout.strip()


def _git_status(project_root: Path) -> list[str]:
    output = _git(project_root, 'status', '--porcelain=v1', '--untracked-files=all')
    return output.splitlines() if output else []


def _validate_matrix(*, count: int, shape: str, scenario: str = 'pass') -> None:
    if count not in {1, 2, 3, 4}:
        raise SmokeFailure('count must be 1, 2, 3, or 4')
    if shape not in {'parallel', 'mixed_dag'}:
        raise SmokeFailure('shape must be parallel or mixed_dag')
    if shape == 'mixed_dag' and count < 3:
        raise SmokeFailure('mixed_dag requires count >= 3')
    if scenario not in SCENARIO_EXPECTATIONS:
        raise SmokeFailure(f'unsupported scenario: {scenario}')
    if scenario in {'worker_failure_partial', 'reviewer_provider_failure'} and count < 2:
        raise SmokeFailure(f'{scenario} requires count >= 2')


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the G5 source/fake multi-workgroup full-flow smoke.')
    parser.add_argument('--root', required=True)
    parser.add_argument('--count', type=int, required=True)
    parser.add_argument('--shape', choices=('parallel', 'mixed_dag'), default='parallel')
    parser.add_argument('--scenario', choices=tuple(SCENARIO_EXPECTATIONS), default='pass')
    parser.add_argument('--ccb-test', default=str(REPO_ROOT / 'ccb_test'))
    parser.add_argument('--keep-running', action='store_true')
    parser.add_argument('--command-timeout', type=int, default=240)
    parser.add_argument('--json', action='store_true')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    try:
        report = run_smoke(
            project_root=Path(args.root),
            count=int(args.count),
            shape=str(args.shape),
            scenario=str(args.scenario),
            ccb_test=Path(args.ccb_test),
            keep_running=bool(args.keep_running),
            command_timeout_s=int(args.command_timeout),
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({'status': 'failed', 'error': str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f'smoke_status: failed\nerror: {exc}', file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f'smoke_status: {report["status"]}')
        print(f'project_root: {report["project_root"]}')
        print(f'report: {report["paths"]["report"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
