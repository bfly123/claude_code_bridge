from __future__ import annotations

_PROVIDER_MODEL_FLAGS = {
    'codex': ('-m', '--model'),
    'claude': ('--model',),
    'gemini': ('-m', '--model'),
    'opencode': ('-m', '--model'),
}

_PROVIDER_MODEL_STARTUP_FLAGS = {
    'codex': '-m',
    'claude': '--model',
    'gemini': '-m',
    'opencode': '-m',
}


def supported_provider_model_shortcuts() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDER_MODEL_FLAGS))


def provider_model_flag_tokens(provider: str) -> tuple[str, ...]:
    return _PROVIDER_MODEL_FLAGS.get(str(provider or '').strip().lower(), ())


def provider_model_startup_args(provider: str, *, model: str) -> tuple[str, ...]:
    normalized = str(provider or '').strip().lower()
    flag = _PROVIDER_MODEL_STARTUP_FLAGS.get(normalized)
    if flag is None:
        supported = ', '.join(supported_provider_model_shortcuts())
        raise ValueError(f'model shortcut is supported only for providers: {supported}')
    resolved_model = str(model or '').strip()
    if not resolved_model:
        raise ValueError('model cannot be empty')
    return (flag, resolved_model)


def startup_args_contain_model_flag(provider: str, startup_args: tuple[str, ...] | list[str]) -> bool:
    flags = set(provider_model_flag_tokens(provider))
    if not flags:
        return False
    for raw_arg in startup_args:
        arg = str(raw_arg)
        if arg in flags or arg.startswith('--model='):
            return True
    return False


def strip_provider_model_startup_args(
    provider: str,
    startup_args: tuple[str, ...] | list[str],
    *,
    model: str,
) -> tuple[str, ...]:
    compiled_prefix = provider_model_startup_args(provider, model=model)
    normalized_args = tuple(str(arg) for arg in startup_args)
    if normalized_args[: len(compiled_prefix)] == compiled_prefix:
        return normalized_args[len(compiled_prefix) :]
    return normalized_args


__all__ = [
    'provider_model_flag_tokens',
    'provider_model_startup_args',
    'startup_args_contain_model_flag',
    'strip_provider_model_startup_args',
    'supported_provider_model_shortcuts',
]
