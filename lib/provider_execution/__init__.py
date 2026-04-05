from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    'CORE_EXECUTION_PROVIDERS',
    'OPTIONAL_EXECUTION_PROVIDERS',
    'TEST_DOUBLE_EXECUTION_PROVIDERS',
    'ExecutionRestoreResult',
    'ExecutionService',
    'ExecutionUpdate',
    'ProviderExecutionRegistry',
    'ProviderPollResult',
    'ProviderRuntimeContext',
    'ProviderSubmission',
    'base',
    'build_default_execution_registry',
    'fake',
    'registry',
    'service',
]


def __getattr__(name: str) -> Any:
    if name in {'base', 'fake', 'registry', 'service'}:
        return import_module(f'.{name}', __name__)
    if name in {'ProviderPollResult', 'ProviderRuntimeContext', 'ProviderSubmission'}:
        module = import_module('.base', __name__)
        return getattr(module, name)
    if name in {
        'CORE_EXECUTION_PROVIDERS',
        'OPTIONAL_EXECUTION_PROVIDERS',
        'TEST_DOUBLE_EXECUTION_PROVIDERS',
        'ProviderExecutionRegistry',
        'build_default_execution_registry',
    }:
        module = import_module('.registry', __name__)
        return getattr(module, name)
    if name in {'ExecutionRestoreResult', 'ExecutionService', 'ExecutionUpdate'}:
        module = import_module('.service', __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
