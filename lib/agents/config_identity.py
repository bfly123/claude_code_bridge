from __future__ import annotations

import hashlib
import json

from agents.models import ProjectConfig


def project_config_identity_payload(config: ProjectConfig) -> dict[str, object]:
    canonical = config.to_record()
    canonical.pop('schema_version', None)
    canonical.pop('record_type', None)
    canonical.pop('source_path', None)

    agents = canonical.get('agents')
    if isinstance(agents, dict):
        for payload in agents.values():
            if isinstance(payload, dict):
                payload.pop('schema_version', None)
                payload.pop('record_type', None)

    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {
        'known_agents': tuple(sorted(config.agents)),
        'config_signature': hashlib.sha256(encoded).hexdigest(),
    }


__all__ = ['project_config_identity_payload']
