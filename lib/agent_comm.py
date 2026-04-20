"""Inter-agent communication for CCB Agent Teams.

Supports three communication patterns:
1. Directed message: ask a --to b "请审查这段代码"
2. Task chain: sequential multi-agent pipeline
3. Broadcast: notify all team members

Messages are wrapped with metadata so the receiving agent knows
the sender and context. Execution uses the existing ask infrastructure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from aliases import load_aliases, resolve_alias
from team_config import TeamAgent, TeamConfig, load_team_config, resolve_team_agent


@dataclass
class AgentMessage:
    """A message from one agent to another."""
    sender: str
    receiver: str
    content: str
    context: str = ""  # optional context from previous agent's output


def resolve_agent_to_provider(
    name: str,
    team: Optional[TeamConfig],
    aliases: Dict[str, str],
) -> Optional[str]:
    """Resolve an agent name to a provider, checking team agents then aliases.

    Returns None if the name doesn't resolve to a known provider.
    """
    key = (name or "").strip().lower()
    if not key:
        return None

    # Team agent takes priority
    agent = resolve_team_agent(key, team)
    if agent:
        return agent.provider

    # Try alias
    resolved = resolve_alias(key, aliases)
    return resolved if resolved else None


def wrap_message(msg: AgentMessage) -> str:
    """Wrap a message with sender metadata for the receiving agent.

    The wrapped format allows the receiving agent to understand context.
    """
    lines = []
    lines.append(f"[CCB_FROM agent={msg.sender}]")
    if msg.context:
        lines.append(f"[CCB_CONTEXT]\n{msg.context}\n[/CCB_CONTEXT]")
    lines.append(msg.content)
    return "\n".join(lines)


def build_chain_script(
    steps: List[AgentMessage],
    ask_cmd: str,
    timeout: float = 3600.0,
    foreground: bool = True,
) -> str:
    """Build a shell script that executes a chain of agent tasks sequentially.

    Each step feeds the previous output as context to the next agent.
    Returns the shell script content.
    """
    import shlex

    lines = ["#!/bin/sh", "set -e", ""]
    lines.append("# CCB Agent Chain")
    lines.append(f"# Steps: {len(steps)}")
    lines.append("")

    for i, step in enumerate(steps):
        step_var = f"STEP{i}_OUTPUT"
        provider = step.receiver
        content = step.content

        # First step: no context from previous
        if i == 0:
            wrapped = wrap_message(step)
        else:
            # Inject previous output as context
            step_with_ctx = AgentMessage(
                sender=step.sender,
                receiver=step.receiver,
                content=step.content,
                context=f"$STEP{i-1}_OUTPUT",
            )
            # For shell script, we build inline
            wrapped = f"[CCB_FROM agent={step.sender}]\\n[CCB_CONTEXT]\\n$STEP{i-1}_OUTPUT\\n[/CCB_CONTEXT]\\n{content}"

        fg_flag = "--foreground" if foreground else ""
        timeout_flag = f"--timeout {timeout}" if timeout else ""

        lines.append(f"echo '[CHAIN] Step {i+1}/{len(steps)}: {step.sender} → {provider}'")
        if i == 0:
            msg_escaped = shlex.quote(wrapped)
            lines.append(f"{step_var}=$(python3 {shlex.quote(ask_cmd)} {shlex.quote(provider)} {fg_flag} {timeout_flag} {msg_escaped})")
        else:
            lines.append(f'WRAPPED="[CCB_FROM agent={step.sender}]')
            lines.append(f"[CCB_CONTEXT]")
            lines.append(f"$STEP{i-1}_OUTPUT")
            lines.append(f"[/CCB_CONTEXT]")
            lines.append(f'{content}"')
            lines.append(f'{step_var}=$(echo "$WRAPPED" | python3 {shlex.quote(ask_cmd)} {shlex.quote(provider)} {fg_flag} {timeout_flag})')
        lines.append(f'echo "${{step_var}}"')
        lines.append("")

    # Final output is last step's output
    if steps:
        lines.append(f'echo "$STEP{len(steps)-1}_OUTPUT"')

    return "\n".join(lines)


def broadcast_message(
    sender: str,
    content: str,
    team: TeamConfig,
    exclude_sender: bool = True,
) -> List[AgentMessage]:
    """Create messages to broadcast to all team agents.

    Returns a list of AgentMessages, one per recipient.
    """
    messages = []
    sender_lower = sender.lower()
    for agent in team.agents:
        if exclude_sender and agent.name.lower() == sender_lower:
            continue
        messages.append(AgentMessage(
            sender=sender,
            receiver=agent.provider,
            content=content,
        ))
    return messages


def parse_chain_spec(spec: str) -> List[tuple[str, str]]:
    """Parse a chain specification string into (agent, task) pairs.

    Format: "agent1:task1 | agent2:task2 | agent3:task3"
    Each segment is "agent:task" separated by " | ".

    Returns list of (agent_name, task_description) tuples.
    """
    steps = []
    for segment in spec.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        if ":" in segment:
            agent, _, task = segment.partition(":")
            agent = agent.strip()
            task = task.strip()
            if agent and task:
                steps.append((agent, task))
        else:
            # No colon: treat whole segment as task with empty agent
            steps.append(("", segment.strip()))
    return steps


def build_chain_messages(
    chain: List[tuple[str, str]],
) -> List[AgentMessage]:
    """Convert a parsed chain spec into AgentMessages.

    Each step's sender is the previous step's receiver (or 'user' for first).
    """
    messages = []
    prev_agent = "user"
    for agent_name, task in chain:
        messages.append(AgentMessage(
            sender=prev_agent,
            receiver=agent_name,
            content=task,
        ))
        prev_agent = agent_name
    return messages
