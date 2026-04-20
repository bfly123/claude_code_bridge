from __future__ import annotations

from typing import Any

from agents.models import ProviderProfileSpec

from ..common import ALLOWED_PROVIDER_PROFILE_KEYS, ConfigValidationError
from .expectations import expect_bool, expect_mapping, expect_string, expect_string_mapping


def parse_provider_profile(agent_name: str, value: Any) -> ProviderProfileSpec:
    raw = expect_mapping(value, field_name=f'agents.{agent_name}.provider_profile')
    unknown = sorted(set(raw) - ALLOWED_PROVIDER_PROFILE_KEYS)
    if unknown:
        raise ConfigValidationError(
            f'agents.{agent_name}.provider_profile contains unknown fields: {", ".join(unknown)}'
        )
    try:
        return ProviderProfileSpec(
            mode=(
                expect_string(raw['mode'], field_name=f'agents.{agent_name}.provider_profile.mode')
                if raw.get('mode') is not None
                else 'inherit'
            ),
            home=(
                expect_string(raw['home'], field_name=f'agents.{agent_name}.provider_profile.home')
                if raw.get('home') is not None
                else None
            ),
            env=expect_string_mapping(
                raw.get('env', {}),
                field_name=f'agents.{agent_name}.provider_profile.env',
            ),
            inherit_api=(
                expect_bool(raw['inherit_api'], field_name=f'agents.{agent_name}.provider_profile.inherit_api')
                if 'inherit_api' in raw
                else True
            ),
            inherit_auth=(
                expect_bool(raw['inherit_auth'], field_name=f'agents.{agent_name}.provider_profile.inherit_auth')
                if 'inherit_auth' in raw
                else True
            ),
            inherit_config=(
                expect_bool(raw['inherit_config'], field_name=f'agents.{agent_name}.provider_profile.inherit_config')
                if 'inherit_config' in raw
                else True
            ),
            inherit_skills=(
                expect_bool(raw['inherit_skills'], field_name=f'agents.{agent_name}.provider_profile.inherit_skills')
                if 'inherit_skills' in raw
                else True
            ),
            inherit_commands=(
                expect_bool(
                    raw['inherit_commands'],
                    field_name=f'agents.{agent_name}.provider_profile.inherit_commands',
                )
                if 'inherit_commands' in raw
                else True
            ),
        )
    except ValueError as exc:
        raise ConfigValidationError(f'agents.{agent_name}.provider_profile: {exc}') from exc


__all__ = ['parse_provider_profile']
