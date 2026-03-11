"""Team configuration for CCB Agent Teams.

Loads team config from JSON files and resolves team agent names to providers.

Configuration layers (higher overrides lower):
1. ~/.ccb/team.json (global)
2. .ccb/team.json (project-level)

A team config defines named agents with provider, model, role, and skills.
Team agent names take priority over aliases when resolving provider names.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TeamAgent:
    """A named agent within a team."""
    name: str
    provider: str
    model: str = ""
    role: str = ""
    skills: List[str] = field(default_factory=list)


@dataclass
class TeamConfig:
    """Team configuration with named agents and allocation strategy."""
    name: str
    agents: List[TeamAgent] = field(default_factory=list)
    strategy: str = "skill_based"  # round_robin | load_balance | skill_based
    description: str = ""

    def agent_map(self) -> Dict[str, TeamAgent]:
        """Build name → TeamAgent lookup (case-insensitive)."""
        return {a.name.lower(): a for a in self.agents}


VALID_STRATEGIES = {"round_robin", "load_balance", "skill_based"}


def _parse_agent(raw: dict) -> Optional[TeamAgent]:
    """Parse a single agent entry from JSON. Returns None on invalid data."""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    provider = str(raw.get("provider", "")).strip().lower()
    if not name or not provider:
        return None
    return TeamAgent(
        name=name.lower(),
        provider=provider,
        model=str(raw.get("model", "")).strip(),
        role=str(raw.get("role", "")).strip().lower(),
        skills=[str(s).strip().lower() for s in raw.get("skills", []) if str(s).strip()],
    )


def _load_team_json(path: Path) -> Optional[TeamConfig]:
    """Load a team config from a JSON file. Returns None on any error."""
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
    except (json.JSONDecodeError, OSError, ValueError):
        print(f"[WARN] Failed to parse team config: {path}", file=sys.stderr)
        return None

    name = str(data.get("name", "")).strip()
    if not name:
        name = "default"

    strategy = str(data.get("strategy", "skill_based")).strip().lower()
    if strategy not in VALID_STRATEGIES:
        strategy = "skill_based"

    agents: List[TeamAgent] = []
    for raw_agent in data.get("agents", []):
        agent = _parse_agent(raw_agent)
        if agent:
            agents.append(agent)

    if not agents:
        return None

    return TeamConfig(
        name=name,
        agents=agents,
        strategy=strategy,
        description=str(data.get("description", "")).strip(),
    )


def load_team_config(work_dir: Optional[Path] = None) -> Optional[TeamConfig]:
    """Load team config: project .ccb/team.json overrides global ~/.ccb/team.json.

    Returns None if no valid team config is found.
    """
    global_path = Path.home() / ".ccb" / "team.json"
    global_config = _load_team_json(global_path)

    project_config: Optional[TeamConfig] = None
    if work_dir is not None:
        project_path = work_dir / ".ccb" / "team.json"
        project_config = _load_team_json(project_path)

    # Project-level takes full priority (not merged)
    return project_config or global_config


def resolve_team_agent(
    name: str,
    team: Optional[TeamConfig],
) -> Optional[TeamAgent]:
    """Resolve a name to a TeamAgent. Returns None if not a team agent."""
    if team is None:
        return None
    key = (name or "").strip().lower()
    if not key:
        return None
    return team.agent_map().get(key)
