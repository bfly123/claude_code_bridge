from __future__ import annotations


def render_fault_list(summary) -> tuple[str, ...]:
    lines = [
        'fault_status: ok',
        f'project_id: {summary.project_id}',
        f'rule_count: {summary.rule_count}',
    ]
    if not summary.rules:
        lines.append('fault_rule: <none>')
        return tuple(lines)
    for rule in summary.rules:
        lines.append(
            'fault_rule: '
            f'id={rule.rule_id} agent={rule.agent_name} task={rule.task_id} '
            f'reason={rule.reason} remaining={rule.remaining_count} '
            f'created={rule.created_at} updated={rule.updated_at} '
            f'error={rule.error_message}'
        )
    return tuple(lines)


def render_fault_arm(summary) -> tuple[str, ...]:
    return (
        'fault_status: armed',
        f'project_id: {summary.project_id}',
        f'rule_id: {summary.rule_id}',
        f'agent_name: {summary.agent_name}',
        f'task_id: {summary.task_id}',
        f'reason: {summary.reason}',
        f'remaining_count: {summary.remaining_count}',
        f'error_message: {summary.error_message}',
    )


def render_fault_clear(summary) -> tuple[str, ...]:
    lines = [
        'fault_status: cleared',
        f'project_id: {summary.project_id}',
        f'target: {summary.target}',
        f'cleared_count: {summary.cleared_count}',
    ]
    for rule_id in summary.cleared_rule_ids:
        lines.append(f'cleared_rule_id: {rule_id}')
    return tuple(lines)


__all__ = ['render_fault_arm', 'render_fault_clear', 'render_fault_list']
