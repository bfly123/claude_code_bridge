from __future__ import annotations

from dataclasses import dataclass

from agents.config_loader import load_project_config
from agents.models import normalize_agent_name
from ccbd.system import utc_now
from cli.models import ParsedFaultArmCommand, ParsedFaultClearCommand
from fault_injection import FaultInjectionService, FaultRule


@dataclass(frozen=True)
class FaultListSummary:
    project_id: str
    rule_count: int
    rules: tuple[FaultRule, ...]


@dataclass(frozen=True)
class FaultArmSummary:
    project_id: str
    rule_id: str
    agent_name: str
    task_id: str
    reason: str
    remaining_count: int
    error_message: str


@dataclass(frozen=True)
class FaultClearSummary:
    project_id: str
    target: str
    cleared_count: int
    cleared_rule_ids: tuple[str, ...]


def list_fault_rules(context) -> FaultListSummary:
    service = FaultInjectionService(context.paths, clock=utc_now)
    rules = service.list_rules()
    return FaultListSummary(
        project_id=context.project.project_id,
        rule_count=len(rules),
        rules=rules,
    )


def arm_fault_rule(context, command: ParsedFaultArmCommand) -> FaultArmSummary:
    normalized = normalize_agent_name(command.agent_name)
    config = load_project_config(context.project.project_root).config
    if normalized not in config.agents:
        raise ValueError(f'unknown agent: {normalized}')
    service = FaultInjectionService(context.paths, clock=utc_now)
    rule = service.arm_rule(
        agent_name=normalized,
        task_id=command.task_id,
        reason=command.reason,
        count=command.count,
        error_message=command.error_message,
    )
    return FaultArmSummary(
        project_id=context.project.project_id,
        rule_id=rule.rule_id,
        agent_name=rule.agent_name,
        task_id=rule.task_id,
        reason=rule.reason,
        remaining_count=rule.remaining_count,
        error_message=rule.error_message,
    )


def clear_fault_rule(context, command: ParsedFaultClearCommand) -> FaultClearSummary:
    service = FaultInjectionService(context.paths, clock=utc_now)
    cleared = service.clear_rule(command.target)
    return FaultClearSummary(
        project_id=context.project.project_id,
        target=command.target,
        cleared_count=len(cleared),
        cleared_rule_ids=tuple(rule.rule_id for rule in cleared),
    )


__all__ = [
    'FaultArmSummary',
    'FaultClearSummary',
    'FaultListSummary',
    'arm_fault_rule',
    'clear_fault_rule',
    'list_fault_rules',
]
